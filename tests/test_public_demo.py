import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from django.test import Client
from django.utils import timezone

from desk import demo
from desk.models import ChangeRequest, DemoActor, DemoBudget, DemoWorkspace, Team
from tests.conftest import command

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def public_settings(settings):
    settings.PUBLIC_DEMO = True
    settings.ROOT_URLCONF = "desk.demo_urls"


def begin(client, locale="en"):
    assert client.post(f"/demo/{locale}/start/").status_code == 302
    workspace = demo.workspace_for(client.session)
    return workspace, ChangeRequest.objects.get(team=workspace.team)


def post(client, record, action, version, **extra):
    return client.post(
        "/demo/en/command/", command(action, rid=record.pk, version=version, **extra)
    )


@pytest.mark.parametrize("locale", ["en", "pl"])
def test_full_journey_export_and_replay(client, locale):
    response = client.get(f"/demo/{locale}/")
    assert response.status_code == 200
    assert f'<html lang="{locale}">'.encode() in response.content
    workspace, record = begin(client, locale)
    assert all(
        not actor.user.has_usable_password()
        for actor in DemoActor.objects.filter(workspace=workspace)
    )
    assert post(client, record, "submit", 1).status_code == 302
    assert client.post(f"/demo/{locale}/role/", {"role": "reviewer"}).status_code == 302
    payload = command("approve", rid=record.pk, version=2)
    assert client.post(f"/demo/{locale}/command/", payload).status_code == 302
    assert client.post(f"/demo/{locale}/command/", payload).status_code == 302
    assert client.session["demo_receipt"]["replayed"] is True
    result = client.get(f"/demo/{locale}/evidence.json")
    assert result.status_code == 200
    assert result.json()["state"] == "APPROVED"
    assert len(result.json()["events"]) == 3
    assert "attachment" in result["Content-Disposition"]
    assert "no-store" in result["Cache-Control"]


def test_two_visitors_cannot_read_or_modify_each_other(client):
    w1, r1 = begin(client)
    other = Client()
    w2, r2 = begin(other)
    assert w1.pk != w2.pk
    assert post(other, r1, "submit", 1).status_code == 404
    assert other.get("/demo/en/evidence.json").json()["request_id"] == str(r2.pk)
    # Classic unbounded endpoints must not be reachable in public mode.
    assert other.get(f"/requests/{r1.pk}/").status_code == 404
    assert other.post(f"/teams/{w1.team_id}/commands/", {}).status_code == 404
    assert other.get("/login/").status_code == 404


def test_roles_and_stale_decision_enforced_by_actual_service(client):
    _, record = begin(client)
    assert post(client, record, "submit", 1).status_code == 302
    assert post(client, record, "approve", 2).status_code == 403
    client.post("/demo/en/role/", {"role": "reviewer"})
    assert post(client, record, "approve", 2).status_code == 302
    client.post("/demo/en/role/", {"role": "second_reviewer"})
    response = post(client, record, "reject", 2)
    assert response.status_code == 409
    assert b"STALE_VERSION" in response.content
    assert record.events.count() == 3
    client.post("/demo/en/role/", {"role": "auditor"})
    assert post(client, record, "reject", 3).status_code == 403
    assert client.get("/demo/en/evidence.json").status_code == 200


def test_reject_revise_edit_resubmit(client):
    _, record = begin(client)
    post(client, record, "submit", 1)
    client.post("/demo/en/role/", {"role": "reviewer"})
    assert post(client, record, "reject", 2).status_code == 302
    client.post("/demo/en/role/", {"role": "requester"})
    assert post(client, record, "revise", 3).status_code == 302
    assert post(client, record, "edit", 4).status_code == 302
    assert post(client, record, "submit", 5).status_code == 302
    record.refresh_from_db()
    assert record.state == "SUBMITTED" and record.version == 6


def test_bad_input_is_escaped_and_retained(client):
    _, record = begin(client)
    response = post(
        client, record, "edit", 1, title="bad", proposal="<script>alert(1)</script>"
    )
    assert response.status_code == 400
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.content
    assert b"<script>alert(1)</script>" not in response.content
    assert b"bad" in response.content
    assert record.events.count() == 1


def test_unknown_database_outcome_retains_same_command(client):
    _, record = begin(client)
    payload = command("submit", rid=record.pk, version=1)
    with patch("desk.demo_views.demo.act", side_effect=DatabaseError("secret sql")):
        response = client.post("/demo/en/command/", payload)
    assert response.status_code == 503
    assert b"secret sql" not in response.content
    assert payload["command_id"].encode() in response.content
    assert b"Retry the same command" in response.content


@pytest.mark.parametrize("path", ["start", "role", "command"])
def test_public_posts_require_csrf(path):
    client = Client(enforce_csrf_checks=True)
    assert client.post(f"/demo/en/{path}/", {}).status_code == 403


