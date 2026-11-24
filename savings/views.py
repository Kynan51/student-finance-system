from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from analytics.services import balance_summary

from . import services
from .forms import GoalForm, MovementForm
from .models import SavingsContribution, SavingsGoal


@login_required
@require_GET
def goal_list(request):
    goals = request.user.savings_goals.prefetch_related("contributions")
    return render(
        request,
        "savings/list.html",
        {
            "active": [g for g in goals if g.status == SavingsGoal.Status.ACTIVE],
            "completed": [g for g in goals if g.status == SavingsGoal.Status.COMPLETED],
            "archived": [g for g in goals if g.status == SavingsGoal.Status.ARCHIVED],
            "balances": balance_summary(request.user),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def goal_form(request, pk=None):
    goal = get_object_or_404(SavingsGoal, pk=pk, owner=request.user) if pk else None
    form = GoalForm(request.POST or None, instance=goal)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        obj.refresh_status()
        messages.success(request, "Savings goal saved.")
        return redirect("savings:detail", pk=obj.pk)
    return render(request, "savings/form.html", {"form": form, "goal": goal})


@login_required
@require_GET
def goal_detail(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, owner=request.user)
    entries = goal.contributions.select_related("reverses").all()
    return render(
        request,
        "savings/detail.html",
        {"goal": goal, "entries": entries, "form": MovementForm(), "balances": balance_summary(request.user)},
    )


@login_required
@require_POST
def goal_move(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, owner=request.user)
    form = MovementForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        try:
            if data["action"] == "allocate":
                services.allocate(goal, data["amount"], data["note"])
                messages.success(request, f"KSh {data['amount']:,.2f} set aside for {goal.name}.")
            else:
                services.release(goal, data["amount"], data["note"])
                messages.success(request, f"KSh {data['amount']:,.2f} released back to your available balance.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "Enter a valid amount.")
    return redirect("savings:detail", pk=pk)


@login_required
@require_POST
def entry_reverse(request, pk, entry_id):
    entry = get_object_or_404(SavingsContribution, pk=entry_id, goal__pk=pk, goal__owner=request.user)
    try:
        services.reverse(entry, request.POST.get("reason", "")[:200])
        messages.success(request, "Entry reversed. The original stays in the history for your records.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect("savings:detail", pk=pk)


@login_required
@require_POST
def goal_archive(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, owner=request.user)
    if goal.status == SavingsGoal.Status.ARCHIVED:
        goal.status = SavingsGoal.Status.ACTIVE
        goal.save(update_fields=["status"])
        goal.refresh_status()
        messages.success(request, "Goal restored.")
    else:
        if goal.saved_amount > 0:
            services.release(goal, goal.saved_amount, "Released when goal was archived")
        goal.status = SavingsGoal.Status.ARCHIVED
        goal.save(update_fields=["status"])
        messages.success(request, "Goal archived and its allocation released to your available balance.")
    return redirect("savings:list")
