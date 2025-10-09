from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.conf import settings
from supabase import create_client

from .utils.passwords import hash_password, verify_password
from .forms import RegistrationForm, LoginForm
from .supabase_sessions import record_login, record_logout

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


# -------------------------------
# LOGIN VIEW
# -------------------------------
def login(request):
    # 🚫 Prevent logged-in users from accessing login page
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        # 🔍 Check credentials in Supabase user table
        response = supabase.table("user").select("user_ID, username, password").eq("email", email).execute()

        if response.data:
            user_data = response.data[0]
            stored_hash = user_data.get("password")

            if verify_password(password, stored_hash):
                # ✅ Track login in Supabase
                record_login(user_data["user_ID"])

                # ✅ Sync / create Django user for session auth
                username = user_data["username"]

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={"email": email}
                )

                # Optional: you can update email if changed in Supabase
                if user.email != email:
                    user.email = email
                    user.save()

                # ✅ Django auth login (so @login_required works)
                auth_login(request, user)

                # ✅ Store Supabase user_ID in session for API use
                request.session["user_ID"] = user_data["user_ID"]

                return redirect("home")

        form.add_error(None, "Invalid email or password")

    return render(request, "login.html", {"form": form})


# -------------------------------
# REGISTER VIEW
# -------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        # 🔍 Check existing users in Supabase
        existing_email = supabase.table("user").select("user_ID").eq("email", email).execute()
        existing_username = supabase.table("user").select("user_ID").eq("username", username).execute()

        if existing_email.data:
            form.add_error("email", "This email is already registered.")
        if existing_username.data:
            form.add_error("username", "This username is already taken.")

        if not form.errors:
            password_hash = hash_password(password)

            # ✅ Insert new user in Supabase
            supabase_response = supabase.table("user").insert({
                "username": username,
                "email": email,
                "password": password_hash
            }).execute()

            # ✅ Also create Django auth user (for session login system)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email}
            )

            # Set a random unusable password (since you use Supabase for verification)
            user.set_unusable_password()
            user.save()

            return redirect("login")

    return render(request, "register.html", {"form": form})


# -------------------------------
# LOGOUT VIEW
# -------------------------------
def logout(request):
    user_id = request.session.get("user_ID")

    if user_id:
        record_logout(user_id)

    # ✅ Clear both Django & Supabase session
    auth_logout(request)
    request.session.flush()

    return redirect("login")
