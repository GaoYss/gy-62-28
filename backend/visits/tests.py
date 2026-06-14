from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.appointments.models import Appointment
from backend.residents.models import Resident

from .models import VisitRecord
from .services import (
    create_visit,
    list_visits,
    normalize_payload,
    serialize_visit,
    summarize_visits,
    update_visit,
)


def _make_resident(**overrides):
    defaults = {
        "name": "张三",
        "gender": "male",
        "age": 80,
        "room_number": "101",
        "care_level": "self_care",
        "emergency_contact": "张四",
        "emergency_phone": "13800000001",
    }
    defaults.update(overrides)
    return Resident.objects.create(**defaults)


def _make_appointment(resident=None, status="approved", **overrides):
    if resident is None:
        resident = _make_resident()
    defaults = {
        "resident": resident,
        "family_name": "李四",
        "family_phone": "13900000001",
        "relationship": "儿子",
        "visit_time": timezone.now(),
        "status": status,
    }
    defaults.update(overrides)
    return Appointment.objects.create(**defaults)


class VisitRecordModelTests(TestCase):
    def test_check_out_time_can_be_null(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        self.assertIsNone(v.check_out_time)

    def test_check_out_time_can_be_set(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        now = timezone.now()
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=now,
            check_out_time=now + timedelta(hours=1),
            staff_name="护工甲",
        )
        self.assertIsNotNone(v.check_out_time)

    def test_visitor_temperature_optional(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        self.assertIsNone(v.visitor_temperature)

    def test_visitor_temperature_decimal(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
            visitor_temperature="36.5",
        )
        v.refresh_from_db()
        self.assertEqual(v.visitor_temperature, Decimal("36.5"))

    def test_ordering_by_check_in_time_desc(self):
        self.assertEqual(VisitRecord._meta.ordering, ["-check_in_time"])

    def test_one_to_one_with_appointment(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        now = timezone.now()
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=now,
            staff_name="护工甲",
        )
        with self.assertRaises(Exception):
            VisitRecord.objects.create(
                appointment=a,
                check_in_time=now + timedelta(hours=2),
                staff_name="护工乙",
            )


class VisitServiceNormalizePayloadTests(TestCase):
    def test_remaps_appointment_to_appointment_id(self):
        payload = {
            "appointment": 1,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        data = normalize_payload(payload)
        self.assertIn("appointment_id", data)
        self.assertNotIn("appointment", data)
        self.assertEqual(data["appointment_id"], 1)

    def test_parses_check_in_time(self):
        payload = {
            "appointment_id": 1,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        data = normalize_payload(payload)
        self.assertIsNotNone(data["check_in_time"])

    def test_parses_check_out_time(self):
        payload = {
            "appointment_id": 1,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "check_out_time": "2025-06-15T10:00:00+08:00",
            "staff_name": "护工甲",
        }
        data = normalize_payload(payload)
        self.assertIsNotNone(data["check_out_time"])

    def test_empty_check_out_time_becomes_none(self):
        payload = {
            "appointment_id": 1,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "check_out_time": "",
            "staff_name": "护工甲",
        }
        data = normalize_payload(payload)
        self.assertIsNone(data["check_out_time"])

    def test_missing_check_out_time_not_in_data(self):
        payload = {
            "appointment_id": 1,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        data = normalize_payload(payload)
        self.assertNotIn("check_out_time", data)


class VisitServiceCreateTests(TestCase):
    def test_create_visit_with_valid_appointment(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        payload = {
            "appointment_id": a.pk,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        record = create_visit(payload)
        self.assertEqual(record.appointment_id, a.pk)
        self.assertEqual(record.staff_name, "护工甲")

    def test_create_visit_nonexistent_appointment_raises(self):
        payload = {
            "appointment_id": 99999,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        with self.assertRaises(Appointment.DoesNotExist):
            create_visit(payload)

    def test_create_visit_rejected_appointment_raises(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="rejected")
        payload = {
            "appointment_id": a.pk,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        with self.assertRaises(ValueError) as ctx:
            create_visit(payload)
        self.assertIn("已拒绝", str(ctx.exception))
        self.assertIn("不允许签到", str(ctx.exception))

    def test_create_visit_cancelled_appointment_raises(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="cancelled")
        payload = {
            "appointment_id": a.pk,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        with self.assertRaises(ValueError) as ctx:
            create_visit(payload)
        self.assertIn("已取消", str(ctx.exception))
        self.assertIn("不允许签到", str(ctx.exception))


class VisitServiceSerializeTests(TestCase):
    def test_serialize_visit_check_out_time_none(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        result = serialize_visit(v)
        self.assertIsNone(result["check_out_time"])

    def test_serialize_visit_check_out_time_set(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        now = timezone.now()
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=now,
            check_out_time=now + timedelta(hours=1),
            staff_name="护工甲",
        )
        result = serialize_visit(v)
        self.assertIsNotNone(result["check_out_time"])

    def test_serialize_visit_temperature_none(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        result = serialize_visit(v)
        self.assertEqual(result["visitor_temperature"], "")

    def test_serialize_visit_temperature_set(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
            visitor_temperature="36.5",
        )
        result = serialize_visit(v)
        self.assertEqual(result["visitor_temperature"], "36.5")

    def test_serialize_visit_keys(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        result = serialize_visit(v)
        expected_keys = {
            "id", "appointment", "appointment_id", "check_in_time",
            "check_out_time", "visitor_temperature", "staff_name",
            "summary", "created_at", "updated_at",
        }
        self.assertEqual(set(result.keys()), expected_keys)


class VisitServiceUpdateTests(TestCase):
    def test_update_visit_adds_check_out_time(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        check_in = timezone.now() - timedelta(hours=3)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=check_in,
            staff_name="护工甲",
        )
        self.assertIsNone(v.check_out_time)
        check_out_str = (check_in + timedelta(hours=2)).isoformat()
        updated = update_visit(v, {"check_out_time": check_out_str})
        self.assertIsNotNone(updated.check_out_time)

    def test_update_visit_changes_temperature(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        updated = update_visit(v, {"visitor_temperature": "37.2"})
        updated.full_clean()
        updated.save()
        v.refresh_from_db()
        self.assertEqual(v.visitor_temperature, Decimal("37.2"))

    def test_update_visit_changes_summary(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        updated = update_visit(v, {"summary": "探视顺利"})
        updated.full_clean()
        updated.save()
        v.refresh_from_db()
        self.assertEqual(v.summary, "探视顺利")


class VisitServiceListTests(TestCase):
    def test_list_visits_returns_all(self):
        r1 = _make_resident(name="老人甲", room_number="101")
        r2 = _make_resident(name="老人乙", room_number="102")
        _make_appointment(resident=r1, family_name="家属甲")
        _make_appointment(resident=r2, family_name="家属乙")
        VisitRecord.objects.create(
            appointment=Appointment.objects.first(),
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        VisitRecord.objects.create(
            appointment=Appointment.objects.last(),
            check_in_time=timezone.now() + timedelta(hours=1),
            staff_name="护工乙",
        )
        results = list_visits()
        self.assertEqual(len(results), 2)


class VisitServiceSummarizeTests(TestCase):
    def test_summarize_groups_by_resident_date_staff(self):
        r = _make_resident(name="老人甲", room_number="101")
        a = _make_appointment(resident=r, family_name="家属甲", visitor_count=2)
        now = timezone.now()
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=now,
            staff_name="护工甲",
        )
        results = summarize_visits()
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["resident_name"], "老人甲")
        self.assertEqual(row["room_number"], "101")
        self.assertEqual(row["visit_count"], 1)
        self.assertEqual(row["total_visitors"], 2)
        self.assertIn("家属甲", row["families"])

    def test_summarize_date_filter(self):
        r = _make_resident()
        a = _make_appointment(resident=r)
        today = timezone.now().date()
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        results = summarize_visits(start_date=today, end_date=today)
        self.assertEqual(len(results), 1)

        results = summarize_visits(
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=2),
        )
        self.assertEqual(len(results), 0)


class VisitViewCreateTests(TestCase):
    def setUp(self):
        self.resident = _make_resident()
        self.appointment = _make_appointment(resident=self.resident, status="approved")

    def test_create_visit_sets_appointment_completed(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": self.appointment.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "completed")

    def test_create_visit_with_check_in_and_check_out(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": self.appointment.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "check_out_time": "2025-06-15T11:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertIsNotNone(body["check_in_time"])
        self.assertIsNotNone(body["check_out_time"])

    def test_create_visit_check_out_before_check_in_rejected(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": self.appointment.pk,
                "check_in_time": "2025-06-15T11:00:00+08:00",
                "check_out_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_visit_with_temperature(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": self.appointment.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "visitor_temperature": "36.5",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["visitor_temperature"], "36.5")

    def test_create_visit_missing_appointment_id_returns_error(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_visit_nonexistent_appointment_returns_error(self):
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": 99999,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_visit_duplicate_appointment_returns_error(self):
        payload = {
            "appointment_id": self.appointment.pk,
            "check_in_time": "2025-06-15T09:00:00+08:00",
            "staff_name": "护工甲",
        }
        self.client.post("/api/visits/", data=payload, content_type="application/json")
        resp = self.client.post("/api/visits/", data=payload, content_type="application/json")
        self.assertEqual(resp.status_code, 400)


class VisitViewUpdateTests(TestCase):
    def setUp(self):
        self.resident = _make_resident()
        self.appointment = _make_appointment(resident=self.resident, status="approved")
        self.check_in = timezone.now() - timedelta(hours=3)
        self.record = VisitRecord.objects.create(
            appointment=self.appointment,
            check_in_time=self.check_in,
            staff_name="护工甲",
        )

    def test_update_visit_add_check_out_time(self):
        check_out_str = (self.check_in + timedelta(hours=2)).isoformat()
        resp = self.client.put(
            f"/api/visits/{self.record.pk}/",
            data={"check_out_time": check_out_str},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()["check_out_time"])

    def test_update_visit_change_temperature(self):
        resp = self.client.put(
            f"/api/visits/{self.record.pk}/",
            data={"visitor_temperature": "37.0"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["visitor_temperature"], "37.0")

    def test_update_visit_change_summary(self):
        resp = self.client.put(
            f"/api/visits/{self.record.pk}/",
            data={"summary": "老人情绪良好"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["summary"], "老人情绪良好")

    def test_update_visit_check_out_before_check_in_rejected(self):
        check_out_str = (self.check_in - timedelta(hours=1)).isoformat()
        resp = self.client.put(
            f"/api/visits/{self.record.pk}/",
            data={"check_out_time": check_out_str},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("签退时间不能早于签到时间", str(body.get("error", "")))

    def test_update_visit_check_out_before_check_in_does_not_save(self):
        original_check_out = self.record.check_out_time
        check_out_str = (self.check_in - timedelta(hours=1)).isoformat()
        self.client.put(
            f"/api/visits/{self.record.pk}/",
            data={"check_out_time": check_out_str},
            content_type="application/json",
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.check_out_time, original_check_out)


class VisitViewListAndDetailTests(TestCase):
    def test_get_visits_list(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        resp = self.client.get("/api/visits/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 1)

    def test_get_visit_detail(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        resp = self.client.get(f"/api/visits/{v.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], v.pk)

    def test_delete_visit(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        v = VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        resp = self.client.delete(f"/api/visits/{v.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(VisitRecord.objects.filter(pk=v.pk).exists())

    def test_get_visits_summary(self):
        r = _make_resident(name="老人甲", room_number="101")
        a = _make_appointment(resident=r, family_name="家属甲", visitor_count=2)
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        resp = self.client.get("/api/visits/summary/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resident_name"], "老人甲")

    def test_get_visits_export_csv(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        VisitRecord.objects.create(
            appointment=a,
            check_in_time=timezone.now(),
            staff_name="护工甲",
        )
        resp = self.client.get("/api/visits/export/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8-sig")


class VisitFlowStatusTransitionTests(TestCase):
    def test_pending_appointment_visit_creates_and_completes(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="pending")
        self.assertEqual(a.status, "pending")
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        a.refresh_from_db()
        self.assertEqual(a.status, "completed")

    def test_approved_appointment_visit_creates_and_completes(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        a.refresh_from_db()
        self.assertEqual(a.status, "completed")

    def test_completed_appointment_cannot_have_second_visit(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="approved")
        self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        a.refresh_from_db()
        self.assertEqual(a.status, "completed")
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T14:00:00+08:00",
                "staff_name": "护工乙",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_rejected_appointment_cannot_create_visit(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="rejected")
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("已拒绝", body.get("error", ""))
        self.assertIn("不允许签到", body.get("error", ""))

    def test_cancelled_appointment_cannot_create_visit(self):
        r = _make_resident()
        a = _make_appointment(resident=r, status="cancelled")
        resp = self.client.post(
            "/api/visits/",
            data={
                "appointment_id": a.pk,
                "check_in_time": "2025-06-15T09:00:00+08:00",
                "staff_name": "护工甲",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("已取消", body.get("error", ""))
        self.assertIn("不允许签到", body.get("error", ""))
