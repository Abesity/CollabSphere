from django.conf import settings
from django.utils import timezone
from supabase import create_client
from django.contrib.auth import get_user_model
from datetime import datetime,timedelta

User = get_user_model()  # CustomUser model from registration_app_collabsphere

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class WellbeingService:
    """Handles all Supabase operations for wellbeing dashboard and check-ins."""

    @staticmethod
    def get_team_checkins(team_id, limit=10):
        """Fetch recent check-ins for all members of a team."""
        try:
            # First get all team members
            members_response = supabase.table('user_team')\
                .select('user_id')\
                .eq('team_ID', team_id)\
                .is_('left_at', None)\
                .execute()
            
            if not members_response.data:
                return []
            
            member_ids = [member['user_id'] for member in members_response.data]
            
            # Get check-ins for all team members
            response = (
                supabase.table("wellbeingcheckin")
                .select("""
                    checkin_id, 
                    date_submitted, 
                    mood_rating, 
                    status, 
                    notes,
                    user_id,
                    user:user_id(username, profile_picture)
                """)
                .in_("user_id", member_ids)
                .order("date_submitted", desc=True)  # Keep descending for recent first
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"Error fetching team check-ins: {e}")
            return []
    
    @staticmethod
    def get_team_checkins_for_chart(team_id, days_back=30):
        """Fetch check-ins for chart data for all team members with user details."""
        try:
            cutoff_date = (timezone.now() - timedelta(days=days_back)).isoformat()
            
            # Get all team members
            members_response = supabase.table('user_team')\
                .select('user_id')\
                .eq('team_ID', team_id)\
                .is_('left_at', None)\
                .execute()
            
            if not members_response.data:
                return []
            
            member_ids = [member['user_id'] for member in members_response.data]
            
            response = (
                supabase.table("wellbeingcheckin")
                .select("""
                    checkin_id,
                    date_submitted,
                    status,
                    user_id,
                    user:user_id(username, profile_picture)
                """)
                .in_("user_id", member_ids)
                .gte("date_submitted", cutoff_date)
                .order("date_submitted", desc=False)  # Oldest first for chart
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"Error fetching team chart data: {e}")
            return []
        
    # ---------------------------------------
    # INDIVIDUAL USER CHECK-INS (keep existing)
    # ---------------------------------------
    @staticmethod
    def get_recent_checkins(user_id, limit=10):
        """Fetch the user's most recent wellbeing check-ins."""
        response = (
            supabase.table("wellbeingcheckin")
            .select("checkin_id, date_submitted, mood_rating, status, notes")
            .eq("user_id", int(user_id))
            .order("date_submitted", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    @staticmethod
    def get_recent_checkins_modal(user_id, limit=5):
        """Fetch the most recent check-ins for the modal."""
        response = (
            supabase.table("wellbeingcheckin")
            .select("*")
            .eq("user_id", user_id)
            .order("date_submitted", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    # ---------------------------------------
    # CHECK-IN STATUS HELPERS
    # ---------------------------------------
    @staticmethod
    def has_checked_in_today(user_id):
        """Return True if the user has already submitted a check-in today."""
        today = timezone.now().date()
        start = datetime.combine(today, datetime.min.time()).isoformat()
        end = datetime.combine(today, datetime.max.time()).isoformat()

        response = (
            supabase.table("wellbeingcheckin")
            .select("checkin_id")
            .eq("user_id", user_id)
            .gte("date_submitted", start)
            .lte("date_submitted", end)
            .execute()
        )
        return bool(response.data)

    # ---------------------------------------
    # USER LOOKUP
    # ---------------------------------------
    @staticmethod
    def get_supabase_user_id(email):
        """Fetch the Supabase user_ID for a given email."""
        response = (
            supabase.table("user").select("user_ID").eq("email", email).single().execute()
        )
        if response.data and "user_ID" in response.data:
            return response.data["user_ID"]
        raise Exception("User not found in Supabase.")

    # ---------------------------------------
    # CREATE NEW CHECK-IN
    # ---------------------------------------
    @staticmethod
    def submit_checkin(user_id, mood_rating, status, notes):
        """Insert a new wellbeing check-in record."""
        payload = {
            "user_id": user_id,
            "mood_rating": int(mood_rating) if mood_rating else None,
            "status": status or "Okay",
            "notes": notes or "",
            "date_submitted": timezone.now().isoformat(),
        }
        response = supabase.table("wellbeingcheckin").insert(payload).execute()
        return response.data or []