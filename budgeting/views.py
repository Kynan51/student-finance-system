from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import BudgetForm, CategoryLimitForm, ObligationForm
from .models import Budget, BudgetCategoryLimit, FixedObligation
from .services import budget_status
from .signals import check_budget_alerts


@login_required
@require_GET
def budget_list(request):
    statuses = [budget_status(b) for b in request.user.budgets.all()]
    active = [s for s in statuses if s["is_active"]]
    other = [s for s in statuses if not s["is_active"]]
    return render(request, "budgeting/list.html", {"active": active, "other": other})


@login_required
@require_http_methods(["GET", "POST"])
def budget_form(request, pk=None):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user) if pk else None
    form = BudgetForm(request.user, request.POST or None, instance=budget)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        check_budget_alerts(request.user)
        messages.success(request, "Budget saved.")
        return redirect("budgeting:detail", pk=obj.pk)
    return render(request, "budgeting/form.html", {"form": form, "budget": budget})


@login_required
@require_GET
def budget_detail(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    status = budget_status(budget)
    return render(
        request,
        "budgeting/detail.html",
        {
            "s": status,
            "limit_form": CategoryLimitForm(request.user, budget),
            "obligation_form": ObligationForm(request.user, budget),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    if request.method == "POST":
        budget.delete()
        messages.success(request, "Budget deleted. Your transactions were not affected.")
        return redirect("budgeting:list")
    return render(request, "budgeting/confirm_delete.html", {"budget": budget})


@login_required
@require_POST
def limit_add(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    form = CategoryLimitForm(request.user, budget, request.POST)
    if form.is_valid():
        limit = form.save(commit=False)
        limit.budget = budget
        limit.save()
        check_budget_alerts(request.user)
        messages.success(request, "Category limit added.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("budgeting:detail", pk=pk)


@login_required
@require_POST
def limit_delete(request, pk, limit_id):
    limit = get_object_or_404(BudgetCategoryLimit, pk=limit_id, budget__pk=pk, budget__owner=request.user)
    limit.delete()
    messages.success(request, "Category limit removed.")
    return redirect("budgeting:detail", pk=pk)


@login_required
@require_POST
def obligation_add(request, pk):
    budget = get_object_or_404(Budget, pk=pk, owner=request.user)
    form = ObligationForm(request.user, budget, request.POST)
    if form.is_valid():
        ob = form.save(commit=False)
        ob.budget = budget
        ob.save()
        messages.success(request, "Obligation added.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("budgeting:detail", pk=pk)


@login_required
@require_POST
def obligation_toggle(request, pk, ob_id):
    ob = get_object_or_404(FixedObligation, pk=ob_id, budget__pk=pk, budget__owner=request.user)
    ob.is_paid = not ob.is_paid
    ob.save(update_fields=["is_paid"])
    return redirect("budgeting:detail", pk=pk)


@login_required
@require_POST
def obligation_delete(request, pk, ob_id):
    ob = get_object_or_404(FixedObligation, pk=ob_id, budget__pk=pk, budget__owner=request.user)
    ob.delete()
    messages.success(request, "Obligation removed.")
    return redirect("budgeting:detail", pk=pk)
