from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections

from desk import demo
from desk.models import ChangeRequest, DemoWorkspace
from desk.services import Rejected
from tests.conftest import command


@pytest.mark.django_db(transaction=True)
def test_global_budget_serializes_simultaneous_starts(settings):
    settings.DEMO_STARTS_HOUR = 1

    def start():
        close_old_connections()
        try:
            demo.start({}, "en")
            return "created"
        except Rejected as error:
            return error.code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))
    assert sorted(results) == ["DEMO_QUOTA", "created"]
    assert DemoWorkspace.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_simultaneous_duplicate_demo_action_records_once():
    workspace = demo.start({}, "en")
    record = ChangeRequest.objects.get(team=workspace.team)
    session = {"demo_workspace": str(workspace.pk), "demo_role": "requester"}
    payload = command("submit", rid=record.pk, version=1)

    def send():
        close_old_connections()
        try:
            event, replay = demo.act(session, payload)
            return event.pk, replay
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert results[0][0] == results[1][0]
    assert sorted(result[1] for result in results) == [False, True]
    assert record.events.count() == 2
