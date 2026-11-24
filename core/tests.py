import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.templatetags.finance import ksh
from core.testutils import PASSWORD, make_user


class PwaTests(TestCase):
    def test_manifest(self):
        response = self.client.get(reverse("core:manifest"))
        data = json.loads(response.content)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["theme_color"], "#123D2B")
        self.assertEqual({i["sizes"] for i in data["icons"]}, {"192x192", "512x512"})

    def test_service_worker_scope_and_safe_caching(self):
        response = self.client.get(reverse("core:service_worker"))
        body = response.content.decode()
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("application/javascript", response["Content-Type"])
        self.assertIn('request.mode === "navigate"', body)
        self.assertIn("/offline/", body)
        for private in ("/dashboard/", "/transactions/", "/reports/", "chart-data"):
            self.assertNotIn(f'"{private}', body.split("STATIC_ASSETS = [")[1].split("];")[0])

    def test_offline_page_has_no_private_data(self):
        user = make_user("pwa")
        self.client.login(username="pwa", password=PASSWORD)
        response = self.client.get(reverse("core:offline"))
        self.assertNotContains(response, user.username)
        self.assertContains(response, "You are offline")


class SecurityHeaderTests(TestCase):
    def test_authenticated_pages_are_no_store(self):
        make_user("hdr")
        self.client.login(username="hdr", password=PASSWORD)
        response = self.client.get(reverse("analytics:dashboard"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Frame-Options"], "DENY")


class FormattingTests(SimpleTestCase):
    def test_ksh_filter(self):
        self.assertEqual(ksh("1234.5"), "KSh 1,234.50")
        self.assertEqual(ksh(-50, 0), "-KSh 50")
        self.assertEqual(ksh(None), "KSh 0.00")
