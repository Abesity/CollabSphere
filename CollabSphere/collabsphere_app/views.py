from django.shortcuts import render, redirect
from django.http import HttpResponse
from supabase import create_client
from django.conf import settings
from .forms import RegistrationForm 
from .forms import LoginForm
from django.contrib.auth.decorators import login_required

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
                supabase.table("users").insert({
                    "username": username,
                    "email": email,
                    "password": password
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
            if response.data and response.data[0].get("password") == password:
                return redirect("home")
            else:
                # Non-field error shown at top of the form
                form.add_error(None, "Invalid email or password")

    return render(request, "login.html", {"form": form})

def home(request):
    return render(request, 'home.html')

def dashboard(request):
    response = supabase.table("users").select("*").execute()
    users = response.data

    return render(request, "dashboard.html", {"users": users})

# require login here to view profile please
def profile_view(request):
    """
    Render the user profile page.
    """
    return render(request, "profile.html")