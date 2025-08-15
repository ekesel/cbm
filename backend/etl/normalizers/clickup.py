from __future__ import annotations
from typing import Iterable, Dict, Any, List, Optional

from metrics.models import WorkItem, Board, ItemType, Source, RawPayload
from .base import to_dt, map_item_type, cfg

class ClickUpNormalizer:
    def __init__(self, board: Board):
        self.board = board
        self.points_field_name = (cfg(["clickup","points_field_name"], "Story Points") or "").lower()

    def _points_from_custom(self, cf_list: list) -> Optional[float]:
        for cf in cf_list or []:
            name = (cf.get("name") or "").lower()
            if name == self.points_field_name:
                val = cf.get("value")
                try:
                    return float(val) if val is not None else None
                except Exception:
                    return None
        return None

    def normalize(self, raw_items: Iterable[RawPayload]) -> int:
        count = 0
        for rp in raw_items:
            if rp.source != Source.CLICKUP or rp.object_type != "task":
                continue
            t = rp.payload or {}

            tid = t.get("id")
            if not tid: 
                continue

            title = t.get("name") or "Untitled"
            status_name = (t.get("status") or {}).get("status") or ""
            itype = ItemType.BUG if "bug" in (title.lower()) else ItemType.STORY  # heuristic

            assignees = []
            for a in (t.get("assignees") or []):
                name = a.get("username") or a.get("email") or a.get("id")
                if name: assignees.append(str(name))
            dev_owner = assignees[0] if assignees else None

            created_at = to_dt(t.get("date_created"))
            updated_at = to_dt(t.get("date_updated"))
            done_at = to_dt(t.get("date_closed"))

            story_points = self._points_from_custom(t.get("custom_fields") or [])

            # Sprint/Iteration best-effort via custom field named Sprint/Iteration
            sprint_id = None
            for cf in (t.get("custom_fields") or []):
                name = (cf.get("name") or "").lower()
                if name in ("sprint","iteration"):
                    v = cf.get("value")
                    sprint_id = str(v.get("id") if isinstance(v, dict) else v) if v else None
                    break

            WorkItem.objects.update_or_create(
                source=Source.CLICKUP,
                source_id=str(tid),
                defaults=dict(
                    board=self.board,
                    title=title,
                    item_type=itype,
                    story_points=story_points,
                    sprint_id=sprint_id,
                    client_id=self.board.client_id,
                    assignees=assignees,
                    dev_owner=dev_owner,
                    status=status_name or "backlog",
                    created_at=created_at,
                    started_at=created_at,  # ClickUp history not fetched here
                    done_at=done_at,
                    closed=bool(done_at),
                    meta={"list_id": (t.get("list") or {}).get("id")},
                )
            )
            count += 1
        return count
