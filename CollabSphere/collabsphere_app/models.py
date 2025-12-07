from django.conf import settings
from supabase import create_client
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

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
        print(f"DEBUG get_user_tasks: Fetching tasks for user_id={user_id}, username={username}")
        created_tasks = (
            supabase.table("tasks").select("*").eq("created_by", username).execute().data or []
        )
        print(f"DEBUG get_user_tasks: Created tasks count={len(created_tasks)}")
        # Build a safe OR clause: check numeric assigned_to, string-assigned_to, and assigned_to_username
        try:
            # Quote string comparisons properly for Supabase filter syntax
            username_quoted = f"'" + str(username).replace("'", "\\'") + f"'"
            # Only check numeric assigned_to and assigned_to_username (avoid quoted numeric forms)
            or_clause = f"assigned_to.eq.{int(user_id)},assigned_to_username.eq.{username_quoted}"
        except Exception:
            # Fallback: conservative OR clause using username only
            username_quoted = f"'" + str(username).replace("'", "\\'") + f"'"
            or_clause = f"assigned_to_username.eq.{username_quoted}"
        logger.debug(f"get_user_tasks: Supabase OR clause -> {or_clause}")
        # Fetch assigned tasks via OR clause, then filter out tasks the user created
        assigned_response = (
            supabase.table("tasks")
            .select("*")
            .or_(or_clause)
            .execute()
        )
        assigned_tasks_raw = assigned_response.data or []
        # Some PostgREST filter combinations can behave unexpectedly; do the final
        # exclusion of user-created tasks in Python to ensure correct results.
        assigned_tasks = [t for t in assigned_tasks_raw if t.get("created_by") != username]
        print(f"DEBUG get_user_tasks: Assigned tasks raw count={len(assigned_tasks_raw)}")
        print(f"DEBUG get_user_tasks: Assigned tasks filtered count={len(assigned_tasks)}")

        all_tasks = created_tasks + assigned_tasks
        all_tasks.sort(key=lambda x: x.get("date_created", ""), reverse=True)
        print(f"DEBUG get_user_tasks: Total tasks={len(all_tasks)}")
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
        response = supabase.table("user").select("*").execute()
        return response.data or []

    @staticmethod
    def get_user_notifications(user_id, limit=10):
        """Fetch recent notifications for the user from Supabase."""
        if not user_id:
            return []

        try:
            response = (
                supabase.table("notifications")
                .select("notification_id, notification_type, title, message, read, created_at, related_object_url")
                .eq("recipient", int(user_id))
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            print(f"Error fetching notifications for user {user_id}: {e}")
            return []
