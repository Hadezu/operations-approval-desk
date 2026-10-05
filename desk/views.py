import json
import uuid

from django.contrib.auth.decorators import login_required
from django.core.exceptions import RequestDataTooBig
from django.core.paginator import Paginator
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import Membership
from .services import Rejected, execute, membership, visible


@require_GET
@login_required
@never_cache
def queue(request):
    records = (
        visible(request.user).select_related("team", "owner").order_by("-updated_at")
    )
    state = request.GET.get("state", "SUBMITTED")
    if state in {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED"}:
        records = records.filter(state=state)
    elif state != "ALL":
        return JsonResponse({"error": "INVALID_FILTER"}, status=400)
    return render(
        request,
        "desk/queue.html",
        {
            "records": Paginator(records, 30).get_page(request.GET.get("page")),
            "state": state,
            "memberships": Membership.objects.filter(user=request.user)
            .exclude(role="auditor")
            .select_related("team"),
            "command_id": uuid.uuid4(),
            "request_id": uuid.uuid4(),
        },
    )


@require_GET
@login_required
@never_cache
def detail(request, pk):
    record = get_object_or_404(
        visible(request.user).select_related("team", "owner"), pk=pk
    )
    member = membership(request.user, record.team_id)
    actions = []
    if member.role != "auditor" and record.owner_id == request.user.pk:
        actions = (
            ["edit", "submit"]
            if record.state == "DRAFT"
            else ["revise"]
            if record.state == "REJECTED"
            else []
        )
    if (
        member.role == "reviewer"
        and record.owner_id != request.user.pk
        and record.state == "SUBMITTED"
    ):
        actions = ["approve", "reject"]
    return render(
        request,
        "desk/detail.html",
        {
            "record": record,
            "events": record.events.all(),
            "role": member.role,
            "actions": [{"name": name, "key": uuid.uuid4()} for name in actions],
        },
    )


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


@require_POST
@login_required
@never_cache
def command(request, team_id):
    wants_json = request.content_type == "application/json"
    try:
        if wants_json:
            data = json.loads(request.body, object_pairs_hook=no_duplicate_keys)
        else:
            data = request.POST.dict()
            if any(len(values) != 1 for key, values in request.POST.lists()):
                raise ValueError("duplicate field")
            data.pop("csrfmiddlewaretoken", None)
        event, replay = execute(request.user, team_id, data)
    except (ValueError, UnicodeDecodeError, RequestDataTooBig):
        return JsonResponse({"error": "INVALID_COMMAND"}, status=400)
    except Rejected as error:
        if wants_json:
            return JsonResponse({"error": error.code}, status=error.status)
        return render(
            request, "desk/error.html", {"code": error.code}, status=error.status
        )
    except DatabaseError:
        # No raw SQL, credentials or exception detail is returned to the user.
        return JsonResponse(
            {"error": "DATABASE_UNAVAILABLE_RETRY_SAME_COMMAND"}, status=503
        )
    if wants_json:
        return JsonResponse(
            {
                "request_id": str(event.request_id),
                "version": event.version,
                "state": event.after_state,
                "event_id": event.pk,
                "replayed": replay,
            }
        )
    return redirect("detail", pk=event.request_id)


@require_GET
@login_required
@never_cache
def evidence(request, pk):
    # One materialized event query is a PostgreSQL statement snapshot. Derive the
    # exported head from it, not from a separate potentially newer request read.
    record = get_object_or_404(visible(request.user), pk=pk)
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
    result = {
        "request_id": str(pk),
        "through_version": rows[-1]["version"],
        "state": rows[-1]["after_state"],
        "events": rows,
        "boundary": "Independent synthetic demo. Application/database append-only history; not signed evidence or protection against the database owner.",
    }
    response = JsonResponse(result, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="request-{pk}.json"'
    return response


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
