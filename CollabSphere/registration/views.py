from django.shortcuts import render, redirect
from supabase import create_client
from django.conf import settings
from .forms import RegistrationForm 
from .forms import LoginForm
from .utils.passwords import hash_password, verify_password

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def register(request):
    form = RegistrationForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # Check for duplicates (username or email)
            existing_user_by_email = supabase.table("users").select("id").eq("email", email).execute()
            if existing_user_by_email.data:
                form.add_error("email", "This email is already registered.")
            existing_user_by_username = supabase.table("users").select("id").eq("username", username).execute()
            if existing_user_by_username.data:
                form.add_error("username", "This username is already taken.")

            if not form.errors:
                # NOTE: In real apps, store a password hash instead of plaintext.
                password_hash = hash_password(password)
                supabase.table("users").insert({
                    "username": username,
                    "email": email,
                    "password": password_hash
                }).execute()
                return redirect("login")  # or redirect to 'home'

    return render(request, "register.html", {"form": form})


def login(request):
    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # Fetch the user by email
            response = supabase.table("users").select("password").eq("email", email).execute()

            # Compare (NOTE: plaintext; recommend hashing in real apps)
            if response.data:
                stored_hash = response.data[0].get("password")

                # ✅ Verify securely
                if verify_password(password, stored_hash):
                    return redirect("home")

            form.add_error(None, "Invalid email or password")

    return render(request, "login.html", {"form": form})
