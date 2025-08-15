from __future__ import annotations
import re, datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from etl.models import MappingVersion
from metrics.models import WorkItem, PR, Board, ItemType, Source

# -------------------- config helpers --------------------

def active_mapping() -> Optional[MappingVersion]:
    return MappingVersion.objects.filter(active=True).order_by("-created_at").first()

def cfg(path: Sequence[str], default=None):
    mv = active_mapping()
    node = mv.config if mv else {}
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
        if node is None:
            return default
    return node if node is not None else default

# -------------------- time parsing ----------------------

def to_dt(val: Any) -> Optional[dt.datetime]:
    """Parse many formats: ISO 8601, Jira '+0000', ClickUp ms epoch, seconds epoch."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            # treat as milliseconds if big, else seconds
            if int(val) > 10_000_000_000:
                return timezone.make_aware(dt.datetime.fromtimestamp(int(val)/1000.0, tz=dt.timezone.utc))
            return timezone.make_aware(dt.datetime.fromtimestamp(int(val), tz=dt.timezone.utc))
        except Exception:
            return None
    if isinstance(val, str):
        s = val.strip()
        # Jira like '2025-08-10T12:34:56.789+0000' -> '+00:00'
        if re.search(r"[+-]\d{4}$", s):
            s = s[:-5] + s[-5:-2] + ":" + s[-2:]
        d = parse_datetime(s)
        if d is None:
            # try without millis
            try:
                d = dt.datetime.fromisoformat(s.replace("Z","+00:00"))
            except Exception:
                return None
        if timezone.is_naive(d):
            d = timezone.make_aware(d, timezone=dt.timezone.utc)
        return d
    return None

def earliest(history_times: List[dt.datetime]) -> Optional[dt.datetime]:
    return min(history_times) if history_times else None

# -------------------- misc extractors -------------------

def map_item_type(name: Optional[str]) -> str:
    n = (name or "").lower()
    if "bug" in n: return ItemType.BUG
    if "sub-task" in n or "subtask" in n: return ItemType.SUBTASK
    if "epic" in n: return ItemType.EPIC
    if "task" in n: return ItemType.TASK
    return ItemType.STORY

def contains_blocked(status_name: str, labels: Iterable[str]) -> bool:
    sn = (status_name or "").lower()
    if "block" in sn: return True
    for l in labels or []:
        if "block" in (l or "").lower():
            return True
    return False

def upsert_parent(board: Board, source: str, parent_key: Optional[str]) -> Optional[WorkItem]:
    if not parent_key: return None
    parent, _ = WorkItem.objects.get_or_create(
        source=source, source_id=str(parent_key),
        defaults=dict(board=board, title=f"Parent {parent_key}", item_type=ItemType.STORY)
    )
    return parent

# -------------------- PR linking ------------------------

JIRA_KEY_RE = re.compile(r"([A-Z]{2,}-\d+)")

def extract_issue_keys_from_text(text: str, extra_patterns: Dict[str, str]) -> Dict[str, List[str]]:
    """
    Returns {'jira': ['PROJ-123', ...], 'azure': ['1234'], ...}
    """
    found: Dict[str, List[str]] = {}
    if text:
        # Jira default pattern
        jira_keys = JIRA_KEY_RE.findall(text)
        if jira_keys:
            found.setdefault("jira", []).extend(sorted(set(jira_keys)))
        # extras from config
        for src, pat in (extra_patterns or {}).items():
            try:
                m = re.findall(pat, text)
                if m: found.setdefault(src, []).extend(sorted(set([str(x) for x in m])))
            except re.error:
                continue
    return found

def add_linked_pr(work_item: WorkItem, pr_dict: Dict[str, Any], reviewers: List[str]):
    """
    Append PR link into WorkItem.linked_prs if not already present.
    """
    linked = work_item.linked_prs or []
    pid = pr_dict.get("pr_id")
    exists = any((x.get("pr_id") == pid) for x in linked)
    if not exists:
        linked.append({
            "pr_id": pid,
            "opened_at": pr_dict.get("opened_at"),
            "first_reviewed_at": pr_dict.get("first_reviewed_at"),
            "merged_at": pr_dict.get("merged_at"),
            "reviewers": reviewers,
        })
        work_item.linked_prs = linked
        work_item.save(update_fields=["linked_prs"])
