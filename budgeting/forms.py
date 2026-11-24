import calendar
from datetime import timedelta

from django import forms
from django.utils import timezone

from transactions.forms import style
from transactions.models import Category

from .models import Budget, BudgetCategoryLimit, FixedObligation


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ("name", "period", "start_date", "end_date", "total_limit", "warning_threshold", "notes")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "total_limit": forms.NumberInput(attrs={"step": "0.01", "min": "1"}),
            "warning_threshold": forms.NumberInput(attrs={"min": 10, "max": 100}),
        }
        labels = {"total_limit": "Overall limit (KSh)", "warning_threshold": "Warn me at (%)"}

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            today = timezone.localdate()
            last_day = calendar.monthrange(today.year, today.month)[1]
            self.fields["start_date"].initial = today.replace(day=1)
            self.fields["end_date"].initial = today.replace(day=last_day)
            self.fields["warning_threshold"].initial = user.budget_warning_default
            self.fields["name"].initial = today.strftime("%B %Y budget")
        style(self)

    def clean(self):
        cleaned = super().clean()
        start, end, period = cleaned.get("start_date"), cleaned.get("end_date"), cleaned.get("period")
        if start and end:
            if end < start:
                self.add_error("end_date", "End date must be on or after the start date.")
            elif (end - start) > timedelta(days=200):
                self.add_error("end_date", "A budget cannot be longer than about 6 months.")
            elif period == Budget.Period.MONTHLY and (end - start).days > 31:
                self.add_error("period", "A monthly budget should cover 31 days or fewer. Choose Semester or Custom.")
        return cleaned


class CategoryLimitForm(forms.ModelForm):
    class Meta:
        model = BudgetCategoryLimit
        fields = ("category", "limit")
        widgets = {"limit": forms.NumberInput(attrs={"step": "0.01", "min": "1"})}
        labels = {"limit": "Limit (KSh)"}

    def __init__(self, user, budget, *args, **kwargs):
        self.budget = budget
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.visible_to(user, Category.Kind.EXPENSE)
        style(self)

    def clean(self):
        cleaned = super().clean()
        cat, limit = cleaned.get("category"), cleaned.get("limit")
        if cat and BudgetCategoryLimit.objects.filter(budget=self.budget, category=cat).exclude(pk=self.instance.pk).exists():
            self.add_error("category", "This category already has a limit in this budget.")
        if limit and limit > self.budget.total_limit:
            self.add_error("limit", "A category limit cannot exceed the overall budget.")
        return cleaned


class ObligationForm(forms.ModelForm):
    class Meta:
        model = FixedObligation
        fields = ("name", "amount", "due_date", "category", "is_paid")
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "name": forms.TextInput(attrs={"placeholder": "e.g. Hostel rent"}),
        }
        labels = {"amount": "Amount (KSh)", "is_paid": "Already paid"}

    def __init__(self, user, budget, *args, **kwargs):
        self.budget = budget
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.visible_to(user, Category.Kind.EXPENSE)
        self.fields["category"].required = False
        style(self)
