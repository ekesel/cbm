from __future__ import annotations
from celery import chain, shared_task

from metrics.models import Board
from .tasks import etl_fetch_raw, etl_normalize, etl_validate
from metrics.snapshots import _utc_date
from etl.snapshotter import run_daily_snapshot  # from E-01

def _build_chain(board_id: int, stages: list[str], mapping_version: str, date_iso: str | None):
    tasks = []
    if "fetch" in stages:
        tasks.append(etl_fetch_raw.s(board_id, mapping_version))
    if "normalize" in stages:
        tasks.append(etl_normalize.s(board_id))
    if "validate" in stages:
        tasks.append(etl_validate.s(board_id))
    if "snapshot" in stages:
        # run snapshot for this board (optionally for a specific date)
        if date_iso:
            tasks.append(run_daily_snapshot.s(board_id, date_iso))
        else:
            tasks.append(run_daily_snapshot.s(board_id))
    if not tasks:
        raise ValueError("No stages provided")
    return chain(*tasks)

@shared_task(queue="default")
def etl_pipeline(board_id: int, stages: list[str], mapping_version: str = "v1", date_iso: str | None = None) -> dict:
    """
    Enqueue the chosen stages as a Celery chain and return summary with the root task id.
    Note: the returned dict is available when the pipeline completes; callers usually use AsyncResult to poll.
    """
    # sanity
    Board.objects.get(pk=board_id)  # will raise DoesNotExist if invalid
    flow = _build_chain(board_id, stages, mapping_version, date_iso)
    res = flow.apply_async()
    return {"root_task_id": res.id, "board_id": board_id, "stages": stages, "mapping_version": mapping_version, "date_iso": date_iso}
