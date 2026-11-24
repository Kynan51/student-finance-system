from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.testutils import PASSWORD, add_expense, add_income, make_user

from . import services


class DashboardAggregateTests(TestCase):
    def setUp(self):
        self.user = make_user("mutua")
        today = date.today()
        add_income(self.user, "30000", on=today.replace(day=1))
        add_expense(self.user, "1200.50", on=today, slug="food")
        add_expense(self.user, "800", on=today, slug="transport")
        add_expense(self.user, "5000", on=today - timedelta(days=60), slug="accommodation")
        add_expense(make_user("noise"), "99999", on=today)
        self.client.login(username="mutua", password=PASSWORD)

    def test_totals_reconcile_with_ledger(self):
        b = services.balance_summary(self.user)
        self.assertEqual(b["income"], Decimal("30000"))
        self.assertEqual(b["expenses"], Decimal("7000.50"))
        self.assertEqual(b["cash_balance"], Decimal("22999.50"))

    def test_period_filter(self):
        week = services.totals(self.user, services.resolve_period(self.user, "week"))
        self.assertEqual(week["expenses"], Decimal("2000.50"))
        all_time = services.totals(self.user, services.resolve_period(self.user, "all"))
        self.assertEqual(all_time["expenses"], Decimal("7000.50"))

    def test_chart_data_is_live_and_scoped(self):
        data = self.client.get(reverse("analytics:chart_data"), {"period": "week"}).json()
        self.assertEqual(sorted(data["categories"]["labels"]), ["Food", "Transport"])
        self.assertAlmostEqual(sum(data["categories"]["values"]), 2000.5)
        self.assertNotIn(99999.0, data["daily"]["values"])
        self.assertEqual(len(data["trend"]["labels"]), 6)

    def test_dashboard_renders_and_invalid_period_falls_back(self):
        response = self.client.get(reverse("analytics:dashboard"), {"period": "bogus"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period"], "month")

    def test_empty_dashboard(self):
        make_user("fresh")
        self.client.login(username="fresh", password=PASSWORD)
        response = self.client.get(reverse("analytics:dashboard"))
        self.assertContains(response, "set things up")
