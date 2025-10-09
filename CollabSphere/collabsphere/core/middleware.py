# Middleware: Auto-logout users after inactivity

from django.utils import timezone
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.conf import settings

class IdleTimeoutMiddleware:
    """
    Logs out authenticated users after SESSION_COOKIE_AGE seconds of inactivity.
    Stores the last activity timestamp in the session.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, "SESSION_COOKIE_AGE", 1800)

    def __call__(self, request):
        if request.user.is_authenticated:
            now_ts = int(timezone.now().timestamp())
            last = request.session.get("last_activity_ts", now_ts)
            idle = now_ts - int(last)

            if idle > self.timeout:
                logout(request)
                return redirect(f"{settings.LOGIN_URL}?expired=1")

            request.session["last_activity_ts"] = now_ts

        response = self.get_response(request)
        return response


class PreventLoggedInAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Redirect logged-in users away from login/register
        if request.path in ["/login/", "/register/"] and request.session.get("user_ID"):
            return redirect("home")
        return self.get_response(request)
