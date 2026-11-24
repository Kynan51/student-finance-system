"""
Django glue for the analytics engine.

Insights are generated only when the student's data has meaningfully
changed: a fingerprint of the ledger (record counts + latest edit times +
today's date) is compared with the fingerprint stored on the latest insight
batch. Page loads with unchanged data reuse the stored insights instead of
re-running the models.
"""
import hashlib
from datetime import timedelta

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone

from analytics.services import balance_summary
from budgeting.services import STATE_EXCEEDED, STATE_WARNING, active_budgets, budget_status
from savings.models import SavingsContribution
from transactions.models import Expense, Income

from .engine.baseline import compute_baseline, daily_series
from .engine.forecasting import backtest, get_model, select_model, InsufficientData
from .engine.patterns import category_trends, detect_anomalies
from .models import FinancialInsight, Notification

KEEP_BATCHES = 10

DISCLAIMER = (
    "Estimates are based only on the transactions you have recorded. "
    "They are not guarantees and are not professional financial advice."
)


def data_fingerprint(user, today=None):
    today = today or timezone.localdate()
    parts = [str(today)]
    for qs in (
        Income.objects.filter(owner=user),
        Expense.objects.filter(owner=user),
        SavingsContribution.objects.filter(goal__owner=user),
    ):
        agg = qs.aggregate(n=Count("id"), s=Sum("amount"))
        latest = qs.aggregate(m=Max("created_at"))["m"]
        parts += [str(agg["n"]), str(agg["s"]), str(latest)]
    for model in (Income, Expense):
        parts.append(str(model.objects.filter(owner=user).aggregate(m=Max("updated_at"))["m"]))
    budgets = user.budgets.aggregate(n=Count("id"), s=Sum("total_limit"))
    parts += [str(budgets["n"]), str(budgets["s"])]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def expense_frame(user):
    rows = Expense.objects.filter(owner=user).values("id", "date", "amount", "category__name", "description")
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(columns=["id", "date", "amount", "category", "description"])
    return frame.rename(columns={"category__name": "category"})


def _reliability(days, n_expenses, rel_mae=None):
    min_days = settings.AI_MIN_DAYS_FOR_FORECAST
    if days < min_days or n_expenses < 10:
        return FinancialInsight.Reliability.LOW
    if days >= 60 and rel_mae is not None and rel_mae <= 0.25:
        return FinancialInsight.Reliability.HIGH
    if days >= 30 and (rel_mae is None or rel_mae <= 0.5):
        return FinancialInsight.Reliability.MEDIUM
    return FinancialInsight.Reliability.LOW


