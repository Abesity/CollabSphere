from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from supabase import create_client
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import json

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

@login_required(login_url='login')
def wellbeing_dashboard(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        return redirect("login")

    # Fetch recent check-ins
    try:
        response = (
            supabase.table("wellbeingcheckin")
            .select("checkin_id, date_submitted, mood_rating, status, notes")
            .eq("user_id", int(user_id))
            .order("date_submitted", desc=True)
            .limit(10)
            .execute()
        )
        recent_checkins = response.data or []
        print(f"Fetched check-ins: {recent_checkins}")  # Debug print
    except Exception as e:
        print(f"Error fetching check-ins: {e}")
        recent_checkins = []

    # Prepare chart data (oldest first for proper timeline)
  # In your wellbeing_dashboard function, update the chart_data preparation:
    chart_data = []
    for checkin in reversed(recent_checkins):
        checkin_date = checkin.get("date_submitted")
        if isinstance(checkin_date, str):
            formatted_date = checkin_date
        else:
            formatted_date = checkin_date.isoformat() if checkin_date else ""
        
        # Handle null status - default to "Okay"
        status = checkin.get("status")
        if status is None:
            status = "Okay"
        
        chart_data.append({
            "date": formatted_date,
            "mood": status
        })

    print(f"Chart data: {chart_data}")  # Debug print

    # Convert to JSON for the template
    chart_data_json = json.dumps(chart_data)

    # Check if user has checked in today
    today = timezone.now().date()
    has_checked_in_today = any(
        checkin.get("date_submitted") == today
        for checkin in recent_checkins
    )

    context = {
        "recent_checkins": recent_checkins,
        "chart_data": chart_data_json,
        "greeting": "Hello",
        "fullname": request.user.username,
        "has_checked_in_today": has_checked_in_today,
    }

    return render(request, "wellbeing_dashboard.html", context)

def checkins_modal(request):
    print("🔥 checkins_modal view hit!")
    user = request.user

    # Get Supabase user_ID for the logged-in user
    try:
        res = supabase.table("user").select("user_ID").eq("email", user.email).single().execute()
        supabase_user_id = res.data["user_ID"]
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Failed to fetch user ID: {e}"})

    today = timezone.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Check if user already submitted today
    existing = supabase.table("wellbeingcheckin") \
        .select("*") \
        .eq("user_id", supabase_user_id) \
        .gte("date_submitted", today_start.isoformat()) \
        .lte("date_submitted", today_end.isoformat()) \
        .execute()

    # 🧠 Handle POST (form submission)
    if request.method == "POST":
        if existing.data:  # already submitted today
            return JsonResponse({"success": False, "message": "You have already submitted your check-in today."})

        mood_rating = request.POST.get("mood_rating")
        status = request.POST.get("status")
        notes = request.POST.get("notes")

        try:
            # Insert wellbeing check-in
            supabase.table("wellbeingcheckin").insert({
                "user_id": supabase_user_id,
                "mood_rating": int(mood_rating) if mood_rating else None,
                "status": status,
                "notes": notes,
                "date_submitted": timezone.now().isoformat()
            }).execute()

            return JsonResponse({"success": True, "message": "Check-in submitted successfully!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    # 🧠 Handle GET (display modal) - return only modal HTML
    try:
        response = (
            supabase.table("wellbeingcheckin")
            .select("*")
            .eq("user_id", supabase_user_id)
            .order("date_submitted", desc=True)
            .limit(5)
            .execute()
        )
        recent_checkins = response.data
    except Exception as e:
        print(f"Error fetching checkins: {e}")
        recent_checkins = []

    return render(request, "partials/checkins_modal.html", {
        "fullname": f"{user.first_name} {user.last_name}".strip() or user.username,
        "recent_checkins": recent_checkins,
        "has_checked_in_today": bool(existing.data),  # pass to template for JS
    })
