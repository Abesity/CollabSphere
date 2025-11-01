from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .notification_triggers import EventNotificationTriggers

@require_GET
@login_required
def events_calendar(request):
    """Main events calendar view"""
    try:
        # In a future update, this might fetch events from Supabase
        # For now, just render the calendar page
        return render(request, "events_calendar.html")
    except Exception as e:
        print(f"Error loading events calendar: {e}")
        return render(request, "events_calendar.html", {"error": "Unable to load events."})


@login_required
def create_event(request):
    """
    Example view to demonstrate how to trigger notifications
    when an event is created.
    """
    if request.method == "POST":
        try:
            # Normally you'd save an event here
            # For now, simulate new event data
            event_data = {
                "event_ID": 1,
                "title": request.POST.get("title", "Sample Event"),
                "date": request.POST.get("date", "2025-11-05"),
                "time": request.POST.get("time", "10:00 AM")
            }

            # Define the action context
            context = {
                "action": "create",
                "creator_id": request.session.get("user_ID")
            }

            # Evaluate triggers
            triggered = EventNotificationTriggers.evaluate_all_triggers(event_data, context)

            # Log or dispatch the triggers
            for trigger in triggered:
                print(f"🔔 EVENT TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")

            return JsonResponse({"success": True, "message": "Event created successfully."})

        except Exception as e:
            print(f"Error creating event: {e}")
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request method."})
