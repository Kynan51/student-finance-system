from django.contrib import admin

from .models import SavingsContribution, SavingsGoal


class ContributionInline(admin.TabularInline):
    model = SavingsContribution
    fk_name = "goal"
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "target_amount", "status", "priority", "target_date")
    inlines = [ContributionInline]
