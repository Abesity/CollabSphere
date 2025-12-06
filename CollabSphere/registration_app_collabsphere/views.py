# app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import get_user_model
from .forms import RegistrationForm, LoginForm
from .utils.passwords import hash_password, verify_password
from .supabase_sessions import record_login, record_logout

User = get_user_model()


# -------------------------------
# LOGIN VIEW
# -------------------------------
def login(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        sb_user = User.get_by_email(email)
        if sb_user and verify_password(password, sb_user["password"]):
            record_login(sb_user["user_ID"])

            user, _ = User.objects.get_or_create(
                supabase_id=sb_user["user_ID"],
                defaults={
                    "username": sb_user["username"],
                    "email": email,
                }
            )

            auth_login(request, user)
            request.session["user_ID"] = sb_user["user_ID"]
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

        if User.email_exists(email):
            form.add_error("email", "Email already registered.")
        if User.username_exists(username):
            form.add_error("username", "Username already taken.")

        if not form.errors:
            hashed_pw = hash_password(password)
            new_sb_user = User.create_supabase_user(username, email, hashed_pw)

            if new_sb_user:
                user = User.objects.create(
                    username=username,
                    email=email,
                    supabase_id=new_sb_user["user_ID"]
                )
                user.set_unusable_password()
                user.save()
                return redirect("login")

    return render(request, "register.html", {"form": form})


# -------------------------------
# LOGOUT VIEW
# -------------------------------
def logout(request):
    if "user_ID" in request.session:
        record_logout(request.session["user_ID"])

    auth_logout(request)
    request.session.flush()
    return redirect("login")

# -------------------------------
# FAQ
# -------------------------------
def faq(request):
    return render(request, "faq.html")