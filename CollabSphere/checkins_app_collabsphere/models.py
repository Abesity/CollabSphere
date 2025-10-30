from django.conf import settings
from django.utils import timezone
from supabase import create_client
from django.contrib.auth import get_user_model
from datetime import datetime

User = get_user_model()  # CustomUser model from registration_app_collabsphere

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class WellbeingService:
    """Handles all Supabase operations for wellbeing dashboard and check-ins."""

    # ---------------------------------------
    # FETCH CHECK-INS
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
