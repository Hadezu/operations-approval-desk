import uuid

import pytest
from django.contrib.auth import get_user_model

from desk.models import Team
from desk.services import execute, set_membership


@pytest.fixture(autouse=True)
def fast_test_passwords(settings):
    # Only the isolated test process; the actual demo/browser uses Django PBKDF2.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def world(db):
    north, south = Team.objects.create(name="North"), Team.objects.create(name="South")
    people = {}
    for name, team, role in [
        ("owner", north, "requester"),
        ("reviewer", north, "reviewer"),
        ("other", north, "reviewer"),
        ("auditor", north, "auditor"),
        ("outsider", south, "reviewer"),
        ("peer", north, "requester"),
    ]:
        user = get_user_model().objects.create_user(
            name, password="test-only-password-2026"
        )
        set_membership(user=user, team=team, role=role)
        people[name] = user
    return {"team": north, "foreign": south, **people}


def command(action="create", *, rid=None, version=0, **extra):
    result = {
        "action": action,
        "request_id": str(rid or uuid.uuid4()),
        "command_id": str(uuid.uuid4()),
        "version": version,
        "reason": "A specific synthetic reason for this action.",
    }
    if action in {"create", "edit"}:
        result.update(
            title="Update a routing rule",
            proposal="Route uncertain imports into a manual review queue.",
        )
    result.update(extra)
    return result


@pytest.fixture
def draft(world):
    event, _ = execute(world["owner"], world["team"].pk, command())
    return event.request


@pytest.fixture
def submitted(world, draft):
    execute(
        world["owner"], world["team"].pk, command("submit", rid=draft.pk, version=1)
    )
    draft.refresh_from_db()
    return draft
