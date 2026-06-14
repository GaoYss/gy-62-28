from django.test import TestCase
from django.utils import timezone

from backend.residents.models import Resident

from .models import Appointment
from .services import create_appointment, normalize_payload, serialize_appointment, update_appointment


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


class AppointmentModelTests(TestCase):
    def test_default_status_is_pending(self):
        r = _make_resident()
        a = Appointment.objects.create(
            resident=r,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        self.assertEqual(a.status, "pending")

    def test_status_choices_valid(self):
        valid = {c[0] for c in Appointment.STATUS_CHOICES}
        self.assertEqual(valid, {"pending", "approved", "rejected", "completed", "cancelled"})


class AppointmentServiceTests(TestCase):
    def setUp(self):
        self.resident = _make_resident()
        self.visit_time = "2025-06-15T10:00:00+08:00"

    def test_create_appointment_saves_all_fields(self):
        payload = {
            "resident_id": self.resident.pk,
            "family_name": "王五",
            "family_phone": "13900000002",
            "relationship": "女儿",
            "visit_time": self.visit_time,
            "visitor_count": 2,
            "status": "pending",
            "notes": "带水果",
        }
        appointment = create_appointment(payload)
        appointment.full_clean()
        appointment.save()

        saved = Appointment.objects.get(pk=appointment.pk)
        self.assertEqual(saved.resident_id, self.resident.pk)
        self.assertEqual(saved.family_name, "王五")
        self.assertEqual(saved.family_phone, "13900000002")
        self.assertEqual(saved.relationship, "女儿")
        self.assertEqual(saved.visitor_count, 2)
        self.assertEqual(saved.status, "pending")
        self.assertEqual(saved.notes, "带水果")

    def test_create_appointment_nonexistent_resident_raises(self):
        payload = {
            "resident_id": 99999,
            "family_name": "赵六",
            "family_phone": "13900000003",
            "relationship": "配偶",
            "visit_time": self.visit_time,
        }
        with self.assertRaises(Resident.DoesNotExist):
            create_appointment(payload)

    def test_normalize_payload_remaps_resident_to_resident_id(self):
        payload = {
            "resident": self.resident.pk,
            "family_name": "孙七",
            "family_phone": "13900000004",
            "relationship": "孙子",
            "visit_time": self.visit_time,
        }
        data = normalize_payload(payload)
        self.assertIn("resident_id", data)
        self.assertNotIn("resident", data)
        self.assertEqual(data["resident_id"], self.resident.pk)

    def test_normalize_payload_parses_visit_time(self):
        payload = {
            "resident_id": self.resident.pk,
            "visit_time": self.visit_time,
        }
        data = normalize_payload(payload)
        self.assertIsNotNone(data["visit_time"])

    def test_serialize_appointment_output_keys(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        result = serialize_appointment(a)
        expected_keys = {
            "id", "resident", "resident_id", "family_name", "family_phone",
            "relationship", "visit_time", "visitor_count", "status", "notes",
            "created_at", "updated_at",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_update_appointment_changes_status(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        self.assertEqual(a.status, "pending")
        updated = update_appointment(a, {"status": "approved"})
        self.assertEqual(updated.status, "approved")
        a.refresh_from_db()
        self.assertEqual(a.status, "approved")

    def test_update_appointment_rejected_status(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        updated = update_appointment(a, {"status": "rejected"})
        self.assertEqual(updated.status, "rejected")

    def test_update_appointment_cancelled_status(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
            status="approved",
        )
        updated = update_appointment(a, {"status": "cancelled"})
        self.assertEqual(updated.status, "cancelled")


class AppointmentViewTests(TestCase):
    def setUp(self):
        self.resident = _make_resident()
        self.visit_time = "2025-06-15T10:00:00+08:00"

    def test_post_create_appointment_returns_201(self):
        payload = {
            "resident_id": self.resident.pk,
            "family_name": "王五",
            "family_phone": "13900000002",
            "relationship": "女儿",
            "visit_time": self.visit_time,
        }
        resp = self.client.post(
            "/api/appointments/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["family_name"], "王五")
        self.assertEqual(body["status"], "pending")

    def test_post_create_appointment_missing_field_returns_error(self):
        payload = {
            "resident_id": self.resident.pk,
            "family_name": "王五",
        }
        resp = self.client.post(
            "/api/appointments/",
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_list_appointments(self):
        Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        resp = self.client.get("/api/appointments/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 1)

    def test_get_list_appointments_filter_by_status(self):
        Appointment.objects.create(
            resident=self.resident,
            family_name="A",
            family_phone="1",
            relationship="子",
            visit_time=timezone.now(),
            status="approved",
        )
        Appointment.objects.create(
            resident=self.resident,
            family_name="B",
            family_phone="2",
            relationship="女",
            visit_time=timezone.now(),
            status="pending",
        )
        resp = self.client.get("/api/appointments/?status=approved")
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "approved")

    def test_put_update_appointment_status(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        resp = self.client.put(
            f"/api/appointments/{a.pk}/",
            data={"status": "approved"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "approved")

    def test_delete_appointment(self):
        a = Appointment.objects.create(
            resident=self.resident,
            family_name="李四",
            family_phone="13900000001",
            relationship="儿子",
            visit_time=timezone.now(),
        )
        resp = self.client.delete(f"/api/appointments/{a.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Appointment.objects.filter(pk=a.pk).exists())
