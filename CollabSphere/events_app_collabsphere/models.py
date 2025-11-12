from django.conf import settings
from supabase import create_client, Client
from datetime import datetime
from django.contrib.auth import get_user_model
from teams_app_collabsphere.models import Team

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