from django.db import models
from django.contrib.auth.models import AbstractUser

class Roles(models.TextChoices):
    VIEWER = "VIEWER", "Viewer"                # read-only dashboards
    TEAM_LEAD = "TEAM_LEAD", "Team Lead"       # team-level visibility
    PROCESS = "PROCESS", "Process Team"        # global metrics, compliance
    CTO = "CTO", "CTO"
    CEO = "CEO", "CEO"
    ADMIN = "ADMIN", "Admin"                   # full access

class User(AbstractUser):
    # username / email fields come from AbstractUser
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.VIEWER,
    )
    # optional: client scoping for client-facing logins
    client_id = models.CharField(max_length=128, null=True, blank=True)

    @property
    def is_admin(self) -> bool:
        return self.role == Roles.ADMIN or self.is_superuser

    @property
    def is_leadership(self) -> bool:
        return self.role in {Roles.CTO, Roles.CEO, Roles.ADMIN}