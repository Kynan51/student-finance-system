"""
Raise in-app budget notifications whenever an expense is saved or deleted.
Notifications are de-duplicated per budget/category/state so the student is
not spammed with the same warning after every expense.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from transactions.models import Expense

from .services import STATE_EXCEEDED, STATE_WARNING, budget_status


def check_budget_alerts(user, on_date=None):
    from ai_engine.models import Notification

    if not user.notify_budget_alerts:
        return []
    budgets = user.budgets.all()
    if on_date:
        budgets = budgets.filter(start_date__lte=on_date, end_date__gte=on_date)

    created = []
    for budget in budgets:
        status = budget_status(budget)
        checks = [(f"budget:{budget.pk}", budget.name, status["state"], status["percent"])]
        checks += [
            (f"budget:{budget.pk}:cat:{row['category'].pk}", f"{row['category'].name} in {budget.name}", row["state"], row["percent"])
            for row in status["categories"]
        ]
        for base_key, label, state, pct in checks:
            if state not in (STATE_WARNING, STATE_EXCEEDED):
                continue
            key = f"{base_key}:{state}"
            if Notification.objects.filter(owner=user, dedupe_key=key).exists():
                continue
            if state == STATE_EXCEEDED:
                level, title = Notification.Level.DANGER, f"Budget exceeded: {label}"
                msg = f"You have spent {pct:.0f}% of this limit."
            else:
                level, title = Notification.Level.WARNING, f"Budget warning: {label}"
                msg = f"You have used {pct:.0f}% of this limit (warning at {budget.warning_threshold}%)."
            created.append(
                Notification.objects.create(
                    owner=user, level=level, title=title, message=msg,
                    link=f"/budgets/{budget.pk}/", dedupe_key=key,
                )
            )
    return created


@receiver(post_save, sender=Expense)
def expense_saved(sender, instance, **kwargs):
    check_budget_alerts(instance.owner, instance.date)


@receiver(post_delete, sender=Expense)
def expense_deleted(sender, instance, **kwargs):
    # Clear warnings that may no longer apply so they can fire again later.
    from ai_engine.models import Notification

    for budget in instance.owner.budgets.filter(start_date__lte=instance.date, end_date__gte=instance.date):
        status = budget_status(budget)
        if status["state"] == "ok":
            Notification.objects.filter(owner=instance.owner, dedupe_key__startswith=f"budget:{budget.pk}:").filter(
                dedupe_key__endswith="warning"
            ).delete()
