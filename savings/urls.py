from django.urls import path

from . import views

app_name = "savings"

urlpatterns = [
    path("", views.goal_list, name="list"),
    path("new/", views.goal_form, name="create"),
    path("<int:pk>/", views.goal_detail, name="detail"),
    path("<int:pk>/edit/", views.goal_form, name="update"),
    path("<int:pk>/move/", views.goal_move, name="move"),
    path("<int:pk>/archive/", views.goal_archive, name="archive"),
    path("<int:pk>/entries/<int:entry_id>/reverse/", views.entry_reverse, name="reverse"),
]
