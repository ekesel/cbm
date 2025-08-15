from __future__ import annotations
import re
from typing import Iterable, Dict, Any, List

from django.db import transaction

from metrics.models import WorkItem, PR, Board, Source, RawPayload
from .base import to_dt, extract_issue_keys_from_text, cfg, add_linked_pr

class GitHubPRNormalizer:
    def __init__(self, board: Board):
        self.board = board
        self.link_patterns = cfg(["github","link_patterns"], {"jira": r"([A-Z]{2,}-\d+)"}) or {}

    def normalize(self, raw_items: Iterable[RawPayload]) -> int:
        count = 0
        for rp in raw_items:
            if rp.source != Source.GITHUB or rp.object_type != "pr":
                continue

            payload = rp.payload or {}
            repo = payload.get("repo") or {}
            pr = payload.get("pr") or {}
            reviews = payload.get("reviews") or []

            owner = repo.get("owner"); name = repo.get("name")
            number = pr.get("number")
            if not (owner and name and number):
                continue

            pr_id = f"{owner}/{name}#{number}"
            opened_at = to_dt(pr.get("created_at"))
            merged_at = to_dt(pr.get("merged_at"))

            # first review time & reviewers
            reviewers = []
            first_reviewed_at = None
            for r in reviews:
                rid = (r.get("user") or {}).get("login")
                if rid and rid not in reviewers:
                    reviewers.append(rid)
                if r.get("submitted_at") and first_reviewed_at is None:
                    first_reviewed_at = to_dt(r.get("submitted_at"))

            # Upsert PR row
            pr_row, _ = PR.objects.update_or_create(
                pr_id=pr_id,
                defaults=dict(
                    source=Source.GITHUB,
                    title=pr.get("title") or "",
                    branch=(pr.get("head") or {}).get("ref"),
                    opened_at=opened_at,
                    first_reviewed_at=first_reviewed_at,
                    merged_at=merged_at,
                    author_id=((pr.get("user") or {}).get("login")),
                    reviewer_ids=reviewers,
                    meta={"repo": f"{owner}/{name}"},
                )
            )

            # Try link to WorkItem(s)
            text = " ".join([
                pr.get("title") or "",
                (pr.get("body") or ""),
                (pr.get("head") or {}).get("ref") or "",
                (pr.get("base") or {}).get("ref") or "",
            ])
            found = extract_issue_keys_from_text(text, self.link_patterns)

            linked = 0
            # Jira keys
            for key in set(found.get("jira", [])):
                wi = WorkItem.objects.filter(source=Source.JIRA, source_id=key).first()
                if wi:
                    pr_row.work_item = wi
                    pr_row.save(update_fields=["work_item"])
                    add_linked_pr(wi, {
                        "pr_id": pr_id,
                        "opened_at": opened_at.isoformat() if opened_at else None,
                        "first_reviewed_at": first_reviewed_at.isoformat() if first_reviewed_at else None,
                        "merged_at": merged_at.isoformat() if merged_at else None,
                    }, reviewers)
                    linked += 1

            # (Optional) handle other sources if you add patterns:
            # for src_name in ("azure","clickup"):
            #   for sid in set(found.get(src_name, [])):
            #       wi = WorkItem.objects.filter(source=src_name, source_id=str(sid)).first()
            #       if wi: ... same as above

            count += 1 if (linked or pr_row) else 0
        return count
