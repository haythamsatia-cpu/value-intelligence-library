from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve, reverse


class LoginRequiredMiddleware:
    """Redirect unauthenticated users to login for all app pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
            return self.get_response(request)
        if path.startswith('/admin'):
            return self.get_response(request)

        try:
            match = resolve(path)
            if match.url_name in ('login', 'logout'):
                return self.get_response(request)
        except Exception:
            pass

        return redirect(reverse('login'))
