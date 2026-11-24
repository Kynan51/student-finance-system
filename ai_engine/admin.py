from django.contrib import admin

from .models import FinancialInsight, Notification


@admin.register(FinancialInsight)
class FinancialInsightAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "kind", "severity", "title", "reliability")
    list_filter = ("kind", "severity", "reliability")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "owner", "level", "title", "is_read")
    list_filter = ("level", "is_read")
