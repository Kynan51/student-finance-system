from django.apps import AppConfig


class BudgetingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "budgeting"

    def ready(self):
        from . import signals  # noqa: F401  (connects budget alert signals)
