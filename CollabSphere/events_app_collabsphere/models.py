from django.conf import settings
from supabase import create_client, Client
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from teams_app_collabsphere.models import Team
import json

User = get_user_model()

# Initialize Supabase client
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class Event:
    """Wrapper for Supabase 'calendarevent' table operations."""

    @staticmethod
    def get_all_for_team(team_ID):
        """Get all events for a specific team."""
        try:
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .order("start_time")
                .execute()
            )
            return getattr(resp, "data", [])
        except Exception as e:
            print("Error fetching events:", e)
            return []

    @staticmethod
    def get_upcoming_for_team(team_ID, limit=5):
        """Get upcoming events for a specific team."""
        try:
            now = datetime.now().isoformat()
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .gte("start_time", now)
                .order("start_time")
                .limit(limit)
                .execute()
            )
            return getattr(resp, "data", [])
        except Exception as e:
            print("Error fetching upcoming events:", e)
            return []

    @staticmethod
    def create(data):
        """Insert a new event."""
        try:  
            res = supabase.table("calendarevent").insert(data).execute()
            print("🟢 Inserted event:", getattr(res, "data", res))
            return getattr(res, "data", res)
        except Exception as e:
            print("❌ Error inserting event into Supabase:", e)
            return None

    @staticmethod
    def update(event_id, data):
        """Update an existing event."""
        try:
            res = supabase.table("calendarevent").update(data).eq("event_id", event_id).execute()
            print("Updated event:", getattr(res, "data", res))
            return getattr(res, "data", res)
        except Exception as e:
            print("Error updating event:", e)
            return None

    @staticmethod
    def delete(event_id):
        """Delete an event."""
        try:
            # First delete participants
            supabase.table("eventsparticipant").delete().eq("event_id", event_id).execute()
            # Then delete the event
            res = supabase.table("calendarevent").delete().eq("event_id", event_id).execute()
            print("Deleted event:", getattr(res, "data", res))
            return True
        except Exception as e:
            print("Error deleting event:", e)
            return False

    @staticmethod
    def get_event_participants(event_id):
        """Get participants for an event."""
        try:
            resp = (
                supabase.table("eventsparticipant")
                .select("user_id, user:user_id(username)")
                .eq("event_id", event_id)
                .execute()
            )
            return getattr(resp, "data", [])
        except Exception as e:
            print("Error fetching event participants:", e)
            return []

    @staticmethod
    def add_participant(event_id, user_id):
        """Add a participant to an event."""
        try:
            res = supabase.table("eventsparticipant").insert({
                "event_id": event_id,
                "user_id": user_id
            }).execute()
            return getattr(res, "data", res)
        except Exception as e:
            print("Error adding participant:", e)
            return None

    @staticmethod
    def get_events_by_date_range(team_ID, start_date, end_date):
        """Get events for a team within a date range."""
        try:
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .gte("start_time", start_date.isoformat())
                .lt("start_time", end_date.isoformat())
                .order("start_time")
                .execute()
            )
            return getattr(resp, "data", [])
        except Exception as e:
            print("Error fetching events by date range:", e)
            return []

    @staticmethod
    def get_by_id(event_id):
        """Get a single event by ID."""
        try:
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("event_id", event_id)
                .single()
                .execute()
            )
            return getattr(resp, "data", None)
        except Exception as e:
            print("Error fetching event by ID:", e)
            return None

    @staticmethod
    def check_conflicts(team_ID, start_time, end_time, exclude_event_id=None):
        """
        Check for conflicting events within the same team.
        Two events conflict if their time ranges overlap.
        
        Args:
            team_ID: The team to check conflicts for
            start_time: Start datetime (ISO format string or datetime)
            end_time: End datetime (ISO format string or datetime)
            exclude_event_id: Event ID to exclude from conflict check (for updates)
        
        Returns:
            List of conflicting events, empty list if no conflicts
        """
        try:
            # Convert to ISO strings if datetime objects
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat()
            
            # Get all events for the team
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .execute()
            )
            
            all_events = getattr(resp, "data", [])
            conflicts = []
            
            for event in all_events:
                # Skip the event being updated
                if exclude_event_id and event.get('event_id') == exclude_event_id:
                    continue
                
                event_start = event.get('start_time', '')
                event_end = event.get('end_time', '')
                
                # Check for overlap: events overlap if one starts before the other ends
                # and ends after the other starts
                # Overlap condition: start1 < end2 AND end1 > start2
                if start_time < event_end and end_time > event_start:
                    conflicts.append({
                        'event_id': event.get('event_id'),
                        'title': event.get('title'),
                        'start_time': event_start,
                        'end_time': event_end
                    })
            
            return conflicts
            
        except Exception as e:
            print("Error checking event conflicts:", e)
            return []


