from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

MIN_AMOUNT = Decimal("0.01")
MAX_DIGITS = 12
DECIMAL_PLACES = 2


class Category(models.Model):
    """
    Income sources and expense categories.

    System categories (owner = NULL) are shared defaults created by a data
    migration. Students can add their own categories (owner = user); those
    are visible only to their owner.
    """

    class Kind(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="categories",
    )
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=60)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    is_essential = models.BooleanField(
        default=False, help_text="Essentials (rent, food, fees) are protected in AI advice."
    )
    keywords = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated words used by the auto-categoriser.",
    )

    class Meta:
        ordering = ["kind", "name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "kind", "slug"], name="uniq_category_per_owner_kind"
            ),
            models.UniqueConstraint(
                fields=["kind", "slug"],
                condition=Q(owner__isnull=True),
                name="uniq_system_category_kind",
            ),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def visible_to(cls, user, kind=None):
        qs = cls.objects.filter(Q(owner__isnull=True) | Q(owner=user))
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class TransactionBase(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        validators=[MinValueValidator(MIN_AMOUNT)],
    )
    date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=200, blank=True)
    reference = models.CharField(
        max_length=30, blank=True, help_text="Optional M-Pesa or receipt reference code."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-date", "-created_at"]


class Income(TransactionBase):
    source = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="income_records",
        limit_choices_to={"kind": Category.Kind.INCOME},
    )

    class Meta(TransactionBase.Meta):
        indexes = [models.Index(fields=["owner", "date"], name="income_owner_date_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="income_amount_positive")
        ]

    def __str__(self):
        return f"{self.source} KSh {self.amount} on {self.date}"


class Expense(TransactionBase):
    class PaymentMethod(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CASH = "cash", "Cash"
        BANK = "bank", "Bank / Card"
        OTHER = "other", "Other"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="expense_records",
        limit_choices_to={"kind": Category.Kind.EXPENSE},
    )
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.MPESA
    )

    class Meta(TransactionBase.Meta):
        indexes = [
            models.Index(fields=["owner", "date"], name="expense_owner_date_idx"),
            models.Index(fields=["owner", "category"], name="expense_owner_cat_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive")
        ]

    def __str__(self):
        return f"{self.category} KSh {self.amount} on {self.date}"
