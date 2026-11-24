"""
Income and expense ledger views.

Every query is filtered by `owner=request.user`; objects are fetched with
get_object_or_404(..., owner=request.user) so guessing another student's
record ID returns 404 rather than leaking data.
"""
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ai_engine.engine.categorizer import suggest_category

from .forms import CategoryForm, ExpenseForm, IncomeForm, PasteMessageForm, TransactionFilterForm
from .models import Category, Expense, Income
from .parsers import ParseError, parse_mpesa_message

PAGE_SIZE = 15

LEDGERS = {
    "income": {
        "model": Income,
        "form": IncomeForm,
        "kind": Category.Kind.INCOME,
        "category_field": "source",
        "title": "Income",
        "singular": "income record",
        "list_url": "transactions:income_list",
    },
    "expense": {
        "model": Expense,
        "form": ExpenseForm,
        "kind": Category.Kind.EXPENSE,
        "category_field": "category",
        "title": "Expenses",
        "singular": "expense",
        "list_url": "transactions:expense_list",
    },
}


def _ledger_list(request, ledger_key):
    cfg = LEDGERS[ledger_key]
    qs = cfg["model"].objects.filter(owner=request.user).select_related(cfg["category_field"])
    filter_form = TransactionFilterForm(request.user, cfg["kind"], request.GET or None)

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data.get("q"):
            qs = qs.filter(Q(description__icontains=data["q"]) | Q(reference__icontains=data["q"]))
        if data.get("category"):
            qs = qs.filter(**{cfg["category_field"]: data["category"]})
        if data.get("start"):
            qs = qs.filter(date__gte=data["start"])
        if data.get("end"):
            qs = qs.filter(date__lte=data["end"])

    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "transactions/list.html",
        {
            "ledger": ledger_key,
            "cfg": cfg,
            "page_obj": page,
            "filter_form": filter_form,
            "filtered_total": total,
            "record_count": paginator.count,
            "querystring": query.urlencode(),
            "paste_form": PasteMessageForm() if ledger_key == "expense" else None,
        },
    )


def _ledger_form(request, ledger_key, pk=None):
    cfg = LEDGERS[ledger_key]
    instance = get_object_or_404(cfg["model"], pk=pk, owner=request.user) if pk else None
    initial = {}
    if not instance:
        for key in ("amount", "date", "description", "reference"):
            if request.GET.get(key):
                initial[key] = request.GET[key]
        cat = request.GET.get("category")
        if cat:
            initial[cfg["category_field"]] = cat
    form = cfg["form"](request.user, request.POST or None, instance=instance, initial=initial)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        verb = "updated" if instance else "added"
        messages.success(request, f"{cfg['singular'].capitalize()} {verb}.")
        if "save_another" in request.POST:
            return redirect(request.path)
        return redirect(cfg["list_url"])

    return render(
        request,
        "transactions/form.html",
        {"form": form, "cfg": cfg, "ledger": ledger_key, "instance": instance},
    )


def _ledger_delete(request, ledger_key, pk):
    cfg = LEDGERS[ledger_key]
    obj = get_object_or_404(cfg["model"], pk=pk, owner=request.user)
    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{cfg['singular'].capitalize()} deleted.")
        return redirect(cfg["list_url"])
    return render(request, "transactions/confirm_delete.html", {"obj": obj, "cfg": cfg, "ledger": ledger_key})


# ---- Income -------------------------------------------------------------
@login_required
@require_GET
def income_list(request):
    return _ledger_list(request, "income")


@login_required
@require_http_methods(["GET", "POST"])
def income_create(request):
    return _ledger_form(request, "income")


@login_required
@require_http_methods(["GET", "POST"])
def income_update(request, pk):
    return _ledger_form(request, "income", pk)


@login_required
@require_http_methods(["GET", "POST"])
def income_delete(request, pk):
    return _ledger_delete(request, "income", pk)


# ---- Expenses -----------------------------------------------------------
@login_required
@require_GET
def expense_list(request):
    return _ledger_list(request, "expense")


@login_required
@require_http_methods(["GET", "POST"])
def expense_create(request):
    return _ledger_form(request, "expense")


@login_required
@require_http_methods(["GET", "POST"])
def expense_update(request, pk):
    return _ledger_form(request, "expense", pk)


@login_required
@require_http_methods(["GET", "POST"])
def expense_delete(request, pk):
    return _ledger_delete(request, "expense", pk)


# ---- JSON helpers used by static/js/forms.js -----------------------------
@login_required
@require_POST
def parse_message(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        payload = {}
    message = (payload.get("message") or request.POST.get("message") or "")[:1000]
    try:
        parsed = parse_mpesa_message(message)
    except ParseError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    data = parsed.as_dict()
    if parsed.kind in ("income", "expense"):
        categories = Category.visible_to(request.user, parsed.kind)
        guess = suggest_category(f"{parsed.counterparty} {parsed.description}", categories)
        data["category_id"] = guess.pk if guess else None
        data["category_name"] = guess.name if guess else None
    return JsonResponse({"ok": True, "transaction": data})


@login_required
@require_GET
def suggest(request):
    text = request.GET.get("q", "")[:200]
    kind = request.GET.get("kind", Category.Kind.EXPENSE)
    if kind not in Category.Kind.values:
        kind = Category.Kind.EXPENSE
    guess = suggest_category(text, Category.visible_to(request.user, kind))
    return JsonResponse(
        {"category_id": guess.pk if guess else None, "category_name": guess.name if guess else None}
    )


# ---- Categories ---------------------------------------------------------
@login_required
@require_http_methods(["GET", "POST"])
def categories(request):
    form = CategoryForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category added.")
        return redirect("transactions:categories")
    system = Category.objects.filter(owner__isnull=True)
    own = Category.objects.filter(owner=request.user)
    return render(
        request, "transactions/categories.html", {"form": form, "system_categories": system, "own_categories": own}
    )


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)
    try:
        category.delete()
        messages.success(request, "Category deleted.")
    except ProtectedError:
        messages.error(request, "This category is used by saved transactions or budgets, so it cannot be deleted.")
    return redirect("transactions:categories")
