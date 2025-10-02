from django.shortcuts import render, redirect
from supabase import create_client
from django.conf import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def home(request):
    return render(request, 'home.html')

def admin_dashboard(request):
    response = supabase.table("users").select("*").execute()
    users = response.data

    return render(request, "admin_dashboard.html", {"users": users})

# require login here to view profile please
def profile_view(request):
    """
    Render the user profile page.
    """
    return render(request, "profile.html")