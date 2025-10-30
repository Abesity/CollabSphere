from django.conf import settings
from supabase import create_client
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()  # CustomUser from registration_app_collabsphere

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class SupabaseService:
    """Handles all Supabase operations used in collabsphere_app."""

    # -------------------------------
    # USER METHODS
    # -------------------------------
    @staticmethod
    def get_user_by_id(user_id: int):
        """Fetch a user's data from Supabase."""
        response = supabase.table("user").select("*").eq("user_ID", user_id).execute()
        return response.data[0] if response.data else {}

    @staticmethod
    def get_user_by_email(email: str):
        """Fetch a user's Supabase record via email."""
        res = supabase.table("user").select("user_ID").eq("email", email).single().execute()
        return res.data if res.data else None

    @staticmethod
    def update_user_profile(user_id, update_data):
        """Update a Supabase user record."""
        return supabase.table("user").update(update_data).eq("user_ID", int(user_id)).execute()

    # -------------------------------
    # WELLBEING CHECK-IN METHODS
    # -------------------------------
    @staticmethod
    def get_today_checkins(user_id):
        """Return True if user has a check-in today."""
        today_date = timezone.now().date().isoformat()
        response = (
            supabase.table("wellbeingcheckin")
            .select("checkin_id, date_submitted, user_id")
            .eq("user_id", int(user_id))
            .execute()
        )
        today_checkins = [
            c for c in response.data if c.get("date_submitted", "").startswith(today_date)
        ]
        return len(today_checkins) > 0

    @staticmethod
    def verify_checkin_today(user_id):
        """Verify if user has checked in today."""
        today = timezone.now().date().isoformat()
        response = (
            supabase.table("wellbeingcheckin")
            .select("date_submitted")
            .eq("user_id", user_id)
            .gte("date_submitted", today)
            .execute()
        )
        return len(response.data) > 0

    @staticmethod
    def get_all_checkins(user_id):
        """Fetch all check-ins for debugging."""
        response = (
            supabase.table("wellbeingcheckin")
            .select("*")
            .eq("user_id", user_id)
            .order("date_submitted", desc=True)
            .execute()
        )
        return response.data

    # -------------------------------
    # TASK METHODS
    # -------------------------------
    @staticmethod
    def get_user_tasks(user_id, username):
        """Get all tasks created by or assigned to the user."""
        created_tasks = (
            supabase.table("tasks").select("*").eq("created_by", username).execute().data or []
        )

        assigned_tasks = (
            supabase.table("tasks")
            .select("*")
            .or_(f"assigned_to.eq.{user_id},assigned_to_username.eq.{username}")
            .neq("created_by", username)
            .execute()
            .data
            or []
        )

        all_tasks = created_tasks + assigned_tasks
        all_tasks.sort(key=lambda x: x.get("date_created", ""), reverse=True)
        return {
            "created_tasks": created_tasks,
            "assigned_tasks": assigned_tasks,
            "all_tasks": all_tasks,
        }

    # -------------------------------
    # PROFILE PICTURE HANDLING
    # -------------------------------
    @staticmethod
    def upload_profile_picture(user_id, profile_picture):
        """Upload a profile picture and return the public URL."""
        file_path = f"profile_pictures/{user_id}_{profile_picture.name}"
        file_bytes = profile_picture.read()
        bucket = supabase.storage.from_("profile_pictures")

        try:
            try:
                bucket.upload(file_path, file_bytes)
            except Exception:
                bucket.update(file_path, file_bytes)
            public_url = bucket.get_public_url(file_path)
            return public_url
        except Exception as e:
            raise Exception(f"Upload failed: {e}")

    # -------------------------------
    # ADMIN METHODS
    # -------------------------------
    @staticmethod
    def get_all_users():
        """Fetch all users (for admin dashboard)."""
        response = supabase.table("users").select("*").execute()
        return response.data or []
