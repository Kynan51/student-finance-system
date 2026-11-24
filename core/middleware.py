class PrivateNoStoreMiddleware:
    """
    Marks every response served to a signed-in user as private and
    non-cacheable, so neither the browser cache, a shared proxy nor the
    service worker keeps a copy of a student's financial pages.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not request.path.startswith("/static/"):
            response["Cache-Control"] = "no-store, private, max-age=0"
            response["Pragma"] = "no-cache"
        return response
