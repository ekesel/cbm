# etl/validator.py
from __future__ import annotations
import datetime as dt
from typing import Dict, Any, Iterable, List, Optional, Tuple

from django.utils import timezone
from django.db import transaction
from django.conf import settings

from etl.models import MappingVersion
from metrics.models import (
    WorkItem, Board, RemediationTicket, RemediationStatus, ItemType
)

# ----------------------- Config helpers --------------------------------------

def _active_cfg() -> Dict[str, Any]:
    mv = MappingVersion.objects.filter(active=True).order_by("-created_at").first()
    root = mv.config if mv else {}
    return root.get("validator", {}) if isinstance(root, dict) else {}

def _cfg(path: List[str], default=None):
    cfg = _active_cfg()
    node = cfg
    for k in path:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
        if node is None:
            return default
    return node if node is not None else default

def _fallback(key: str):
    defaults = getattr(settings, "VALIDATOR_DEFAULTS", {})
    return defaults.get(key)

def _days_ago(d: Optional[dt.datetime]) -> Optional[int]:
    if not d:
        return None
    return int((timezone.now() - d).total_seconds() // 86400)

# ----------------------- Ticket helpers --------------------------------------

def open_ticket(board: Board, work_item: Optional[WorkItem], rule_code: str, message: str, meta: Dict[str, Any] | None = None) -> RemediationTicket:
    """
    Idempotent: finds an open/in-progress ticket for the same (board, work_item, rule_code) or creates one.
    If a resolved ticket exists and violation reappears, re-open by creating a new ticket.
    """
    meta = meta or {}
    rt = (RemediationTicket.objects
          .filter(board=board, work_item=work_item, rule_code=rule_code)
          .exclude(status=RemediationStatus.DONE)
          .order_by("-created_at")
          .first())
    if rt:
        # update message/meta if changed
        changed = False
        if rt.message != message:
            rt.message = message
            changed = True
        if meta and (rt.meta or {}) != meta:
            rt.meta = meta
            changed = True
        if changed:
            rt.save(update_fields=["message", "meta"])
        return rt

    return RemediationTicket.objects.create(
        board=board,
        work_item=work_item,
        rule_code=rule_code,
        message=message,
        meta=meta,
    )

def resolve_ticket_if_any(board: Board, work_item: Optional[WorkItem], rule_code: str):
    q = (RemediationTicket.objects
         .filter(board=board, work_item=work_item, rule_code=rule_code)
         .exclude(status=RemediationStatus.DONE))
    now = timezone.now()
    for rt in q:
        rt.status = RemediationStatus.DONE
        rt.resolved_at = now
        rt.save(update_fields=["status", "resolved_at"])

# ----------------------- Rules ------------------------------------------------
# Each rule returns an integer count of violations for reporting.

def rule_missing_points(board: Board, items: Iterable[WorkItem]) -> int:
    """
    Require story points for certain item types before status passes dev_started.
    """
    require_types = set(_cfg(["require_points_for_types"], _fallback("require_points_for_types")) or [])
    ignore_subtasks = bool(_cfg(["ignore_when_subtask"], _fallback("ignore_when_subtask")))

    count = 0
    for wi in items:
        if ignore_subtasks and wi.item_type == ItemType.SUBTASK:
            resolve_ticket_if_any(board, wi, "MISSING_POINTS")
            continue
        if wi.item_type.lower() not in require_types:
            resolve_ticket_if_any(board, wi, "MISSING_POINTS")
            continue
        if wi.dev_started_at and wi.story_points is None:
            open_ticket(board, wi, "MISSING_POINTS", f"Story points are required before dev starts (item: {wi.source_id}).")
            count += 1
        else:
            resolve_ticket_if_any(board, wi, "MISSING_POINTS")
    return count

def rule_stuck_in_dev(board: Board, items: Iterable[WorkItem]) -> int:
    """
    If dev_started_at set but dev_done_at missing for > X days.
    """
    max_days = int(_cfg(["max_dev_days_without_progress"], _fallback("max_dev_days_without_progress")) or 4)
    count = 0
    for wi in items:
        if wi.dev_started_at and not wi.dev_done_at and not wi.closed:
            days = _days_ago(wi.dev_started_at) or 0
            if days > max_days:
                open_ticket(board, wi, "STUCK_IN_DEV", f"Dev in progress for {days} days (> {max_days}).")
                count += 1
            else:
                resolve_ticket_if_any(board, wi, "STUCK_IN_DEV")
        else:
            resolve_ticket_if_any(board, wi, "STUCK_IN_DEV")
    return count

def rule_waiting_for_qa(board: Board, items: Iterable[WorkItem]) -> int:
    """
    Ready for QA > X days without qa_started_at.
    """
    max_days = int(_cfg(["max_ready_for_qa_days"], _fallback("max_ready_for_qa_days")) or 2)
    count = 0
    for wi in items:
        if wi.ready_for_qa_at and not wi.qa_started_at and not wi.closed:
            days = _days_ago(wi.ready_for_qa_at) or 0
            if days > max_days:
                open_ticket(board, wi, "WAITING_FOR_QA", f"In 'Ready for QA' for {days} days (> {max_days}).")
                count += 1
            else:
                resolve_ticket_if_any(board, wi, "WAITING_FOR_QA")
        else:
            resolve_ticket_if_any(board, wi, "WAITING_FOR_QA")
    return count

def rule_stuck_in_qa(board: Board, items: Iterable[WorkItem]) -> int:
    """
    QA started but not verified/done for > X days.
    """
    max_days = int(_cfg(["max_qa_days"], _fallback("max_qa_days")) or 3)
    count = 0
    for wi in items:
        if wi.qa_started_at and not (wi.qa_verified_at or wi.signed_off_at or wi.done_at):
            days = _days_ago(wi.qa_started_at) or 0
            if days > max_days:
                open_ticket(board, wi, "STUCK_IN_QA", f"QA in progress for {days} days (> {max_days}).")
                count += 1
            else:
                resolve_ticket_if_any(board, wi, "STUCK_IN_QA")
        else:
            resolve_ticket_if_any(board, wi, "STUCK_IN_QA")
    return count

def rule_blocked_reason(board: Board, items: Iterable[WorkItem]) -> int:
    """
    If blocked_flag is true, require blocked_reason non-empty.
    """
    count = 0
    for wi in items:
        if wi.blocked_flag and not (wi.blocked_reason or "").strip():
            open_ticket(board, wi, "BLOCKED_NO_REASON", "Work item is blocked but no blocked_reason is provided.")
            count += 1
        else:
            resolve_ticket_if_any(board, wi, "BLOCKED_NO_REASON")
    return count

def rule_pr_required(board: Board, items: Iterable[WorkItem]) -> int:
    """
    If status indicates code work (Dev/Ready for QA/etc.) then require at least one linked PR (from C-03 GH normalizer).
    Only for certain item types.
    """
    require_types = set(_cfg(["require_pr_for_types"], _fallback("require_pr_for_types")) or [])
    keywords = [k.lower() for k in (_cfg(["pr_required_when_status_contains"], _fallback("pr_required_when_status_contains")) or [])]

    count = 0
    for wi in items:
        if wi.item_type.lower() not in require_types:
            resolve_ticket_if_any(board, wi, "PR_REQUIRED")
            continue
        status = (wi.status or "").lower()
        needs_pr = any(kw in status for kw in keywords)
        has_pr = bool(wi.linked_prs)
        if needs_pr and not has_pr:
            open_ticket(board, wi, "PR_REQUIRED", f"Status is '{wi.status}' but no linked PR found.")
            count += 1
        else:
            resolve_ticket_if_any(board, wi, "PR_REQUIRED")
    return count

# ----------------------- Runner ------------------------------------------------

ALL_RULES = [
    ("MISSING_POINTS", rule_missing_points),
    ("STUCK_IN_DEV", rule_stuck_in_dev),
    ("WAITING_FOR_QA", rule_waiting_for_qa),
    ("STUCK_IN_QA", rule_stuck_in_qa),
    ("BLOCKED_NO_REASON", rule_blocked_reason),
    ("PR_REQUIRED", rule_pr_required),
]

def validate_board(board: Board) -> Dict[str, int]:
    """
    Run all rules on the board's open (non-closed) items.
    Returns dict of rule_code -> violations count.
    """
    items = WorkItem.objects.filter(board=board).only(
        "id", "source", "source_id", "item_type", "status", "story_points",
        "dev_started_at", "dev_done_at", "ready_for_qa_at", "qa_started_at",
        "qa_verified_at", "signed_off_at", "done_at", "blocked_flag",
        "blocked_reason", "linked_prs", "closed"
    )
    # Most rules ignore closed items implicitly; keep them in queryset, rules check .closed

    results: Dict[str, int] = {}
    for code, func in ALL_RULES:
        results[code] = int(func(board, items))
    return results
