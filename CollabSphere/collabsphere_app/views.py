from django.shortcuts import render, redirect
from supabase import create_client
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

@login_required(login_url='login')
def home(request):
    user = request.user
    now = timezone.localtime(timezone.now())  # ensure local time (Asia/Manila)
    current_hour = now.hour  # 0-23

    # Determine greeting
    if 5 <= current_hour < 12:      # 05:00 - 11:59 → morning
        greeting = "Good morning"
    elif 12 <= current_hour < 18:   # 12:00 - 17:59 → afternoon
        greeting = "Good afternoon"
    elif 18 <= current_hour < 24:   # 18:00 - 21:59 → evening
        greeting = "Good evening"
    else:                           # everything else → night
        greeting = "Hello"


    today = now.date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    response = (
        supabase
        .table("wellbeingcheckin")
        .select("*")
        .eq("user_id", user.id)
        .gte("date_submitted", today_start.isoformat())
        .lte("date_submitted", today_end.isoformat())
        .execute()
    )
    has_checked_in_today = len(response.data) > 0  

    context = {
        "greeting": greeting,
        "user_name": user.username,
        "has_checked_in_today": has_checked_in_today,
    }

    return render(request, "home.html", context)

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