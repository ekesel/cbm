from __future__ import annotations
import statistics
import datetime as dt
from collections import defaultdict
from typing import Dict, Any, List, Tuple

from django.utils import timezone
from django.db.models import Q, Count, Avg, F, Value, IntegerField

from .models import (
    Board, WorkItem, PR, RemediationTicket, RemediationStatus,
    BoardDailySnapshot, UserDailySnapshot, ItemType,
)

# ------------ Helpers ------------
def _utc_date(target: dt.datetime | None = None) -> dt.date:
    now = target or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    return now.astimezone(dt.timezone.utc).date()

def _range_days(end_date_utc: dt.date, days: int) -> Tuple[dt.datetime, dt.datetime]:
    # inclusive end at 23:59:59 for the given date (UTC)
    end_dt = dt.datetime.combine(end_date_utc, dt.time(23,59,59, tzinfo=dt.timezone.utc))
    start_dt = end_dt - dt.timedelta(days=days-1)
    return start_dt, end_dt

def _median_deltas(seconds_list: List[float]) -> float | None:
    vals = [s for s in seconds_list if s is not None]
    if not vals:
        return None
    return statistics.median(vals)

# ------------ Calculations (Board) ------------
def compute_board_metrics(board: Board, snapshot_date: dt.date) -> Dict[str, Any]:
    """
    Returns a dict of metrics for the given board & date.
    Windows: 1d (yesterday), 7d, 14d, 30d rolling ending at snapshot_date (UTC).
    """
    m: Dict[str, Any] = {}
    win_defs = {"1d": 1, "7d": 7, "14d": 14, "30d": 30}
    windows: Dict[str, Dict[str, Any]] = {}

    for name, n_days in win_defs.items():
        start, end = _range_days(snapshot_date, n_days)

        # Completed items in window
        done_q = WorkItem.objects.filter(board=board, done_at__isnull=False, done_at__range=(start, end))
        done_count = done_q.count()
        done_points = float(done_q.exclude(story_points__isnull=True).aggregate(p=Avg("story_points"))["p"] or 0)  # avg points (for info)
        sum_points = sum(done_q.values_list("story_points", flat=True).exclude(story_points__isnull=True))

        # Throughput (count), Velocity (sum of story_points)
        windows[name] = {
            "throughput": done_count,
            "velocity_points": float(sum_points or 0.0),
            "avg_points_per_done": float(done_points or 0.0),
        }

        # Defect density: share of bugs among completed items (fallback 0)
        bug_done = done_q.filter(item_type=ItemType.BUG).count()
        windows[name]["defect_density"] = float(bug_done / done_count) if done_count else 0.0

        # Lead/Cycle time (coarse): created → done in seconds (median)
        lead_secs = []
        for wi in done_q.only("created_at", "done_at"):
            if wi.created_at and wi.done_at:
                lead_secs.append((wi.done_at - wi.created_at).total_seconds())
        windows[name]["median_lead_time_sec"] = _median_deltas(lead_secs)

        # PR metrics (if this board tracks GitHub PR links)
        prs = PR.objects.filter(
            work_item__board=board,
            opened_at__range=(start, end)
        ).select_related("work_item")
        opened = prs.count()
        merged = prs.filter(merged_at__isnull=False, merged_at__range=(start, end)).count()
        # time to first review (opened → first_reviewed_at)
        tfr = []
        for pr in prs:
            if pr.opened_at and pr.first_reviewed_at:
                tfr.append((pr.first_reviewed_at - pr.opened_at).total_seconds())
        windows[name]["prs_opened"] = opened
        windows[name]["prs_merged"] = merged
        windows[name]["median_time_to_first_review_sec"] = _median_deltas(tfr)
        # review participation (unique reviewers / PR)
        unique_reviewers = set()
        for pr in prs:
            for rid in (pr.reviewer_ids or []):
                unique_reviewers.add(rid)
        windows[name]["unique_reviewers"] = len(unique_reviewers)
        windows[name]["avg_reviews_per_pr"] = float(sum(len(pr.reviewer_ids or []) for pr in prs) / opened) if opened else 0.0

    m["windows"] = windows

    # WIP / Delay tracking (point-in-time counts on snapshot_date end)
    end = _range_days(snapshot_date, 1)[1]
    wip_dev = WorkItem.objects.filter(board=board, dev_started_at__isnull=False, dev_done_at__isnull=True, closed=False).count()
    wip_qa = WorkItem.objects.filter(board=board, qa_started_at__isnull=False, qa_verified_at__isnull=True, closed=False).count()
    m["wip"] = {"dev": wip_dev, "qa": wip_qa}

    # Outstanding remediation tickets by rule
    open_rts = RemediationTicket.objects.filter(board=board).exclude(status=RemediationStatus.DONE)
    per_rule = defaultdict(int)
    for rt in open_rts:
        per_rule[rt.rule_code] += 1
    m["remediation_open_counts"] = per_rule

    return m

# ------------ Calculations (User) ------------
def compute_user_metrics(board: Board, snapshot_date: dt.date) -> Dict[str, Any]:
    """
    Returns dict: user_id -> metrics
    user_id is taken from WorkItem.dev_owner for dev, and PR.reviewer_ids for code review participation.
    """
    start7, end7 = _range_days(snapshot_date, 7)
    start30, end30 = _range_days(snapshot_date, 30)

    user_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "done_count_7d": 0, "done_points_7d": 0.0,
        "done_count_30d": 0, "done_points_30d": 0.0,
        "prs_reviewed_7d": 0, "prs_reviewed_30d": 0,
    })

    # Done work items grouped by dev_owner
    done_items_7 = WorkItem.objects.filter(board=board, done_at__range=(start7, end7)).exclude(dev_owner__isnull=True)
    for wi in done_items_7.values("dev_owner", "story_points"):
        uid = wi["dev_owner"]
        user_data[uid]["done_count_7d"] += 1
        user_data[uid]["done_points_7d"] += float(wi["story_points"] or 0.0)

    done_items_30 = WorkItem.objects.filter(board=board, done_at__range=(start30, end30)).exclude(dev_owner__isnull=True)
    for wi in done_items_30.values("dev_owner", "story_points"):
        uid = wi["dev_owner"]
        user_data[uid]["done_count_30d"] += 1
        user_data[uid]["done_points_30d"] += float(wi["story_points"] or 0.0)

    # Review participation from PRs (reviewer_ids)
    prs_7 = PR.objects.filter(work_item__board=board, opened_at__range=(start7, end7))
    for pr in prs_7:
        for rid in (pr.reviewer_ids or []):
            user_data[rid]["prs_reviewed_7d"] += 1

    prs_30 = PR.objects.filter(work_item__board=board, opened_at__range=(start30, end30))
    for pr in prs_30:
        for rid in (pr.reviewer_ids or []):
            user_data[rid]["prs_reviewed_30d"] += 1

    return user_data
