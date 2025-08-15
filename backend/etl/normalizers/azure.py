from __future__ import annotations
from typing import Iterable, Dict, Any, Optional

from metrics.models import WorkItem, Board, ItemType, Source, RawPayload
from .base import to_dt, map_item_type, cfg

class AzureNormalizer:
    def __init__(self, board: Board):
        self.board = board
        self.points_field = cfg(["azure","points_field"], "Microsoft.VSTS.Scheduling.StoryPoints")

    def normalize(self, raw_items: Iterable[RawPayload]) -> int:
        count = 0
        for rp in raw_items:
            if rp.source != Source.AZURE or rp.object_type != "work_item":
                continue
            wi = rp.payload or {}
            fields = wi.get("fields") or {}

            wid = wi.get("id")
            if not wid:
                continue

            title = fields.get("System.Title") or "Untitled"
            itype = map_item_type(fields.get("System.WorkItemType"))
            status_name = fields.get("System.State") or ""

            assignees = []
            assigned_to = fields.get("System.AssignedTo")
            if isinstance(assigned_to, dict):
                nm = assigned_to.get("displayName") or assigned_to.get("uniqueName")
                if nm: assignees.append(str(nm))
            elif isinstance(assigned_to, str):
                assignees.append(assigned_to)
            dev_owner = assignees[0] if assignees else None

            story_points = fields.get(self.points_field)
            try:
                story_points = float(story_points) if story_points is not None else None
            except Exception:
                story_points = None

            created_at = to_dt(fields.get("System.CreatedDate"))
            changed_at = to_dt(fields.get("System.ChangedDate"))
            closed_at = to_dt(fields.get("Microsoft.VSTS.Common.ClosedDate")) or to_dt(fields.get("System.ClosedDate"))

            sprint_id = fields.get("System.IterationPath")  # path string; keep as id-like

            WorkItem.objects.update_or_create(
                source=Source.AZURE,
                source_id=str(wid),
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
                    started_at=created_at,  # no changelog here
                    done_at=closed_at,
                    closed=bool(closed_at),
                    meta={"rev": wi.get("rev")},
                )
            )
            count += 1
        return count
