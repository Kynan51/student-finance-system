from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from analytics.services import balance_summary
from core.testutils import PASSWORD, add_expense, add_income, cat, make_user

from .models import Category, Expense, Income
from .parsers import ParseError, parse_mpesa_message


class LedgerCrudTests(TestCase):
    def setUp(self):
        self.user = make_user("achieng")
        self.client.login(username="achieng", password=PASSWORD)

    def test_add_edit_delete_expense_updates_totals(self):
        add_income(self.user, "10000")
        self.client.post(reverse("transactions:expense_create"), {
            "category": cat("food").pk, "amount": "250.50", "date": date.today().isoformat(),
            "payment_method": "mpesa", "description": "Lunch",
        })
        self.assertEqual(balance_summary(self.user)["cash_balance"], Decimal("9749.50"))

        expense = Expense.objects.get(owner=self.user)
        self.client.post(reverse("transactions:expense_update", args=[expense.pk]), {
            "category": cat("food").pk, "amount": "300.00", "date": date.today().isoformat(), "payment_method": "cash",
        })
        self.assertEqual(balance_summary(self.user)["cash_balance"], Decimal("9700.00"))

        self.client.post(reverse("transactions:expense_delete", args=[expense.pk]))
        self.assertEqual(balance_summary(self.user)["cash_balance"], Decimal("10000.00"))

    def test_decimal_precision_no_float_drift(self):
        for _ in range(10):
            add_expense(self.user, "0.10")
        self.assertEqual(balance_summary(self.user)["expenses"], Decimal("1.00"))

    def test_invalid_amounts_rejected(self):
        for amount in ("0", "-50", "abc", "20000000"):
            response = self.client.post(reverse("transactions:income_create"), {
                "source": cat("helb", "income").pk, "amount": amount, "date": date.today().isoformat(),
            })
            self.assertEqual(response.status_code, 200, amount)
            self.assertIn("amount", response.context["form"].errors, amount)
        self.assertEqual(Income.objects.count(), 0)

    def test_future_date_rejected(self):
        response = self.client.post(reverse("transactions:expense_create"), {
            "category": cat("food").pk, "amount": "100", "date": (date.today() + timedelta(days=5)).isoformat(),
            "payment_method": "cash",
        })
        self.assertIn("date", response.context["form"].errors)

    def test_filters_search_and_pagination(self):
        for i in range(20):
            add_expense(self.user, 100, on=date(2026, 10, 1) + timedelta(days=i), slug="food", description=f"lunch {i}")
        add_expense(self.user, 500, on=date(2026, 10, 5), slug="transport", description="Bus to Thika")
        response = self.client.get(reverse("transactions:expense_list"), {"q": "thika"})
        self.assertEqual(response.context["record_count"], 1)
        response = self.client.get(reverse("transactions:expense_list"), {"category": cat("food").pk, "start": "2026-10-01", "end": "2026-10-10"})
        self.assertEqual(response.context["record_count"], 10)
        self.assertEqual(response.context["filtered_total"], Decimal("1000"))
        page2 = self.client.get(reverse("transactions:expense_list"), {"page": 2})
        self.assertEqual(len(page2.context["page_obj"].object_list), 6)

    def test_custom_category_visible_only_to_owner(self):
        self.client.post(reverse("transactions:categories"), {"name": "Church offering", "kind": "expense", "keywords": "church,offering"})
        mine = Category.objects.get(owner=self.user, slug="church-offering")
        other = make_user("other")
        self.assertIn(mine, Category.visible_to(self.user, "expense"))
        self.assertNotIn(mine, Category.visible_to(other, "expense"))


