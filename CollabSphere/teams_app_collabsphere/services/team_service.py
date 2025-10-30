from django.utils import timezone
from django.contrib import messages
from ..models import TeamModel
from supabase import create_client
from django.conf import settings

# Initialize Supabase Storage client
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class TeamService:
    """
    High-level logic that combines Supabase database and storage operations.
    Used by Django views.
    """

    # =====================================================
    # TEAM CREATION
    # =====================================================
    @staticmethod
    def create_team(request, name, description="", icon_file=None):
        """
        Creates a new team in Supabase + uploads icon if provided.
        """
        user = request.user
        owner_id = user.id
        icon_url = None

        # Upload icon to Supabase Storage if provided
        if icon_file:
            icon_url = TeamService.upload_team_icon(owner_id, icon_file)

        # Insert team record into Supabase
        team_record = TeamModel.create_team(
            owner_id=owner_id,
            name=name,
            description=description,
            icon_url=icon_url
        )

        if not team_record:
            messages.error(request, "Failed to create team.")
            return None

        messages.success(request, f"✅ Team '{name}' created successfully!")
        return team_record

    # =====================================================
    # TEAM FETCHING
    # =====================================================
    @staticmethod
    def list_user_teams(user_id: int):
        """Return all teams for a given user."""
        return TeamModel.get_user_teams(user_id)

    @staticmethod
    def get_team_detail(team_id: int):
        """Return details for a specific team."""
        team = TeamModel.get_team_by_id(team_id)
        if team:
            team["members"] = TeamModel.get_team_members(team_id)
        return team

    # =====================================================
    # TEAM SWITCH / MEMBERSHIP
    # =====================================================
    @staticmethod
    def switch_team(request, team_id: int):
        """Set the user’s active team."""
        if TeamModel.switch_team(request.user, team_id):
            messages.info(request, "✅ Switched active team.")
            return True
        messages.error(request, "❌ Failed to switch team.")
        return False

    @staticmethod
    def join_team(user_id: int, team_id: int):
        """Adds a user to a team."""
        return TeamModel.add_user_to_team(user_id, team_id)

    @staticmethod
    def leave_team(user_id: int, team_id: int):
        """Removes a user from a team."""
        return TeamModel.remove_user_from_team(user_id, team_id)

    # =====================================================
    # SUPABASE STORAGE
    # =====================================================
    @staticmethod
    def upload_team_icon(user_id, icon_file):
        """Uploads team icon to Supabase Storage and returns public URL."""
        try:
            bucket = supabase.storage.from_("team-icons")
            file_path = f"team_icons/{user_id}_{icon_file.name}"
            file_bytes = icon_file.read()

            try:
                bucket.upload(file_path, file_bytes)
            except Exception:
                bucket.update(file_path, file_bytes)

            public_url = bucket.get_public_url(file_path)
            return public_url
        except Exception as e:
            print("❌ Supabase upload_team_icon failed:", e)
            return None
