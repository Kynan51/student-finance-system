from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("chart-data/", views.chart_data, name="chart_data"),
]
