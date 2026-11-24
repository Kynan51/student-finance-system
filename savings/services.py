"""
Savings ledger operations. All writes go through these functions so the
rules are enforced in one place and are easy to test:

  * allocations cannot exceed the student's available balance
  * releases cannot take a goal below zero
  * nothing is ever deleted: a correction is a REVERSAL entry
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from analytics.services import balance_summary

from .models import SavingsContribution, SavingsGoal


@transaction.atomic
def allocate(goal: SavingsGoal, amount: Decimal, note="", on_date=None):
    if amount <= 0:
        raise ValidationError("Enter an amount greater than zero.")
    if goal.status == SavingsGoal.Status.ARCHIVED:
        raise ValidationError("This goal is archived.")
    available = balance_summary(goal.owner)["available_balance"]
    if amount > available:
        raise ValidationError(
            f"You only have KSh {available:,.2f} unallocated. Record income first or allocate less."
        )
    entry = SavingsContribution.objects.create(
        goal=goal, amount=amount, entry_type=SavingsContribution.EntryType.ALLOCATE,
        note=note, date=on_date or timezone.localdate(),
    )
    goal.refresh_status()
    return entry


@transaction.atomic
def release(goal: SavingsGoal, amount: Decimal, note="", on_date=None):
    if amount <= 0:
        raise ValidationError("Enter an amount greater than zero.")
    if amount > goal.saved_amount:
        raise ValidationError(f"This goal only has KSh {goal.saved_amount:,.2f} set aside.")
    entry = SavingsContribution.objects.create(
        goal=goal, amount=-amount, entry_type=SavingsContribution.EntryType.RELEASE,
        note=note or "Released back to available balance", date=on_date or timezone.localdate(),
    )
    goal.refresh_status()
    return entry


@transaction.atomic
def reverse(entry: SavingsContribution, reason=""):
    if entry.entry_type == SavingsContribution.EntryType.REVERSAL:
        raise ValidationError("A reversal cannot itself be reversed.")
    if entry.is_reversed:
        raise ValidationError("This entry has already been reversed.")
    goal = entry.goal
    if entry.amount > 0 and goal.saved_amount - entry.amount < 0:
        raise ValidationError("Reversing this would make the goal negative.")
    if entry.amount < 0:
        available = balance_summary(goal.owner)["available_balance"]
        if -entry.amount > available:
            raise ValidationError("Not enough available balance to undo this release.")
    reversal = SavingsContribution.objects.create(
        goal=goal, amount=-entry.amount, entry_type=SavingsContribution.EntryType.REVERSAL,
        reverses=entry, note=reason or f"Correction of entry #{entry.pk}",
    )
    goal.refresh_status()
    return reversal
