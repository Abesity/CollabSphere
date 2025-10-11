# Middleware: Auto-logout users after inactivity

import logging
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

# Middleware: Attach Supabase user_ID to request.user
logger = logging.getLogger(__name__)

class SupabaseUserIDMiddleware:
    """Attaches the Supabase UUID (user_ID) to request.user."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 1. Try to get the ID from session (fastest) or request.user (if already attached)
            supabase_id = request.session.get('supabase_user_id') or getattr(request.user, 'user_ID', None)
            
            if not supabase_id:
                # 2. ID is missing: Query Supabase
                if supabase:
                    try:
                        # Use username to find the UUID in the Supabase 'user' table
                        response = supabase.table('user').select('user_ID').eq('username', request.user.username).single().execute()
                        
                        if response.data and 'user_ID' in response.data:
                            supabase_id = response.data['user_ID']
                            request.session['supabase_user_id'] = supabase_id
                            
                    except Exception as e:
                        logger.error(f"Supabase fetch error for user {request.user.username}: {e}")
                
            # 3. Final check: If ID is present, attach it.
            if supabase_id:
                setattr(request.user, 'user_ID', supabase_id)
            else:
                # 4. ID is still missing: LOG OUT. This is the only way to stop the 401.
                logger.warning(f"CRITICAL: Supabase user_ID not found. Logging out user: {request.user.username}.")
                logout(request)
                # Redirecting prevents the 401 from being sent to the AJAX call
                return redirect(f"{settings.LOGIN_URL}?error=missing_id")

        response = self.get_response(request)
        return response