from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import datetime, timedelta
import json

from .models import Event
from .notification_triggers import EventNotificationTriggers
from teams_app_collabsphere.models import Team



@require_GET
@login_required
def events_calendar(request):
    """Main events calendar view"""
    try:
        # Initialize active team
        Team.initialize_active_team(request.user)
        
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        
        # Get events for the active team
        events = []
        upcoming_events = []
        
        if active_team_id:
            events = Event.get_all_for_team(active_team_id)
            upcoming_events = Event.get_upcoming_for_team(active_team_id, limit=5)
        
        # Format events for the calendar
        formatted_events = []
        for event in events:
            try:
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                
                formatted_events.append({
                    'id': event['event_id'],
                    'title': event['title'],
                    'start': start_time.strftime('%Y-%m-%d'),
                    'start_time': start_time.strftime('%I:%M %p'),
                    'end_time': end_time.strftime('%I:%M %p'),
                    'description': event.get('description', ''),
                    'all_day': False,
                })
            except Exception as e:
                print(f"Error formatting event {event.get('event_id')}: {e}")
                continue
        
        # Format upcoming events
        formatted_upcoming = []
        for event in upcoming_events:
            try:
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                formatted_upcoming.append({
                    'id': event['event_id'],
                    'title': event['title'],
                    'day': start_time.day,
                    'month': start_time.strftime('%b'),
                    'time': f"{start_time.strftime('%I:%M %p')} - {datetime.fromisoformat(event['end_time'].replace('Z', '+00:00')).strftime('%I:%M %p')}",
                    'description': event.get('description', '')
                })
            except Exception as e:
                print(f"Error formatting upcoming event {event.get('event_id')}: {e}")
                continue
        
        # Get team name using the helper function
        team_name = Team.get_team_name(active_team_id)
        
        context = {
            'events_json': json.dumps(formatted_events),
            'upcoming_events': formatted_upcoming,
            'active_team_id': active_team_id,
            'has_active_team': active_team_id is not None,
            'team_name': team_name
        }
        
        return render(request, "events_calendar.html", context)
        
    except Exception as e:
        print(f"Error loading events calendar: {e}")
        return render(request, "events_calendar.html", {
            "error": "Unable to load events.",
            "events_json": "[]",
            "upcoming_events": [],
            "has_active_team": False
        })

@login_required
@require_http_methods(["POST"])
def create_event(request):
    """Create a new event for the active team"""
    try:
        print("🟢 Create event endpoint hit")
        
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        print(f"🟢 Active team ID: {active_team_id}")
        
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})
        
        # Parse request data - handle both JSON and FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            print(f"🟢 JSON data received: {data}")
        else:
            data = request.POST.dict()
            print(f"🟢 FormData received: {data}")
        
        # Validate required fields
        required_fields = ['title', 'start_date']
        for field in required_fields:
            if not data.get(field):
                print(f"❌ Missing required field: {field}")
                return JsonResponse({"success": False, "error": f"{field.replace('_', ' ').title()} is required"})
        
        # Convert date/time strings to ISO format for Supabase
        start_date = data.get('start_date')
        start_time_str = data.get('start_time', '09:00')
        end_date = data.get('end_date', start_date)
        end_time_str = data.get('end_time', '23:59')
        
        print(f"🟢 Date info - Start: {start_date} {start_time_str}, End: {end_date} {end_time_str}")
        
        # Create datetime strings
        start_datetime_str = f"{start_date}T{start_time_str}:00"
        end_datetime_str = f"{end_date}T{end_time_str}:00"
        
        try:
            start_time = datetime.fromisoformat(start_datetime_str)
            end_time = datetime.fromisoformat(end_datetime_str)
            print(f"🟢 Parsed dates - Start: {start_time}, End: {end_time}")
        except ValueError as e:
            print(f"❌ Date parsing error: {e}")
            return JsonResponse({"success": False, "error": f"Invalid date/time format: {str(e)}"})
        
        # Validate end time is after start time
        if end_time <= start_time:
            print("❌ End time is not after start time")
            return JsonResponse({"success": False, "error": "End time must be after start time"})
        
        # Create event payload - matching your calendarevent table schema
        event_data = {
            "title": data.get('title', 'Untitled Event'),
            "description": data.get('description', ''),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "team_ID": active_team_id,  # Use team_ID (uppercase) to match database
            "user_id": request.session.get("user_ID") or request.user.id
        }
        
        print(f"🟢 Event data to save: {event_data}")
        
        # Save to database
        result = Event.create(event_data)
        print(f"🟢 Database result: {result}")
        
        if not result:
            print("❌ Database returned no result")
            return JsonResponse({"success": False, "error": "Failed to create event in database"})
        
        # Evaluate notification triggers
        event_with_id = {
            "event_ID": result[0]['event_id'] if result and len(result) > 0 else None,
            "title": event_data['title'],
            "date": data.get('start_date'),
            "time": data.get('start_time')
        }
        
        context = {
            "action": "create",
            "creator_id": request.session.get("user_ID") or request.user.id
        }
        
        triggered = EventNotificationTriggers.evaluate_all_triggers(event_with_id, context)
        
        # Log triggers
        for trigger in triggered:
            print(f"🔔 EVENT TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        
        return JsonResponse({
            "success": True, 
            "message": "Event created successfully",
            "event_id": result[0]['event_id'] if result and len(result) > 0 else None
        })
        
    except Exception as e:
        print(f"❌ Error creating event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})

@login_required
@require_http_methods(["GET"])
def get_events(request):
    """Get events for the current month"""
    try:
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": True, "events": []})
        
        # Get month from request
        try:
            year = int(request.GET.get('year', datetime.now().year))
            month = int(request.GET.get('month', datetime.now().month))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid year or month parameter"})
        
        # Calculate date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get events for the team within date range
        events = Event.get_events_by_date_range(active_team_id, start_date, end_date)
        
        # Format events for response
        month_events = []
        for event in events:
            try:
                event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                
                month_events.append({
                    'id': event['event_id'],
                    'title': event['title'],
                    'start': event_start.strftime('%Y-%m-%d'),
                    'start_time': event_start.strftime('%I:%M %p'),
                    'end_time': event_end.strftime('%I:%M %p'),
                    'description': event.get('description', ''),
                    'day': event_start.day
                })
            except Exception as e:
                print(f"Error formatting event {event.get('event_id')}: {e}")
                continue
        
        return JsonResponse({"success": True, "events": month_events})
        
    except Exception as e:
        print(f"Error getting events: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@require_http_methods(["DELETE"])
def delete_event(request, event_id):
    """Delete an event"""
    try:
        success = Event.delete(event_id)
        if success:
            return JsonResponse({"success": True, "message": "Event deleted successfully"})
        else:
            return JsonResponse({"success": False, "error": "Failed to delete event"})
    except Exception as e:
        print(f"Error deleting event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})