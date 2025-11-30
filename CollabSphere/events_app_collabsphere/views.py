from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from datetime import datetime, timedelta
import json

from .models import Event, RecurringEvent
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
        
        # Check for conflicts unless explicitly skipped
        skip_conflict_check = data.get('skip_conflict_check', False)
        if not skip_conflict_check:
            conflicts = Event.check_conflicts(active_team_id, start_time, end_time)
            if conflicts:
                print(f"⚠️ Found {len(conflicts)} conflicting event(s)")
                return JsonResponse({
                    "success": False,
                    "error": "Event conflicts with existing events",
                    "conflict": True,
                    "conflicts": conflicts
                })
        
        # Create event payload - matching your calendarevent table schema
        event_data = {
            "title": data.get('title', 'Untitled Event'),
            "description": data.get('description', ''),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "team_ID": active_team_id,  # Use team_ID (uppercase) to match database
            "user_id": request.session.get("user_ID") or request.user.id
        }
        
        # Check if this is a recurring event
        is_recurring = data.get('is_recurring') == 'on' or data.get('is_recurring') == True
        
        if is_recurring:
            print("🔁 Creating recurring event")
            
            # Parse recurring event data
            frequency = data.get('frequency', 'weekly')
            ends_on = data.get('ends_on', 'never')
            
            # Parse selected days for weekly recurrence
            days = []
            if frequency == 'weekly':
                # Handle both array format and individual day fields
                if 'days[]' in data:
                    days = [int(d) for d in request.POST.getlist('days[]')]
                else:
                    # Check individual day values
                    for i in range(7):
                        if data.get(f'day_{i}'):
                            days.append(i)
            
            # Build recurrence rule
            recurrence_rule = {
                'frequency': frequency,
                'days': days,
                'end_type': ends_on,
                'interval': 1
            }
            
            # Add end condition
            if ends_on == 'on':
                recurrence_rule['end_date'] = data.get('recurrence_end_date')
            elif ends_on == 'after':
                try:
                    recurrence_rule['occurrences'] = int(data.get('occurrences', 10))
                except (ValueError, TypeError):
                    recurrence_rule['occurrences'] = 10
            
            print(f"🔁 Recurrence rule: {recurrence_rule}")
            
            # Create recurring event
            result = RecurringEvent.create_recurring_event(event_data, recurrence_rule)
            if result:
                result = [result]  # Wrap in list for consistent handling below
        else:
            # Save regular event to database
            result = Event.create(event_data)
        
        print(f"🟢 Event data to save: {event_data}")
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
        
        # Get events for the team within date range (including expanded recurring events)
        events = RecurringEvent.get_expanded_events_for_range(active_team_id, start_date, end_date)
        
        # Format events for response
        month_events = []
        for event in events:
            try:
                event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                
                formatted_event = {
                    'id': event.get('event_id'),
                    'title': event['title'],
                    'start': event_start.strftime('%Y-%m-%d'),
                    'start_time': event_start.strftime('%I:%M %p'),
                    'end_time': event_end.strftime('%I:%M %p'),
                    'description': event.get('description', ''),
                    'day': event_start.day,
                    'is_recurring': event.get('is_recurring', False),
                    'is_occurrence': event.get('is_occurrence', False),
                    'parent_event_id': event.get('parent_event_id'),
                    'occurrence_index': event.get('occurrence_index')
                }
                
                # Add recurrence summary if it's a recurring event
                if event.get('is_recurring'):
                    formatted_event['recurrence_summary'] = RecurringEvent.get_recurrence_summary(event)
                
                month_events.append(formatted_event)
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
@require_http_methods(["GET"])
def get_event(request, event_id):
    """Get a single event by ID"""
    try:
        event = Event.get_by_id(event_id)
        if not event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)
        
        # Format event data
        try:
            event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
            
            formatted_event = {
                'id': event['event_id'],
                'title': event['title'],
                'description': event.get('description', ''),
                'start_date': event_start.strftime('%Y-%m-%d'),
                'start_time': event_start.strftime('%H:%M'),
                'end_date': event_end.strftime('%Y-%m-%d'),
                'end_time': event_end.strftime('%H:%M'),
                'team_id': event.get('team_ID'),
                'user_id': event.get('user_id')
            }
        except Exception as e:
            print(f"Error formatting event: {e}")
            formatted_event = event
        
        return JsonResponse({"success": True, "event": formatted_event})
        
    except Exception as e:
        print(f"Error getting event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@require_http_methods(["PUT", "PATCH"])
def update_event(request, event_id):
    """Update an existing event with conflict validation"""
    try:
        print(f"🟢 Update event endpoint hit for event_id: {event_id}")
        
        # Get the existing event
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)
        
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})
        
        # Verify user has permission (event belongs to their team)
        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to update this event"}, status=403)
        
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        print(f"🟢 Update data received: {data}")
        
        # Build update payload - only include fields that are provided
        update_data = {}
        
        if 'title' in data and data['title']:
            update_data['title'] = data['title']
        
        if 'description' in data:
            update_data['description'] = data['description']
        
        # Handle date/time updates
        start_date = data.get('start_date')
        start_time_str = data.get('start_time')
        end_date = data.get('end_date')
        end_time_str = data.get('end_time')
        
        # Determine final start and end times
        if start_date and start_time_str:
            start_datetime_str = f"{start_date}T{start_time_str}:00"
            try:
                start_time = datetime.fromisoformat(start_datetime_str)
                update_data['start_time'] = start_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid start date/time format: {str(e)}"})
        else:
            # Use existing start time for conflict check
            start_time = datetime.fromisoformat(existing_event['start_time'].replace('Z', '+00:00'))
        
        if end_date and end_time_str:
            end_datetime_str = f"{end_date}T{end_time_str}:00"
            try:
                end_time = datetime.fromisoformat(end_datetime_str)
                update_data['end_time'] = end_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid end date/time format: {str(e)}"})
        else:
            # Use existing end time for conflict check
            end_time = datetime.fromisoformat(existing_event['end_time'].replace('Z', '+00:00'))
        
        # Validate end time is after start time
        if end_time <= start_time:
            return JsonResponse({"success": False, "error": "End time must be after start time"})
        
        # Check for conflicts (excluding the current event)
        skip_conflict_check = data.get('skip_conflict_check', False)
        if not skip_conflict_check:
            conflicts = Event.check_conflicts(
                active_team_id, 
                start_time, 
                end_time, 
                exclude_event_id=event_id
            )
            if conflicts:
                print(f"⚠️ Found {len(conflicts)} conflicting event(s)")
                return JsonResponse({
                    "success": False,
                    "error": "Event conflicts with existing events",
                    "conflict": True,
                    "conflicts": conflicts
                })
        
        if not update_data:
            return JsonResponse({"success": False, "error": "No valid fields to update"})
        
        print(f"🟢 Update payload: {update_data}")
        
        # Perform update
        result = Event.update(event_id, update_data)
        
        if not result:
            return JsonResponse({"success": False, "error": "Failed to update event in database"})
        
        # Evaluate notification triggers
        event_with_id = {
            "event_ID": event_id,
            "title": update_data.get('title', existing_event['title']),
            "date": start_date or existing_event['start_time'][:10],
            "time": start_time_str or existing_event['start_time'][11:16]
        }
        
        context = {
            "action": "update",
            "updater_id": request.session.get("user_ID") or request.user.id
        }
        
        triggered = EventNotificationTriggers.evaluate_all_triggers(event_with_id, context)
        
        for trigger in triggered:
            print(f"🔔 EVENT TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        
        return JsonResponse({
            "success": True,
            "message": "Event updated successfully",
            "event_id": event_id
        })
        
    except Exception as e:
        print(f"❌ Error updating event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})

@login_required
@require_http_methods(["DELETE"])
def delete_event(request, event_id):
    """Delete an event"""
    try:
        # Verify the event exists and belongs to user's team
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)
        
        active_team_id = Team.get_active_team_id(request.user)
        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to delete this event"}, status=403)
        
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

@login_required
@require_http_methods(["POST"])
def check_event_conflicts(request):
    """Check for event conflicts without creating an event"""
    try:
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})
        
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        # Validate required fields
        required_fields = ['start_date', 'start_time', 'end_date', 'end_time']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"success": False, "error": f"{field.replace('_', ' ').title()} is required"})
        
        # Parse datetime
        start_datetime_str = f"{data['start_date']}T{data['start_time']}:00"
        end_datetime_str = f"{data['end_date']}T{data['end_time']}:00"
        
        try:
            start_time = datetime.fromisoformat(start_datetime_str)
            end_time = datetime.fromisoformat(end_datetime_str)
        except ValueError as e:
            return JsonResponse({"success": False, "error": f"Invalid date/time format: {str(e)}"})
        
        # Optional: exclude a specific event (for update checks)
        exclude_event_id = data.get('exclude_event_id')
        
        conflicts = Event.check_conflicts(
            active_team_id, 
            start_time, 
            end_time,
            exclude_event_id=exclude_event_id
        )
        
        return JsonResponse({
            "success": True,
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts
        })
        
    except Exception as e:
        print(f"Error checking conflicts: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})

# ============================================
# Recurring Event Series Management Endpoints
# ============================================

@login_required
@require_http_methods(["PUT", "PATCH"])
def update_recurring_event(request, event_id):
    """
    Update a recurring event with scope options.
    
    Scope options (passed in request body):
    - 'all': Update entire series (default)
    - 'single': Update only this occurrence (creates exception)
    - 'future': Update this and future occurrences
    """
    try:
        print(f"🔁 Update recurring event endpoint hit for event_id: {event_id}")
        
        # Get the existing event
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)
        
        # Verify it's a recurring event
        if not existing_event.get('is_recurring'):
            return JsonResponse({"success": False, "error": "This is not a recurring event"}, status=400)
        
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})
        
        # Verify user has permission
        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to update this event"}, status=403)
        
        # Parse request data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        update_scope = data.get('update_scope', 'all')
        
        # Build update payload
        update_data = {}
        if 'title' in data and data['title']:
            update_data['title'] = data['title']
        if 'description' in data:
            update_data['description'] = data['description']
        
        # Handle date/time updates
        if data.get('start_date') and data.get('start_time'):
            start_datetime_str = f"{data['start_date']}T{data['start_time']}:00"
            try:
                start_time = datetime.fromisoformat(start_datetime_str)
                update_data['start_time'] = start_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid start date/time: {str(e)}"})
        
        if data.get('end_date') and data.get('end_time'):
            end_datetime_str = f"{data['end_date']}T{data['end_time']}:00"
            try:
                end_time = datetime.fromisoformat(end_datetime_str)
                update_data['end_time'] = end_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid end date/time: {str(e)}"})
        
        # Handle recurrence rule updates (only for 'all' scope)
        if update_scope == 'all':
            if 'frequency' in data:
                update_data['frequency'] = data['frequency']
            if 'recurrence_days' in data:
                update_data['recurrence_days'] = json.dumps(data['recurrence_days'])
            if 'ends_on' in data:
                update_data['recurrence_end_type'] = data['ends_on']
            if 'recurrence_end_date' in data:
                update_data['recurrence_end_date'] = data['recurrence_end_date']
            if 'occurrences' in data:
                update_data['recurrence_count'] = int(data['occurrences'])
        
        print(f"🔁 Update scope: {update_scope}, Update data: {update_data}")
        
        # Perform update based on scope
        result = RecurringEvent.update_recurring_event(event_id, update_data, update_scope)
        
        if not result:
            return JsonResponse({"success": False, "error": "Failed to update recurring event"})
        
        return JsonResponse({
            "success": True,
            "message": f"Recurring event updated successfully (scope: {update_scope})",
            "event_id": event_id
        })
        
    except Exception as e:
        print(f"❌ Error updating recurring event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})


@login_required
@require_http_methods(["DELETE"])
def delete_recurring_event(request, event_id):
    """
    Delete a recurring event with scope options.
    
    Scope options (passed as query param or in body):
    - 'all': Delete entire series (default)
    - 'single': Delete only this occurrence
    - 'future': Delete this and future occurrences
    """
    try:
        print(f"🔁 Delete recurring event endpoint hit for event_id: {event_id}")
        
        # Get the existing event
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)
        
        # Verify it's a recurring event
        if not existing_event.get('is_recurring'):
            return JsonResponse({"success": False, "error": "This is not a recurring event. Use regular delete endpoint."}, status=400)
        
        # Get active team ID
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        # Verify user has permission
        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to delete this event"}, status=403)
        
        # Get delete scope from query params or body
        delete_scope = request.GET.get('scope', 'all')

        print(f"🔁 Delete scope: {delete_scope}")
        
        # Perform delete based on scope
        success = RecurringEvent.delete_recurring_event(event_id, delete_scope)
        
        if not success:
            return JsonResponse({"success": False, "error": "Failed to delete recurring event"})

        return JsonResponse({
            "success": True,
            "message": f"Recurring event deleted successfully (scope: {delete_scope})"
        })
        
    except Exception as e:
        print(f"❌ Error deleting recurring event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})


@login_required
@require_http_methods(["GET"])
def get_recurring_events(request):
    """Get all recurring events (master events) for the active team."""
    try:
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": True, "events": []})
        
        recurring_events = RecurringEvent.get_recurring_events_for_team(active_team_id)
        
        # Format events for response
        formatted_events = []
        for event in recurring_events:
            try:
                event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                
                formatted_events.append({
                    'id': event['event_id'],
                    'title': event['title'],
                    'description': event.get('description', ''),
                    'start_date': event_start.strftime('%Y-%m-%d'),
                    'start_time': event_start.strftime('%H:%M'),
                    'end_date': event_end.strftime('%Y-%m-%d'),
                    'end_time': event_end.strftime('%H:%M'),
                    'frequency': event.get('frequency'),
                    'recurrence_days': json.loads(event['recurrence_days']) if event.get('recurrence_days') else [],
                    'recurrence_end_type': event.get('recurrence_end_type'),
                    'recurrence_end_date': event.get('recurrence_end_date'),
                    'recurrence_count': event.get('recurrence_count'),
                    'recurrence_summary': RecurringEvent.get_recurrence_summary(event)
                })
            except Exception as e:
                print(f"Error formatting recurring event {event.get('event_id')}: {e}")
                continue
        
        return JsonResponse({"success": True, "events": formatted_events})
        
    except Exception as e:
        print(f"Error getting recurring events: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})