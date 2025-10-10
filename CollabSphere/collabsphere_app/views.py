from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from supabase import create_client
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

@login_required(login_url='login')
def home(request):
    user = request.user
    now = timezone.localtime(timezone.now())  
    current_hour = now.hour 

    # Determine greeting 
    if 5 <= current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 18:
        greeting = "Good afternoon"
    elif 18 <= current_hour < 24:
        greeting = "Good evening"
    else:
        greeting = "Hello"

    # Get today's date in the correct timezone
    today_date = timezone.localtime(timezone.now()).date()
    
    print(f"DEBUG - User: {user.id}, Today's date: {today_date}")
    
    # Query for check-ins - use date comparison only
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("checkin_id, date_submitted, user_id")
        .eq("user_id", user.id)
        .eq("date_submitted", today_date.isoformat())
        .execute()
    )
    
    # Debug logging
    print(f"Check-ins found: {len(response.data)}")
    for checkin in response.data:
        print(f"Check-in: ID={checkin.get('checkin_id')}, Date={checkin.get('date_submitted')}")
    
    # Alternative: Try a more flexible date comparison
    if len(response.data) == 0:
        print("Trying alternative date comparison...")
        # Sometimes the date might be stored differently, try a contains approach
        all_response = (
            supabase
            .table("wellbeingcheckin")
            .select("checkin_id, date_submitted, user_id")
            .eq("user_id", user.id)
            .execute()
        )
        
        today_str = today_date.isoformat()
        today_checkins = [c for c in all_response.data if c.get('date_submitted', '').startswith(today_str)]
        print(f"Alternative check found: {len(today_checkins)}")
        
        has_checked_in_today = len(today_checkins) > 0
    else:
        has_checked_in_today = len(response.data) > 0

    # Fetch tasks belonging to the logged-in user
    try:
        tasks_response = (
            supabase
            .table("tasks")
            .select("*")
            .eq("created_by", user.username)
            .order("date_created", desc=True)
            .execute()
        )
        user_tasks = tasks_response.data or [] 
        print(f"Tasks fetched for {user.username}: {len(user_tasks)}") 
    except Exception as e: 
        print(f"Error fetching tasks: {e}") 
        user_tasks = []

    context = {
        "greeting": greeting,
        "user_name": user.username,
        "has_checked_in_today": has_checked_in_today,
        "tasks": user_tasks,
    }

    response = render(request, "home.html", context)
    # Add headers to prevent caching
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
    


@require_GET
@login_required
def verify_checkin_status(request):
    """API endpoint to verify if user has checked in today"""
    user = request.user
    today_date = timezone.localtime(timezone.now()).date()
    
    print(f"VERIFY - User: {user.id}, Today: {today_date}")
    
    # Try exact date match first
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("checkin_id, date_submitted")
        .eq("user_id", user.id)
        .eq("date_submitted", today_date.isoformat())
        .execute()
    )
    
    has_checked_in_today = len(response.data) > 0
    
    # If no exact match, try alternative approach
    if not has_checked_in_today:
        all_response = (
            supabase
            .table("wellbeingcheckin")
            .select("checkin_id, date_submitted")
            .eq("user_id", user.id)
            .execute()
        )
        
        today_str = today_date.isoformat()
        today_checkins = [c for c in all_response.data if c.get('date_submitted', '').startswith(today_str)]
        has_checked_in_today = len(today_checkins) > 0
        print(f"Alternative check found: {len(today_checkins)}")
    
    print(f"Final result: {has_checked_in_today}")
    
    return JsonResponse({
        'has_checked_in_today': has_checked_in_today,
        'user_id': user.id,
        'today_date': today_date.isoformat(),
        'checkins_found': len(response.data)
    })


@require_GET
@login_required
def debug_checkins(request):
    """Debug endpoint to see all check-ins for the user"""
    user = request.user
    
    # Get ALL check-ins for this user to see what exists
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("*")
        .eq("user_id", user.id)
        .order("date_submitted", desc=True)
        .execute()
    )
    
    debug_info = {
        'user_id': user.id,
        'total_checkins': len(response.data),
        'checkins': response.data,
        'today_date': timezone.now().date().isoformat()
    }
    
    return JsonResponse(debug_info)


def admin_dashboard(request):
    response = supabase.table("users").select("*").execute()
    users = response.data

    return render(request, "admin_dashboard.html", {"users": users})


@login_required
def profile_view(request):
    """
    Render the user profile page.
    """
    return render(request, "profile.html")