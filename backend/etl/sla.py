from __future__ import annotations
import datetime as dt
from typing import Dict, Any, Optional, Tuple

from django.utils import timezone
from celery import shared_task
from django.conf import settings
from django.db.models import Q

from etl.models import MappingVersion
from metrics.models import WorkItem, Board, RemediationTicket, RemediationStatus
from etl.validator import open_ticket, resolve_ticket_if_any  # reuse helpers

def _cfg() -> Dict[str, Any]:
    mv = MappingVersion.objects.filter(active=True).order_by("-created_at").first()
    root = mv.config if mv else {}
    return (root.get("sla") or {}) if isinstance(root, dict) else {}

def _hours_for_item(wi: WorkItem) -> int:
    cfg = _cfg()
    defaults = getattr(settings, "SLA_DEFAULTS", {}) or {}
    # priority-based override (by label or status/priority field in meta)
    pri_map = (cfg.get("by_priority") or {}) or (defaults.get("by_priority") or {})
    priority = None
    # try from meta or labels in meta
    if isinstance(wi.meta, dict):
        priority = (wi.meta.get("priority") or wi.meta.get("Priority") or "").strip()
        if not priority:
            labels = wi.meta.get("labels") or []
            if isinstance(labels, list):
                for l in labels:
                    if str(l).lower() in {k.lower() for k in pri_map.keys()}:
                        priority = str(l)
                        break
    if priority:
        for k, v in pri_map.items():
            if priority.lower() == str(k).lower():
                try: return int(v)
                except: pass

    # type-based override
    type_map = (cfg.get("by_type") or {}) or (defaults.get("by_type") or {})
    t = (wi.item_type or "").lower()
    if t in {k.lower(): v for k, v in type_map.items()}:
        try:
            return int({k.lower(): v for k, v in type_map.items()}[t])
        except:
            pass

    # global fallback
    try:
        return int(cfg.get("blocked_hours", defaults.get("blocked_hours", 48)))
    except:
        return 48

@shared_task(queue="default")
def sla_check_blocked(board_id: Optional[int] = None, lookback_days: int = 30) -> int:
    """
    Create/resolve RemediationTickets when blocked > SLA.
    Returns number of tickets opened/updated.
    """
    boards = Board.objects.filter(id=board_id) if board_id else Board.objects.all()
    touched = 0

    for b in boards:
        # Only consider items with blocked_flag true and blocked_since known; small lookback bound for perf
        since = timezone.now() - dt.timedelta(days=lookback_days)
        items = (WorkItem.objects
                 .filter(board=b, blocked_flag=True)
                 .filter(Q(blocked_since__isnull=False) | Q(updated_at__gte=since)))  # tolerate missing blocked_since

        for wi in items:
            # skip closed
            if wi.closed:
                resolve_ticket_if_any(b, wi, "BLOCKED_SLA")
                continue

            start = wi.blocked_since or wi.dev_started_at or wi.created_at
            if not start:
                resolve_ticket_if_any(b, wi, "BLOCKED_SLA")
                continue

            hours = (timezone.now() - start).total_seconds() / 3600.0
            limit_h = _hours_for_item(wi)

            if hours > limit_h:
                msg = f"Blocked for ~{int(hours)}h, SLA {limit_h}h exceeded (item {wi.source_id})."
                open_ticket(b, wi, "BLOCKED_SLA", msg, meta={"blocked_since": start.isoformat(), "sla_hours": limit_h})
                touched += 1
            else:
                resolve_ticket_if_any(b, wi, "BLOCKED_SLA")

    return touched

@shared_task(queue="default")
def backfill_blocked_since(board_id: Optional[int] = None, set_to_now_if_missing: bool = True) -> int:
    """
    Best-effort: for items currently blocked but missing blocked_since, set it (now or created_at).
    """
    boards = Board.objects.filter(id=board_id) if board_id else Board.objects.all()
    n = 0
    for b in boards:
        qs = WorkItem.objects.filter(board=b, blocked_flag=True, blocked_since__isnull=True)
        now = timezone.now()
        for wi in qs[:5000]:
            wi.blocked_since = wi.dev_started_at or wi.ready_for_qa_at or wi.created_at or (now if set_to_now_if_missing else None)
            wi.save(update_fields=["blocked_since"])
            n += 1
    return n
