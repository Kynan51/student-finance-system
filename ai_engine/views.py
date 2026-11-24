from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import FinancialInsight, Notification
from .services import DISCLAIMER, refresh_insights

SEVERITY_ORDER = {"danger": 0, "warning": 1, "positive": 2, "info": 3}


@login_required
@require_GET
def insights(request):
    current = sorted(refresh_insights(request.user), key=lambda i: SEVERITY_ORDER.get(i.severity, 9))
    forecast = next((i for i in current if i.kind == FinancialInsight.Kind.FORECAST), None)
    history = (
        request.user.insights.exclude(pk__in=[i.pk for i in current])
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "insights/insights.html",
        {"insights": current, "forecast": forecast, "history": history, "disclaimer": DISCLAIMER},
    )


@login_required
@require_POST
def insights_refresh(request):
    refresh_insights(request.user, force=True)
    messages.success(request, "Insights recalculated from your latest records.")
    return redirect("ai_engine:insights")


@login_required
@require_GET
def notifications(request):
    items = request.user.notifications.all()[:50]
    return render(request, "insights/notifications.html", {"items": items})


@login_required
@require_POST
def notification_read(request, pk):
    item = get_object_or_404(Notification, pk=pk, owner=request.user)
    item.is_read = True
    item.save(update_fields=["is_read"])
    if item.link and item.link.startswith("/"):
        return redirect(item.link)
    return redirect("ai_engine:notifications")


@login_required
@require_POST
def notifications_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("ai_engine:notifications")
