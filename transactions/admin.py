from django.contrib import admin

from .models import Category, Expense, Income


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "owner", "is_essential")
    list_filter = ("kind", "is_essential")
    search_fields = ("name",)


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ("date", "owner", "source", "amount")
    list_filter = ("source",)
    date_hierarchy = "date"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "owner", "category", "amount", "payment_method")
    list_filter = ("category", "payment_method")
    date_hierarchy = "date"
