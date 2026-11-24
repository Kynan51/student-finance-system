from django.urls import path

from . import views

app_name = "ai_engine"

urlpatterns = [
    path("", views.insights, name="insights"),
    path("refresh/", views.insights_refresh, name="refresh"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
]
