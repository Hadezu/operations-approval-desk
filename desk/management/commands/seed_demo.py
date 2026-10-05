import os
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from desk.models import Team
from desk.services import execute, set_membership


class Command(BaseCommand):
    help = "Create synthetic demo accounts and requests in an EMPTY application. Never resets data."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "")
        if len(password) < 16:
            raise CommandError(
                "Set DEMO_PASSWORD to a private password of at least 16 characters."
            )
        if Team.objects.exists() or get_user_model().objects.exists():
            raise CommandError(
                "Seed requires an empty application; existing data is never reset."
            )
        north = Team.objects.create(name="North Operations")
        south = Team.objects.create(name="South Operations")
        users = {}
        for name, team, role in [
            ("alice", north, "requester"),
            ("bob", north, "reviewer"),
            ("carol", north, "reviewer"),
            ("dana", north, "auditor"),
            ("eve", south, "reviewer"),
        ]:
            users[name] = get_user_model().objects.create_user(name, password=password)
            set_membership(user=users[name], team=team, role=role)
        samples = [
            (
                "Correct the warehouse routing rule",
                "Synthetic proposal: route North warehouse returns to the review queue instead of automatic closure. No warehouse system is connected.",
                True,
            ),
            (
                "Require a source reference on import exceptions",
                "Synthetic proposal: add a required source reference before an import exception can be marked reviewed. No source files are modified.",
                True,
            ),
            (
                "Update the weekly review checklist",
                "Synthetic proposal: include currency and duplicate checks in the weekly operations checklist.",
                False,
            ),
        ]
        for title, proposal, submit in samples:
            rid = str(uuid.uuid4())
            execute(
                users["alice"],
                north.pk,
                {
                    "action": "create",
                    "request_id": rid,
                    "command_id": str(uuid.uuid4()),
                    "version": 0,
                    "title": title,
                    "proposal": proposal,
                    "reason": "Prepare a synthetic request for review.",
                },
            )
            if submit:
                execute(
                    users["alice"],
                    north.pk,
                    {
                        "action": "submit",
                        "request_id": rid,
                        "command_id": str(uuid.uuid4()),
                        "version": 1,
                        "reason": "The proposed scope is ready for independent review.",
                    },
                )
        execute(
            users["eve"],
            south.pk,
            {
                "action": "create",
                "request_id": str(uuid.uuid4()),
                "command_id": str(uuid.uuid4()),
                "version": 0,
                "title": "South team private example",
                "proposal": "This synthetic record must not be visible to North team accounts.",
                "reason": "Demonstrate isolation between the two teams.",
            },
        )
        self.stdout.write(
            "Created synthetic teams, 5 accounts and 4 requests. Use your DEMO_PASSWORD; it was not logged."
        )
