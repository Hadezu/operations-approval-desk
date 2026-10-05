"""All workflow writes pass through one bounded, team-serialized transaction."""

import hashlib
import json
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import ChangeRequest, Event, Membership, Team


class Rejected(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def membership(actor, team_id):
    if (
        not actor.is_authenticated
        or not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists()
    ):
        raise Rejected("AUTHENTICATION_REQUIRED", 401)
    member = Membership.objects.filter(user=actor, team_id=team_id).first()
    if not member:
        raise Rejected("NOT_FOUND", 404)
    return member


def visible(actor):
    if not actor.is_authenticated:
        return ChangeRequest.objects.none()
    memberships = Membership.objects.filter(user=actor)
    from django.db.models import Q

    return ChangeRequest.objects.filter(
        Q(team_id__in=memberships.exclude(role="requester").values("team_id"))
        | Q(team_id__in=memberships.values("team_id"), owner=actor)
    )


def validate(data):
    if not isinstance(data, dict):
        raise Rejected("INVALID_COMMAND", 400)
    action = data.get("action")
    if not isinstance(action, str):
        raise Rejected("INVALID_COMMAND", 400)
    allowed = {"action", "command_id", "request_id", "version", "reason"}
    if action in {"create", "edit"}:
        allowed |= {"title", "proposal"}
    if set(data) - allowed or action not in {
        "create",
        "edit",
        "submit",
        "approve",
        "reject",
        "revise",
    }:
        raise Rejected("INVALID_COMMAND", 400)
    try:
        command_id, request_id = (
            uuid.UUID(str(data["command_id"])),
            uuid.UUID(str(data["request_id"])),
        )
        version = int(str(data["version"]))
        if str(version) != str(data["version"]) or not 0 <= version < 2**31 - 1:
            raise ValueError
    except (KeyError, ValueError, TypeError, AttributeError):
        raise Rejected("INVALID_COMMAND", 400) from None
    reason = data.get("reason", "")
    if (
        not isinstance(reason, str)
        or "\x00" in reason
        or not 10 <= len(reason.strip()) <= 500
    ):
        raise Rejected("REASON_REQUIRED_10_TO_500", 400)
    result = dict(
        action=action,
        command_id=str(command_id),
        request_id=str(request_id),
        version=version,
        reason=reason.strip(),
    )
    if action in {"create", "edit"}:
        for key, maximum in [("title", 120), ("proposal", 4000)]:
            value = data.get(key)
            if (
                not isinstance(value, str)
                or "\x00" in value
                or not 5 <= len(value.strip()) <= maximum
            ):
                raise Rejected("INVALID_" + key.upper(), 400)
            result[key] = value.strip()
    return result


@transaction.atomic
def execute(actor, team_id, data):
    cmd = validate(data)
    # Reject cross-team probes before acquiring that team's shared workflow lock.
    membership(actor, team_id)
    Team.objects.select_for_update().get(pk=team_id)
    member = membership(actor, team_id)  # Re-evaluate after waiting for the lock.
    if member.role == "auditor":
        raise Rejected("READ_ONLY_ROLE", 403)
    fingerprint = digest(cmd)
    prior = Event.objects.filter(
        team_id=team_id, actor=actor, command_id=cmd["command_id"]
    ).first()
    if prior:
        if prior.fingerprint != fingerprint:
            raise Rejected("COMMAND_KEY_CONFLICT")
        if not visible(actor).filter(pk=prior.request_id).exists():
            raise Rejected("NOT_FOUND", 404)
        return prior, True
    action = cmd["action"]
    if action == "create":
        if cmd["version"] != 0:
            raise Rejected("STALE_VERSION")
        if ChangeRequest.objects.filter(pk=cmd["request_id"]).exists():
            raise Rejected("REQUEST_ID_UNAVAILABLE")
        record = ChangeRequest(
            id=cmd["request_id"],
            team_id=team_id,
            owner=actor,
            title=cmd["title"],
            proposal=cmd["proposal"],
        )
        before = "NONE"
    else:
        record = visible(actor).filter(pk=cmd["request_id"], team_id=team_id).first()
        if not record:
            raise Rejected("NOT_FOUND", 404)
        if cmd["version"] != record.version:
            raise Rejected("STALE_VERSION")
        before = record.state
        if action in {"edit", "submit", "revise"} and record.owner_id != actor.pk:
            raise Rejected("OWNER_REQUIRED", 403)
        if action in {"approve", "reject"}:
            if member.role != "reviewer":
                raise Rejected("REVIEWER_REQUIRED", 403)
            if record.owner_id == actor.pk:
                raise Rejected("SELF_REVIEW_FORBIDDEN", 403)
        expected = {
            "edit": "DRAFT",
            "submit": "DRAFT",
            "approve": "SUBMITTED",
            "reject": "SUBMITTED",
            "revise": "REJECTED",
        }[action]
        if record.state != expected:
            raise Rejected("INVALID_TRANSITION")
        if action == "edit":
            record.title, record.proposal = cmd["title"], cmd["proposal"]
        record.state = {
            "submit": "SUBMITTED",
            "approve": "APPROVED",
            "reject": "REJECTED",
            "revise": "DRAFT",
        }.get(action, record.state)
        record.version += 1
    record.save()
    snapshot = {"title": record.title, "proposal": record.proposal}
    event = Event.objects.create(
        request=record,
        team_id=team_id,
        actor=actor,
        actor_name=actor.username,
        actor_role=member.role,
        command_id=cmd["command_id"],
        fingerprint=fingerprint,
        action=action,
        version=record.version,
        before_state=before,
        after_state=record.state,
        reason=cmd["reason"],
        snapshot=snapshot,
        content_sha256=digest(snapshot),
    )
    return event, False


@transaction.atomic
def set_membership(*, user, team, role):
    """Administrative integration point; not exposed as a public endpoint."""
    Team.objects.select_for_update().get(pk=team.pk)
    if role is None:
        Membership.objects.filter(user=user, team=team).delete()
    elif role in Membership.Role.values:
        Membership.objects.update_or_create(
            user=user, team=team, defaults={"role": role}
        )
    else:
        raise ValueError("Unknown role")
