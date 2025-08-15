from __future__ import annotations
import datetime as dt
from typing import Optional
from celery import shared_task

from metrics.models import Board, BoardDailySnapshot, UserDailySnapshot
from metrics.snapshots import compute_board_metrics, compute_user_metrics, _utc_date

def _upsert_board_snapshot(board, date_utc, metrics):
    obj, created = BoardDailySnapshot.objects.update_or_create(
        board=board, date=date_utc,
        defaults={"metrics": metrics}
    )
    return obj

def _upsert_user_snapshots(board, date_utc, user_metrics: dict):
    for user_id, m in user_metrics.items():
        UserDailySnapshot.objects.update_or_create(
            board=board, date=date_utc, user_id=str(user_id),
            defaults={"metrics": m}
        )

@shared_task(queue="default")
def run_daily_snapshot(board_id: Optional[int] = None, date_iso: Optional[str] = None) -> int:
    """
    Compute & upsert daily snapshots for a board (or all boards).
    date_iso: optional 'YYYY-MM-DD' in UTC. Defaults to current UTC date.
    Returns number of boards processed.
    """
    if date_iso:
        date_utc = dt.date.fromisoformat(date_iso)
    else:
        date_utc = _utc_date()

    boards = Board.objects.filter(id=board_id) if board_id else Board.objects.all()
    count = 0
    for b in boards:
        bm = compute_board_metrics(b, date_utc)
        _upsert_board_snapshot(b, date_utc, bm)

        um = compute_user_metrics(b, date_utc)
        _upsert_user_snapshots(b, date_utc, um)
        count += 1
    return count
