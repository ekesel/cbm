from django.db import models
from django.contrib.postgres.fields import ArrayField


# ----- Helpers / choices ------------------------------------------------------

class Source(models.TextChoices):
    JIRA = "jira", "Jira"
    CLICKUP = "clickup", "ClickUp"
    AZURE = "azure", "Azure Boards"
    GITHUB = "github", "GitHub"


class ItemType(models.TextChoices):
    STORY = "story", "Story"
    BUG = "bug", "Bug"
    TASK = "task", "Task"
    SUBTASK = "subtask", "Sub-task"
    EPIC = "epic", "Epic"


# ----- Board & Raw payloads ---------------------------------------------------

class Board(models.Model):
    """
    A logical work board / list / project in a given source tool.
    """
    source = models.CharField(max_length=32, choices=Source.choices)
    board_id = models.CharField(max_length=128)                  # external id / key
    name = models.CharField(max_length=255)
    client_id = models.CharField(max_length=128, null=True, blank=True)  # internal-only tag
    meta = models.JSONField(default=dict, blank=True)            # freeform per-source metadata
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("source", "board_id")
        indexes = [
            models.Index(fields=["source", "board_id"]),
            models.Index(fields=["client_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.source}:{self.board_id}]"


class RawPayload(models.Model):
    """
    Stores raw JSON for audit/replay (also push to S3/MinIO at ETL time).
    """
    source = models.CharField(max_length=32, choices=Source.choices)
    board = models.ForeignKey(Board, null=True, blank=True, on_delete=models.SET_NULL)
    object_type = models.CharField(max_length=64)                # e.g., 'issue', 'sprint', 'pr'
    external_id = models.CharField(max_length=256)               # source id
    payload = models.JSONField()                                 # raw JSON blob
    object_storage_key = models.CharField(max_length=512, null=True, blank=True)
    payload_bytes = models.IntegerField(default=0)

    mapping_version = models.CharField(max_length=32, default="v1")
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["source", "object_type"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["fetched_at"]),
            models.Index(fields=["object_storage_key"]),  # NEW (helps find not-yet-offloaded rows)
        ]

# ----- Canonical Work Item ----------------------------------------------------

class WorkItem(models.Model):
    """
    Canonical normalized work item across Jira/ClickUp/Azure.
    """
    source = models.CharField(max_length=32, choices=Source.choices)
    source_id = models.CharField(max_length=256, unique=True)      # global unique per source
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="work_items")

    title = models.TextField()
    description = models.TextField(null=True, blank=True)
    item_type = models.CharField(max_length=16, choices=ItemType.choices)

    story_points = models.FloatField(null=True, blank=True)
    sprint_id = models.CharField(max_length=128, null=True, blank=True)
    release_id = models.CharField(max_length=128, null=True, blank=True)
    client_id = models.CharField(max_length=128, null=True, blank=True)  # redundantly stored for faster filters

    # Ownership
    assignees = ArrayField(models.CharField(max_length=128), default=list, blank=True)
    dev_owner = models.CharField(max_length=128, null=True, blank=True)
    qa_owner = models.CharField(max_length=128, null=True, blank=True)
    code_reviewer_ids = ArrayField(models.CharField(max_length=128), default=list, blank=True)

    # Status & timestamps (canonical flow)
    status = models.CharField(max_length=64, default="backlog")        # last mapped status
    created_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)

    dev_started_at = models.DateTimeField(null=True, blank=True)
    dev_done_at = models.DateTimeField(null=True, blank=True)
    deployed_dev_at = models.DateTimeField(null=True, blank=True)
    ready_for_qa_at = models.DateTimeField(null=True, blank=True)
    qa_started_at = models.DateTimeField(null=True, blank=True)
    qa_verified_at = models.DateTimeField(null=True, blank=True)
    signed_off_at = models.DateTimeField(null=True, blank=True)
    ready_for_uat_at = models.DateTimeField(null=True, blank=True)
    deployed_uat_at = models.DateTimeField(null=True, blank=True)

    done_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    closed = models.BooleanField(default=False)

    # Blockers
    blocked_flag = models.BooleanField(default=False)
    blocked_since = models.DateTimeField(null=True, blank=True)
    blocked_reason = models.TextField(null=True, blank=True)

    # Linkage
    parent_story = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    linked_prs = models.JSONField(default=list, blank=True)          # [{id, opened_at, first_reviewed_at, merged_at, reviewers:[..]}]
    meta = models.JSONField(default=dict, blank=True)                # per-source extra fields
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["board", "sprint_id"]),
            models.Index(fields=["client_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["dev_owner"]),
            models.Index(fields=["qa_owner"]),
            models.Index(fields=["done_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.source}:{self.source_id})"


# ----- Pull Requests ----------------------------------------------------------

class PR(models.Model):
    """
    GitHub (or other) Pull Request linked to a WorkItem.
    """
    pr_id = models.CharField(max_length=256, unique=True)
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.GITHUB)
    work_item = models.ForeignKey(WorkItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="prs")

    title = models.TextField(null=True, blank=True)
    branch = models.CharField(max_length=256, null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    first_reviewed_at = models.DateTimeField(null=True, blank=True)
    merged_at = models.DateTimeField(null=True, blank=True)
    author_id = models.CharField(max_length=128, null=True, blank=True)
    reviewer_ids = ArrayField(models.CharField(max_length=128), default=list, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["merged_at"]),
            models.Index(fields=["author_id"]),
        ]

    def __str__(self) -> str:
        return f"PR {self.pr_id}"


# ----- Defects ---------------------------------------------------------------

class Defect(models.Model):
    """
    Post-release (or pre-release) defects attributed to a WorkItem or release.
    """
    defect_id = models.CharField(max_length=256, unique=True)
    source = models.CharField(max_length=32, choices=Source.choices)
    work_item = models.ForeignKey(WorkItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="defects")

    title = models.TextField()
    severity = models.CharField(max_length=32, null=True, blank=True)
    detected_at = models.DateTimeField(null=True, blank=True)
    environment = models.CharField(max_length=32, null=True, blank=True)  # prod/staging/uat/dev
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["detected_at"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self) -> str:
        return self.defect_id


# ----- Metric snapshots ------------------------------------------------------

class MetricScope(models.TextChoices):
    TEAM = "team", "Team"
    BOARD = "board", "Board"
    CLIENT = "client", "Client"
    USER = "user", "User"
    ORG = "org", "Org"


class MetricSnapshot(models.Model):
    """
    Denormalized daily/sprint snapshots for fast dashboards.
    """
    scope = models.CharField(max_length=16, choices=MetricScope.choices)
    scope_id = models.CharField(max_length=128, null=True, blank=True)  # board_id, client_id, user_id, etc.
    sprint_id = models.CharField(max_length=128, null=True, blank=True)
    date = models.DateField()                                           # snapshot date

    metrics = models.JSONField(default=dict, blank=True)
    # examples:
    # {
    #   "velocity": 24,
    #   "throughput": 13,
    #   "defects_per_100_points": 11.2,
    #   "blocked_count": 4,
    #   "avg_dev_hours": 6.5,
    #   "avg_qa_hours": 8.1
    # }

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scope", "scope_id", "sprint_id", "date")
        indexes = [
            models.Index(fields=["scope", "scope_id"]),
            models.Index(fields=["date"]),
            models.Index(fields=["sprint_id"]),
        ]


# ----- Remediation tickets (validation failures) -----------------------------

class RemediationStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    DONE = "done", "Done"


class RemediationTicket(models.Model):
    """
    Generated by Validator when rules fail (e.g., missing story_points, missing done_at, etc.).
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="remediations")
    work_item = models.ForeignKey(WorkItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="remediations")

    rule_code = models.CharField(max_length=64)       # e.g., MISSING_POINTS, MISSING_DONE_AT
    message = models.TextField()
    status = models.CharField(max_length=16, choices=RemediationStatus.choices, default=RemediationStatus.OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.rule_code} on {self.work_item_id or 'board'}"


# --- Daily metric snapshots ---
class BoardDailySnapshot(models.Model):
    """
    One row per Board per UTC date capturing summary metrics.
    Date is stored as date (UTC). All rates are rolling-window unless noted.
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="daily_snapshots")
    date = models.DateField()  # snapshot date (UTC)
    metrics = models.JSONField(default=dict, blank=True)  # see snapshots.py for schema
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("board", "date")
        indexes = [
            models.Index(fields=["board", "date"]),
        ]

class UserDailySnapshot(models.Model):
    """
    One row per Board+User per UTC date. User is a free-form string (e.g., email/login/displayName).
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="user_daily_snapshots")
    date = models.DateField()
    user_id = models.CharField(max_length=255)  # assignee or reviewer id
    metrics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("board", "date", "user_id")
        indexes = [
            models.Index(fields=["board", "date"]),
            models.Index(fields=["board", "user_id"]),
        ]
        
class Team(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    is_active = models.BooleanField(default=True)
    boards = models.ManyToManyField(Board, through="TeamBoard", related_name="teams")
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return self.name

class TeamBoard(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    board = models.ForeignKey(Board, on_delete=models.CASCADE)
    weight = models.FloatField(default=1.0)  # reserved for weighted rollups later

    class Meta:
        unique_together = ("team", "board")
        indexes = [models.Index(fields=["team", "board"])]