def build_insights(user, today=None):
    """Return a list of unsaved insight dicts. Pure computation, no writes."""
    today = today or timezone.localdate()
    horizon = settings.AI_FORECAST_HORIZON_DAYS
    expenses = expense_frame(user)
    balances = balance_summary(user)
    available = float(balances["available_balance"])
    insights = []

    if expenses.empty:
        insights.append(
            dict(
                kind=FinancialInsight.Kind.DATA, severity=FinancialInsight.Severity.INFO,
                title="Add a few expenses to unlock insights",
                message="Record your income and daily expenses for at least two weeks. "
                "The engine needs real history before it can estimate your runway.",
                metrics={"expenses_recorded": 0}, assumptions=DISCLAIMER,
                reliability=FinancialInsight.Reliability.LOW,
            )
        )
        return insights

    first_day = pd.to_datetime(expenses["date"]).min().date()
    daily = daily_series(expenses, first_day, today)
    n_exp = len(expenses)
    days = len(daily)

    unpaid = 0.0
    for budget in active_budgets(user, today):
        unpaid += float(sum(o.amount for o in budget.obligations.all() if not o.is_paid and o.due_date >= today))

    base = compute_baseline(daily, available, today, horizon_days=horizon, upcoming_obligations=unpaid)

    # ---------- Model evaluation and forecast ----------
    scores, mean_actual = backtest(daily, horizon=7)
    chosen, reason = select_model(scores)
    model = get_model(chosen)
    try:
        forecast_spend = model.predict(daily, horizon)
        model_used = model.label
    except InsufficientData:
        forecast_spend = base.projected_spending
        model_used = f"Average daily spending ({base.burn_rate_basis})"
    chosen_score = scores.get(chosen)
    rel_mae = (chosen_score.mae / mean_actual) if chosen_score and chosen_score.mae and mean_actual else None
    reliability = _reliability(days, n_exp, rel_mae)
    projected_balance = available - forecast_spend - unpaid

    if days < settings.AI_MIN_DAYS_FOR_FORECAST:
        insights.append(
            dict(
                kind=FinancialInsight.Kind.DATA, severity=FinancialInsight.Severity.INFO,
                title="Early estimates only",
                message=f"You have {days} day(s) of history. Forecasts become more meaningful after "
                f"{settings.AI_MIN_DAYS_FOR_FORECAST} days of regular records.",
                metrics={"days_of_history": days, "expenses_recorded": n_exp},
                assumptions=DISCLAIMER, reliability=FinancialInsight.Reliability.LOW,
            )
        )

    # ---------- Runway ----------
    if base.burn_rate > 0:
        runway_msg = (
            f"At your recent spending rate of about KSh {base.burn_rate:,.0f} per day ({base.burn_rate_basis}), "
            f"your available balance of KSh {available:,.0f} would last roughly {base.runway_days:,.0f} days"
            f" (around {base.runway_date:%d %b %Y})."
        )
        severity = FinancialInsight.Severity.INFO
        if available <= 0:
            severity = FinancialInsight.Severity.DANGER
            runway_msg = "Your recorded spending and savings allocations exceed your recorded income. " \
                         "Check for missing income records or release some savings allocations."
        elif base.runway_days < 14:
            severity = FinancialInsight.Severity.WARNING
        insights.append(
            dict(
                kind=FinancialInsight.Kind.RUNWAY, severity=severity, title="Estimated financial runway",
                message=runway_msg, metrics=base.as_dict(),
                assumptions="Assumes you keep spending at the recent rate and receive no new income. " + DISCLAIMER,
                reliability=reliability,
            )
        )

    # ---------- Shortfall before semester end ----------
    sem_end = user.semester_end
    if sem_end and sem_end > today and base.burn_rate > 0:
        days_to_end = (sem_end - today).days
        needed = base.burn_rate * days_to_end + unpaid
        gap = needed - available
        if gap > 0:
            insights.append(
                dict(
                    kind=FinancialInsight.Kind.SHORTFALL, severity=FinancialInsight.Severity.DANGER,
                    title="Possible shortfall before semester ends",
                    message=f"Your semester ends in {days_to_end} days. At the current rate you would need about "
                    f"KSh {needed:,.0f} but have KSh {available:,.0f} available, a gap of roughly KSh {gap:,.0f}. "
                    f"Cutting about KSh {gap / days_to_end:,.0f} per day would close it.",
                    metrics={"days_to_semester_end": days_to_end, "needed": round(needed, 2), "available": round(available, 2),
                             "gap": round(gap, 2), "daily_cut_needed": round(gap / days_to_end, 2), "unpaid_obligations": round(unpaid, 2)},
                    assumptions="Assumes no further income this semester. " + DISCLAIMER, reliability=reliability,
                )
            )
        else:
            insights.append(
                dict(
                    kind=FinancialInsight.Kind.SHORTFALL, severity=FinancialInsight.Severity.POSITIVE,
                    title="On track to reach semester end",
                    message=f"At your current pace your available balance should cover the {days_to_end} days left "
                    f"in the semester with about KSh {-gap:,.0f} to spare.",
                    metrics={"days_to_semester_end": days_to_end, "surplus": round(-gap, 2)},
                    assumptions="Assumes spending continues at the recent rate. " + DISCLAIMER, reliability=reliability,
                )
            )

    # ---------- Forecast with model comparison ----------
    insights.append(
        dict(
            kind=FinancialInsight.Kind.FORECAST,
            severity=FinancialInsight.Severity.WARNING if projected_balance < 0 else FinancialInsight.Severity.INFO,
            title=f"Next {horizon} days: estimated spending",
            message=f"Expected spending over the next {horizon} days is about KSh {forecast_spend:,.0f}, "
            f"leaving an estimated balance of KSh {projected_balance:,.0f}"
            + (f" after KSh {unpaid:,.0f} of unpaid obligations." if unpaid else ".")
            + (f" {reason}" if model_used in reason else f" Method: {model_used}. {reason}"),
            metrics={
                "forecast_spending": round(forecast_spend, 2), "projected_balance": round(projected_balance, 2),
                "unpaid_obligations": round(unpaid, 2), "model_selected": chosen,
                "relative_mae": None if rel_mae is None else round(rel_mae, 3),
                "mean_actual_7day_spend": round(mean_actual, 2),
                "model_scores": [s.as_dict() for s in scores.values()],
            },
            assumptions="Models were compared with a rolling-origin backtest on your own history "
            "(7-day-ahead MAE in KSh). " + DISCLAIMER,
            reliability=reliability,
        )
    )

    # ---------- Category trends ----------
    for change in category_trends(expenses, today)[:3]:
        up = change["change"] > 0
        pct = f" ({change['change_pct']:+.0f}%)" if change["change_pct"] is not None else ""
        insights.append(
            dict(
                kind=FinancialInsight.Kind.TREND,
                severity=FinancialInsight.Severity.WARNING if up else FinancialInsight.Severity.POSITIVE,
                title=f"{change['category']} spending {'up' if up else 'down'}",
                message=f"You spent KSh {change['current']:,.0f} on {change['category']} in the last "
                f"{change['window_days']} days, compared with KSh {change['previous']:,.0f} in the "
                f"{change['window_days']} days before{pct}.",
                metrics=change,
                assumptions="Compares two equal back-to-back periods of recorded expenses.",
                reliability=FinancialInsight.Reliability.MEDIUM if n_exp >= 20 else FinancialInsight.Reliability.LOW,
            )
        )

    # ---------- Unusual spending ----------
    for anomaly in detect_anomalies(expenses, today)[:3]:
        insights.append(
            dict(
                kind=FinancialInsight.Kind.ANOMALY, severity=FinancialInsight.Severity.WARNING,
                title=f"Unusual {anomaly['category']} expense",
                message=f"KSh {anomaly['amount']:,.0f} on {anomaly['date']} is much higher than your typical "
                f"{anomaly['category']} expense of about KSh {anomaly['typical']:,.0f}. If it was planned, you can ignore this.",
                metrics=anomaly,
                assumptions=f"Flagged using a robust z-score (median/MAD) over {anomaly['sample_size']} {anomaly['category']} records.",
                reliability=FinancialInsight.Reliability.MEDIUM,
            )
        )

    # ---------- Budget alerts ----------
    for budget in active_budgets(user, today):
        status = budget_status(budget, today)
        if status["state"] in (STATE_WARNING, STATE_EXCEEDED):
            ahead = status["percent"] - status["time_percent"]
            insights.append(
                dict(
                    kind=FinancialInsight.Kind.BUDGET,
                    severity=FinancialInsight.Severity.DANGER if status["state"] == STATE_EXCEEDED else FinancialInsight.Severity.WARNING,
                    title=f"{budget.name}: {status['percent']:.0f}% used",
                    message=f"You have used {status['percent']:.0f}% of this budget with {status['time_percent']:.0f}% "
                    f"of the period gone" + (f", {ahead:.0f} points ahead of pace." if ahead > 0 else "."),
                    metrics={"spent": float(status["spent"]), "limit": float(budget.total_limit),
                             "percent_used": round(status["percent"], 1), "percent_time": round(status["time_percent"], 1)},
                    assumptions="Calculated from saved expenses inside the budget dates.",
                    reliability=FinancialInsight.Reliability.HIGH,
                )
            )

    # ---------- Essentials vs non-essentials ----------
    recent = expenses[pd.to_datetime(expenses["date"]).dt.date >= today - timedelta(days=29)]
    if not recent.empty:
        essential_names = set(
            Expense.objects.filter(owner=user, category__is_essential=True).values_list("category__name", flat=True)
        )
        total = float(recent["amount"].astype(float).sum())
        non_ess = float(recent[~recent["category"].isin(essential_names)]["amount"].astype(float).sum())
        share = non_ess / total * 100 if total else 0
        if share >= 35:
            insights.append(
                dict(
                    kind=FinancialInsight.Kind.CATEGORY, severity=FinancialInsight.Severity.WARNING,
                    title="Non-essential spending is high",
                    message=f"{share:.0f}% of your last 30 days of spending (KSh {non_ess:,.0f}) went to non-essential "
                    "categories such as entertainment and personal items. Moving part of it to a savings goal "
                    "would protect rent and food money.",
                    metrics={"non_essential_share_pct": round(share, 1), "non_essential_total": round(non_ess, 2), "total_30d": round(total, 2)},
                    assumptions="Essential categories are those marked essential (food, accommodation, transport, education, internet).",
                    reliability=FinancialInsight.Reliability.MEDIUM,
                )
            )
    return insights


