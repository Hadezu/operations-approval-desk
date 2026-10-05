from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import (
    DatabaseError,
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)

from desk.models import ChangeRequest, Membership
from desk.services import Rejected, digest, execute, set_membership, validate, visible
from tests.conftest import command


def test_complete_decision_has_exact_snapshot(world, submitted):
    event, replay = execute(
        world["reviewer"],
        world["team"].pk,
        command("approve", rid=submitted.pk, version=2),
    )
    submitted.refresh_from_db()
    assert (submitted.state, submitted.version, replay) == ("APPROVED", 3, False)
    assert event.snapshot == {"title": submitted.title, "proposal": submitted.proposal}
    assert event.content_sha256 == digest(event.snapshot)
    assert list(submitted.events.values_list("action", flat=True)) == [
        "create",
        "submit",
        "approve",
    ]


@pytest.mark.parametrize("action", ["edit", "submit", "revise", "approve", "reject"])
def test_approved_record_is_closed(world, submitted, action):
    execute(
        world["reviewer"],
        world["team"].pk,
        command("approve", rid=submitted.pk, version=2),
    )
    actor = world["reviewer"] if action in {"approve", "reject"} else world["owner"]
    with pytest.raises(Rejected, match="INVALID_TRANSITION"):
        execute(actor, world["team"].pk, command(action, rid=submitted.pk, version=3))
    assert submitted.events.count() == 3


def test_rejection_revision_preserves_old_content(world, submitted):
    original = submitted.proposal
    execute(
        world["reviewer"],
        world["team"].pk,
        command("reject", rid=submitted.pk, version=2),
    )
    execute(
        world["owner"], world["team"].pk, command("revise", rid=submitted.pk, version=3)
    )
    execute(
        world["owner"],
        world["team"].pk,
        command(
            "edit",
            rid=submitted.pk,
            version=4,
            proposal="A revised and more bounded operational change.",
        ),
    )
    execute(
        world["owner"], world["team"].pk, command("submit", rid=submitted.pk, version=5)
    )
    execute(
        world["reviewer"],
        world["team"].pk,
        command("approve", rid=submitted.pk, version=6),
    )
    assert submitted.events.get(version=3).snapshot["proposal"] == original
    assert submitted.events.get(version=7).snapshot["proposal"] != original


def test_self_review_forbidden_even_for_reviewer(world):
    created, _ = execute(world["reviewer"], world["team"].pk, command())
    execute(
        world["reviewer"],
        world["team"].pk,
        command("submit", rid=created.request_id, version=1),
    )
    for action in ["approve", "reject"]:
        with pytest.raises(Rejected, match="SELF_REVIEW_FORBIDDEN"):
            execute(
                world["reviewer"],
                world["team"].pk,
                command(action, rid=created.request_id, version=2),
            )


@pytest.mark.parametrize(
    "who,code",
    [
        ("auditor", "READ_ONLY_ROLE"),
        ("outsider", "NOT_FOUND"),
        ("peer", "NOT_FOUND"),
        ("owner", "REVIEWER_REQUIRED"),
    ],
)
def test_direct_transition_requires_scoped_role(world, submitted, who, code):
    with pytest.raises(Rejected, match=code):
        execute(
            world[who],
            world["team"].pk,
            command("approve", rid=submitted.pk, version=2),
        )
    assert submitted.events.count() == 2


def test_reviewer_cannot_edit_another_owners_draft(world, draft):
    with pytest.raises(Rejected, match="OWNER_REQUIRED"):
        execute(
            world["reviewer"],
            world["team"].pk,
            command("edit", rid=draft.pk, version=1),
        )


def test_submitted_cannot_be_edited(world, submitted):
    with pytest.raises(Rejected, match="INVALID_TRANSITION"):
        execute(
            world["owner"],
            world["team"].pk,
            command("edit", rid=submitted.pk, version=2),
        )


def test_stale_form_cannot_approve_revised_content(world, submitted):
    stale = command("approve", rid=submitted.pk, version=2)
    execute(
        world["reviewer"],
        world["team"].pk,
        command("reject", rid=submitted.pk, version=2),
    )
    execute(
        world["owner"], world["team"].pk, command("revise", rid=submitted.pk, version=3)
    )
    execute(
        world["owner"], world["team"].pk, command("submit", rid=submitted.pk, version=4)
    )
    with pytest.raises(Rejected, match="STALE_VERSION"):
        execute(world["other"], world["team"].pk, stale)