def test_expiry_blocks_all_reads_and_writes(client):
    workspace, record = begin(client)
    DemoWorkspace.objects.filter(pk=workspace.pk).update(
        expires_at=timezone.now() - timedelta(seconds=2)
    )
    assert client.get("/demo/en/evidence.json").status_code == 410
    assert post(client, record, "submit", 1).status_code == 410
    assert client.post("/demo/en/role/", {"role": "reviewer"}).status_code == 410
    assert b"Start my private demo" in client.get("/demo/en/").content


def test_reset_expires_only_owned_workspace(client):
    first, _ = begin(client)
    other, _ = begin(Client())
    fresh, _ = begin(client)
    assert first.pk != fresh.pk
    first.refresh_from_db()
    other.refresh_from_db()
    assert first.expires_at <= timezone.now() < other.expires_at


def test_cleanup_preserves_normal_audit_and_active_workspace(client, world, draft):
    expired, _ = begin(client)
    active, _ = begin(Client())
    users = list(
        DemoActor.objects.filter(workspace=expired).values_list("user_id", flat=True)
    )
    DemoWorkspace.objects.filter(pk=expired.pk).update(
        expires_at=timezone.now() - timedelta(seconds=2)
    )
    assert demo.cleanup() == 1
    assert not Team.objects.filter(pk=expired.team_id).exists()
    assert not get_user_model().objects.filter(pk__in=users).exists()
    assert DemoWorkspace.objects.filter(pk=active.pk).exists()
    assert draft.events.count() == 1
    with pytest.raises(DatabaseError), transaction.atomic():
        draft.events.all().delete()


def test_live_demo_audit_cannot_be_deleted_or_updated(client):
    workspace, record = begin(client)
    with pytest.raises(DatabaseError), transaction.atomic():
        record.events.all().delete()
    DemoWorkspace.objects.filter(pk=workspace.pk).update(
        expires_at=timezone.now() - timedelta(seconds=2)
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        record.events.update(reason="Even expired history cannot be rewritten")


@pytest.mark.parametrize(
    "limit", ["DEMO_STARTS_HOUR", "DEMO_STARTS_DAY", "DEMO_ACTIVE_LIMIT"]
)
def test_global_start_quota_survives_new_browser(settings, limit):
    setattr(settings, limit, 1)
    begin(Client())
    assert Client().post("/demo/en/start/").status_code == 429
    assert DemoWorkspace.objects.count() == 1


def test_rejected_attempts_consume_bounded_quota(client, settings):
    settings.DEMO_ACTION_LIMIT = 2
    _, record = begin(client)
    for _ in range(2):
        assert post(client, record, "submit", 1, reason="bad").status_code == 400
    assert post(client, record, "submit", 1).status_code == 429
    assert record.events.count() == 1


def test_invalid_role_create_and_duplicate_fields_rejected(client):
    workspace, record = begin(client)
    assert client.post("/demo/en/role/", {"role": "admin"}).status_code == 400
    assert post(client, record, "create", 0).status_code == 400
    data = command("submit", rid=record.pk, version=1)
    data["action"] = ["submit", "approve"]
    assert client.post("/demo/en/command/", data).status_code == 400
    assert ChangeRequest.objects.filter(team=workspace.team).count() == 1


def test_disabled_demo_and_unknown_locale(client, settings):
    assert client.get("/demo/fr/").status_code == 404
    settings.PUBLIC_DEMO = False
    assert client.post("/demo/en/start/").status_code == 404


def test_forged_workspace_and_bad_role_fail_closed(client):
    _, record = begin(client)
    session = client.session
    session["demo_role"] = "admin"
    session.save()
    assert post(client, record, "submit", 1).status_code == 404
    session["demo_workspace"] = str(uuid.uuid4())
    session.save()
    assert client.get("/demo/en/evidence.json").status_code == 410


def test_start_failure_rolls_back_budget_and_partial_users(client):
    with patch("desk.demo.execute", side_effect=DatabaseError("private")):
        response = client.post("/demo/en/start/")
    assert response.status_code == 503
    assert not DemoWorkspace.objects.exists()
    assert not DemoActor.objects.exists()
    assert not DemoBudget.objects.filter(daily_starts__gt=0).exists()
    assert not get_user_model().objects.filter(username__startswith="demo-").exists()


def test_owned_reset_reuses_last_active_slot(client, settings):
    settings.DEMO_ACTIVE_LIMIT = 1
    previous, _ = begin(client)
    fresh, _ = begin(client)
    assert fresh.pk != previous.pk
    assert DemoWorkspace.objects.filter(expires_at__gt=timezone.now()).count() == 1
    assert Client().post("/demo/en/start/").status_code == 429


def test_second_reviewer_identity_is_preserved_in_evidence(client):
    _, record = begin(client)
    post(client, record, "submit", 1)
    client.post("/demo/en/role/", {"role": "second_reviewer"})
    post(client, record, "approve", 2)
    rows = client.get("/demo/en/evidence.json").json()["events"]
    assert rows[-1]["actor_name"].endswith("-second_reviewer")
    assert rows[-1]["actor_role"] == "reviewer"
    assert b"Second reviewer" in client.get("/demo/en/").content
