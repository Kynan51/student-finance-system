from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from transactions.models import Category


class Budget(models.Model):
    class Period(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        SEMESTER = "semester", "Semester"
        CUSTOM = "custom", "Custom range"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets"
    )
    name = models.CharField(max_length=80)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.MONTHLY)
    start_date = models.DateField()
    end_date = models.DateField()
    total_limit = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1.00"))]
    )
    warning_threshold = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(10), MaxValueValidator(100)],
        help_text="Warn when this percentage of a limit is used.",
    )
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["owner", "start_date", "end_date"], name="budget_owner_range_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="budget_dates_ordered")
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date} – {self.end_date})"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date must be on or after the start date."})


class BudgetCategoryLimit(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="category_limits")
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, limit_choices_to={"kind": Category.Kind.EXPENSE}
    )
    limit = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1.00"))]
    )

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.UniqueConstraint(fields=["budget", "category"], name="uniq_budget_category")
        ]

    def __str__(self):
        return f"{self.category}: KSh {self.limit}"


class FixedObligation(models.Model):
    """Planned commitments such as hostel rent or examination fees."""

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="obligations")
    name = models.CharField(max_length=80)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    due_date = models.DateField()
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={"kind": Category.Kind.EXPENSE},
    )
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.name} KSh {self.amount} due {self.due_date}"
