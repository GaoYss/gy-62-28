from django.test import TestCase

from .models import EmergencyNotification
from .services import (
    create_notification,
    list_notifications,
    serialize_notification,
    update_notification,
)


class EmergencyNotificationModelTests(TestCase):
    def test_default_level_is_warning(self):
        n = EmergencyNotification.objects.create(
            title="测试通知",
            content="测试内容",
        )
        self.assertEqual(n.level, "warning")

    def test_default_target_group_is_families(self):
        n = EmergencyNotification.objects.create(
            title="测试通知",
            content="测试内容",
        )
        self.assertEqual(n.target_group, "families")

    def test_default_is_active_true(self):
        n = EmergencyNotification.objects.create(
            title="测试通知",
            content="测试内容",
        )
        self.assertTrue(n.is_active)

    def test_level_choices(self):
        valid = {c[0] for c in EmergencyNotification.LEVEL_CHOICES}
        self.assertEqual(valid, {"info", "warning", "critical"})

    def test_target_choices(self):
        valid = {c[0] for c in EmergencyNotification.TARGET_CHOICES}
        self.assertEqual(valid, {"all", "families", "staff"})

    def test_ordering_by_published_at_desc(self):
        self.assertEqual(EmergencyNotification._meta.ordering, ["-published_at"])


class NotificationServiceCreateTests(TestCase):
    def test_create_notification_with_all_fields(self):
        payload = {
            "title": "紧急停水通知",
            "content": "今日14:00-18:00停水，请家属知悉",
            "level": "critical",
            "target_group": "all",
            "is_active": True,
        }
        n = create_notification(payload)
        n.full_clean()
        n.save()
        saved = EmergencyNotification.objects.get(pk=n.pk)
        self.assertEqual(saved.title, "紧急停水通知")
        self.assertEqual(saved.content, "今日14:00-18:00停水，请家属知悉")
        self.assertEqual(saved.level, "critical")
        self.assertEqual(saved.target_group, "all")
        self.assertTrue(saved.is_active)

    def test_create_notification_partial_fields(self):
        payload = {
            "title": "普通通知",
            "content": "食堂菜单更新",
        }
        n = create_notification(payload)
        n.full_clean()
        n.save()
        self.assertEqual(n.level, "warning")
        self.assertEqual(n.target_group, "families")

    def test_create_notification_critical_level(self):
        payload = {
            "title": "火灾警报",
            "content": "三楼火警，请立即疏散",
            "level": "critical",
            "target_group": "all",
        }
        n = create_notification(payload)
        n.full_clean()
        n.save()
        self.assertEqual(n.level, "critical")

    def test_create_notification_info_level(self):
        payload = {
            "title": "活动通知",
            "content": "本周五下午有文娱活动",
            "level": "info",
            "target_group": "families",
        }
        n = create_notification(payload)
        n.full_clean()
        n.save()
        self.assertEqual(n.level, "info")


class NotificationServiceSerializeTests(TestCase):
    def test_serialize_keys(self):
        n = EmergencyNotification.objects.create(
            title="测试",
            content="内容",
        )
        result = serialize_notification(n)
        expected_keys = {
            "id", "title", "content", "level", "target_group",
            "is_active", "published_at", "updated_at",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_serialize_values(self):
        n = EmergencyNotification.objects.create(
            title="紧急通知",
            content="请速来",
            level="critical",
            target_group="all",
        )
        result = serialize_notification(n)
        self.assertEqual(result["title"], "紧急通知")
        self.assertEqual(result["content"], "请速来")
        self.assertEqual(result["level"], "critical")
        self.assertEqual(result["target_group"], "all")
        self.assertTrue(result["is_active"])


class NotificationServiceListTests(TestCase):
    def test_list_all_notifications(self):
        EmergencyNotification.objects.create(title="A", content="a", level="info")
        EmergencyNotification.objects.create(title="B", content="b", level="critical")
        results = list_notifications()
        self.assertEqual(len(results), 2)

    def test_list_active_notifications(self):
        EmergencyNotification.objects.create(title="A", content="a", is_active=True)
        EmergencyNotification.objects.create(title="B", content="b", is_active=False)
        results = list_notifications(active=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "A")

    def test_list_inactive_notifications(self):
        EmergencyNotification.objects.create(title="A", content="a", is_active=True)
        EmergencyNotification.objects.create(title="B", content="b", is_active=False)
        results = list_notifications(active=False)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "B")


class NotificationServiceUpdateTests(TestCase):
    def test_update_notification_deactivate(self):
        n = EmergencyNotification.objects.create(title="A", content="a")
        self.assertTrue(n.is_active)
        updated = update_notification(n, {"is_active": False})
        self.assertFalse(updated.is_active)
        n.refresh_from_db()
        self.assertFalse(n.is_active)

    def test_update_notification_change_level(self):
        n = EmergencyNotification.objects.create(title="A", content="a", level="info")
        updated = update_notification(n, {"level": "critical"})
        self.assertEqual(updated.level, "critical")

    def test_update_notification_change_content(self):
        n = EmergencyNotification.objects.create(title="A", content="a")
        updated = update_notification(n, {"content": "更新内容"})
        self.assertEqual(updated.content, "更新内容")

    def test_update_notification_change_target_group(self):
        n = EmergencyNotification.objects.create(title="A", content="a", target_group="families")
        updated = update_notification(n, {"target_group": "staff"})
        self.assertEqual(updated.target_group, "staff")


class NotificationViewCreateTests(TestCase):
    def test_post_create_notification_returns_201(self):
        resp = self.client.post(
            "/api/notifications/",
            data={
                "title": "紧急通知",
                "content": "请速来院",
                "level": "critical",
                "target_group": "all",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["title"], "紧急通知")
        self.assertEqual(body["level"], "critical")
        self.assertEqual(body["target_group"], "all")
        self.assertTrue(body["is_active"])

    def test_post_create_notification_missing_title_returns_error(self):
        resp = self.client.post(
            "/api/notifications/",
            data={"content": "内容"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_create_notification_missing_content_returns_error(self):
        resp = self.client.post(
            "/api/notifications/",
            data={"title": "标题"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class NotificationViewListAndDetailTests(TestCase):
    def test_get_list_notifications(self):
        EmergencyNotification.objects.create(title="A", content="a")
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 1)

    def test_get_list_active_filter(self):
        EmergencyNotification.objects.create(title="A", content="a", is_active=True)
        EmergencyNotification.objects.create(title="B", content="b", is_active=False)
        resp = self.client.get("/api/notifications/?active=true")
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["is_active"])

    def test_get_notification_detail(self):
        n = EmergencyNotification.objects.create(title="A", content="a")
        resp = self.client.get(f"/api/notifications/{n.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "A")

    def test_delete_notification(self):
        n = EmergencyNotification.objects.create(title="A", content="a")
        resp = self.client.delete(f"/api/notifications/{n.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EmergencyNotification.objects.filter(pk=n.pk).exists())

    def test_put_update_notification(self):
        n = EmergencyNotification.objects.create(title="A", content="a")
        resp = self.client.put(
            f"/api/notifications/{n.pk}/",
            data={"level": "critical", "is_active": False},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["level"], "critical")
        self.assertFalse(body["is_active"])
