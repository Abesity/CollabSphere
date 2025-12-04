from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from datetime import datetime, timedelta

import json

from .models import Event, RecurringEvent
from .notification_triggers import EventNotificationTriggers
from teams_app_collabsphere.models import Team
from notifications_app_collabsphere.views import create_event_notifications

DEFAULT_EVENT_DURATION_MINUTES = 60

User = get_user_model()


def _format_participants(participant_records):
    formatted = []
    if not participant_records:
        return formatted

    for record in participant_records:
        user_id = record.get('user_id')
        username = None
        user_meta = record.get('user')
        if isinstance(user_meta, dict):
            username = user_meta.get('username')
        formatted.append({
            'id': user_id,
            'name': username or (f"User #{user_id}" if user_id else "Unknown member"),
            'is_host': False
        })
    return formatted


def _get_host_display_name(host_id):
    if not host_id:
        return "Unknown Host"

    try:
        host = User.objects.filter(pk=host_id).first()
        if not host:
            return f"Host #{host_id}"
        full_name = (host.get_full_name() or '').strip()
        return full_name if full_name else host.get_username()
    except Exception:
        return f"Host #{host_id}"


def _build_event_participant_payload(event, viewer_id):
    event_id = event.get('event_id') or event.get('id')
    host_id = event.get('user_id')
    host_name = _get_host_display_name(host_id)

    participants_raw = Event.get_event_participants(event_id)
    participants = _format_participants(participants_raw)

    host_in_list = False
    for participant in participants:
        if participant['id'] == host_id:
            participant['is_host'] = True
            host_in_list = True
            break

    if host_id and not host_in_list:
        participants.insert(0, {
            'id': host_id,
            'name': host_name,
            'is_host': True
        })

    participant_ids = {participant['id'] for participant in participants if participant['id'] is not None}
    is_host = host_id == viewer_id
    has_joined = is_host or (viewer_id in participant_ids if viewer_id is not None else False)

    return {
        'event_id': event_id,
        'host_name': host_name,
        'participants': participants,
        'participant_count': len(participants),
        'is_host': is_host,
        'has_joined': has_joined
    }


@require_GET
@login_required
def events_calendar(request):
    """Render the main calendar view with formatted events."""
    try:
        Team.initialize_active_team(request.user)
        active_team_id = Team.get_active_team_id(request.user)

        today = datetime.now()
        start_date = datetime(today.year, today.month, 1)
        end_date = datetime(today.year + 1, 1, 1) if today.month == 12 else datetime(today.year, today.month + 1, 1)

        events = []
        upcoming_events = []
        if active_team_id:
            Event.delete_expired_non_recurring_events(active_team_id)
            events = RecurringEvent.get_expanded_events_for_range(active_team_id, start_date, end_date)
            upcoming_events = Event.get_upcoming_for_team(active_team_id, limit=5)

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
            except Exception as exc:
                print(f"Error formatting event {event.get('event_id')}: {exc}")
                continue

        formatted_upcoming = []
        for event in upcoming_events:
            try:
                start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                formatted_upcoming.append({
                    'id': event['event_id'],
                    'title': event['title'],
                    'day': start_time.day,
                    'month': start_time.strftime('%b'),
                    'time': f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}",
                    'description': event.get('description', ''),
                })
            except Exception as exc:
                print(f"Error formatting upcoming event {event.get('event_id')}: {exc}")
                continue

        team_name = Team.get_team_name(active_team_id)

        context = {
            'events_json': json.dumps(formatted_events),
            'upcoming_events': formatted_upcoming,
            'active_team_id': active_team_id,
            'has_active_team': active_team_id is not None,
            'team_name': team_name,
            'initial_year': start_date.year,
            'initial_month': start_date.month,
        }

        return render(request, "events_calendar.html", context)

    except Exception as exc:
        print(f"Error loading events calendar: {exc}")
        return render(request, "events_calendar.html", {
            'error': 'Unable to load events.',
            'events_json': '[]',
            'upcoming_events': [],
            'has_active_team': False,
        })


