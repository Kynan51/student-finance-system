from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from ai_engine.services import get_or_refresh_insights
from budgeting.services import active_budgets, budget_status
from savings.models import SavingsGoal

from . import services


def _period(request):
    period = request.GET.get("period", "month")
    valid = {key for key, _ in services.PERIOD_CHOICES}
    return period if period in valid else "month"


@login_required
@require_GET
def dashboard(request):
    user = request.user
    period = _period(request)
    date_range = services.resolve_period(user, period)
    balances = services.balance_summary(user)
    period_totals = services.totals(user, date_range)
    budgets = [budget_status(b) for b in active_budgets(user)[:3]]
    goals = user.savings_goals.filter(status=SavingsGoal.Status.ACTIVE).prefetch_related("contributions")[:4]
    insights = get_or_refresh_insights(user)
    top_insights = sorted(
        insights, key=lambda i: {"danger": 0, "warning": 1, "positive": 2, "info": 3}.get(i.severity, 4)
    )[:3]
    has_data = balances["income"] > 0 or balances["expenses"] > 0

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "period": period,
            "period_choices": services.PERIOD_CHOICES,
            "date_range": date_range,
            "balances": balances,
            "period_totals": period_totals,
            "budgets": budgets,
            "goals": goals,
            "recent": services.recent_transactions(user),
            "insights": top_insights,
            "has_data": has_data,
        },
    )


def _num(values):
    return [float(v) for v in values]


@login_required
@require_GET
def chart_data(request):
    """User-scoped JSON for Chart.js. Responses are marked no-store by middleware."""
    user = request.user
    period = _period(request)
    date_range = services.resolve_period(user, period)
    trend = services.monthly_trend(user, months=6)
    breakdown = services.category_breakdown(user, date_range)
    daily = services.daily_spending(user, date_range if period != "all" else services.resolve_period(user, "semester"))
    budgets = [budget_status(b) for b in active_budgets(user)]
    goals = user.savings_goals.filter(status=SavingsGoal.Status.ACTIVE).prefetch_related("contributions")
    period_totals = services.totals(user, date_range)

    return JsonResponse(
        {
            "period": period,
            "trend": {"labels": trend["labels"], "income": _num(trend["income"]), "expenses": _num(trend["expenses"])},
            "categories": {"labels": [r["category"] for r in breakdown], "values": [float(r["total"]) for r in breakdown]},
            "daily": {"labels": daily["labels"], "values": _num(daily["values"])},
            "income_vs_expense": {"income": float(period_totals["income"]), "expenses": float(period_totals["expenses"])},
            "budgets": [
                {"name": s["budget"].name, "percent": round(s["percent"], 1), "state": s["state"]} for s in budgets
            ],
            "goals": [
                {"name": g.name, "saved": float(g.saved_amount), "target": float(g.target_amount)} for g in goals
            ],
        }
    )
