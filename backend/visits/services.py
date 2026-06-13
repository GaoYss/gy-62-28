import csv
import io
from collections import defaultdict

from django.utils.dateparse import parse_date, parse_datetime

from backend.appointments.models import Appointment
from backend.appointments.services import serialize_appointment

from .models import VisitRecord


WRITE_FIELDS = [
    "appointment",
    "appointment_id",
    "check_in_time",
    "check_out_time",
    "visitor_temperature",
    "staff_name",
    "summary",
]


def serialize_visit(record):
    return {
        "id": record.id,
        "appointment": serialize_appointment(record.appointment),
        "appointment_id": record.appointment_id,
        "check_in_time": record.check_in_time.isoformat(),
        "check_out_time": record.check_out_time.isoformat() if record.check_out_time else None,
        "visitor_temperature": str(record.visitor_temperature) if record.visitor_temperature is not None else "",
        "staff_name": record.staff_name,
        "summary": record.summary,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def normalize_payload(payload):
    data = {field: payload.get(field) for field in WRITE_FIELDS if field in payload}
    if "appointment" in data:
        data["appointment_id"] = data.pop("appointment")
    for key in ["check_in_time", "check_out_time"]:
        if key in data and isinstance(data[key], str) and data[key]:
            data[key] = parse_datetime(data[key])
    if data.get("check_out_time") == "":
        data["check_out_time"] = None
    return data


def list_visits():
    queryset = VisitRecord.objects.select_related("appointment", "appointment__resident")
    return [serialize_visit(item) for item in queryset]


def create_visit(payload):
    data = normalize_payload(payload)
    Appointment.objects.get(pk=data["appointment_id"])
    return VisitRecord(**data)


def update_visit(record, payload):
    data = normalize_payload(payload)
    for field, value in data.items():
        setattr(record, field, value)
    record.save()
    return record


def _build_queryset(start_date=None, end_date=None):
    queryset = VisitRecord.objects.select_related("appointment", "appointment__resident").all()
    if start_date:
        queryset = queryset.filter(check_in_time__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(check_in_time__date__lte=end_date)
    return queryset.order_by("check_in_time")


def summarize_visits(start_date=None, end_date=None):
    queryset = _build_queryset(start_date, end_date)
    groups = defaultdict(list)
    for record in queryset:
        key = (
            record.appointment.resident_id,
            record.check_in_time.date(),
            record.staff_name,
        )
        groups[key].append(record)

    results = []
    for (resident_id, visit_date, staff_name), records in sorted(
        groups.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])
    ):
        resident = records[0].appointment.resident
        total_visitors = sum(r.appointment.visitor_count for r in records)
        results.append({
            "resident_name": resident.name,
            "room_number": resident.room_number,
            "visit_date": visit_date.isoformat(),
            "staff_name": staff_name,
            "visit_count": len(records),
            "total_visitors": total_visitors,
            "families": [r.appointment.family_name for r in records],
        })
    return results


def export_visits_csv(start_date=None, end_date=None):
    summary = summarize_visits(start_date, end_date)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["老人姓名", "房间号", "探视日期", "接待员工", "探视次数", "访客总人数", "来访家属"])
    for row in summary:
        writer.writerow([
            row["resident_name"],
            row["room_number"],
            row["visit_date"],
            row["staff_name"],
            row["visit_count"],
            row["total_visitors"],
            "、".join(row["families"]),
        ])
    return buffer.getvalue()
