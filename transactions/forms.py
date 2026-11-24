from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone
from django.utils.text import slugify

from .models import Category, Expense, Income


def style(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "checkbox")
        else:
            widget.attrs.setdefault("class", "input")


class TransactionFormMixin:
    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= Decimal("0"):
            raise forms.ValidationError("Enter an amount greater than zero.")
        if amount > Decimal("10000000"):
            raise forms.ValidationError("That amount looks too large. Please check it.")
        return amount

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate() + timedelta(days=1):
            raise forms.ValidationError("Transactions cannot be dated in the future.")
        return value


class IncomeForm(TransactionFormMixin, forms.ModelForm):
    class Meta:
        model = Income
        fields = ("source", "amount", "date", "description", "reference")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}),
            "description": forms.TextInput(attrs={"placeholder": "e.g. HELB first disbursement"}),
        }
        labels = {"amount": "Amount (KSh)", "source": "Source"}

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = Category.visible_to(user, Category.Kind.INCOME)
        style(self)


class ExpenseForm(TransactionFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("category", "amount", "date", "payment_method", "description", "reference")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}),
            "description": forms.TextInput(attrs={"placeholder": "e.g. Lunch at the kibanda"}),
        }
        labels = {"amount": "Amount (KSh)"}

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.visible_to(user, Category.Kind.EXPENSE)
        style(self)


class TransactionFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Description or reference"}))
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False, empty_label="All")
    start = forms.DateField(required=False, label="From", widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, label="To", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, user, kind, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.visible_to(user, kind)
        self.fields["category"].label = "Source" if kind == Category.Kind.INCOME else "Category"
        style(self)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start"), cleaned.get("end")
        if start and end and end < start:
            self.add_error("end", "'To' must be on or after 'From'.")
        return cleaned


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "kind", "is_essential", "keywords")
        labels = {"is_essential": "Essential (e.g. rent, food, fees)"}
        widgets = {"keywords": forms.TextInput(attrs={"placeholder": "comma, separated, words"})}

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style(self)

    def clean(self):
        cleaned = super().clean()
        name, kind = cleaned.get("name"), cleaned.get("kind")
        if name and kind:
            slug = slugify(name)[:60]
            clash = Category.visible_to(self.user, kind).filter(slug=slug).exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("name", "You already have a category with this name.")
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.owner = self.user
        obj.slug = slugify(obj.name)[:60]
        if commit:
            obj.save()
        return obj


class PasteMessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "class": "input", "placeholder": "Paste an M-Pesa confirmation SMS here"}),
        max_length=1000,
    )
