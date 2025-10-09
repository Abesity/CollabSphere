# Middleware: Auto-logout users after inactivity

from django.shortcuts import redirect
from django.utils import timezone
from django.contrib.auth import logout
from django.conf import settings
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

class IdleTimeoutMiddleware:
    """
    Logs out authenticated users after SESSION_COOKIE_AGE seconds of inactivity.
    Logs out from Supabase and updates the logout_time in the login table.
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
                user_email = request.user.email

                # Update logout_time in login table
                try:
                    # Get Supabase user ID
                    res = supabase.table("user").select("user_ID").eq("email", user_email).single().execute()
                    supabase_user_id = res.data.get("user_ID") if res.data else None

                    if supabase_user_id:
                        supabase.table("login").update({
                            "logout_time": timezone.now().isoformat()
                        }).eq("user_id", supabase_user_id).execute()
                except Exception as e:
                    print(f"Failed to update logout_time in login table: {e}")

                # Logout from Django
                logout(request)

                # Logout from Supabase if access token is stored in session
                supabase_access_token = request.session.get("supabase_access_token")
                if supabase_access_token:
                    try:
                        supabase.auth.sign_out()  # invalidates server-side token
                    except Exception as e:
                        print(f"Supabase logout failed: {e}")
                    request.session.pop("supabase_access_token", None)

                return redirect(f"{settings.LOGIN_URL}?expired=1")

            # Update last activity timestamp
            request.session["last_activity_ts"] = now_ts

        response = self.get_response(request)
        return response

#Prevent user from logging in again if still in session
class PreventLoggedInAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Redirect logged-in users away from login/register
        if request.path in ["/login/", "/register/"] and request.session.get("user_ID"):
            return redirect("home")
        return self.get_response(request)
