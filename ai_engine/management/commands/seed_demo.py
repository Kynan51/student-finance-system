"""
Create a demo account filled with SYNTHETIC data so the app can be explored
immediately:   python manage.py seed_demo

Login:  username = demo   password = DemoPass2026!
Every synthetic record's description starts with [SYNTHETIC].
"""
import calendar
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from ai_engine.engine.synthetic import generate_student
from ai_engine.services import refresh_insights
from budgeting.models import Budget, BudgetCategoryLimit, FixedObligation
from savings import services as savings_services
from savings.models import SavingsGoal
from transactions.models import Category, Expense, Income

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "DemoPass2026!"


class Command(BaseCommand):
    help = "Create (or recreate) the 'demo' user with clearly-labelled synthetic data."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--seed", type=int, default=7)
        parser.add_argument("--keep", action="store_true", help="Do nothing if the demo user already exists.")

    @transaction.atomic
    def handle(self, *args, **opts):
        existing = User.objects.filter(username=DEMO_USERNAME).first()
        if existing and opts["keep"]:
            self.stdout.write(self.style.NOTICE("Demo user already exists; leaving it unchanged."))
            return
        if existing:
            existing.delete()

        today = timezone.localdate()
        days = opts["days"]
        start = today - timedelta(days=days - 1)
        user = User.objects.create_user(
            username=DEMO_USERNAME, email="demo@example.com", password=DEMO_PASSWORD,
            first_name="Demo", university="Mount Kenya University", year_of_study=3,
            semester_start=start, semester_end=today + timedelta(days=30),
        )

        cats = {(c.kind, c.slug): c for c in Category.objects.filter(owner__isnull=True)}
        incomes, expenses = generate_student(seed=opts["seed"], start=start, days=days)

        Income.objects.bulk_create([
            Income(owner=user, source=cats[("income", r.category)], amount=Decimal(str(r.amount)),
                   date=r.date, description=r.description)
            for r in incomes.itertuples() if r.date <= today
        ])
        Expense.objects.bulk_create([
            Expense(owner=user, category=cats[("expense", r.category)], amount=Decimal(str(r.amount)),
                    date=r.date, description=r.description,
                    payment_method="cash" if r.category == "food" and r.amount < 150 else "mpesa")
            for r in expenses.itertuples() if r.date <= today
        ])

        last_day = calendar.monthrange(today.year, today.month)[1]
        budget = Budget.objects.create(
            owner=user, name=f"{today:%B %Y} budget", period=Budget.Period.MONTHLY,
            start_date=today.replace(day=1), end_date=today.replace(day=last_day),
            total_limit=Decimal("17000"), warning_threshold=80, notes="[SYNTHETIC] demo budget",
        )
        for slug, limit in (("food", "6500"), ("entertainment", "1500"), ("transport", "1500"), ("internet", "1000")):
            BudgetCategoryLimit.objects.create(budget=budget, category=cats[("expense", slug)], limit=Decimal(limit))
        FixedObligation.objects.create(
            budget=budget, name="Exam card / clearance fee", amount=Decimal("1500"),
            due_date=today.replace(day=last_day), category=cats[("expense", "education")],
        )

        rent_goal = SavingsGoal.objects.create(
            owner=user, name="Next month's hostel rent", target_amount=Decimal("5000"),
            target_date=today.replace(day=last_day), priority=SavingsGoal.Priority.HIGH,
            description="[SYNTHETIC] virtual allocation for rent",
        )
        emergency = SavingsGoal.objects.create(
            owner=user, name="Emergency fund", target_amount=Decimal("10000"),
            priority=SavingsGoal.Priority.MEDIUM, description="[SYNTHETIC] virtual emergency buffer",
        )
        for goal, amount in ((rent_goal, Decimal("3000")), (emergency, Decimal("1500"))):
            try:
                savings_services.allocate(goal, amount, "[SYNTHETIC] demo allocation")
            except Exception:  # not enough available balance in this synthetic run
                pass

        refresh_insights(user, force=True)
        self.stdout.write(self.style.SUCCESS(
            f"Demo user ready -> username: {DEMO_USERNAME}  password: {DEMO_PASSWORD}  "
            f"({Income.objects.filter(owner=user).count()} income, {Expense.objects.filter(owner=user).count()} expenses, all SYNTHETIC)"
        ))
