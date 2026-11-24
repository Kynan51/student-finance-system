from django.conf import settings


def app_context(request):
    data = {
        "APP_NAME": "Student Finance",
        "APP_FULL_NAME": "AI-Based Personal Finance & Budget Tracker",
        "CURRENCY": settings.CURRENCY_CODE,
        "unread_notifications": 0,
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        data["unread_notifications"] = user.notifications.filter(is_read=False).count()
    return data
