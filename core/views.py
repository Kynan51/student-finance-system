from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

# Bump this when static assets change so the service worker refreshes caches.
PWA_CACHE_VERSION = "v1.0.0"


@require_GET
def landing(request):
    if request.user.is_authenticated:
        return redirect("analytics:dashboard")
    return render(request, "core/landing.html")


@require_GET
def offline(request):
    return render(request, "core/offline.html")


@require_GET
def install_help(request):
    return render(request, "core/install.html")


@require_GET
@cache_control(max_age=3600, public=True)
def manifest(request):
    response = render(
        request, "core/manifest.webmanifest", content_type="application/manifest+json"
    )
    return response


@require_GET
@cache_control(no_cache=True, max_age=0)
def service_worker(request):
    """
    Served from the site root so its scope covers the whole app.
    The list of cached files is rendered here so hashed static URLs stay correct.
    """
    static_assets = [
        static("css/base.css"),
        static("css/layout.css"),
        static("css/components.css"),
        static("js/app.js"),
        static("js/pwa-register.js"),
        static("icons/icon-192.png"),
        static("icons/icon-512.png"),
    ]
    response = render(
        request,
        "core/service-worker.js",
        {
            "cache_version": PWA_CACHE_VERSION,
            "static_assets": static_assets,
            "offline_url": "/offline/",
        },
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def robots(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


def error_404(request, exception=None):
    return render(request, "core/error.html", {"code": 404, "title": "Page not found"}, status=404)


def error_500(request):
    return render(request, "core/error.html", {"code": 500, "title": "Something went wrong"}, status=500)


def health(request):
    return HttpResponse("ok", content_type="text/plain")