@transaction.atomic
def refresh_insights(user, force=False, today=None):
    today = today or timezone.localdate()
    fingerprint = data_fingerprint(user, today)
    latest = user.insights.order_by("-created_at").first()
    if latest and latest.data_fingerprint == fingerprint and not force:
        return list(user.insights.filter(data_fingerprint=fingerprint))

    created = [
        FinancialInsight.objects.create(owner=user, data_fingerprint=fingerprint, **data)
        for data in build_insights(user, today)
    ]

    # Keep a short dated history of insight batches.
    fingerprints = list(
        user.insights.order_by("-created_at").values_list("data_fingerprint", flat=True).distinct()
    )
    seen = []
    for fp in fingerprints:
        if fp not in seen:
            seen.append(fp)
    if len(seen) > KEEP_BATCHES:
        user.insights.filter(data_fingerprint__in=seen[KEEP_BATCHES:]).delete()

    if user.notify_insight_alerts:
        for insight in created:
            if insight.severity in (FinancialInsight.Severity.WARNING, FinancialInsight.Severity.DANGER) \
                    and insight.kind not in (FinancialInsight.Kind.BUDGET,):
                key = f"insight:{insight.kind}:{insight.title}:{today.isoformat()}"
                if not Notification.objects.filter(owner=user, dedupe_key=key).exists():
                    Notification.objects.create(
                        owner=user,
                        level=Notification.Level.DANGER if insight.severity == "danger" else Notification.Level.WARNING,
                        title=insight.title, message=insight.message[:300], link="/insights/", dedupe_key=key,
                    )
    return created


def get_or_refresh_insights(user):
    return refresh_insights(user, force=False)
