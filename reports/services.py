import calendar
from datetime import date, timedelta

from django.utils import timezone

from analytics.services import DateRange, category_breakdown, income_breakdown, totals
from transactions.models import Expense, Income


def month_range(year, month):
    last = calendar.monthrange(year, month)[1]
    start, end = date(year, month, 1), date(year, month, last)
    return DateRange(start, end, start.strftime("%B %Y"))


def resolve_report_range(user, kind, month=None, start=None, end=None):
    today = timezone.localdate()
    if kind == "semester":
        if user.semester_start:
            return DateRange(user.semester_start, user.semester_end or today, "Semester")
        return DateRange(today - timedelta(days=119), today, "Last 4 months")
    if kind == "custom" and start and end:
        return DateRange(start, end, f"{start:%d %b %Y} – {end:%d %b %Y}")
    if month:
        return month_range(month.year, month.month)
    return month_range(today.year, today.month)


def build_report(user, date_range):
    t = totals(user, date_range)
    filters = date_range.as_filter()
    incomes = Income.objects.filter(owner=user, **filters).select_related("source").order_by("date")
    expenses = Expense.objects.filter(owner=user, **filters).select_related("category").order_by("date")
    days = (date_range.end - date_range.start).days + 1 if date_range.start and date_range.end else None
    return {
        "range": date_range,
        "totals": t,
        "categories": category_breakdown(user, date_range),
        "income_sources": income_breakdown(user, date_range),
        "incomes": incomes,
        "expenses": expenses,
        "days": days,
        "avg_daily_spend": (t["expenses"] / days) if days else None,
        "savings_rate": (float(t["savings"] / t["income"] * 100) if t["income"] else None),
        "generated": timezone.localtime(),
    }