@login_required
@require_http_methods(["GET"])
def get_events(request):
    """Get events for the current month."""
    try:
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": True, "events": []})

        Event.delete_expired_non_recurring_events(active_team_id)

        try:
            year = int(request.GET.get('year', datetime.now().year))
            month = int(request.GET.get('month', datetime.now().month))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Invalid year or month parameter"})

        start_date = datetime(year, month, 1)
        end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        events = RecurringEvent.get_expanded_events_for_range(active_team_id, start_date, end_date)

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
    """Get a single event by ID."""
    try:
        event = Event.get_by_id(event_id)
        if not event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

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
            print(f"Error formatting event {event_id}: {e}")
            formatted_event = event

        viewer_id = request.session.get("user_ID") or request.user.id
        participant_payload = _build_event_participant_payload(event, viewer_id)
        formatted_event.update({
            'host_name': participant_payload['host_name'],
            'participants': participant_payload['participants'],
            'participant_count': participant_payload['participant_count'],
            'is_host': participant_payload['is_host'],
            'has_joined': participant_payload['has_joined']
        })

        return JsonResponse({"success": True, "event": formatted_event})

    except Exception as e:
        print(f"Error getting event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@require_http_methods(["POST"])
def create_event(request):
    """Create a new event for the active team."""
    try:
        print("🟢 Create event endpoint hit")

        active_team_id = Team.get_active_team_id(request.user)
        print(f"🟢 Active team ID: {active_team_id}")
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        if request.content_type == 'application/json':
            data = json.loads(request.body)
            print(f"🟢 JSON data received: {data}")
        else:
            data = request.POST.dict()
            print(f"🟢 FormData received: {data}")

        required_fields = ['title', 'start_date']
        for field in required_fields:
            if not data.get(field):
                print(f"❌ Missing required field: {field}")
                return JsonResponse({"success": False, "error": f"{field.replace('_', ' ').title()} is required"})

        start_date = data.get('start_date')
        start_time_str = data.get('start_time', '09:00')
        end_date = data.get('end_date')
        end_time_str = data.get('end_time')
        if not end_date and end_time_str:
            end_date = data.get('start_date')

        print(f"🟢 Date info - Start: {start_date} {start_time_str}, End: {end_date} {end_time_str}")

        try:
            start_time = datetime.fromisoformat(f"{start_date}T{start_time_str}:00")
        except ValueError as e:
            print(f"❌ Start date parsing error: {e}")
            return JsonResponse({"success": False, "error": f"Invalid start date/time format: {str(e)}"})

        if end_date and end_time_str:
            try:
                end_time = datetime.fromisoformat(f"{end_date}T{end_time_str}:00")
            except ValueError as e:
                print(f"❌ End date parsing error: {e}")
                return JsonResponse({"success": False, "error": f"Invalid end date/time format: {str(e)}"})
        else:
            duration_minutes = DEFAULT_EVENT_DURATION_MINUTES
            try:
                if data.get('duration_minutes'):
                    parsed_duration = int(data.get('duration_minutes'))
                    if parsed_duration > 0:
                        duration_minutes = parsed_duration
            except (ValueError, TypeError):
                pass
            end_time = start_time + timedelta(minutes=duration_minutes)
            print(f"🟢 Auto-derived end time using {duration_minutes} minute buffer: {end_time}")

        if end_time <= start_time:
            print("❌ End time is not after start time")
            return JsonResponse({"success": False, "error": "End time must be after start time"})

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

        event_data = {
            "title": data.get('title', 'Untitled Event'),
            "description": data.get('description', ''),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "team_ID": active_team_id,
            "user_id": request.session.get("user_ID") or request.user.id
        }

        is_recurring = data.get('is_recurring') == 'on' or data.get('is_recurring') is True
        if is_recurring:
            print("🔁 Creating recurring event")
            frequency = data.get('frequency', 'weekly')
            ends_on = data.get('ends_on', 'never')
            days = []
            if frequency == 'weekly':
                if hasattr(request, 'POST') and request.POST.getlist('days[]'):
                    days = [int(d) for d in request.POST.getlist('days[]')]
                elif 'days[]' in data:
                    raw_days = data['days[]']
                    if isinstance(raw_days, list):
                        days = [int(d) for d in raw_days]
                    else:
                        try:
                            days = [int(raw_days)]
                        except (TypeError, ValueError):
                            days = []

            recurrence_rule = {
                'frequency': frequency,
                'days': days,
                'end_type': ends_on,
                'interval': 1
            }

            if ends_on == 'on':
                recurrence_rule['end_date'] = data.get('recurrence_end_date')
            elif ends_on == 'after':
                try:
                    recurrence_rule['occurrences'] = int(data.get('occurrences', 10))
                except (ValueError, TypeError):
                    recurrence_rule['occurrences'] = 10

            print(f"🔁 Recurrence rule: {recurrence_rule}")
            result = RecurringEvent.create_recurring_event(event_data, recurrence_rule)
            if result:
                result = [result]
        else:
            result = Event.create(event_data)

        print(f"🟢 Event data to save: {event_data}")
        print(f"🟢 Database result: {result}")

        if not result:
            print("❌ Database returned no result")
            return JsonResponse({"success": False, "error": "Failed to create event in database"})

        new_event_id = result[0]['event_id'] if result and len(result) > 0 else None

        event_with_id = {
            "event_ID": new_event_id,
            "title": event_data['title'],
            "date": data.get('start_date'),
            "time": data.get('start_time')
        }

        context = {
            "action": "create",
            "creator_id": request.session.get("user_ID") or request.user.id
        }

        triggered = EventNotificationTriggers.evaluate_all_triggers(event_with_id, context)
        for trigger in triggered:
            print(f"🔔 EVENT TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")

        try:
            team_members = Team.get_team_members(active_team_id)
        except Exception as notification_err:
            team_members = []
            print(f"Warning: Unable to fetch team members for notifications: {notification_err}")

        notification_payload = {
            'event_id': new_event_id,
            'title': event_data['title'],
            'description': event_data.get('description', ''),
            'start_date': data.get('start_date'),
            'start_time': data.get('start_time'),
        }

        create_event_notifications(notification_payload, team_members, sender_user=request.user, action='create')

        return JsonResponse({
            "success": True,
            "message": "Event created successfully",
            "event_id": new_event_id
        })

    except Exception as e:
        print(f"❌ Error creating event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"})


