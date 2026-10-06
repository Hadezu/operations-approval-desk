import uuid

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import demo
from .demo_copy import COPY
from .models import ChangeRequest
from .services import Rejected


def context(locale):
    if not settings.PUBLIC_DEMO or locale not in COPY:
        raise Http404
    return {
        "c": COPY[locale],
        "locale": locale,
        "other": "pl" if locale == "en" else "en",
        "contact": ("/en" if locale == "en" else "/")
        + "?example=services%2Finternal-applications#contact",
    }


def failure(request, locale, error, data=None):
    ctx = context(locale)
    c = ctx["c"]
    message = (
        c["unknown"]
        if error.status == 503
        else c["expired"]
        if error.code == "DEMO_EXPIRED"
        else c["quota"]
        if error.code == "DEMO_QUOTA"
        else c["codes"].get(error.code, c["codes"]["INVALID_COMMAND"])
    )
    ctx.update(
        error=message,
        code=error.code,
        retained=data or {},
        retryable=error.status == 503
        or error.code
        in {"INVALID_TITLE", "INVALID_PROPOSAL", "REASON_REQUIRED_10_TO_500"},
        editable=error.status == 400,
    )
    response = render(request, "desk/demo_error.html", ctx, status=error.status)
    if error.status in {429, 503}:
        response["Retry-After"] = "60"
    return response


@require_GET
@never_cache
@transaction.atomic
def home(request, locale="en"):
    ctx = context(locale)
    try:
        workspace = demo.workspace_for(request.session, lock=True)
        record = ChangeRequest.objects.get(team=workspace.team)
        role = request.session.get("demo_role", "requester")
        names = []
        if role == "requester":
            names = (
                ["edit", "submit"]
                if record.state == "DRAFT"
                else ["revise"]
                if record.state == "REJECTED"
                else []
            )
        elif role in {"reviewer", "second_reviewer"} and record.state == "SUBMITTED":
            names = ["approve", "reject"]
        events = list(record.events.all())
        for event in events:
            event.state_label = ctx["c"][event.after_state]
            label = event.actor_name.rsplit("-", 1)[-1]
            event.role_label = ctx["c"].get(label, ctx["c"][event.actor_role])
        ctx.update(
            workspace=workspace,
            record=record,
            state_label=ctx["c"][record.state],
            role=role,
            roles=[{"key": key, "label": ctx["c"][key]} for key in demo.LABELS],
            actions=[
                {"key": name, "label": ctx["c"][name], "command": uuid.uuid4()}
                for name in names
            ],
            events=events,
            stale_version=max(
                (event.version for event in events if event.action == "submit"),
                default=0,
            ),
            stale_command=uuid.uuid4(),
            show_stale=role in {"reviewer", "second_reviewer"}
            and record.state in {"APPROVED", "REJECTED"},
            receipt=request.session.get("demo_receipt"),
        )
    except Rejected:
        pass
    except DatabaseError:
        return failure(request, locale, Rejected("DATABASE_UNAVAILABLE", 503))
    return render(request, "desk/demo.html", ctx)


@require_POST
@never_cache
def start(request, locale):
    context(locale)
    try:
        demo.cleanup()
        workspace = demo.start(request.session, locale)
        request.session.cycle_key()
        request.session["demo_workspace"] = str(workspace.pk)
        request.session["demo_role"] = "requester"
        request.session.pop("demo_receipt", None)
        request.session.set_expiry(1200)
    except Rejected as error:
        return failure(request, locale, error)
    except DatabaseError:
        return failure(request, locale, Rejected("DATABASE_UNAVAILABLE", 503))
    return redirect("demo-home", locale=locale)


@require_POST
@never_cache
def role(request, locale):
    context(locale)
    try:
        demo.workspace_for(request.session)
        label = request.POST.get("role")
        if label not in demo.LABELS or len(request.POST.getlist("role")) != 1:
            raise Rejected("INVALID_COMMAND", 400)
        request.session["demo_role"] = label
        request.session.pop("demo_receipt", None)
    except Rejected as error:
        return failure(request, locale, error)
    except DatabaseError:
        return failure(request, locale, Rejected("DATABASE_UNAVAILABLE", 503))
    return redirect("demo-home", locale=locale)


@require_POST
@never_cache
def command(request, locale):
    context(locale)
    data = {}
    try:
        data = request.POST.dict()
        if any(len(values) != 1 for _, values in request.POST.lists()):
            raise Rejected("INVALID_COMMAND", 400)
        data.pop("csrfmiddlewaretoken", None)
        event, replay = demo.act(request.session, data)
        request.session["demo_receipt"] = {
            "id": event.pk,
            "version": event.version,
            "replayed": replay,
        }
    except RequestDataTooBig:
        return failure(request, locale, Rejected("INVALID_COMMAND", 400))
    except Rejected as error:
        return failure(request, locale, error, data)
    except DatabaseError:
        return failure(request, locale, Rejected("DATABASE_UNAVAILABLE", 503), data)
    return redirect("demo-home", locale=locale)


@require_GET
@never_cache
def evidence(request, locale):
    context(locale)
    try:
        with transaction.atomic():
            workspace = demo.workspace_for(request.session, lock=True)
            record = ChangeRequest.objects.get(team=workspace.team)
            rows = list(
                record.events.values(
                    "version",
                    "actor_name",
                    "actor_role",
                    "action",
                    "before_state",
                    "after_state",
                    "reason",
                    "snapshot",
                    "content_sha256",
                    "created_at",
                    "command_id",
                )
            )
    except Rejected as error:
        return failure(request, locale, error)
    except DatabaseError:
        return failure(request, locale, Rejected("DATABASE_UNAVAILABLE", 503))
    response = JsonResponse(
        {
            "request_id": str(record.pk),
            "through_version": rows[-1]["version"],
            "state": rows[-1]["after_state"],
            "events": rows,
            "boundary": "Synthetic public workspace. Append-only until expiry, then deleted. Not signed evidence; database owner remains trusted. No external action.",
        },
        json_dumps_params={"indent": 2},
    )
    response["Content-Disposition"] = 'attachment; filename="approval-evidence.json"'
    return response
