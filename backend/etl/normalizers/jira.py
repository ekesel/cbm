from __future__ import annotations
from typing import Iterable, Dict, Any, List

from django.db import transaction
from django.utils import timezone

from metrics.models import WorkItem, Board, ItemType, Source, RawPayload
from .base import to_dt, earliest, map_item_type, contains_blocked, upsert_parent, cfg

class JiraNormalizer:
    def __init__(self, board: Board):
        self.board = board
        self.points_field = cfg(["jira","points_field"], "customfield_10016")
        self.status_map = cfg(["jira","status_map"], {}) or {}

    def _status_time(self, issue: Dict[str,Any], targets: List[str]):
        """
        Find first time status moved into any of the target names using changelog.
        """
        targets_lower = {t.lower() for t in targets or []}
        histories = ((issue or {}).get("changelog") or {}).get("histories", []) or []
        hits = []
        for h in histories:
            when = to_dt(h.get("created"))
            for item in h.get("items", []) or []:
                if item.get("field") == "status":
                    to_name = (item.get("toString") or "").lower()
                    if to_name in targets_lower and when:
                        hits.append(when)
        return earliest(hits)

    def normalize(self, raw_items: Iterable[RawPayload]) -> int:
        count = 0
        # Only issues for this board/source
        for rp in raw_items:
            if rp.source != Source.JIRA or rp.object_type != "issue":
                continue
            issue = rp.payload or {}
            fields = issue.get("fields") or {}

            key = issue.get("key") or issue.get("id")
            if not key: 
                continue

            title = fields.get("summary") or "Untitled"
            itype = map_item_type(((fields.get("issuetype") or {}).get("name")))
            assignee = (fields.get("assignee") or {})
            assignees = [a for a in [assignee.get("displayName") or assignee.get("emailAddress") or assignee.get("accountId")] if a]
            dev_owner = assignees[0] if assignees else None

            # Story points
            sp = fields.get(self.points_field)
            try:
                story_points = float(sp) if sp is not None else None
            except Exception:
                story_points = None

            # Sprint id (best-effort)
            sprint_id = None
            sprint_obj = fields.get("sprint")
            if isinstance(sprint_obj, dict):
                sprint_id = str(sprint_obj.get("id") or sprint_obj.get("name") or "")
            else:
                # sometimes it's a list of sprint objs
                sprints = fields.get("sprint") or fields.get("customfield_10020")
                if isinstance(sprints, list) and sprints:
                    s0 = sprints[-1]
                    sprint_id = str((s0.get("id") if isinstance(s0, dict) else s0) or "")

            status_name = ((fields.get("status") or {}).get("name")) or ""
            labels = fields.get("labels") or []

            created_at = to_dt(fields.get("created"))
            updated_at = to_dt(fields.get("updated"))
            resolutiondate = to_dt(fields.get("resolutiondate"))

            # status-based timestamps via changelog
            dev_started_at = self._status_time(issue, self.status_map.get("dev_started", []))
            dev_done_at = self._status_time(issue, self.status_map.get("dev_done", []))
            ready_for_qa_at = self._status_time(issue, self.status_map.get("ready_for_qa", []))
            qa_started_at = self._status_time(issue, self.status_map.get("qa_started", []))
            qa_verified_at = self._status_time(issue, self.status_map.get("qa_verified", []))
            signed_off_at = self._status_time(issue, self.status_map.get("signed_off", []))
            ready_for_uat_at = self._status_time(issue, self.status_map.get("ready_for_uat", []))
            deployed_uat_at = self._status_time(issue, self.status_map.get("deployed_uat", []))
            done_at = resolutiondate or self._status_time(issue, self.status_map.get("done", []))

            blocked_flag = contains_blocked(status_name, labels)

            parent_key = ((fields.get("parent") or {}).get("key"))
            parent_story = upsert_parent(self.board, Source.JIRA, parent_key)

            defaults = dict(
                board=self.board,
                title=title,
                description=(fields.get("description") or ""),
                item_type=itype,
                story_points=story_points,
                sprint_id=sprint_id,
                client_id=self.board.client_id,
                assignees=assignees,
                dev_owner=dev_owner,
                status=status_name or "backlog",
                created_at=created_at,
                started_at=dev_started_at or created_at,
                dev_started_at=dev_started_at,
                dev_done_at=dev_done_at,
                deployed_dev_at=None,
                ready_for_qa_at=ready_for_qa_at,
                qa_started_at=qa_started_at,
                qa_verified_at=qa_verified_at,
                signed_off_at=signed_off_at,
                ready_for_uat_at=ready_for_uat_at,
                deployed_uat_at=deployed_uat_at,
                done_at=done_at,
                blocked_flag=blocked_flag,
                parent_story=parent_story,
                meta={"project": (fields.get("project") or {}).get("key")},
                closed=bool(done_at),
            )
            
            with transaction.atomic():
                existing = WorkItem.objects.filter(source=Source.JIRA, source_id=str(key)).select_for_update().first()

                # Carry forward / set blocked_since
                if existing:
                    # if newly blocked
                    if blocked_flag and not existing.blocked_flag:
                        defaults["blocked_since"] = timezone.now()
                    # if still blocked, keep original
                    elif blocked_flag and existing.blocked_flag:
                        defaults["blocked_since"] = existing.blocked_since or timezone.now()
                    # if unblocked now
                    elif not blocked_flag:
                        defaults["blocked_since"] = None
                else:
                    defaults["blocked_since"] = timezone.now() if blocked_flag else None

            WorkItem.objects.update_or_create(
                source=Source.JIRA,
                source_id=str(key),
                defaults=defaults
            )
            count += 1
        return count
