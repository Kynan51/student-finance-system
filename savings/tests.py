from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from analytics.services import balance_summary
from core.testutils import PASSWORD, add_expense, add_income, make_user
from transactions.models import Expense

from . import services
from .models import SavingsContribution, SavingsGoal


class SavingsReconciliationTests(TestCase):
    def setUp(self):
        self.user = make_user("faith")
        add_income(self.user, "20000")
        add_expense(self.user, "5000")
        self.goal = SavingsGoal.objects.create(owner=self.user, name="Rent", target_amount=Decimal("6000"))

    def test_allocation_reduces_available_not_cash_or_expenses(self):
        services.allocate(self.goal, Decimal("4000"))
        b = balance_summary(self.user)
        self.assertEqual(b["cash_balance"], Decimal("15000"))
        self.assertEqual(b["expenses"], Decimal("5000"))  # not double-counted as an expense
        self.assertEqual(b["allocated_savings"], Decimal("4000"))
        self.assertEqual(b["available_balance"], Decimal("11000"))
        self.assertEqual(Expense.objects.filter(owner=self.user).count(), 1)

    def test_cannot_allocate_more_than_available(self):
        with self.assertRaises(ValidationError):
            services.allocate(self.goal, Decimal("15000.01"))

    def test_release_and_completion(self):
        services.allocate(self.goal, Decimal("6000"))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, SavingsGoal.Status.COMPLETED)
        services.release(self.goal, Decimal("1000"))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, SavingsGoal.Status.ACTIVE)
        self.assertEqual(self.goal.saved_amount, Decimal("5000"))
        with self.assertRaises(ValidationError):
            services.release(self.goal, Decimal("5000.01"))

    def test_reversal_keeps_audit_trail(self):
        entry = services.allocate(self.goal, Decimal("2500"))
        reversal = services.reverse(entry, "typo")
        self.assertEqual(self.goal.saved_amount, Decimal("0"))
        self.assertEqual(SavingsContribution.objects.filter(goal=self.goal).count(), 2)
        self.assertEqual(reversal.reverses, entry)
        with self.assertRaises(ValidationError):
            services.reverse(entry)
        with self.assertRaises(ValidationError):
            services.reverse(reversal)

    def test_ledger_sum_matches_goal_totals(self):
        services.allocate(self.goal, Decimal("1000"))
        services.allocate(self.goal, Decimal("1500.50"))
        services.release(self.goal, Decimal("500.25"))
        total = sum(c.amount for c in self.goal.contributions.all())
        self.assertEqual(total, Decimal("2000.25"))
        self.assertEqual(balance_summary(self.user)["allocated_savings"], Decimal("2000.25"))


class SavingsViewTests(TestCase):
    def test_goal_ownership_enforced(self):
        owner = make_user("owner")
        goal = SavingsGoal.objects.create(owner=owner, name="Fees", target_amount=1000)
        make_user("intruder")
        self.client.login(username="intruder", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("savings:detail", args=[goal.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("savings:move", args=[goal.pk]), {"action": "allocate", "amount": "10"}).status_code, 404)

    def test_move_form_reports_errors(self):
        user = make_user("lucy")
        goal = SavingsGoal.objects.create(owner=user, name="Fees", target_amount=1000)
        self.client.login(username="lucy", password=PASSWORD)
        response = self.client.post(reverse("savings:move", args=[goal.pk]), {"action": "allocate", "amount": "10"}, follow=True)
        self.assertContains(response, "unallocated")
        self.assertEqual(goal.contributions.count(), 0)
