from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class StudentUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Student profile",
            {
                "fields": (
                    "university",
                    "year_of_study",
                    "semester_start",
                    "semester_end",
                    "notify_budget_alerts",
                    "notify_insight_alerts",
                    "budget_warning_default",
                )
            },
        ),
    )
    list_display = ("username", "email", "first_name", "university", "year_of_study", "is_staff")
