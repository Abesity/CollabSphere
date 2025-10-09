from django.shortcuts import render, redirect

from .utils.passwords import hash_password, verify_password
from .forms import RegistrationForm, LoginForm
from .supabase_sessions import record_login  
from .supabase_sessions import record_logout
from supabase import create_client
from django.conf import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def login(request):
    # 🚫 Prevent logged-in users from accessing the login page
    user_id = request.session.get("user_ID")
    if user_id:
        # Check if login is still recorded (not logged out)
        active_session = supabase.table("sessions").select("*").eq("user_ID", user_id).eq("is_logged_in", True).execute()
        if active_session.data:
            return redirect("home")

    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            response = supabase.table("user").select("user_ID, password").eq("email", email).execute()

            if response.data:
                user = response.data[0]
                stored_hash = user.get("password")

                if verify_password(password, stored_hash):
                    # ✅ Store user session
                    request.session["user_ID"] = user["user_ID"]
                    request.session["email"] = email
                    record_login(user["user_ID"])  # ✅ track Supabase login
                    return redirect("home")

            form.add_error(None, "Invalid email or password")

    return render(request, "login.html", {"form": form})
def register(request):
    user_id = request.session.get("user_ID")
    if user_id:
        active_session = supabase.table("sessions").select("*").eq("user_ID", user_id).eq("is_logged_in", True).execute()
        if active_session.data:
            return redirect("home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            existing_user_by_email = supabase.table("user").select("id").eq("email", email).execute()
            if existing_user_by_email.data:
                form.add_error("email", "This email is already registered.")

            existing_user_by_username = supabase.table("user").select("id").eq("username", username).execute()
            if existing_user_by_username.data:
                form.add_error("username", "This username is already taken.")

            if not form.errors:
                password_hash = hash_password(password)
                supabase.table("user").insert({
                    "username": username,
                    "email": email,
                    "password": password_hash
                }).execute()
                return redirect("login")

    return render(request, "register.html", {"form": form})


def logout(request):
    user_id = request.session.get("user_ID")

    if user_id:
        record_logout(user_id)  # ✅ mark logout in Supabase

    request.session.flush()  # clear Django session
    return redirect("login")