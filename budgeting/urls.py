from django.urls import path

from . import views

app_name = "budgeting"

urlpatterns = [
    path("", views.budget_list, name="list"),
    path("new/", views.budget_form, name="create"),
    path("<int:pk>/", views.budget_detail, name="detail"),
    path("<int:pk>/edit/", views.budget_form, name="update"),
    path("<int:pk>/delete/", views.budget_delete, name="delete"),
    path("<int:pk>/limits/add/", views.limit_add, name="limit_add"),
    path("<int:pk>/limits/<int:limit_id>/delete/", views.limit_delete, name="limit_delete"),
    path("<int:pk>/obligations/add/", views.obligation_add, name="obligation_add"),
    path("<int:pk>/obligations/<int:ob_id>/toggle/", views.obligation_toggle, name="obligation_toggle"),
    path("<int:pk>/obligations/<int:ob_id>/delete/", views.obligation_delete, name="obligation_delete"),
]
