from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, timedelta
from django.db import connection

def _range(start: Optional[date], end: Optional[date]) -> tuple[str, str]:
    if end is None:
        from datetime import date as _d
        end = _d.today()
    if start is None:
        start = end - timedelta(days=29)  # default 30d
    start_ts = f"{start.isoformat()} 00:00:00+00"
    end_ts   = f"{end.isoformat()} 23:59:59.999999+00"
    return start_ts, end_ts

def _fetchall(cur) -> List[Dict[str, Any]]:
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

# ---------- SUMMARY ----------
def user_summary(board_id: int, uid: str, start: Optional[date], end: Optional[date]) -> Dict[str, Any]:
    start_ts, end_ts = _range(start, end)
    sql_done = """
    with done as (
      select
        coalesce(story_points,0)::float as pts,
        extract(epoch from (done_at - created_at)) as lead_sec
      from metrics_workitem
      where board_id = %s
        and dev_owner = %s
        and done_at between %s and %s
    )
    select
      count(*)::int as done_count,
      coalesce(sum(pts),0)::float as done_points,
      percentile_cont(0.5) within group (order by lead_sec) as median_lead_time_sec
    from done;
    """
    sql_prs = """
    with prs as (
      select author_id, reviewer_ids, opened_at
      from metrics_pr p
      join metrics_workitem w on w.id = p.work_item_id
      where w.board_id = %s and opened_at between %s and %s
    ),
    auth as (
      select count(*)::int as prs_opened from prs where author_id = %s
    ),
    rev as (
      select count(*)::int as prs_reviewed
      from (
        select jsonb_array_elements_text(coalesce(reviewer_ids,'[]')) as rid from prs
      ) t where rid = %s
    )
    select a.prs_opened, r.prs_reviewed from auth a cross join rev r;
    """
    with connection.cursor() as cur:
        cur.execute(sql_done, [board_id, uid, start_ts, end_ts])
        done_row = cur.fetchone()
        if not done_row:
            done = {"done_count": 0, "done_points": 0.0, "median_lead_time_sec": None}
        else:
            done = dict(zip([c[0] for c in cur.description], done_row))

    with connection.cursor() as cur:
        cur.execute(sql_prs, [board_id, start_ts, end_ts, uid, uid])
        row = cur.fetchone()
        prs = {"prs_opened": 0, "prs_reviewed": 0} if not row else dict(zip([c[0] for c in cur.description], row))

    out = {**done, **prs}
    return out

# ---------- TIMESERIES (daily) ----------
def user_timeseries(board_id: int, uid: str, start: Optional[date], end: Optional[date]) -> List[Dict[str, Any]]:
    start_ts, end_ts = _range(start, end)
    sql = """
    with done as (
      select
        (done_at at time zone 'UTC')::date as d,
        coalesce(story_points,0)::float as pts
      from metrics_workitem
      where board_id = %s and dev_owner = %s
        and done_at between %s and %s
    ),
    prs as (
      select
        (opened_at at time zone 'UTC')::date as d_open,
        author_id,
        reviewer_ids
      from metrics_pr p
      join metrics_workitem w on w.id=p.work_item_id
      where w.board_id=%s and opened_at between %s and %s
    ),
    opened as (
      select d_open as d, count(*)::int as prs_opened
      from prs where author_id = %s group by d_open
    ),
    reviewed as (
      select d_open as d, count(*)::int as prs_reviewed
      from (
        select d_open, jsonb_array_elements_text(coalesce(reviewer_ids,'[]')) as rid from prs
      ) t where rid = %s group by d_open
    )
    select
      d::date as date,
      coalesce(sum_done,0)::int as done_count,
      coalesce(sum_pts,0)::float as done_points,
      coalesce(o.prs_opened,0)::int as prs_opened,
      coalesce(r.prs_reviewed,0)::int as prs_reviewed
    from (
      select d, count(*) as sum_done, sum(pts)::float as sum_pts from done group by d
      union
      select d, 0, 0 from opened
      union
      select d, 0, 0 from reviewed
    ) base
    left join opened  o on o.d = base.d
    left join reviewed r on r.d = base.d
    order by date;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [board_id, uid, start_ts, end_ts, board_id, start_ts, end_ts, uid, uid])
        return _fetchall(cur)

# ---------- WIP (point-in-time) ----------
def user_wip(board_id: int, uid: str) -> Dict[str, Any]:
    sql = """
    select
      sum( case when dev_started_at is not null and dev_done_at is null and closed = false then 1 else 0 end )::int as in_dev,
      sum( case when ready_for_qa_at is not null and qa_started_at is null and closed = false then 1 else 0 end )::int as waiting_for_qa,
      sum( case when qa_started_at is not null and qa_verified_at is null and closed = false then 1 else 0 end )::int as in_qa
    from metrics_workitem
    where board_id=%s and dev_owner=%s;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [board_id, uid])
        row = cur.fetchone()
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row)) if row else {"in_dev": 0, "waiting_for_qa": 0, "in_qa": 0}
