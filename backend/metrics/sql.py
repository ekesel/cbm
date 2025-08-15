from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, datetime, time, timedelta, timezone as tzinfo
from django.db import connection

# ---- utils ----
def _range(start: Optional[date], end: Optional[date]) -> Tuple[str, str]:
    # inclusive day range in UTC
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=29)  # default 30d window
    start_ts = f"{start.isoformat()} 00:00:00+00"
    end_ts   = f"{end.isoformat()} 23:59:59.999999+00"
    return start_ts, end_ts

def _fetchall(cursor) -> List[Dict[str, Any]]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

# ---- Board time-series (throughput, velocity, bugs%, lead-time median) ----
def timeseries_board(board_id: int, start: Optional[date], end: Optional[date]) -> List[Dict[str, Any]]:
    start_ts, end_ts = _range(start, end)
    sql = """
    with done as (
      select
        (done_at at time zone 'UTC')::date as d,
        coalesce(story_points, 0)::float as pts,
        (item_type = 'bug')::int as is_bug,
        extract(epoch from (done_at - created_at)) as lead_sec
      from metrics_workitem
      where board_id = %s
        and done_at is not null
        and done_at between %s and %s
    )
    select
      d as date,
      count(*)::int as throughput,
      sum(pts)::float as velocity_points,
      case when count(*)=0 then 0 else sum(is_bug)::float / count(*) end as defect_density,
      percentile_cont(0.5) within group (order by lead_sec) as median_lead_time_sec
    from done
    group by d
    order by d;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [board_id, start_ts, end_ts])
        return _fetchall(cur)

# ---- WIP counts at "now" (point-in-time) ----
def wip_board(board_id: int) -> Dict[str, Any]:
    sql = """
    select
      sum( case when dev_started_at is not null and dev_done_at is null and closed = false then 1 else 0 end )::int as wip_dev,
      sum( case when qa_started_at  is not null and (qa_verified_at is null and signed_off_at is null and done_at is null) and closed = false then 1 else 0 end )::int as wip_qa,
      sum( case when ready_for_qa_at is not null and qa_started_at is null and closed = false then 1 else 0 end )::int as waiting_for_qa
    from metrics_workitem
    where board_id = %s;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [board_id])
        rows = _fetchall(cur)
        return rows[0] if rows else {"wip_dev": 0, "wip_qa": 0, "waiting_for_qa": 0}

# ---- PR review metrics time-series ----
def timeseries_review(board_id: int, start: Optional[date], end: Optional[date]) -> List[Dict[str, Any]]:
    start_ts, end_ts = _range(start, end)
    sql = """
    with prs as (
      select
        (opened_at at time zone 'UTC')::date as d_open,
        (merged_at at time zone 'UTC')::date as d_merged,
        opened_at, first_reviewed_at, merged_at,
        reviewer_ids
      from metrics_pr p
      join metrics_workitem w on w.id = p.work_item_id
      where w.board_id = %s
        and opened_at between %s and %s
    )
    select
      d_open as date,
      count(*)::int as prs_opened,
      sum( case when merged_at is not null then 1 else 0 end )::int as prs_merged,
      percentile_cont(0.5) within group (order by extract(epoch from (first_reviewed_at - opened_at))) as median_time_to_first_review_sec,
      coalesce(avg( jsonb_array_length(coalesce(reviewer_ids, '[]'::jsonb)) ), 0)::float as avg_reviews_per_pr
    from prs
    group by d_open
    order by d_open;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [board_id, start_ts, end_ts])
        return _fetchall(cur)

# ---- User leaderboard (windowed) ----
def user_leaderboard(board_id: int, start: Optional[date], end: Optional[date],
                     limit: int, sort: str) -> List[Dict[str, Any]]:
    start_ts, end_ts = _range(start, end)

    # materialize 7d and 30d windows relative to 'end'
    sql = """
    with params as (
      select %s::int as board_id, %s::timestamptz as start_ts, %s::timestamptz as end_ts
    ),
    wi_30 as (
      select dev_owner as user_id,
             count(*)::int as done_count_30d,
             sum(coalesce(story_points,0))::float as done_points_30d
      from metrics_workitem, params
      where board_id = params.board_id
        and done_at between (params.end_ts - interval '29 day') and params.end_ts
        and dev_owner is not null
      group by dev_owner
    ),
    wi_7 as (
      select dev_owner as user_id,
             count(*)::int as done_count_7d,
             sum(coalesce(story_points,0))::float as done_points_7d
      from metrics_workitem, params
      where board_id = params.board_id
        and done_at between (params.end_ts - interval '6 day') and params.end_ts
        and dev_owner is not null
      group by dev_owner
    ),
    pr_30 as (
      select rid as user_id, count(*)::int as reviews_30d
      from (
        select jsonb_array_elements_text(coalesce(reviewer_ids,'[]')) as rid
        from metrics_pr p
        join metrics_workitem w on w.id=p.work_item_id, params
        where w.board_id = params.board_id
          and opened_at between (params.end_ts - interval '29 day') and params.end_ts
      ) t group by rid
    ),
    pr_7 as (
      select rid as user_id, count(*)::int as reviews_7d
      from (
        select jsonb_array_elements_text(coalesce(reviewer_ids,'[]')) as rid
        from metrics_pr p
        join metrics_workitem w on w.id=p.work_item_id, params
        where w.board_id = params.board_id
          and opened_at between (params.end_ts - interval '6 day') and params.end_ts
      ) t group by rid
    )
    select
      coalesce(w30.user_id, w7.user_id, p30.user_id, p7.user_id) as user_id,
      coalesce(w30.done_count_30d, 0) as done_count_30d,
      coalesce(w30.done_points_30d, 0)::float as done_points_30d,
      coalesce(w7.done_count_7d, 0)   as done_count_7d,
      coalesce(w7.done_points_7d, 0)::float   as done_points_7d,
      coalesce(p30.reviews_30d, 0)    as reviews_30d,
      coalesce(p7.reviews_7d, 0)      as reviews_7d
    from wi_30 w30
    full outer join wi_7  w7  on w7.user_id  = w30.user_id
    full outer join pr_30 p30 on p30.user_id = coalesce(w30.user_id, w7.user_id)
    full outer join pr_7  p7  on p7.user_id  = coalesce(w30.user_id, w7.user_id, p30.user_id)
    order by {SORT} desc, user_id asc
    limit %s;
    """

    sort_whitelist = {
        "done_points_30d": "coalesce(w30.done_points_30d,0)",
        "done_points_7d":  "coalesce(w7.done_points_7d,0)",
        "done_count_30d":  "coalesce(w30.done_count_30d,0)",
        "done_count_7d":   "coalesce(w7.done_count_7d,0)",
        "reviews_30d":     "coalesce(p30.reviews_30d,0)",
        "reviews_7d":      "coalesce(p7.reviews_7d,0)"
    }
    sort_sql = sort_whitelist.get(sort, sort_whitelist["done_points_30d"])
    sql = sql.replace("{SORT}", sort_sql)

    with connection.cursor() as cur:
        cur.execute(sql, [board_id, start_ts, end_ts, limit])
        return _fetchall(cur)
