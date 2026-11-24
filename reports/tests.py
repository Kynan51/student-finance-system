from datetime import date

from django.test import TestCase
from django.urls import reverse

from core.testutils import PASSWORD, add_expense, add_income, make_user


class ReportTests(TestCase):
    def setUp(self):
        self.user = make_user("njeri")
        self.other = make_user("other")
        add_income(self.user, 10000, on=date(2026, 10, 2), description="HELB October")
        add_expense(self.user, 450, on=date(2026, 10, 5), description="Lunch")
        add_expense(self.user, 999, on=date(2026, 11, 5), description="Outside range")
        add_expense(self.other, 777, on=date(2026, 10, 5), description="SECRET-OTHER-USER")
        add_expense(self.user, 50, on=date(2026, 10, 6), description="=HYPERLINK(\"http://evil\")")
        self.client.login(username="njeri", password=PASSWORD)
        self.params = {"kind": "month", "month": "2026-10"}

    def test_report_totals_for_month(self):
        response = self.client.get(reverse("reports:report"), self.params)
        r = response.context["r"]
        self.assertEqual(r["totals"]["income"], 10000)
        self.assertEqual(r["totals"]["expenses"], 500)

    def test_csv_is_user_scoped_and_safe(self):
        response = self.client.get(reverse("reports:csv"), self.params)
        body = response.content.decode("utf-8-sig")
        self.assertIn("HELB October", body)
        self.assertNotIn("SECRET-OTHER-USER", body)
        self.assertNotIn("Outside range", body)
        self.assertIn("'=HYPERLINK", body)  # formula injection neutralised
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_pdf_generated(self):
        response = self.client.get(reverse("reports:pdf"), self.params)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_custom_range_validation(self):
        response = self.client.get(reverse("reports:report"), {"kind": "custom", "start": "2026-10-10", "end": "2026-10-01"})
        self.assertFalse(response.context["form"].is_valid())

    def test_anonymous_cannot_export(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("reports:csv")).status_code, 302)
