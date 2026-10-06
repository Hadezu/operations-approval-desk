"""Public synthetic tenants. Business writes still use the original command service."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from .demo_copy import COPY
from .models import (
    ChangeRequest,
    DemoActor,
    DemoBudget,
    DemoWorkspace,
    Event,
    Membership,
    Team,
)
from .services import Rejected, execute

LABELS = ("requester", "reviewer", "second_reviewer", "auditor")


def workspace_for(session, *, lock=False):
    try:
        key = uuid.UUID(str(session.get("demo_workspace", "")))
    except ValueError:
        raise Rejected("DEMO_EXPIRED", 410) from None
    query = DemoWorkspace.objects.select_for_update() if lock else DemoWorkspace.objects
    workspace = query.filter(pk=key, expires_at__gt=timezone.now()).first()
    if not workspace:
        raise Rejected("DEMO_EXPIRED", 410)
    return workspace


def actor_for(workspace, session):
    label = session.get("demo_role", "requester")
    actor = (
        DemoActor.objects.select_related("user")
        .filter(workspace=workspace, label=label)
        .first()
    )
    if not actor:
        raise Rejected("NOT_FOUND", 404)
    return actor.user


@transaction.atomic
def start(session, locale):
    # The unique PK serializes initialization; then every start takes this lock.
    DemoBudget.objects.get_or_create(pk=1)
    budget = DemoBudget.objects.select_for_update().get(pk=1)
    now = timezone.now()
    hour, day = now.strftime("%Y-%m-%dT%H"), now.strftime("%Y-%m-%d")
    hourly = budget.hourly_starts if budget.hour == hour else 0
    daily = budget.daily_starts if budget.day == day else 0
    if hourly >= settings.DEMO_STARTS_HOUR or daily >= settings.DEMO_STARTS_DAY:
        raise Rejected("DEMO_QUOTA", 429)
    # Reset replaces an owned active slot; it does not consume a second one.
    try:
        previous = workspace_for(session, lock=True)
    except Rejected:
        previous = None
    active = DemoWorkspace.objects.filter(expires_at__gt=now)
    if previous:
        active = active.exclude(pk=previous.pk)
    if active.count() >= settings.DEMO_ACTIVE_LIMIT:
        raise Rejected("DEMO_QUOTA", 429)
    budget.hour, budget.day = hour, day
    budget.hourly_starts, budget.daily_starts = hourly + 1, daily + 1
    budget.save()
    # Only the capability already owned by this session can be expired by reset.
    if previous:
        previous.expires_at = now
        previous.save(update_fields=["expires_at"])
    key = uuid.uuid4()
    team = Team.objects.create(name=f"Demo {key}")
    workspace = DemoWorkspace.objects.create(
        id=key, team=team, expires_at=now + timedelta(minutes=20)
    )
    for label in LABELS:
        user = get_user_model().objects.create_user(
            username=f"demo-{key}-{label}", password=None
        )
        DemoActor.objects.create(workspace=workspace, user=user, label=label)
        Membership.objects.create(
            team=team,
            user=user,
            role="reviewer" if label == "second_reviewer" else label,
        )
    owner = DemoActor.objects.get(workspace=workspace, label="requester").user
    c = COPY[locale]
    execute(
        owner,
        team.pk,
        {
            "action": "create",
            "request_id": str(uuid.uuid4()),
            "command_id": str(uuid.uuid4()),
            "version": 0,
            "title": c["default_title"],
            "proposal": c["default_proposal"],
            "reason": c["default_reason"],
        },
    )
    return workspace


def act(session, data):
    # Charge failed attempts as well; the business operation uses a separate
    # transaction so a rejected command cannot roll back its abuse counter.
    with transaction.atomic():
        workspace = workspace_for(session, lock=True)
        if workspace.attempts >= settings.DEMO_ACTION_LIMIT:
            raise Rejected("DEMO_QUOTA", 429)
        workspace.attempts += 1
        workspace.save(update_fields=["attempts"])
    with transaction.atomic():
        workspace = workspace_for(session, lock=True)
        if data.get("action") == "create":
            raise Rejected("INVALID_COMMAND", 400)
        return execute(actor_for(workspace, session), workspace.team_id, data)


@transaction.atomic
def cleanup():
    """Purge only expired synthetic tenants. Never disable the audit trigger."""
    removed = 0
    Session.objects.filter(expire_date__lt=timezone.now()).delete()
    for workspace in DemoWorkspace.objects.select_for_update(skip_locked=True).filter(
        expires_at__lte=timezone.now()
    )[:100]:
        team = workspace.team
        users = list(
            DemoActor.objects.filter(workspace=workspace).values_list(
                "user_id", flat=True
            )
        )
        Event.objects.filter(team=team).delete()
        ChangeRequest.objects.filter(team=team).delete()
        Membership.objects.filter(team=team).delete()
        workspace.delete()
        # These identities were created for this workspace only. PROTECT prevents
        # deleting an identity that unexpectedly acquired another audit record.
        get_user_model().objects.filter(pk__in=users).delete()
        team.delete()
        removed += 1
    return removed
