from django.conf import settings
from django.contrib.auth import get_user_model
from supabase import create_client, Client
from datetime import datetime, timezone

# Use your registered user model
User = get_user_model()

# Initialize Supabase client
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class TeamModel:
    """
    Handles interactions with the 'team' and 'user_team' tables in Supabase.
    Provides high-level methods to create, fetch, and manage teams + members.
    """

    # =====================================================
    # TEAM TABLE METHODS
    # =====================================================
    @staticmethod
    def create_team(owner_id: int, name: str, description: str = "", icon_url: str = None):
        """
        Creates a new team in Supabase and automatically links the owner in user_team.
        """
        default_icon_url = static("images/default-team-icon.png")
        icon = icon_url or default_icon_url
        now = datetime.now(timezone.utc).isoformat()

        # Insert into 'team'
        try:
            response = supabase.table("team").insert({
                "team_name": name,
                "description": description,
                "joined_at": now,
                "user_id_owner": owner_id,
                "icon_url": icon
            }).execute()

            if not response.data:
                print("❌ Failed to insert new team (no data returned).")
                return None

            team = response.data[0]
            team_id = team.get("team_ID")

            # Add owner as a member in user_team
            supabase.table("user_team").insert({
                "user_id": owner_id,
                "team_id": team_id,
                "joined_at": now,
                "left_at": None
            }).execute()

            return team

        except Exception as e:
            print("❌ Supabase create_team failed:", e)
            return None

    @staticmethod
    def get_team_by_id(team_id: int):
        """Fetch a specific team by its ID."""
        try:
            response = supabase.table("team").select("*").eq("team_ID", team_id).single().execute()
            return response.data
        except Exception as e:
            print("❌ Supabase get_team_by_id failed:", e)
            return None

    @staticmethod
    def get_all_teams():
        """Fetch all teams (admin-level usage)."""
        try:
            response = supabase.table("team").select("*").execute()
            return response.data
        except Exception as e:
            print("❌ Supabase get_all_teams failed:", e)
            return []

    @staticmethod
    def delete_team(team_id: int):
        """Deletes a team and all its user_team relationships."""
        try:
            # Remove all user_team links first (to maintain FK consistency)
            supabase.table("user_team").delete().eq("team_id", team_id).execute()
            # Then delete team
            supabase.table("team").delete().eq("team_ID", team_id).execute()
            return True
        except Exception as e:
            print("❌ Supabase delete_team failed:", e)
            return False

    # =====================================================
    # USER_TEAM TABLE METHODS
    # =====================================================
    @staticmethod
    def get_user_teams(user_id: int):
        """
        Returns a list of all teams that a user belongs to.
        """
        try:
            user_teams = supabase.table("user_team").select("team_id").eq("user_id", user_id).execute()
            team_ids = [ut["team_id"] for ut in user_teams.data] if user_teams.data else []
            if not team_ids:
                return []

            teams = supabase.table("team").select("*").in_("team_ID", team_ids).execute()
            return teams.data or []
        except Exception as e:
            print("❌ Supabase get_user_teams failed:", e)
            return []

    @staticmethod
    def get_team_members(team_id: int):
        """
        Returns a list of members in a given team, including user details.
        """
        try:
            # Get all user IDs linked to the team
            user_team_data = supabase.table("user_team").select("user_id, joined_at").eq("team_id", team_id).execute()
            user_ids = [row["user_id"] for row in user_team_data.data] if user_team_data.data else []
            if not user_ids:
                return []

            # Fetch user details for each user_id
            users = supabase.table("user").select("user_ID, username, avatar_url").in_("user_ID", user_ids).execute()
            return users.data or []
        except Exception as e:
            print("❌ Supabase get_team_members failed:", e)
            return []

    @staticmethod
    def add_user_to_team(user_id: int, team_id: int):
        """Adds a user to a team (creates user_team entry)."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            supabase.table("user_team").insert({
                "user_id": user_id,
                "team_id": team_id,
                "joined_at": now,
                "left_at": None
            }).execute()
            return True
        except Exception as e:
            print("❌ Supabase add_user_to_team failed:", e)
            return False

    @staticmethod
    def remove_user_from_team(user_id: int, team_id: int):
        """Marks user as having left the team."""
        try:
            supabase.table("user_team").update({
                "left_at": datetime.now(timezone.utc).isoformat()
            }).eq("user_id", user_id).eq("team_id", team_id).execute()
            return True
        except Exception as e:
            print("❌ Supabase remove_user_from_team failed:", e)
            return False

    # =====================================================
    # USER PROFILE INTEGRATION
    # =====================================================
    @staticmethod
    def switch_team(user: User, team_id: int):
        """
        Sets the user's active team on their profile (if profile model supports it).
        """
        try:
            if hasattr(user, "profile"):
                user.profile.active_team_id = team_id
                user.profile.save()
                return True
            else:
                print("⚠️ User has no profile attribute. Skipping switch_team update.")
                return False
        except Exception as e:
            print("❌ switch_team failed:", e)
            return False
        
        
