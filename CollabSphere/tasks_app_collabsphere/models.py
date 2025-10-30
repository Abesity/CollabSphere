from django.conf import settings
from supabase import create_client, Client
from datetime import datetime
from django.contrib.auth import get_user_model

User = get_user_model()  # Use the user model from registration_app_collabsphere

# Initialize Supabase client
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)



class Task:
    """Wrapper for Supabase 'tasks' table operations."""

    @staticmethod
    def fetch_team_members():
        """Return list of dicts: {id, username} from public.user."""
        try:
            resp = supabase.table("user").select("user_ID, username").execute()
            members = getattr(resp, "data", resp) or []
            return [{"id": m["user_ID"], "username": m["username"]} for m in members]
        except Exception as e:
            print("Error fetching team members:", e)
            return []

    @staticmethod
    def fetch_comments(task_id):
        """Return list of comments for a given task."""
        try:
            resp = (
                supabase.table("task_comments")
                .select("*")
                .eq("task_id", task_id)
                .order("created_at")
                .execute()
            )
            return getattr(resp, "data", resp) or []
        except Exception as e:
            print("Error fetching comments:", e)
            return []

    @staticmethod
    def get(task_id):
        """Retrieve a single task by ID."""
        try:
            resp = supabase.table("tasks").select("*").eq("task_id", task_id).execute()
            rows = getattr(resp, "data", resp) or []
            return rows[0] if rows else None
        except Exception as e:
            print("Error fetching task:", e)
            return None

    @staticmethod
    def create(data):
        """Insert a new task."""
        try:
            res = supabase.table("tasks").insert(data).execute()
            print("Inserted task:", getattr(res, "data", res))
            return getattr(res, "data", res)
        except Exception as e:
            print("Error inserting task into Supabase:", e)
            return None

    @staticmethod
    def update(task_id, data):
        """Update an existing task."""
        try:
            res = supabase.table("tasks").update(data).eq("task_id", task_id).execute()
            print("Updated task:", getattr(res, "data", res))
            return getattr(res, "data", res)
        except Exception as e:
            print("Error updating task:", e)
            return None

    @staticmethod
    def delete(task_id):
        """Delete task and related comments."""
        try:
            supabase.table("task_comments").delete().eq("task_id", task_id).execute()
            res = supabase.table("tasks").delete().eq("task_id", task_id).execute()
            print("Deleted task:", getattr(res, "data", res))
            return True
        except Exception as e:
            print("Error deleting task:", e)
            return False

    @staticmethod
    def count_by_creator(username):
        """Count number of tasks created by a specific user."""
        try:
            count_res = (
                supabase.table("tasks")
                .select("task_id", count="exact")
                .eq("created_by", username)
                .execute()
            )
            return count_res.count if hasattr(count_res, "count") else len(count_res.data)
        except Exception as e:
            print("Error counting tasks:", e)
            return 0


class Comment:
    """Wrapper for Supabase 'task_comments' table operations."""

    @staticmethod
    def add(task_id, username, content):
        """Add a new comment to a task."""
        created_at = datetime.now().isoformat()
        payload = {
            "task_id": task_id,
            "username": username,
            "content": content,
            "created_at": created_at,
        }

        try:
            supabase.table("task_comments").insert(payload).execute()
            return {
                "success": True,
                "username": username,
                "content": content,
                "created_at": created_at,
            }
        except Exception as e:
            print("Error adding comment:", e)
            return {"error": "DB failure"}


class TaskPermissions:
    """Encapsulates task access logic."""

    @staticmethod
    def user_can_access(task_data, username, user_id):
        created_by = task_data.get("created_by")
        assigned_to = task_data.get("assigned_to")
        assigned_to_username = task_data.get("assigned_to_username")

        return (
            created_by == username
            or assigned_to == user_id
            or assigned_to_username == username
        )