@login_required
@require_http_methods(["PUT", "PATCH"])
def update_event(request, event_id):
    """Update an existing event with conflict validation."""
    try:
        print(f"🟢 Update event endpoint hit for event_id: {event_id}")

        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to update this event"}, status=403)

        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()

        print(f"🟢 Update data received: {data}")

        update_data = {}
        if 'title' in data and data['title']:
            update_data['title'] = data['title']

        if 'description' in data:
            update_data['description'] = data['description']

        start_date = data.get('start_date')
        start_time_str = data.get('start_time')
        end_date = data.get('end_date')
        end_time_str = data.get('end_time')
        if not end_date and end_time_str:
            end_date = start_date

        start_time = datetime.fromisoformat(existing_event['start_time'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(existing_event['end_time'].replace('Z', '+00:00'))

        if start_date and start_time_str:
            start_datetime_str = f"{start_date}T{start_time_str}:00"
            try:
                start_time = datetime.fromisoformat(start_datetime_str)
                update_data['start_time'] = start_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid start date/time format: {str(e)}"})

        if end_date and end_time_str:
            end_datetime_str = f"{end_date}T{end_time_str}:00"
            try:
                end_time = datetime.fromisoformat(end_datetime_str)
                update_data['end_time'] = end_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid end date/time format: {str(e)}"})

        if end_time <= start_time:
            return JsonResponse({"success": False, "error": "End time must be after start time"})

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

        result = Event.update(event_id, update_data)
        if not result:
            return JsonResponse({"success": False, "error": "Failed to update event in database"})

        return JsonResponse({"success": True, "message": "Event updated successfully"})

    except Exception as e:
        print(f"❌ Error updating event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@require_http_methods(["DELETE"])
def delete_event(request, event_id):
    """Delete an event."""
    try:
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to delete this event"}, status=403)

        success = Event.delete(event_id)
        if not success:
            return JsonResponse({"success": False, "error": "Failed to delete event"})

        try:
            team_members = Team.get_team_members(active_team_id)
        except Exception as notification_err:
            team_members = []
            print(f"Warning: Unable to fetch team members for notifications: {notification_err}")

        try:
            event_start = datetime.fromisoformat(existing_event['start_time'].replace('Z', '+00:00'))
            start_date = event_start.strftime('%Y-%m-%d')
            start_time = event_start.strftime('%H:%M')
        except Exception:
            start_date = None
            start_time = None

        notification_payload = {
            'event_id': existing_event.get('event_id'),
            'title': existing_event.get('title'),
            'description': existing_event.get('description', ''),
            'start_date': start_date,
            'start_time': start_time,
        }

        create_event_notifications(notification_payload, team_members, sender_user=request.user, action='delete')

        return JsonResponse({"success": True, "message": "Event deleted successfully"})

    except Exception as e:
        print(f"❌ Error deleting event: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@require_http_methods(["POST"])
def join_event(request, event_id):
    """Allow a user to join an event as a participant."""
    try:
        event = Event.get_by_id(event_id)
        if not event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        viewer_id = request.session.get("user_ID") or request.user.id
        active_team_id = Team.get_active_team_id(request.user)
        event_team_id = event.get('team_ID')

        if event_team_id and active_team_id and event_team_id != active_team_id and event.get('user_id') != viewer_id:
            return JsonResponse({"success": False, "error": "You don't have permission to join this event"}, status=403)

        participant_payload = _build_event_participant_payload(event, viewer_id)
        if participant_payload['has_joined']:
            return JsonResponse({
                "success": True,
                "message": "Already participating",
                "participant_data": participant_payload
            })

        result = Event.add_participant(event_id, viewer_id)
        if result is None:
            return JsonResponse({"success": False, "error": "Unable to join event"}, status=500)

        participant_payload = _build_event_participant_payload(event, viewer_id)
        return JsonResponse({"success": True, "participant_data": participant_payload})

    except Exception as e:
        print(f"Error joining event {event_id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def leave_event(request, event_id):
    """Allow a user to leave an event they previously joined."""
    try:
        event = Event.get_by_id(event_id)
        if not event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        viewer_id = request.session.get("user_ID") or request.user.id
        active_team_id = Team.get_active_team_id(request.user)
        event_team_id = event.get('team_ID')

        if event_team_id and active_team_id and event_team_id != active_team_id and event.get('user_id') != viewer_id:
            return JsonResponse({"success": False, "error": "You don't have permission to modify this event"}, status=403)

        participant_payload = _build_event_participant_payload(event, viewer_id)
        if participant_payload['is_host']:
            return JsonResponse({"success": False, "error": "Hosts cannot leave their own event"}, status=400)

        if not participant_payload['has_joined']:
            return JsonResponse({
                "success": True,
                "message": "You are not part of this event",
                "participant_data": participant_payload
            })

        success = Event.remove_participant(event_id, viewer_id)
        if not success:
            return JsonResponse({"success": False, "error": "Unable to leave event"}, status=500)

        participant_payload = _build_event_participant_payload(event, viewer_id)
        return JsonResponse({"success": True, "participant_data": participant_payload})

    except Exception as e:
        print(f"Error leaving event {event_id}: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def check_event_conflicts(request):
    """Check for event conflicts without creating an event"""
    try:
        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()

        required_fields = ['start_date', 'start_time']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"success": False, "error": f"{field.replace('_', ' ').title()} is required"})

        start_datetime_str = f"{data['start_date']}T{data['start_time']}:00"
        try:
            start_time = datetime.fromisoformat(start_datetime_str)
        except ValueError as e:
            return JsonResponse({"success": False, "error": f"Invalid start date/time format: {str(e)}"})

        end_date = data.get('end_date')
        end_time_str = data.get('end_time')
        if end_date and end_time_str:
            end_datetime_str = f"{end_date}T{end_time_str}:00"
            try:
                end_time = datetime.fromisoformat(end_datetime_str)
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid end date/time format: {str(e)}"})
        else:
            duration_minutes = data.get('duration_minutes')
            try:
                parsed_duration = int(duration_minutes) if duration_minutes else DEFAULT_EVENT_DURATION_MINUTES
                if parsed_duration <= 0:
                    parsed_duration = DEFAULT_EVENT_DURATION_MINUTES
            except (ValueError, TypeError):
                parsed_duration = DEFAULT_EVENT_DURATION_MINUTES
            end_time = start_time + timedelta(minutes=parsed_duration)

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

        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        if not existing_event.get('is_recurring'):
            return JsonResponse({"success": False, "error": "This is not a recurring event"}, status=400)

        active_team_id = Team.get_active_team_id(request.user)
        if not active_team_id:
            return JsonResponse({"success": False, "error": "No active team selected"})

        if existing_event.get('team_ID') != active_team_id:
            return JsonResponse({"success": False, "error": "You don't have permission to update this event"}, status=403)

        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()

        update_scope = data.get('update_scope', 'all')

        update_data = {}
        if 'title' in data and data['title']:
            update_data['title'] = data['title']
        if 'description' in data:
            update_data['description'] = data['description']

        start_date = data.get('start_date')
        start_time_str = data.get('start_time')
        end_date = data.get('end_date')
        end_time_str = data.get('end_time')

        if start_date and start_time_str:
            start_datetime_str = f"{start_date}T{start_time_str}:00"
            try:
                start_time = datetime.fromisoformat(start_datetime_str)
                update_data['start_time'] = start_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid start date/time format: {str(e)}"})

        if end_date and end_time_str:
            end_datetime_str = f"{end_date}T{end_time_str}:00"
            try:
                end_time = datetime.fromisoformat(end_datetime_str)
                update_data['end_time'] = end_time.isoformat()
            except ValueError as e:
                return JsonResponse({"success": False, "error": f"Invalid end date/time format: {str(e)}"})

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
        existing_event = Event.get_by_id(event_id)
        if not existing_event:
            return JsonResponse({"success": False, "error": "Event not found"}, status=404)

        if not existing_event.get('is_recurring'):
            return JsonResponse({"success": False, "error": "This is not a recurring event. Use regular delete endpoint."}, status=400)

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