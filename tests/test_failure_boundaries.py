import json
import os
import subprocess
import sys

import pytest
from django.db import connection

from desk.models import ChangeRequest
from desk.services import Rejected, validate
from tests.conftest import command


@pytest.mark.parametrize(
    "extra",
    [
        {"action": []},
        {"action": {}},
        {"action": None},
        {"title": "some\x00text"},
        {"proposal": "some\x00text"},
        {"reason": "reason with a\x00null byte"},
    ],
)
def test_untrusted_types_and_nul_are_validation_errors(extra):
    payload = command()
    payload.update(extra)
    with pytest.raises(Rejected):
        validate(payload)


@pytest.mark.django_db(transaction=True)
def test_process_death_before_event_insert_rolls_back_entire_transition(
    world, submitted
):
    child = """
import os, json, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.contrib.auth import get_user_model
from unittest.mock import patch
from desk.services import execute
data = json.load(sys.stdin)
user = get_user_model().objects.get(pk=data['user'])
with patch('desk.services.Event.objects.create', side_effect=lambda **kw: os._exit(71)):
    execute(user, data['team'], data['command'])
"""
    env = dict(os.environ, PGDATABASE=connection.settings_dict["NAME"])
    result = subprocess.run(
        [sys.executable, "-c", child],
        input=json.dumps(
            {
                "user": world["reviewer"].pk,
                "team": world["team"].pk,
                "command": command("approve", rid=submitted.pk, version=2),
            }
        ),
        text=True,
        capture_output=True,
        env=env,
        timeout=20,
    )
    assert result.returncode == 71, result.stderr
    record = ChangeRequest.objects.get(pk=submitted.pk)
    assert (record.state, record.version, record.events.count()) == ("SUBMITTED", 2, 2)
