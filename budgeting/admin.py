from django.contrib import admin

from .models import Budget, BudgetCategoryLimit, FixedObligation


class LimitInline(admin.TabularInline):
    model = BudgetCategoryLimit
    extra = 0


class ObligationInline(admin.TabularInline):
    model = FixedObligation
    extra = 0


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "period", "start_date", "end_date", "total_limit")
    inlines = [LimitInline, ObligationInline]
