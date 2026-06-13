from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from backend.common.http import error, list_response, ok, parse_json

from .models import VisitRecord
from .services import create_visit, export_visits_csv, list_visits, serialize_visit, summarize_visits, update_visit


def _parse_date_params(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    return (
        parse_date(start_date) if start_date else None,
        parse_date(end_date) if end_date else None,
    )


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def visits_collection(request):
    if request.method == "GET":
        return list_response(list_visits())

    try:
        record = create_visit(parse_json(request))
        record.full_clean()
        record.save()
        record.appointment.status = "completed"
        record.appointment.save(update_fields=["status", "updated_at"])
        return ok(serialize_visit(record), status=201)
    except (ObjectDoesNotExist, ValidationError, IntegrityError, KeyError, TypeError, ValueError) as exc:
        return error(str(exc))


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE", "OPTIONS"])
def visit_detail(request, pk):
    record = get_object_or_404(VisitRecord.objects.select_related("appointment", "appointment__resident"), pk=pk)

    if request.method == "GET":
        return ok(serialize_visit(record))

    if request.method == "DELETE":
        record.delete()
        return ok({"deleted": True})

    try:
        record = update_visit(record, parse_json(request))
        record.full_clean()
        record.save()
        return ok(serialize_visit(record))
    except (ObjectDoesNotExist, ValidationError, IntegrityError, TypeError, ValueError) as exc:
        return error(str(exc))


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def visits_summary(request):
    start_date, end_date = _parse_date_params(request)
    return list_response(summarize_visits(start_date, end_date))


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
def visits_export(request):
    start_date, end_date = _parse_date_params(request)
    csv_content = export_visits_csv(start_date, end_date)
    filename = "visit_records.csv"
    response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
