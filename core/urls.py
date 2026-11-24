from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("offline/", views.offline, name="offline"),
    path("install/", views.install_help, name="install"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("robots.txt", views.robots, name="robots"),
    path("health/", views.health, name="health"),
]
