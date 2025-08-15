from django.db import models
import uuid
from django.utils import timezone
from .crypto import encrypt_value, decrypt_value

from metrics.models import Board

class MappingVersion(models.Model):
    """
    Versioned mapping configuration used by normalizers to transform raw → canonical.
    Keep a row per 'version' label; the actual mapping config can live in code or in JSON here.
    """
    version = models.CharField(max_length=32, unique=True, default="v1")
    description = models.TextField(blank=True, default="")
    config = models.JSONField(default=dict, blank=True)  # optional: store mapping JSON per source/board
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.version} ({'active' if self.active else 'inactive'})"


class ETLStatus(models.TextChoices):
    STARTED = "started", "Started"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    PARTIAL = "partial", "Partial Success"


class ETLJobRun(models.Model):
    """
    One record per ETL execution (connector pull, normalize, validate, snapshot, etc.)
    """
    run_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    job_name = models.CharField(max_length=128)                           # e.g., jira_board_pull, clickup_normalize
    board = models.ForeignKey(Board, null=True, blank=True, on_delete=models.SET_NULL)

    mapping_version = models.ForeignKey(MappingVersion, null=True, blank=True, on_delete=models.SET_NULL)

    status = models.CharField(max_length=16, choices=ETLStatus.choices, default=ETLStatus.STARTED)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Counters & diagnostics
    records_pulled = models.IntegerField(default=0)
    records_normalized = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_summary = models.JSONField(default=dict, blank=True)  # { "message": "...", "traceback": "...", "examples": [...] }
    log_url = models.CharField(max_length=512, null=True, blank=True)     # link to external log if any (e.g., S3, CloudWatch)

    # Arbitrary metadata (rate limit info, paging tokens, durations ...)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["job_name", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["started_at"]),
        ]
        ordering = ["-started_at"]

    def mark_success(self):
        self.status = ETLStatus.SUCCESS
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])

    def mark_failed(self, message: str = "", traceback_text: str = ""):
        self.status = ETLStatus.FAILED
        self.finished_at = timezone.now()
        self.error_summary = {"message": message, "traceback": traceback_text}
        self.save(update_fields=["status", "finished_at", "error_summary"])

    def duration_seconds(self) -> float:
        if not self.finished_at:
            return (timezone.now() - self.started_at).total_seconds()
        return (self.finished_at - self.started_at).total_seconds()

    def __str__(self) -> str:
        return f"{self.job_name} [{self.status}] {self.run_id}"

AUTH_TYPES = (
    ("basic", "Basic (username/password)"),
    ("pat", "Personal Access Token"),
    ("oauth", "OAuth (token)"),
)

class BoardCredential(models.Model):
    """
    Secure per-board credential storage (encrypted tokens).
    """
    board = models.OneToOneField(Board, on_delete=models.CASCADE, related_name="credential")
    api_base_url = models.CharField(max_length=512, help_text="https://your-instance.example.com")
    auth_type = models.CharField(max_length=16, choices=AUTH_TYPES, default="pat")
    username = models.CharField(max_length=255, null=True, blank=True)
    token_encrypted = models.BinaryField(null=True, blank=True)
    extra = models.JSONField(default=dict, blank=True)  # space for OAuth client_id/secret, scopes, etc.

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # convenience
    def set_token(self, token: str):
        self.token_encrypted = encrypt_value(token)

    def get_token(self) -> str:
        return decrypt_value(self.token_encrypted or b"")

    def __str__(self):
        return f"Creds for {self.board}"

NOTIFY_CHANNEL_TYPES = (
    ("teams", "Microsoft Teams"),
)

class NotificationChannel(models.Model):
    """
    Per-board notification channel (Teams-only for now).
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="notify_channels")
    channel_type = models.CharField(max_length=16, choices=NOTIFY_CHANNEL_TYPES, default="teams")
    name = models.CharField(max_length=255, help_text="Human label for this channel")
    is_active = models.BooleanField(default=True)

    # Encrypted Teams webhook
    webhook_encrypted = models.BinaryField(null=True, blank=True)

    # Filters/config
    rules = models.JSONField(default=list, blank=True)   # e.g., ["MISSING_POINTS","STUCK_IN_DEV"] or []
    min_severity = models.CharField(max_length=16, default="info")  # reserved for future
    extra = models.JSONField(default=dict, blank=True)   # e.g., {"batch_limit": 20}

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # helpers
    def set_webhook(self, url: str):
        self.webhook_encrypted = encrypt_value(url)

    def get_webhook(self) -> str:
        return decrypt_value(self.webhook_encrypted or b"")

    def __str__(self):
        return f"{self.name} ({self.channel_type}) → {self.board}"