from __future__ import annotations
import datetime as dt
from typing import List

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from metrics.models import RawPayload, Board
from .object_store import ensure_bucket, build_key, put_json_gz, delete_object

BUCKET = getattr(settings, "RAW_OFFLOAD_BUCKET", "sldp-raw")
PREFIX = getattr(settings, "RAW_OFFLOAD_PREFIX", "raw")
KEEP_INLINE_DAYS = int(getattr(settings, "RAW_KEEP_INLINE_DAYS", 7))
RETENTION_DAYS = int(getattr(settings, "RAW_RETENTION_DAYS", 90))
BATCH = int(getattr(settings, "RAW_OFFLOAD_BATCH", 500))

@shared_task(queue="default")
def offload_rawpayloads(board_id: int | None = None, limit: int = BATCH) -> int:
    """
    Upload RawPayload.payload JSON to object store (gzip) and set object_storage_key + payload_bytes.
    Leaves payload in DB temporarily if fetched_at is within KEEP_INLINE_DAYS; otherwise clears payload (saves space).
    """
    ensure_bucket(BUCKET)
    qs = RawPayload.objects.filter(object_storage_key__isnull=True)
    if board_id:
        qs = qs.filter(board_id=board_id)
    qs = qs.order_by("fetched_at")[:limit]

    count = 0
    for rp in qs:
        key = build_key(PREFIX,
                        source=rp.source,
                        board_id=str(rp.board.board_id if rp.board else "na"),
                        object_type=rp.object_type,
                        external_id=str(rp.external_id),
                        fetched_at=rp.fetched_at)
        size = put_json_gz(BUCKET, key, rp.payload)
        with transaction.atomic():
            rp.object_storage_key = key
            rp.payload_bytes = size
            # clear inline payload if older than KEEP_INLINE_DAYS
            if rp.fetched_at and rp.fetched_at < (timezone.now() - dt.timedelta(days=KEEP_INLINE_DAYS)):
                rp.payload = {"_offloaded": True}
            rp.save(update_fields=["object_storage_key", "payload_bytes", "payload"])
        count += 1
    return count

@shared_task(queue="default")
def rawpayload_retention(board_id: int | None = None) -> int:
    """
    Delete RawPayload rows older than RETENTION_DAYS and remove corresponding objects from bucket.
    """
    cutoff = timezone.now() - dt.timedelta(days=RETENTION_DAYS)
    qs = RawPayload.objects.filter(fetched_at__lt=cutoff)
    if board_id:
        qs = qs.filter(board_id=board_id)
    qs = qs.only("id", "object_storage_key").order_by("id")[:5000]  # safety cap per run

    deleted = 0
    for rp in qs:
        key = rp.object_storage_key
        try:
            if key:
                delete_object(BUCKET, key)
        except Exception:
            # tolerate missing objects; proceed to delete row
            pass
        rp.delete()
        deleted += 1
    return deleted