class RecurringEvent:
    """
    Handles recurring event rules, storage, and dynamic expansion.
    
    Recurrence metadata stored in calendarevent table:
    - is_recurring: boolean
    - frequency: 'daily', 'weekly', 'monthly', 'yearly'
    - recurrence_days: JSON array of day indices (0=Sun, 6=Sat) for weekly
    - recurrence_end_type: 'never', 'on', 'after'
    - recurrence_end_date: date string (for 'on' type)
    - recurrence_count: integer (for 'after' type)
    - recurrence_interval: integer (every N days/weeks/months/years, default 1)
    """
    
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_YEARLY = 'yearly'
    
    END_TYPE_NEVER = 'never'
    END_TYPE_ON_DATE = 'on'
    END_TYPE_AFTER_COUNT = 'after'
    
    # Maximum occurrences to generate (safety limit)
    MAX_OCCURRENCES = 365
    
    @staticmethod
    def create_recurring_event(event_data, recurrence_rule):
        """
        Create a recurring event with its recurrence rule.
        
        Args:
            event_data: Base event data (title, description, start_time, end_time, team_ID, user_id)
            recurrence_rule: Dict containing recurrence settings:
                - frequency: 'daily', 'weekly', 'monthly', 'yearly'
                - days: List of day indices for weekly (0=Sun, 6=Sat)
                - end_type: 'never', 'on', 'after'
                - end_date: End date string (for 'on' type)
                - occurrences: Number of occurrences (for 'after' type)
                - interval: Repeat interval (default 1)
        
        Returns:
            Created event with recurrence metadata, or None on failure
        """
        try:
            # Add recurrence metadata to event data
            event_data['is_recurring'] = True
            event_data['frequency'] = recurrence_rule.get('frequency', RecurringEvent.FREQUENCY_WEEKLY)
            
            # Store days as JSON string
            days = recurrence_rule.get('days', [])
            event_data['recurrence_days'] = json.dumps(days) if days else None
            
            event_data['recurrence_end_type'] = recurrence_rule.get('end_type', RecurringEvent.END_TYPE_NEVER)
            event_data['recurrence_end_date'] = recurrence_rule.get('end_date')
            event_data['recurrence_count'] = recurrence_rule.get('occurrences')
            event_data['recurrence_interval'] = recurrence_rule.get('interval', 1)
            
            # Create the master recurring event
            result = Event.create(event_data)
            
            if result and len(result) > 0:
                print(f"🔁 Created recurring event: {result[0].get('event_id')}")
                return result[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error creating recurring event: {e}")
            return None
    
    @staticmethod
    def get_recurring_events_for_team(team_ID):
        """Get all recurring events (master events) for a team."""
        try:
            resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .eq("is_recurring", True)
                .order("start_time")
                .execute()
            )
            return getattr(resp, "data", [])
        except Exception as e:
            print(f"Error fetching recurring events: {e}")
            return []
    
    @staticmethod
    def expand_recurring_event(event, range_start, range_end):
        """
        Expand a single recurring event into individual occurrences within a date range.
        
        Args:
            event: The master recurring event from database
            range_start: Start of the date range (datetime)
            range_end: End of the date range (datetime)
        
        Returns:
            List of expanded event instances (virtual, not stored in DB)
        """
        try:
            if not event.get('is_recurring'):
                return [event]
            
            frequency = event.get('frequency', RecurringEvent.FREQUENCY_WEEKLY)
            interval = event.get('recurrence_interval', 1) or 1
            end_type = event.get('recurrence_end_type', RecurringEvent.END_TYPE_NEVER)
            
            # Parse recurrence days for weekly
            recurrence_days = []
            if event.get('recurrence_days'):
                try:
                    recurrence_days = json.loads(event['recurrence_days'])
                except (json.JSONDecodeError, TypeError):
                    recurrence_days = []
            
            # Parse event start/end times
            event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
            event_duration = event_end - event_start
            
            # Determine recurrence end boundary
            recurrence_end = None
            max_count = RecurringEvent.MAX_OCCURRENCES
            
            if end_type == RecurringEvent.END_TYPE_ON_DATE and event.get('recurrence_end_date'):
                recurrence_end = datetime.fromisoformat(event['recurrence_end_date'])
                if recurrence_end.tzinfo is None:
                    recurrence_end = recurrence_end.replace(hour=23, minute=59, second=59)
            elif end_type == RecurringEvent.END_TYPE_AFTER_COUNT and event.get('recurrence_count'):
                max_count = min(int(event['recurrence_count']), RecurringEvent.MAX_OCCURRENCES)
            
            # Generate occurrences
            occurrences = []
            current_date = event_start
            occurrence_count = 0
            
            while occurrence_count < max_count:
                # Check if we've passed the recurrence end date
                if recurrence_end and current_date.date() > recurrence_end.date():
                    break
                
                # Check if occurrence is within the requested range
                if current_date >= range_start and current_date < range_end:
                    # For weekly frequency, check if the day matches
                    if frequency == RecurringEvent.FREQUENCY_WEEKLY:
                        if recurrence_days and current_date.weekday() not in [((d + 6) % 7) for d in recurrence_days]:
                            # weekday() is Mon=0, but our days are Sun=0, so convert
                            current_date += timedelta(days=1)
                            continue
                    
                    # Create the occurrence instance
                    occurrence = {
                        **event,
                        'occurrence_date': current_date.isoformat(),
                        'start_time': current_date.isoformat(),
                        'end_time': (current_date + event_duration).isoformat(),
                        'is_occurrence': True,
                        'parent_event_id': event.get('event_id'),
                        'occurrence_index': occurrence_count
                    }
                    occurrences.append(occurrence)
                
                # Move to next occurrence based on frequency
                if frequency == RecurringEvent.FREQUENCY_DAILY:
                    current_date += timedelta(days=interval)
                    occurrence_count += 1
                elif frequency == RecurringEvent.FREQUENCY_WEEKLY:
                    if recurrence_days:
                        # Find next matching day
                        current_date += timedelta(days=1)
                        days_checked = 0
                        while days_checked < 7:
                            # Convert weekday to our Sun=0 format
                            current_weekday = (current_date.weekday() + 1) % 7
                            if current_weekday in recurrence_days:
                                break
                            current_date += timedelta(days=1)
                            days_checked += 1
                        occurrence_count += 1
                    else:
                        current_date += timedelta(weeks=interval)
                        occurrence_count += 1
                elif frequency == RecurringEvent.FREQUENCY_MONTHLY:
                    current_date += relativedelta(months=interval)
                    occurrence_count += 1
                elif frequency == RecurringEvent.FREQUENCY_YEARLY:
                    current_date += relativedelta(years=interval)
                    occurrence_count += 1
                else:
                    break
                
                # Safety check - don't go too far into the future
                if current_date > range_end + timedelta(days=1):
                    break
            
            return occurrences
            
        except Exception as e:
            print(f"❌ Error expanding recurring event: {e}")
            import traceback
            traceback.print_exc()
            return [event]  # Return original event as fallback
    
    @staticmethod
    def get_expanded_events_for_range(team_ID, range_start, range_end):
        """
        Get all events for a team within a date range, expanding recurring events.
        
        Args:
            team_ID: Team ID
            range_start: Start of date range (datetime)
            range_end: End of date range (datetime)
        
        Returns:
            List of all events including expanded recurring event occurrences
        """
        try:
            all_events = []
            
            # Get non-recurring events in the range
            non_recurring_resp = (
                supabase.table("calendarevent")
                .select("*")
                .eq("team_ID", team_ID)
                .gte("start_time", range_start.isoformat())
                .lt("start_time", range_end.isoformat())
                .order("start_time")
                .execute()
            )
            non_recurring = [
                event for event in getattr(non_recurring_resp, "data", [])
                if not event.get('is_recurring')
            ]
            all_events.extend(non_recurring)
            
            # Get recurring events (master events that could have occurrences in range)
            recurring = RecurringEvent.get_recurring_events_for_team(team_ID)
            
            for event in recurring:
                # Expand each recurring event
                occurrences = RecurringEvent.expand_recurring_event(event, range_start, range_end)
                all_events.extend(occurrences)
            
            # Sort all events by start time
            all_events.sort(key=lambda e: e.get('start_time', ''))
            
            return all_events
            
        except Exception as e:
            print(f"❌ Error getting expanded events: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    @staticmethod
    def update_recurring_event(event_id, update_data, update_scope='all'):
        """
        Update a recurring event.
        
        Args:
            event_id: The master event ID
            update_data: Fields to update
            update_scope: 'all' (entire series), 'single' (create exception), 'future' (this and future)
        
        Returns:
            Updated event data or None on failure
        """
        try:
            if update_scope == 'all':
                # Update the master event (affects all occurrences)
                return Event.update(event_id, update_data)
            
            elif update_scope == 'single':
                # Create a single exception event (non-recurring copy)
                master_event = Event.get_by_id(event_id)
                if not master_event:
                    return None
                
                # Create a new non-recurring event for this occurrence
                exception_data = {
                    'title': update_data.get('title', master_event['title']),
                    'description': update_data.get('description', master_event.get('description', '')),
                    'start_time': update_data.get('start_time', master_event['start_time']),
                    'end_time': update_data.get('end_time', master_event['end_time']),
                    'team_ID': master_event['team_ID'],
                    'user_id': master_event.get('user_id'),
                    'is_recurring': False,
                    'parent_event_id': event_id,  # Link to master for reference
                    'is_exception': True
                }
                return Event.create(exception_data)
            
            # For 'future' scope - would need more complex logic to split the series
            return None
            
        except Exception as e:
            print(f"❌ Error updating recurring event: {e}")
            return None
    
    @staticmethod
    def delete_recurring_event(event_id, delete_scope='all'):
        """
        Delete a recurring event.
        
        Args:
            event_id: The master event ID
            delete_scope: 'all' (entire series), 'single' (add exception), 'future' (this and future)
        
        Returns:
            True on success, False on failure
        """
        try:
            if delete_scope == 'all':
                # Delete the master event (removes all occurrences)
                # Also delete any exception events
                supabase.table("calendarevent").delete().eq("parent_event_id", event_id).execute()
                return Event.delete(event_id)
            
            elif delete_scope == 'single':
                # For single occurrence deletion, we could add an exclusion date
                # For now, this would require storing exception dates in the master event
                # This is a simplified implementation
                master_event = Event.get_by_id(event_id)
                if not master_event:
                    return False
                
                # Get current exception dates
                exception_dates = []
                if master_event.get('exception_dates'):
                    try:
                        exception_dates = json.loads(master_event['exception_dates'])
                    except:
                        exception_dates = []
                
                # Note: The actual exception date would need to be passed in
                # This is a placeholder for the pattern
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error deleting recurring event: {e}")
            return False
    
    @staticmethod
    def get_recurrence_summary(event):
        """
        Generate a human-readable summary of the recurrence rule.
        
        Args:
            event: Event with recurrence metadata
        
        Returns:
            String describing the recurrence pattern
        """
        if not event.get('is_recurring'):
            return "Does not repeat"
        
        frequency = event.get('frequency', '')
        interval = event.get('recurrence_interval', 1) or 1
        end_type = event.get('recurrence_end_type', 'never')
        
        # Build frequency text
        freq_text = ""
        if frequency == RecurringEvent.FREQUENCY_DAILY:
            freq_text = "every day" if interval == 1 else f"every {interval} days"
        elif frequency == RecurringEvent.FREQUENCY_WEEKLY:
            days = []
            if event.get('recurrence_days'):
                try:
                    day_indices = json.loads(event['recurrence_days'])
                    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
                    days = [day_names[i] for i in day_indices if 0 <= i <= 6]
                except:
                    pass
            
            if interval == 1:
                freq_text = f"weekly on {', '.join(days)}" if days else "every week"
            else:
                freq_text = f"every {interval} weeks on {', '.join(days)}" if days else f"every {interval} weeks"
        elif frequency == RecurringEvent.FREQUENCY_MONTHLY:
            freq_text = "every month" if interval == 1 else f"every {interval} months"
        elif frequency == RecurringEvent.FREQUENCY_YEARLY:
            freq_text = "every year" if interval == 1 else f"every {interval} years"
        
        # Add end condition
        end_text = ""
        if end_type == RecurringEvent.END_TYPE_ON_DATE and event.get('recurrence_end_date'):
            end_text = f", until {event['recurrence_end_date']}"
        elif end_type == RecurringEvent.END_TYPE_AFTER_COUNT and event.get('recurrence_count'):
            end_text = f", {event['recurrence_count']} times"
        
        return f"Repeats {freq_text}{end_text}"