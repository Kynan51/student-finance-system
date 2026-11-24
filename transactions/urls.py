from django.urls import path

from . import views

app_name = "transactions"

urlpatterns = [
    path("income/", views.income_list, name="income_list"),
    path("income/add/", views.income_create, name="income_create"),
    path("income/<int:pk>/edit/", views.income_update, name="income_update"),
    path("income/<int:pk>/delete/", views.income_delete, name="income_delete"),
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/add/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="expense_update"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("parse-message/", views.parse_message, name="parse_message"),
    path("suggest-category/", views.suggest, name="suggest_category"),
    path("categories/", views.categories, name="categories"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
]
