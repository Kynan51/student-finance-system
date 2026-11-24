from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class StyledFormMixin:
    """Adds the shared `.input` class to every widget (plain CSS, no framework)."""

    def _style_fields(self):
        for name, field in self.fields.items():
            widget = field.widget
            css = "checkbox" if isinstance(widget, forms.CheckboxInput) else "input"
            widget.attrs.setdefault("class", css)
            if field.required and css == "input":
                widget.attrs.setdefault("required", "required")


class RegistrationForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=60, required=True, label="First name")
    email = forms.EmailField(required=True)
    consent = forms.BooleanField(
        required=True,
        label="I understand this app stores my financial records to give me insights, "
        "and that I can delete my data at any time.",
    )

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "university", "year_of_study")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["university"].widget.attrs["placeholder"] = "e.g. Mount Kenya University"
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username"
        self._style_fields()


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "university",
            "year_of_study",
            "semester_start",
            "semester_end",
        )
        widgets = {
            "semester_start": forms.DateInput(attrs={"type": "date"}),
            "semester_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("semester_start"), cleaned.get("semester_end")
        if start and end and end <= start:
            self.add_error("semester_end", "Semester end must be after the start.")
        return cleaned


class PreferencesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("notify_budget_alerts", "notify_insight_alerts", "budget_warning_default")
        labels = {
            "notify_budget_alerts": "Show budget warnings in my notifications",
            "notify_insight_alerts": "Show AI insight alerts in my notifications",
            "budget_warning_default": "Default budget warning threshold (%)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget_warning_default"].widget.attrs.update({"min": 10, "max": 100})
        self._style_fields()

    def clean_budget_warning_default(self):
        value = self.cleaned_data["budget_warning_default"]
        if not 10 <= value <= 100:
            raise forms.ValidationError("Choose a value between 10 and 100.")
        return value


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="Confirm your password")

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Incorrect password.")
        return password
