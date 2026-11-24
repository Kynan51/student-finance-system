from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


class SavingsGoal(models.Model):
    """
    A VIRTUAL savings goal. Contributions are planning allocations that set
    money aside on paper; the app never moves, holds or locks real funds.
    """

    class Priority(models.IntegerChoices):
        HIGH = 1, "High"
        MEDIUM = 2, "Medium"
        LOW = 3, "Low"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="savings_goals"
    )
    name = models.CharField(max_length=80)
    target_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("1.00"))]
    )
    target_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "priority", "target_date"]
        indexes = [models.Index(fields=["owner", "status"], name="goal_owner_status_idx")]

    def __str__(self):
        return self.name

    @property
    def saved_amount(self):
        total = self.contributions.aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0.00")

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.saved_amount, Decimal("0.00"))

    @property
    def progress_percent(self):
        if not self.target_amount:
            return 0
        pct = (self.saved_amount / self.target_amount) * 100
        return int(min(max(pct, 0), 100))

    def refresh_status(self):
        """Mark complete when the target is reached; reopen if a correction drops it."""
        if self.status == self.Status.ARCHIVED:
            return
        reached = self.saved_amount >= self.target_amount
        if reached and self.status != self.Status.COMPLETED:
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at"])
        elif not reached and self.status == self.Status.COMPLETED:
            self.status = self.Status.ACTIVE
            self.completed_at = None
            self.save(update_fields=["status", "completed_at"])


class SavingsContribution(models.Model):
    """
    Append-only ledger of allocations. Mistakes are corrected by adding a
    REVERSAL entry (negative amount) that points at the original, so the
    audit trail is never lost.
    """

    class EntryType(models.TextChoices):
        ALLOCATE = "allocate", "Allocation"
        RELEASE = "release", "Release back to balance"
        REVERSAL = "reversal", "Reversal / correction"

    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name="contributions")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    entry_type = models.CharField(max_length=10, choices=EntryType.choices, default=EntryType.ALLOCATE)
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=200, blank=True)
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversed_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name="contribution_nonzero"),
        ]

    def __str__(self):
        return f"{self.get_entry_type_display()} KSh {self.amount} → {self.goal}"

    @property
    def is_reversed(self):
        return hasattr(self, "reversed_by")
