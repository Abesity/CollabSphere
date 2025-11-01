from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime
import json

from .models import WellbeingService
from .notification_triggers import CheckinNotificationTriggers


@login_required(login_url='login')
def wellbeing_dashboard(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        return redirect("login")

    # Fetch recent check-ins from service
    try:
        recent_checkins = WellbeingService.get_recent_checkins(user_id)
    except Exception as e:
        print(f"Error fetching check-ins: {e}")
        recent_checkins = []

    # Prepare chart data (oldest first)
    chart_data = []
    for checkin in reversed(recent_checkins):
        date_val = checkin.get("date_submitted")
        formatted_date = date_val if isinstance(date_val, str) else date_val.isoformat() if date_val else ""

        status = checkin.get("status") or "Okay"

        chart_data.append({
            "date": formatted_date,
            "mood": status,
        })

    chart_data_json = json.dumps(chart_data)

    # Check if user has checked in today
    has_checked_in_today = WellbeingService.has_checked_in_today(user_id)

    context = {
        "recent_checkins": recent_checkins,
        "chart_data": chart_data_json,
        "greeting": "Hello",
        "fullname": request.user.username,
        "has_checked_in_today": has_checked_in_today,
    }

    return render(request, "wellbeing_dashboard.html", context)


@login_required(login_url='login')
def checkins_modal(request):
    print("🔥 checkins_modal view hit!")
    user = request.user

    # Get Supabase user ID for logged-in user
    try:
        supabase_user_id = WellbeingService.get_supabase_user_id(user.email)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Failed to fetch user ID: {e}"})

    # Check today's submission
    already_checked_in = WellbeingService.has_checked_in_today(supabase_user_id)

    # Handle POST (submission)
    if request.method == "POST":
        if already_checked_in:
            return JsonResponse({
                "success": False,
                "message": "You have already submitted your check-in today."
            })

        mood_rating = request.POST.get("mood_rating")
        status = request.POST.get("status")
        notes = request.POST.get("notes")

        try:
            # Submit the check-in
            WellbeingService.submit_checkin(supabase_user_id, mood_rating, status, notes)
            
            # Evaluate notification triggers
            checkin_data = {
                'mood_rating': mood_rating,
                'status': status,
                'notes': notes
            }
            
            triggered_notifications = CheckinNotificationTriggers.evaluate_all_triggers(
                supabase_user_id,
                checkin_data
            )
            
            # Log triggered notifications
            for trigger in triggered_notifications:
                print(f"🔔 TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
            
            return JsonResponse({"success": True, "message": "Check-in submitted successfully!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    # Handle GET (display modal)
    try:
        recent_checkins = WellbeingService.get_recent_checkins_modal(supabase_user_id)
    except Exception as e:
        print(f"Error fetching check-ins: {e}")
        recent_checkins = []

    return render(request, "partials/checkins_modal.html", {
        "fullname": f"{user.first_name} {user.last_name}".strip() or user.username,
        "recent_checkins": recent_checkins,
        "has_checked_in_today": already_checked_in,
    })