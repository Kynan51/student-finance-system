"""
Budget utilisation is always computed from saved expenses at read time,
so it is automatically correct after any add / edit / delete.
Date ranges are inclusive at both ends.
"""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from transactions.models import Expense

ZERO = Decimal("0.00")

STATE_OK = "ok"
STATE_WARNING = "warning"
STATE_EXCEEDED = "exceeded"


def utilisation_state(spent, limit, threshold):
    if limit <= 0:
        return STATE_OK, 0.0
    pct = float(spent / limit * 100)
    if spent > limit:
        return STATE_EXCEEDED, pct
    if pct >= threshold:
        return STATE_WARNING, pct
    return STATE_OK, pct


def budget_expenses(budget):
    return Expense.objects.filter(
        owner=budget.owner, date__gte=budget.start_date, date__lte=budget.end_date
    )


def budget_status(budget, today=None):
    today = today or timezone.localdate()
    expenses = budget_expenses(budget)
    spent = expenses.aggregate(t=Sum("amount"))["t"] or ZERO
    state, pct = utilisation_state(spent, budget.total_limit, budget.warning_threshold)

    by_cat = {r["category"]: r["t"] for r in expenses.values("category").annotate(t=Sum("amount"))}
    categories = []
    for limit in budget.category_limits.select_related("category"):
        c_spent = by_cat.get(limit.category_id, ZERO)
        c_state, c_pct = utilisation_state(c_spent, limit.limit, budget.warning_threshold)
        categories.append(
            {
                "limit_obj": limit,
                "category": limit.category,
                "limit": limit.limit,
                "spent": c_spent,
                "remaining": limit.limit - c_spent,
                "percent": c_pct,
                "state": c_state,
            }
        )

    obligations = list(budget.obligations.select_related("category"))
    unpaid = sum((o.amount for o in obligations if not o.is_paid), ZERO)

    total_days = (budget.end_date - budget.start_date).days + 1
    if today < budget.start_date:
        elapsed = 0
    elif today > budget.end_date:
        elapsed = total_days
    else:
        elapsed = (today - budget.start_date).days + 1
    time_pct = (elapsed / total_days * 100) if total_days else 0

    remaining = budget.total_limit - spent
    days_left = max(total_days - elapsed, 0)
    return {
        "budget": budget,
        "spent": spent,
        "remaining": remaining,
        "percent": pct,
        "state": state,
        "categories": categories,
        "obligations": obligations,
        "unpaid_obligations": unpaid,
        "free_after_obligations": remaining - unpaid,
        "time_percent": time_pct,
        "days_left": days_left,
        "daily_allowance": (remaining - unpaid) / days_left if days_left and remaining > unpaid else ZERO,
        "is_active": budget.start_date <= today <= budget.end_date,
    }


def active_budgets(user, today=None):
    today = today or timezone.localdate()
    return user.budgets.filter(start_date__lte=today, end_date__gte=today)
