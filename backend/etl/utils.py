import traceback as _tb
from contextlib import contextmanager
from typing import Optional, Dict, Any

from django.db import transaction
from metrics.models import Board
from .models import ETLJobRun, MappingVersion, ETLStatus

@contextmanager
def etl_run(job_name: str, board: Optional[Board] = None, mapping_version: Optional[str] = None, meta: Optional[Dict[str, Any]] = None):
    """
    Usage:
      with etl_run("jira_board_pull", board=board, mapping_version="v1") as run:
          # ... pull data
          run.records_pulled += len(issues)
          # ... normalize
          run.records_normalized += normalized_count
    """
    with transaction.atomic():
        mv = None
        if mapping_version:
            mv = MappingVersion.objects.filter(version=mapping_version).first()
        run = ETLJobRun.objects.create(
            job_name=job_name,
            board=board,
            mapping_version=mv,
            status=ETLStatus.STARTED,
            meta=meta or {},
        )
    try:
        yield run
    except Exception as exc:
        tb = _tb.format_exc()
        run.mark_failed(message=str(exc), traceback_text=tb)
        raise
    else:
        run.mark_success()

def increment(run: ETLJobRun, **kwargs):
    """
    Convenience to update counters within a run.
    Example: increment(run, records_pulled=+100)
    """
    for field, delta in kwargs.items():
        if hasattr(run, field):
            setattr(run, field, getattr(run, field) + (delta or 0))
    run.save()
