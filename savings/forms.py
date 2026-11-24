from decimal import Decimal

from django import forms
from django.utils import timezone

from transactions.forms import style

from .models import SavingsGoal


class GoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ("name", "target_amount", "target_date", "priority", "description")
        widgets = {
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "target_amount": forms.NumberInput(attrs={"step": "0.01", "min": "1"}),
            "name": forms.TextInput(attrs={"placeholder": "e.g. January hostel rent"}),
        }
        labels = {"target_amount": "Target (KSh)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def clean_target_date(self):
        value = self.cleaned_data.get("target_date")
        if value and not self.instance.pk and value < timezone.localdate():
            raise forms.ValidationError("The target date cannot be in the past.")
        return value


class MovementForm(forms.Form):
    ACTIONS = [("allocate", "Set aside"), ("release", "Release back")]
    action = forms.ChoiceField(choices=ACTIONS, initial="allocate")
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), label="Amount (KSh)")
    note = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0.01"})
        style(self)
