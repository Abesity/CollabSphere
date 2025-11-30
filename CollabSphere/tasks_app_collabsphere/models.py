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
        """Return list of comments for a given task, organized by thread."""
        try:
            resp = (
                supabase.table("task_comments")
                .select("*")
                .eq("task_id", task_id)
                .order("created_at")
                .execute()
            )
            comments = getattr(resp, "data", resp) or []
            
            # Organize comments into threads
            return Task._organize_comments_threaded(comments)
        except Exception as e:
            print("Error fetching comments:", e)
            return []

    @staticmethod
    def _organize_comments_threaded(comments):
        """Organize flat comment list into threaded structure."""
        comment_dict = {c['comment_id']: {**c, 'replies': []} for c in comments}
        root_comments = []
        
        for comment in comments:
            parent_id = comment.get('parent_id')
            if parent_id and parent_id in comment_dict:
                comment_dict[parent_id]['replies'].append(comment_dict[comment['comment_id']])
            else:
                root_comments.append(comment_dict[comment['comment_id']])
        
        return root_comments

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
# Get users team members and current active team
    @staticmethod
    def get_active_team_members(django_user):
        """Get members of user's active team"""
        try:
            # Use the imported Team class
            return Team.get_active_team_members(django_user)
        except Exception as e:
            print("Error fetching active team members:", e)
            return []

    @staticmethod
    def get_user_active_team_id(django_user):
        """Get user's active team ID"""
        try:
            # Use the imported Team class
            return Team.get_active_team_id(django_user)
        except Exception as e:
            print("Error getting active team ID:", e)
            return None
        
# HELPER METHOD TO GET TEAM MEMBERS
    @staticmethod
    def get_team_members(team_ID):
        """Get members of a specific team"""
        try:
            members_response = supabase.table('user_team')\
                .select('user_id, user:user_id(username, profile_picture)')\
                .eq('team_ID', team_ID)\
                .is_('left_at', None)\
                .execute()
            
            members = []
            for member_data in members_response.data:
                user_data = member_data.get('user', {})
                members.append({
                    "id": member_data.get('user_id'),
                    "username": user_data.get('username', 'Unknown')
                })
            
            return members
            
        except Exception as e:
            print(f"Error fetching team {team_ID} members:", e)
            return []
        
    @staticmethod
    def get_team_name(team_ID):
        """Get team name by team ID"""
        try:
            if not team_ID:
                return None
                
            response = supabase.table('team')\
                .select('team_name')\
                .eq('team_ID', team_ID)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]['team_name']
            return None
        except Exception as e:
            print(f"Error fetching team name for ID {team_ID}:", e)
            return None
# COMMENTS
class Comment:
    """Wrapper for Supabase 'task_comments' table operations."""

    @staticmethod
    def add(task_id, username, content, parent_id=None):
        """Add a new comment or reply to a task."""
        created_at = datetime.now().isoformat()
        payload = {
            "task_id": task_id,
            "username": username,
            "content": content,
            "created_at": created_at,
            "parent_id": parent_id,
        }

        try:
            res = supabase.table("task_comments").insert(payload).execute()
            data = getattr(res, "data", None)
            comment_id = None
            if data and isinstance(data, list) and len(data) > 0:
                comment_id = data[0].get("comment_id") or data[0].get("id")

            return {
                "success": True,
                "username": username,
                "content": content,
                "created_at": created_at,
                "comment_id": comment_id,
                "parent_id": parent_id,
            }
        except Exception as e:
            print("Error adding comment:", e)
            return {"error": "DB failure"}

    @staticmethod
    def get(comment_id):
        """Retrieve a single comment by its comment_id."""
        try:
            res = supabase.table("task_comments").select("*").eq("comment_id", comment_id).execute()
            rows = getattr(res, "data", res) or []
            return rows[0] if rows else None
        except Exception as e:
            print("Error fetching comment:", e)
            return None

    @staticmethod
    def delete(comment_id):
        """Delete a comment by its comment_id (cascade will delete replies)."""
        try:
            supabase.table("task_comments").delete().eq("comment_id", comment_id).execute()
            return True
        except Exception as e:
            print("Error deleting comment:", e)
            return False

    @staticmethod
    def get_commenter_usernames(task_id):
        """Return a set of usernames who have commented on a task."""
        try:
            resp = (
                supabase.table("task_comments")
                .select("username")
                .eq("task_id", task_id)
                .execute()
            )
            rows = getattr(resp, "data", resp) or []
            return {row.get("username") for row in rows if row.get("username")}
        except Exception as e:
            print("Error fetching comment usernames:", e)
            return set()


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