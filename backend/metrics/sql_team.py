from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, timedelta
from django.db import connection

def _range(start: Optional[date], end: Optional[date]) -> tuple[str, str]:
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=29)  # default 30d
    start_ts = f"{start.isoformat()} 00:00:00+00"
    end_ts   = f"{end.isoformat()} 23:59:59.999999+00"
    return start_ts, end_ts

def team_timeseries(team_id: int, start: Optional[date], end: Optional[date]) -> List[Dict[str, Any]]:
    """
    Daily time-series across all boards mapped to the team.
    Returns: [{date, throughput, velocity_points, defect_density, median_lead_time_sec}, ...]
    """
    start_ts, end_ts = _range(start, end)
    sql = """
    with team_boards as (
      select board_id from metrics_teamboard where team_id = %s
    ),
    done as (
      select
        (w.done_at at time zone 'UTC')::date as d,
        coalesce(w.story_points, 0)::float as pts,
        (w.item_type = 'bug')::int as is_bug,
        extract(epoch from (w.done_at - w.created_at)) as lead_sec
      from metrics_workitem w
      join team_boards tb on tb.board_id = w.board_id
      where w.done_at is not null
        and w.done_at between %s and %s
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
        cur.execute(sql, [team_id, start_ts, end_ts])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

def team_summary(team_id: int, start: Optional[date], end: Optional[date]) -> Dict[str, Any]:
    """
    Range summary across all boards mapped to the team.
    Returns: {throughput, velocity_points, defect_density, median_lead_time_sec}
    """
    start_ts, end_ts = _range(start, end)
    sql = """
    with team_boards as (
      select board_id from metrics_teamboard where team_id = %s
    ),
    done as (
      select
        coalesce(w.story_points, 0)::float as pts,
        (w.item_type = 'bug')::int as is_bug,
        extract(epoch from (w.done_at - w.created_at)) as lead_sec
      from metrics_workitem w
      join team_boards tb on tb.board_id = w.board_id
      where w.done_at is not null
        and w.done_at between %s and %s
    )
    select
      count(*)::int as throughput,
      coalesce(sum(pts),0)::float as velocity_points,
      case when count(*)=0 then 0 else sum(is_bug)::float / count(*) end as defect_density,
      percentile_cont(0.5) within group (order by lead_sec) as median_lead_time_sec
    from done;
    """
    with connection.cursor() as cur:
        cur.execute(sql, [team_id, start_ts, end_ts])
        row = cur.fetchone()
        if not row:
            return {"throughput": 0, "velocity_points": 0.0, "defect_density": 0.0, "median_lead_time_sec": None}
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))
