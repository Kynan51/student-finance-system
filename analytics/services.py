"""
Single source of truth for the money arithmetic shown across the app.

Definitions (documented for the project defence):
  * total income      = sum of Income.amount
  * total expenses    = sum of Expense.amount
  * cash balance      = total income - total expenses
  * allocated savings = net sum of SavingsContribution.amount (virtual)
  * available balance = cash balance - allocated savings

Savings allocations are NOT expenses: they only earmark part of the cash
balance, so they are subtracted from "available" but never from "cash".
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from savings.models import SavingsContribution
from transactions.models import Expense, Income

ZERO = Decimal("0.00")

PERIOD_CHOICES = [
    ("week", "Last 7 days"),
    ("month", "This month"),
    ("semester", "This semester"),
    ("all", "All time"),
]


@dataclass
class DateRange:
    start: date | None
    end: date | None
    label: str

    def as_filter(self, field="date"):
        filters = {}
        if self.start:
            filters[f"{field}__gte"] = self.start
        if self.end:
            filters[f"{field}__lte"] = self.end
        return filters


def resolve_period(user, period, today=None):
    today = today or timezone.localdate()
    if period == "week":
        return DateRange(today - timedelta(days=6), today, "Last 7 days")
    if period == "month":
        return DateRange(today.replace(day=1), today, today.strftime("%B %Y"))
    if period == "semester":
        if user.semester_start:
            end = user.semester_end or today
            return DateRange(user.semester_start, end, "This semester")
        # No semester configured: assume a ~4-month semester ending today.
        return DateRange(today - timedelta(days=119), today, "Last 4 months (set semester dates in Settings)")
    return DateRange(None, None, "All time")


def _sum(qs, field="amount"):
    return qs.aggregate(total=Sum(field))["total"] or ZERO


def totals(user, date_range=None):
    filters = date_range.as_filter() if date_range else {}
    income = _sum(Income.objects.filter(owner=user, **filters))
    expenses = _sum(Expense.objects.filter(owner=user, **filters))
    savings = _sum(SavingsContribution.objects.filter(goal__owner=user, **filters))
    return {"income": income, "expenses": expenses, "net": income - expenses, "savings": savings}


def balance_summary(user):
    """All-time balances (a balance only makes sense over the full ledger)."""
    income = _sum(Income.objects.filter(owner=user))
    expenses = _sum(Expense.objects.filter(owner=user))
    allocated = _sum(SavingsContribution.objects.filter(goal__owner=user))
    cash = income - expenses
    return {
        "income": income,
        "expenses": expenses,
        "cash_balance": cash,
        "allocated_savings": allocated,
        "available_balance": cash - allocated,
    }


def category_breakdown(user, date_range=None):
    filters = date_range.as_filter() if date_range else {}
    rows = (
        Expense.objects.filter(owner=user, **filters)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    grand = sum((r["total"] for r in rows), ZERO)
    return [
        {
            "category": r["category__name"],
            "total": r["total"],
            "share": float(r["total"] / grand * 100) if grand else 0.0,
        }
        for r in rows
    ]


def income_breakdown(user, date_range=None):
    filters = date_range.as_filter() if date_range else {}
    rows = (
        Income.objects.filter(owner=user, **filters)
        .values("source__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return [{"source": r["source__name"], "total": r["total"]} for r in rows]


def monthly_trend(user, months=6, today=None):
    today = today or timezone.localdate()
    first_this = today.replace(day=1)
    # walk back (months-1) months
    year, month = first_this.year, first_this.month
    for _ in range(months - 1):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    start = date(year, month, 1)

    def by_month(model):
        rows = (
            model.objects.filter(owner=user, date__gte=start, date__lte=today)
            .annotate(m=TruncMonth("date"))
            .values("m")
            .annotate(total=Sum("amount"))
        )
        out = {}
        for r in rows:
            key = r["m"]
            if hasattr(key, "date"):
                key = key.date()
            out[(key.year, key.month)] = r["total"]
        return out

    inc, exp = by_month(Income), by_month(Expense)
    labels, income_vals, expense_vals = [], [], []
    y, m = start.year, start.month
    for _ in range(months):
        labels.append(date(y, m, 1).strftime("%b %Y"))
        income_vals.append(inc.get((y, m), ZERO))
        expense_vals.append(exp.get((y, m), ZERO))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return {"labels": labels, "income": income_vals, "expenses": expense_vals}


def daily_spending(user, date_range):
    """Daily expense totals across the range, including zero-spend days."""
    if not date_range.start:
        first = Expense.objects.filter(owner=user).order_by("date").values_list("date", flat=True).first()
        start = first or timezone.localdate()
    else:
        start = date_range.start
    end = date_range.end or timezone.localdate()
    rows = (
        Expense.objects.filter(owner=user, date__gte=start, date__lte=end)
        .values("date")
        .annotate(total=Sum("amount"))
    )
    lookup = {r["date"]: r["total"] for r in rows}
    labels, values = [], []
    day = start
    while day <= end:
        labels.append(day.isoformat())
        values.append(lookup.get(day, ZERO))
        day += timedelta(days=1)
    return {"labels": labels, "values": values}


def recent_transactions(user, limit=8):
    incomes = Income.objects.filter(owner=user).select_related("source").order_by("-date", "-created_at")[:limit]
    expenses = Expense.objects.filter(owner=user).select_related("category").order_by("-date", "-created_at")[:limit]
    merged = [
        {"type": "income", "date": i.date, "label": i.source.name, "description": i.description, "amount": i.amount, "obj": i, "created": i.created_at}
        for i in incomes
    ] + [
        {"type": "expense", "date": e.date, "label": e.category.name, "description": e.description, "amount": e.amount, "obj": e, "created": e.created_at}
        for e in expenses
    ]
    merged.sort(key=lambda t: (t["date"], t["created"]), reverse=True)
    return merged[:limit]