def test_replayed_command_returns_original_receipt(world, submitted):
    cmd = command("approve", rid=submitted.pk, version=2)
    first, replay = execute(world["reviewer"], world["team"].pk, cmd)
    second, replay = execute(world["reviewer"], world["team"].pk, cmd)
    assert replay and first.pk == second.pk and submitted.events.count() == 3
    cmd["reason"] = "A different payload with the same command key."
    with pytest.raises(Rejected, match="COMMAND_KEY_CONFLICT"):
        execute(world["reviewer"], world["team"].pk, cmd)


def test_create_replay_and_request_id_conflict(world):
    cmd = command()
    first, _ = execute(world["owner"], world["team"].pk, cmd)
    second, replay = execute(world["owner"], world["team"].pk, cmd)
    assert replay and first.pk == second.pk and ChangeRequest.objects.count() == 1
    with pytest.raises(Rejected, match="REQUEST_ID_UNAVAILABLE"):
        execute(world["owner"], world["team"].pk, command(rid=cmd["request_id"]))


def test_revoked_membership_and_inactive_account_block_replay(world, submitted):
    cmd = command("approve", rid=submitted.pk, version=2)
    execute(world["reviewer"], world["team"].pk, cmd)
    set_membership(user=world["reviewer"], team=world["team"], role=None)
    with pytest.raises(Rejected, match="NOT_FOUND"):
        execute(world["reviewer"], world["team"].pk, cmd)
    world["other"].is_active = False
    world["other"].save()
    with pytest.raises(Rejected, match="AUTHENTICATION_REQUIRED"):
        execute(world["other"], world["team"].pk, cmd)


def test_team_and_owner_read_scope(world, draft):
    assert visible(world["outsider"]).count() == 0
    assert visible(world["peer"]).count() == 0
    assert visible(world["owner"]).count() == 1
    assert visible(world["auditor"]).count() == 1


def test_event_write_failure_rolls_back_state(world, submitted):
    with patch(
        "desk.services.Event.objects.create",
        side_effect=DatabaseError("injected failure"),
    ):
        with pytest.raises(DatabaseError):
            execute(
                world["reviewer"],
                world["team"].pk,
                command("approve", rid=submitted.pk, version=2),
            )
    submitted.refresh_from_db()
    assert (submitted.state, submitted.version, submitted.events.count()) == (
        "SUBMITTED",
        2,
        2,
    )


@pytest.mark.parametrize("mutation", ["update", "delete"])
def test_postgres_rejects_audit_mutation_even_raw_sql(world, draft, mutation):
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE desk_event SET reason='changed'"
                if mutation == "update"
                else "DELETE FROM desk_event"
            )
    assert draft.events.count() == 1


def test_database_constraints(world, draft):
    with pytest.raises(IntegrityError), transaction.atomic():
        ChangeRequest.objects.filter(pk=draft.pk).update(state="UNKNOWN")
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.filter(user=world["owner"]).update(role="admin")


@pytest.mark.parametrize(
    "extra",
    [
        {"version": True},
        {"version": -1},
        {"version": "1.5"},
        {"version": 2**31},
        {"request_id": "not-a-uuid"},
        {"command_id": None},
        {"action": "delete"},
        {"reason": "short"},
        {"reason": "x" * 501},
        {"title": "x" * 121},
        {"proposal": "x" * 4001},
        {"role": "reviewer"},
        {"team_id": 1},
    ],
)
def test_malformed_command_rejected(extra):
    with pytest.raises(Rejected):
        validate(command(**extra))


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same", [True, False])
def test_real_concurrent_decisions(world, submitted, same):
    barrier = Barrier(2)
    one = command("approve", rid=submitted.pk, version=2)
    two = one if same else command("reject", rid=submitted.pk, version=2)

    def decide(user, data):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            event, replay = execute(user, world["team"].pk, data)
            return ("ok", event.pk, replay)
        except Rejected as error:
            return (error.code, None, False)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(decide, world["reviewer"], one),
            pool.submit(decide, world["reviewer"] if same else world["other"], two),
        ]
        results = [job.result(timeout=20) for job in jobs]
    assert submitted.events.count() == 3
    if same:
        assert all(row[0] == "ok" for row in results)
        assert results[0][1] == results[1][1]
        assert sorted(row[2] for row in results) == [False, True]
    else:
        assert sorted(row[0] for row in results) == ["STALE_VERSION", "ok"]