class OwnershipTests(TestCase):
    """A student must never read or change another student's records."""

    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.bob_expense = add_expense(self.bob, 999)
        self.bob_income = add_income(self.bob, 5000)
        self.client.login(username="alice", password=PASSWORD)

    def test_cannot_view_edit_or_delete_others_records(self):
        for name, pk in (
            ("transactions:expense_update", self.bob_expense.pk),
            ("transactions:expense_delete", self.bob_expense.pk),
            ("transactions:income_update", self.bob_income.pk),
            ("transactions:income_delete", self.bob_income.pk),
        ):
            self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404, name)
            self.assertEqual(self.client.post(reverse(name, args=[pk]), {"amount": "1"}).status_code, 404, name)
        self.assertTrue(Expense.objects.filter(pk=self.bob_expense.pk, amount=999).exists())

    def test_lists_and_totals_exclude_others(self):
        response = self.client.get(reverse("transactions:expense_list"))
        self.assertEqual(response.context["record_count"], 0)
        self.assertNotContains(response, "999")

    def test_owner_cannot_be_injected_via_post(self):
        self.client.post(reverse("transactions:expense_create"), {
            "category": cat("food").pk, "amount": "50", "date": date.today().isoformat(),
            "payment_method": "cash", "owner": self.bob.pk,
        })
        self.assertEqual(Expense.objects.filter(owner=self.alice).count(), 1)
        self.assertEqual(Expense.objects.filter(owner=self.bob).count(), 1)

    def test_cannot_use_another_users_private_category(self):
        private = Category.objects.create(owner=self.bob, name="Bob only", slug="bob-only", kind="expense")
        response = self.client.post(reverse("transactions:expense_create"), {
            "category": private.pk, "amount": "50", "date": date.today().isoformat(), "payment_method": "cash",
        })
        self.assertIn("category", response.context["form"].errors)


class MpesaParserTests(SimpleTestCase):
    def test_paid_to_till(self):
        t = parse_mpesa_message(
            "QKL3ABC123 Confirmed. Ksh350.00 paid to MAMA OCHIENG KIBANDA. on 20/11/26 at 1:15 PM.New M-PESA balance is Ksh1,200.00."
        )
        self.assertEqual((t.kind, t.amount, t.date, t.reference), ("expense", Decimal("350.00"), date(2026, 11, 20), "QKL3ABC123"))
        self.assertIn("Kibanda", t.description)

    def test_received_strips_phone_number(self):
        t = parse_mpesa_message(
            "QAB1234XYZ Confirmed.You have received Ksh3,000.00 from JANE WANJIRU 0712345678 on 1/11/26 at 9:02 AM New M-PESA balance is Ksh4,000.00."
        )
        self.assertEqual(t.kind, "income")
        self.assertEqual(t.amount, Decimal("3000.00"))
        self.assertNotIn("0712345678", t.description)
        self.assertNotIn("4,000", t.description)

    def test_sent_to_person_and_paybill(self):
        sent = parse_mpesa_message("QQQ1112223 Confirmed. Ksh1,250.00 sent to JOHN DOE 0722000111 on 12/11/26 at 3:15 PM. New M-PESA balance is Ksh500.00.")
        self.assertEqual((sent.kind, sent.amount), ("expense", Decimal("1250.00")))
        paybill = parse_mpesa_message("QRS0001112 Confirmed. Ksh4,500.00 sent to SUNRISE HOSTEL for account ROOM12 on 02/11/2026 at 8:00 AM New M-PESA balance")
        self.assertEqual(paybill.counterparty, "Sunrise Hostel")
        self.assertEqual(paybill.date, date(2026, 11, 2))

    def test_airtime_and_withdrawal(self):
        airtime = parse_mpesa_message("QAT9998887 confirmed.You bought Ksh100.00 of airtime on 10/11/26 at 7:45 PM.")
        self.assertEqual((airtime.kind, airtime.amount), ("expense", Decimal("100.00")))
        withdraw = parse_mpesa_message("QWD5556667 Confirmed.on 9/11/26 at 2:00 PMWithdraw Ksh2,000.00 from 123456 - JUJA AGENT New M-PESA balance is Ksh300.00.")
        self.assertEqual(withdraw.kind, "withdrawal")
        self.assertTrue(withdraw.warnings)

    def test_unrecognised_and_empty(self):
        with self.assertRaises(ParseError):
            parse_mpesa_message("hello there")
        with self.assertRaises(ParseError):
            parse_mpesa_message("   ")


class ParseEndpointTests(TestCase):
    def test_parse_endpoint_suggests_category(self):
        make_user("p")
        self.client.login(username="p", password=PASSWORD)
        response = self.client.post(
            reverse("transactions:parse_message"),
            data='{"message": "QKL3ABC123 Confirmed. Ksh80.00 paid to CITY MATATU SACCO. on 20/11/26 at 1:15 PM."}',
            content_type="application/json",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["transaction"]["category_name"], "Transport")
        self.assertEqual(Expense.objects.count(), 0)  # parsing never saves
