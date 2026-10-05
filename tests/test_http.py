import json
from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.test import Client

from desk.services import execute
from tests.conftest import command


def test_auth_required_for_queue_detail_export_and_commands(client, world, draft):
    for url in ["/", f"/requests/{draft.pk}/", f"/requests/{draft.pk}/evidence.json"]:
        assert client.get(url).status_code == 302
    assert client.post(f"/teams/{world['team'].pk}/commands/", {}).status_code == 302


@pytest.mark.parametrize("who", ["outsider", "peer"])
def test_no_cross_scope_detail_or_export(client, world, draft, who):
    client.force_login(world[who])
    assert draft.title.encode() not in client.get("/?state=ALL").content
    assert client.get(f"/requests/{draft.pk}/").status_code == 404
    assert client.get(f"/requests/{draft.pk}/evidence.json").status_code == 404


def test_session_csrf_is_enforced_on_json_and_form(world, submitted):
    client = Client(enforce_csrf_checks=True)
    client.force_login(world["reviewer"])
    url = f"/teams/{world['team'].pk}/commands/"
    data = command("approve", rid=submitted.pk, version=2)
    assert client.post(url, data).status_code == 403
    assert client.post(url, data, content_type="application/json").status_code == 403
    client.get(f"/requests/{submitted.pk}/")
    token = client.cookies["csrftoken"].value
    assert (
        client.post(
            url, data, content_type="application/json", HTTP_X_CSRFTOKEN=token
        ).status_code
        == 200
    )


def test_stale_http_response_and_readonly_auditor(client, world, submitted):
    client.force_login(world["reviewer"])
    url = f"/teams/{world['team'].pk}/commands/"
    data = command("approve", rid=submitted.pk, version=1)
    response = client.post(url, data, content_type="application/json")
    assert response.status_code == 409 and response.json()["error"] == "STALE_VERSION"
    client.force_login(world["auditor"])
    assert b"Approve request" not in client.get(f"/requests/{submitted.pk}/").content
    data["version"] = 2
    assert client.post(url, data, content_type="application/json").status_code == 403


def test_evidence_contains_every_version_and_safe_headers(client, world, submitted):
    client.force_login(world["auditor"])
    response = client.get(f"/requests/{submitted.pk}/evidence.json")
    assert response.status_code == 200
    assert response.json()["through_version"] == 2
    assert len(response.json()["events"]) == 2
    assert "attachment" in response["Content-Disposition"]
    assert "no-store" in response["Cache-Control"]
    assert response["X-Content-Type-Options"] == "nosniff"


def test_template_escapes_untrusted_proposal(client, world):
    event, _ = execute(
        world["owner"],
        world["team"].pk,
        command(
            title="<script>alert(1)</script>", proposal='<img src=x onerror="alert(1)">'
        ),
    )
    client.force_login(world["reviewer"])
    html = client.get(f"/requests/{event.request_id}/").content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html and "&lt;img" in html


def test_database_outage_is_not_success(client, world, submitted):
    client.force_login(world["reviewer"])
    with patch(
        "desk.views.execute", side_effect=OperationalError("SECRET INTERNAL DSN")
    ):
        response = client.post(
            f"/teams/{world['team'].pk}/commands/",
            command("approve", rid=submitted.pk, version=2),
            content_type="application/json",
        )
    assert response.status_code == 503 and b"SECRET" not in response.content
    assert submitted.events.count() == 2


@pytest.mark.parametrize(
    "body", ["{", "[]", '{"action":"create","action":"approve"}', '"hello"']
)
def test_bad_json_returns_400(client, world, body):
    client.force_login(world["owner"])
    assert (
        client.post(
            f"/teams/{world['team'].pk}/commands/",
            body,
            content_type="application/json",
        ).status_code
        == 400
    )


def test_post_only_and_unknown_fields(client, world, draft):
    client.force_login(world["owner"])
    url = f"/teams/{world['team'].pk}/commands/"
    assert client.get(url).status_code == 405
    cmd = command("submit", rid=draft.pk, version=1)
    cmd["owner_id"] = world["reviewer"].pk
    assert (
        client.post(url, json.dumps(cmd), content_type="application/json").status_code
        == 400
    )
