from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from ai_engine.models import Notification
from core.testutils import PASSWORD, add_expense, cat, make_user

from .models import Budget, BudgetCategoryLimit, FixedObligation
from .services import budget_status


class BudgetCalculationTests(TestCase):
    def setUp(self):
        self.user = make_user("otieno")
        self.budget = Budget.objects.create(
            owner=self.user, name="Nov", period="monthly", start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30), total_limit=Decimal("10000"), warning_threshold=80,
        )

    def test_date_boundaries_are_inclusive(self):
        add_expense(self.user, 100, on=date(2026, 10, 31))  # before
        add_expense(self.user, 200, on=date(2026, 11, 1))   # first day
        add_expense(self.user, 300, on=date(2026, 11, 30))  # last day
        add_expense(self.user, 400, on=date(2026, 12, 1))   # after
        status = budget_status(self.budget, today=date(2026, 11, 15))
        self.assertEqual(status["spent"], Decimal("500"))
        self.assertEqual(status["remaining"], Decimal("9500"))

    def test_states_ok_warning_exceeded(self):
        add_expense(self.user, 7999, on=date(2026, 11, 5))
        self.assertEqual(budget_status(self.budget)["state"], "ok")
        add_expense(self.user, 1, on=date(2026, 11, 5))
        self.assertEqual(budget_status(self.budget)["state"], "warning")
        add_expense(self.user, 2001, on=date(2026, 11, 5))
        self.assertEqual(budget_status(self.budget)["state"], "exceeded")

    def test_recalculates_after_edit_and_delete(self):
        e = add_expense(self.user, 9000, on=date(2026, 11, 2))
        self.assertEqual(budget_status(self.budget)["state"], "warning")
        e.amount = Decimal("1000")
        e.save()
        self.assertEqual(budget_status(self.budget)["spent"], Decimal("1000"))
        e.delete()
        self.assertEqual(budget_status(self.budget)["spent"], Decimal("0"))

    def test_category_limits_and_obligations(self):
        BudgetCategoryLimit.objects.create(budget=self.budget, category=cat("food"), limit=Decimal("3000"))
        FixedObligation.objects.create(budget=self.budget, name="Rent", amount=Decimal("4500"), due_date=date(2026, 11, 30))
        add_expense(self.user, 2500, on=date(2026, 11, 3), slug="food")
        add_expense(self.user, 1000, on=date(2026, 11, 3), slug="transport")
        status = budget_status(self.budget, today=date(2026, 11, 10))
        food = status["categories"][0]
        self.assertEqual(food["spent"], Decimal("2500"))
        self.assertEqual(food["state"], "warning")
        self.assertEqual(status["unpaid_obligations"], Decimal("4500"))
        self.assertEqual(status["free_after_obligations"], Decimal("10000") - Decimal("3500") - Decimal("4500"))

    def test_other_users_expenses_not_counted(self):
        other = make_user("stranger")
        add_expense(other, 5000, on=date(2026, 11, 5))
        self.assertEqual(budget_status(self.budget)["spent"], Decimal("0"))

    def test_notifications_raised_once(self):
        add_expense(self.user, 8500, on=date(2026, 11, 5))
        add_expense(self.user, 10, on=date(2026, 11, 6))
        self.assertEqual(Notification.objects.filter(owner=self.user, dedupe_key=f"budget:{self.budget.pk}:warning").count(), 1)
        add_expense(self.user, 2000, on=date(2026, 11, 6))
        self.assertTrue(Notification.objects.filter(owner=self.user, dedupe_key=f"budget:{self.budget.pk}:exceeded").exists())


class BudgetViewTests(TestCase):
    def setUp(self):
        self.user = make_user("mercy")
        self.client.login(username="mercy", password=PASSWORD)

    def test_create_budget_and_validation(self):
        bad = self.client.post(reverse("budgeting:create"), {
            "name": "x", "period": "monthly", "start_date": "2026-11-30", "end_date": "2026-11-01",
            "total_limit": "5000", "warning_threshold": 80,
        })
        self.assertIn("end_date", bad.context["form"].errors)
        self.client.post(reverse("budgeting:create"), {
            "name": "Semester", "period": "semester", "start_date": "2026-09-01", "end_date": "2026-12-20",
            "total_limit": "60000", "warning_threshold": 75,
        })
        self.assertTrue(Budget.objects.filter(owner=self.user, name="Semester").exists())

    def test_cannot_access_other_users_budget(self):
        other = make_user("x")
        b = Budget.objects.create(owner=other, name="Theirs", start_date=date(2026, 11, 1), end_date=date(2026, 11, 30), total_limit=100)
        self.assertEqual(self.client.get(reverse("budgeting:detail", args=[b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("budgeting:delete", args=[b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("budgeting:limit_add", args=[b.pk]), {"category": cat("food").pk, "limit": "50"}).status_code, 404)
        self.assertTrue(Budget.objects.filter(pk=b.pk).exists())
