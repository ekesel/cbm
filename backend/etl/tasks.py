# etl/tasks.py
from celery import shared_task
from django.utils import timezone
from etl.validator import validate_board
from metrics.models import Board, RawPayload
from etl.utils import etl_run, increment
from etl.registry import get_connector, get_normalizer

DEFAULT_MAPPING_VERSION = "v1"

@shared_task(queue="default")
def etl_fetch_raw(board_id: int, mapping_version: str = DEFAULT_MAPPING_VERSION) -> int:
    board = Board.objects.get(pk=board_id)
    since = board.last_synced
    with etl_run("fetch_raw", board=board, mapping_version=mapping_version, meta={"since": str(since)}) as run:
        connector = get_connector(board)
        items = connector.fetch_since(since_ts=since)  # list of dicts
        increment(run, records_pulled=len(items))
        # store to RawPayload
        objs = []
        for obj in items:
            objs.append(RawPayload(
                source=board.source,
                board=board,
                object_type=obj.get("object_type", "issue"),
                external_id=str(obj.get("external_id") or ""),
                payload=obj.get("payload") or {},
                mapping_version=mapping_version,
            ))
        if objs:
            RawPayload.objects.bulk_create(objs, ignore_conflicts=True)
        return len(items)

@shared_task(queue="default")
def etl_normalize(board_id: int, mapping_version: str = DEFAULT_MAPPING_VERSION) -> int:
    board = Board.objects.get(pk=board_id)
    with etl_run("normalize", board=board, mapping_version=mapping_version) as run:
        # get recent raw payloads for this board (last 2 days backstop)
        recent_raw = RawPayload.objects.filter(board=board).order_by("-fetched_at")[:5000]
        normalizer = get_normalizer(board)
        normalized_count = normalizer.normalize(recent_raw)
        increment(run, records_normalized=normalized_count)
        return normalized_count


@shared_task(queue="default")
def etl_validate(board_id: int) -> int:
    board = Board.objects.get(pk=board_id)
    from etl.utils import etl_run  # local import to avoid cycles
    with etl_run("validate", board=board) as run:
        results = validate_board(board)
        # store counts in run.meta for quick inspection
        run.meta = {"violations": results}
        run.save(update_fields=["meta"])
        # Return total violations
        return sum(results.values())

@shared_task(queue="default")
def etl_snapshot(board_id: int) -> int:
    """
    Placeholder; E-01/E-02 will compute & store MetricSnapshot and serve API queries.
    """
    board = Board.objects.get(pk=board_id)
    with etl_run("snapshot", board=board) as run:
        # TODO: compute velocity/throughput/defects metrics and persist snapshots
        return 0

@shared_task(queue="default")
def run_etl_for_board(board_id: int, mapping_version: str = DEFAULT_MAPPING_VERSION) -> dict:
    """
    Orchestrator for a single board: fetch → normalize → validate → snapshot → bump last_synced
    """
    board = Board.objects.get(pk=board_id)
    result = {"board": board_id, "fetched": 0, "normalized": 0, "validated": 0, "snapshots": 0}
    result["fetched"] = etl_fetch_raw(board_id, mapping_version)
    result["normalized"] = etl_normalize(board_id, mapping_version)
    result["validated"] = etl_validate(board_id)
    result["snapshots"] = etl_snapshot(board_id)
    # bump last_synced
    Board.objects.filter(pk=board_id).update(last_synced=timezone.now())
    return result

@shared_task(queue="default")
def run_all_boards(mapping_version: str = DEFAULT_MAPPING_VERSION) -> int:
    """
    Fan-out over all boards; enqueue per-board orchestrations.
    """
    ids = list(Board.objects.values_list("id", flat=True))
    for bid in ids:
        run_etl_for_board.delay(bid, mapping_version=mapping_version)
    return len(ids)