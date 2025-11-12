from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime
from collections import defaultdict
import json

from .models import WellbeingService
from .notification_triggers import CheckinNotificationTriggers
from teams_app_collabsphere.models import Team


def group_checkins_by_date(checkins):
    grouped = defaultdict(list)
    for c in checkins:
        date_val = c.get("date_submitted")
        if not date_val:
            continue
        # Convert string or datetime to normalized date string
        if isinstance(date_val, str):
            try:
                date_obj = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            except:
                try:
                    date_obj = datetime.strptime(date_val, "%Y-%m-%dT%H:%M:%S.%fZ")
                except:
                    date_obj = datetime.now()
        else:
            date_obj = date_val

        date_str = date_obj.strftime("%Y-%m-%d")
        grouped[date_str].append(c)
    
    # Sort newest to oldest
    return dict(sorted(grouped.items(), key=lambda x: x[0], reverse=True))


@login_required(login_url='login')
def wellbeing_dashboard(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        return redirect("login")

    # Get active team info
    active_team = Team.get_active_team(request.user)
    active_team_id = active_team['team_ID'] if active_team else None

    # Fetch team check-ins if user has an active team
    team_checkins = []
    team_chart_data = []
    individual_checkins_data = []  # Store individual check-ins for detailed tooltips
    
    if active_team_id:
        try:
            # Get team check-ins for the list
            team_checkins = WellbeingService.get_team_checkins(active_team_id, limit=15)
            
            # Get team check-ins for the chart with user details
            team_chart_raw_data = WellbeingService.get_team_checkins_for_chart(active_team_id)
            
            # Store individual check-ins for detailed tooltips
            individual_checkins_data = team_chart_raw_data
            
            # Prepare chart data (group by date and calculate average mood)
            chart_data_by_date = {}
            for checkin in team_chart_raw_data:
                date_val = checkin.get("date_submitted")
                if not date_val:
                    continue
                    
                # Convert to date string for grouping
                if isinstance(date_val, str):
                    try:
                        date_obj = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except:
                        date_str = date_val.split('T')[0] if 'T' in date_val else date_val
                else:
                    date_str = date_val.strftime('%Y-%m-%d')
                
                # Convert status to numerical value
                status = checkin.get("status") or "Okay"
                mood_value = 1  # Default to "Okay"
                if status == 'Good':
                    mood_value = 2
                elif status == 'Needs Support':
                    mood_value = 0
                
                if date_str not in chart_data_by_date:
                    chart_data_by_date[date_str] = {
                        'date': date_str,
                        'moods': [],
                        'checkins': [],  # Store individual check-ins for this date
                        'count': 0
                    }
                
                chart_data_by_date[date_str]['moods'].append(mood_value)
                chart_data_by_date[date_str]['checkins'].append({
                    'username': checkin.get('user', {}).get('username', 'Unknown'),
                    'status': status,
                    'mood_value': mood_value
                })
                chart_data_by_date[date_str]['count'] += 1
            
            # Calculate average mood per day
            for date_data in chart_data_by_date.values():
                if date_data['moods']:
                    avg_mood = sum(date_data['moods']) / len(date_data['moods'])
                    # Convert back to status for display
                    if avg_mood >= 1.5:
                        status_display = 'Good'
                    elif avg_mood >= 0.5:
                        status_display = 'Okay'
                    else:
                        status_display = 'Needs Support'
                    
                    team_chart_data.append({
                        "date": date_data['date'],
                        "mood": status_display,
                        "avg_mood": avg_mood,
                        "checkin_count": date_data['count'],
                        "individual_checkins": date_data['checkins']  # Include individual check-ins
                    })
            
            # Sort by date for the chart
            team_chart_data.sort(key=lambda x: x['date'])
            
        except Exception as e:
            print(f"Error fetching team check-ins: {e}")
            team_checkins = []
            team_chart_data = []
            individual_checkins_data = []
    
    # Also get user's personal check-ins
    try:
        user_checkins = WellbeingService.get_recent_checkins(user_id)
    except Exception as e:
        print(f"Error fetching user check-ins: {e}")
        user_checkins = []

    # Prepare chart data JSON
    chart_data_json = json.dumps(team_chart_data if active_team_id else [])

    # Check if user has checked in today
    has_checked_in_today = WellbeingService.has_checked_in_today(user_id)

    # Team message
    team_message = f"Team {active_team['team_name']}'s recent check-ins" if active_team else "Your recent check-ins"

    # Group check-ins by date
    grouped_checkins = group_checkins_by_date(team_checkins if active_team_id else user_checkins)
 
    context = {
        "recent_checkins": team_checkins if active_team_id else user_checkins,
        "chart_data": chart_data_json,
        "greeting": "Hello",
        "fullname": request.user.username,
        "has_checked_in_today": has_checked_in_today,
        "team_message": team_message,
        "is_team_view": active_team_id is not None,
        "active_team": active_team,
        "individual_checkins_data": json.dumps(individual_checkins_data), 
        "grouped_checkins": grouped_checkins,
    }

    return render(request, "wellbeing_dashboard.html", context)

@login_required(login_url='login')
def checkins_modal(request):
    print("checkins_modal view accessible")
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