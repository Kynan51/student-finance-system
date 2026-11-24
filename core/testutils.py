"""Small factories shared by the test suites."""
from datetime import date
from decimal import Decimal

from accounts.models import User
from transactions.models import Category, Expense, Income

PASSWORD = "Str0ng-Pass-2026!"


def make_user(username="amina", **extra):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, first_name=username.title(), **extra
    )


def cat(slug, kind="expense"):
    return Category.objects.get(owner__isnull=True, kind=kind, slug=slug)


def add_income(user, amount, on=None, slug="helb", description=""):
    return Income.objects.create(
        owner=user, source=cat(slug, "income"), amount=Decimal(str(amount)), date=on or date.today(), description=description
    )


def add_expense(user, amount, on=None, slug="food", description=""):
    return Expense.objects.create(
        owner=user, category=cat(slug), amount=Decimal(str(amount)), date=on or date.today(), description=description
    )
