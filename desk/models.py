import uuid

from django.conf import settings
from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        REQUESTER = "requester"
        REVIEWER = "reviewer"
        AUDITOR = "auditor"

    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(max_length=12, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="one_team_role"),
            models.CheckConstraint(
                condition=models.Q(role__in=["requester", "reviewer", "auditor"]),
                name="known_role",
            ),
        ]


class ChangeRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=120)
    proposal = models.TextField(max_length=4000)
    state = models.CharField(max_length=12, default="DRAFT")
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    state__in=["DRAFT", "SUBMITTED", "APPROVED", "REJECTED"]
                ),
                name="known_state",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="positive_version"
            ),
        ]
        indexes = [models.Index(fields=["team", "state", "updated_at"])]


class Event(models.Model):
    request = models.ForeignKey(
        ChangeRequest, on_delete=models.PROTECT, related_name="events"
    )
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_name = models.CharField(max_length=150)
    actor_role = models.CharField(max_length=12)
    command_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    action = models.CharField(max_length=12)
    version = models.PositiveIntegerField()
    before_state = models.CharField(max_length=12)
    after_state = models.CharField(max_length=12)
    reason = models.CharField(max_length=500)
    snapshot = models.JSONField()
    content_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "version"], name="one_event_per_version"
            ),
            models.UniqueConstraint(
                fields=["team", "actor", "command_id"],
                name="one_command_per_actor_team",
            ),
        ]


class DemoWorkspace(models.Model):
    """Disposable synthetic tenant; its capability stays in the server session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(Team, on_delete=models.PROTECT)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class DemoActor(models.Model):
    workspace = models.ForeignKey(DemoWorkspace, on_delete=models.CASCADE)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    label = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "label"], name="demo_actor_label"
            )
        ]


class DemoBudget(models.Model):
    """One persistent lock/counter row. Session clearing cannot reset this budget."""

    hour = models.CharField(max_length=13, default="")
    day = models.CharField(max_length=10, default="")
    hourly_starts = models.PositiveIntegerField(default=0)
    daily_starts = models.PositiveIntegerField(default=0)
