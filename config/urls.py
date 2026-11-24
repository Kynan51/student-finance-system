from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("transactions/", include("transactions.urls")),
    path("budgets/", include("budgeting.urls")),
    path("savings/", include("savings.urls")),
    path("dashboard/", include("analytics.urls")),
    path("insights/", include("ai_engine.urls")),
    path("reports/", include("reports.urls")),
    path("", include("core.urls")),
]

handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
