from django.db import models
from django.conf import settings
from supabase import create_client
import os
import uuid

# Get user model from settings
User = settings.AUTH_USER_MODEL

# Initialize Supabase client
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class Team:
    """Team model handling all database communications for teams""" 
    supabase = supabase
   
    @staticmethod
    def get_supabase_user_id(django_user):
        """Get or create Supabase user ID for Django user"""
        try:
            # Check if user exists in Supabase by email
            existing_user = supabase.table('user')\
                .select('user_ID, email, username')\
                .eq('email', django_user.email)\
                .execute()
            
            if existing_user.data:
                # User exists in Supabase, return their Supabase ID
                supabase_user_id = existing_user.data[0]['user_ID']
                print(f"Found Supabase user ID {supabase_user_id} for Django user {django_user.id}")
                return supabase_user_id
            
            # User doesn't exist in Supabase, create them
            user_data = {
                'username': django_user.username,
                'email': django_user.email,
                'password': 'django-synced-user',  # Required field
                'created_at': django_user.date_joined.isoformat() if hasattr(django_user, 'date_joined') and django_user.date_joined else 'now()',
                'profile_picture': getattr(django_user, 'profile_picture', ''),
                'full_name': f"{django_user.first_name} {django_user.last_name}".strip() or django_user.username,
                'title': getattr(django_user, 'title', ''),
                'role_id': getattr(django_user, 'role_id', None)
            }
            
            # Remove None values
            user_data = {k: v for k, v in user_data.items() if v is not None}
            
            result = supabase.table('user')\
                .insert(user_data)\
                .execute()
            
            if result.data:
                supabase_user_id = result.data[0]['user_ID']
                print(f"Created new Supabase user ID {supabase_user_id} for Django user {django_user.id}")
                return supabase_user_id
            else:
                print(f"Failed to create Supabase user for Django user {django_user.id}")
                return None
                
        except Exception as e:
            print(f"Error getting Supabase user ID for Django user {django_user.id}: {e}")
            return None

    @staticmethod
    def upload_team_icon(icon_file):
        """Upload team icon to Supabase Storage"""
        try:
            if not icon_file:
                return None
                
            # Upload to Supabase Storage
            file_extension = os.path.splitext(icon_file.name)[1]
            file_name = f"team_icon_{uuid.uuid4()}{file_extension}"
            
            # Read file content
            file_content = icon_file.read()
            
            # Upload file to Supabase Storage
            upload_response = supabase.storage.from_("team-icons").upload(
                file_name,
                file_content,
                {"content-type": icon_file.content_type}
            )
            
            if upload_response:
                # Get public URL
                public_url_response = supabase.storage.from_("team-icons").get_public_url(file_name)
                return public_url_response
            else:
                print("Failed to upload team icon to Supabase Storage")
                return None
                
        except Exception as e:
            print(f"Error uploading team icon: {e}")
            return None

    @staticmethod
    def get_user_teams(django_user):
        """Get all teams where the user is a member"""
        try:
            # Get the Supabase user ID
            supabase_user_id = Team.get_supabase_user_id(django_user)
            if not supabase_user_id:
                return []

            # Query to get teams where user is a member
            response = supabase.table('user_team')\
                .select('team_ID, team(*)')\
                .eq('user_id', supabase_user_id)\
                .is_('left_at', None)\
                .execute()
            
            teams = []
            for membership in response.data:
                team_data = membership.get('team', {})
                if team_data:
                    # Get team owner information
                    owner_response = supabase.table('user')\
                        .select('*')\
                        .eq('user_ID', team_data.get('user_id_owner'))\
                        .execute()
                    
                    team_data['owner'] = owner_response.data[0] if owner_response.data else {'username': f'user-{team_data.get("user_id_owner")}'}
                    
                    # Get team members with profile pictures
                    members_response = supabase.table('user_team')\
                        .select('user_id, user!inner(username, profile_picture)')\
                        .eq('team_ID', team_data['team_ID'])\
                        .is_('left_at', None)\
                        .execute()
                    
                    team_data['members'] = members_response.data if members_response.data else []
                    teams.append(team_data)
            
            return teams
            
        except Exception as e:
            print(f"Error getting user teams: {e}")
            return []
        
    @staticmethod
    def get(team_ID):
            """Get a specific team by ID"""
            try:
                response = supabase.table('team')\
                    .select('*')\
                    .eq('team_ID', team_ID)\
                    .execute()
                
                if response.data:
                    return response.data[0]
                return None
            except Exception as e:
                print(f"Error getting team: {e}")
                return None
        
    @staticmethod
    def delete(team_ID):
            """Delete a team"""
            try:
                response = supabase.table('team')\
                    .delete()\
                    .eq('team_ID', team_ID)\
                    .execute()
                
                return {'success': True, 'message': 'Team deleted successfully'}
            except Exception as e:
                print(f"Error deleting team: {e}")
                return {'success': False, 'error': str(e)}

    @staticmethod
    def create_new_team(team_name, description, icon_file, django_user, selected_members):
        """Create a new team and add members"""
        try:
            # Get the Supabase user ID for the owner
            owner_supabase_id = Team.get_supabase_user_id(django_user)
            if not owner_supabase_id:
                return {'success': False, 'error': 'Failed to get user information. Please try again.'}
            
            # Handle file upload
            icon_url = Team.upload_team_icon(icon_file)
            
            # Insert team
            team_response = supabase.table('team')\
                .insert({
                    'team_name': team_name,
                    'description': description,
                    'icon_url': icon_url,
                    'user_id_owner': owner_supabase_id,
                    'joined_at': 'now()'
                })\
                .execute()
            
            if not team_response.data:
                return {'success': False, 'error': 'Failed to create team in database.'}
            
            team_ID = team_response.data[0]['team_ID']
            
            # Add owner as member
            owner_member_result = supabase.table('user_team')\
                .insert({
                    'user_id': owner_supabase_id,
                    'team_ID': team_ID,
                    'joined_at': 'now()'
                })\
                .execute()
            
            if not owner_member_result.data:
                # If adding owner as member fails, delete the team and return error
                supabase.table('team').delete().eq('team_ID', team_ID).execute()
                return {'success': False, 'error': 'Failed to add owner as team member.'}
            
            # Add selected members if any - using Supabase IDs directly
            if selected_members and selected_members.strip():
                supabase_member_ids = [int(id.strip()) for id in selected_members.split(',') if id.strip()]
                
                print(f"Attempting to add {len(supabase_member_ids)} members to team: {supabase_member_ids}")
                
                for supabase_member_id in supabase_member_ids:
                    try:
                        # Skip if trying to add owner again (already added above)
                        if supabase_member_id == owner_supabase_id:
                            continue
                            
                        # Add member to team
                        member_result = supabase.table('user_team')\
                            .insert({
                                'user_id': supabase_member_id,
                                'team_ID': team_ID,
                                'joined_at': 'now()'
                            })\
                            .execute()
                        
                        if member_result.data:
                            print(f"Successfully added member {supabase_member_id} to team")
                        else:
                            print(f"Failed to add member {supabase_member_id} to team")
                            
                    except Exception as e:
                        print(f"Error adding member {supabase_member_id} to team: {e}")
            
            return {'success': True, 'team_ID': team_ID}
            
        except Exception as e:
            print(f"Error creating team: {e}")
            return {'success': False, 'error': f'Database error: {str(e)}'}
    
    @staticmethod
    def get_active_team_members(django_user):
        """Get members of user's active team"""
        try:
            # Get active team ID
            active_team = Team.get_active_team(django_user)
            if not active_team:
                print(f"DEBUG: No active team for user {django_user.username}")
                return []
            
            active_team_id = active_team['team_ID']
            print(f"DEBUG: Active team ID found: {active_team_id}")
            
            # Get team members
            members_response = Team.supabase.table('user_team')\
                .select('user_id, user:user_id(username, profile_picture)')\
                .eq('team_ID', active_team_id)\
                .is_('left_at', None)\
                .execute()
            
            members = []
            for member_data in members_response.data:
                user_data = member_data.get('user', {})
                members.append({
                    "id": member_data.get('user_id'),
                    "username": user_data.get('username', 'Unknown')
                })
            
            print(f"DEBUG: Found {len(members)} members for active team {active_team_id}")
            return members
            
        except Exception as e:
            print(f"Error fetching active team members: {e}")
            return []
                
    @staticmethod
    def switch_user_team(django_user, team_ID):
        """Switch user's active team"""
        try:
            # Get the Supabase user ID
            supabase_user_id = Team.get_supabase_user_id(django_user)
            if not supabase_user_id:
                return {'success': False, 'error': 'User not found in database'}

            # Verify user is member of the team
            membership_check = supabase.table('user_team')\
                .select('*')\
                .eq('user_id', supabase_user_id)\
                .eq('team_ID', team_ID)\
                .is_('left_at', None)\
                .execute()
            
            if not membership_check.data:
                return {'success': False, 'error': 'Not a member of this team'}
            
            return {'success': True}
            
        except Exception as e:
            print(f"Error switching team: {e}")
            return {'success': False, 'error': str(e)}
        
    @staticmethod
    def update_team(team_ID, team_name, description, icon_file, remove_icon, team_members, members_to_remove, django_user):
        """Update an existing team"""
        try:
            # Get the Supabase user ID for the current user
            current_user_id = Team.get_supabase_user_id(django_user)
            if not current_user_id:
                return {'success': False, 'error': 'Failed to get user information.'}

            # Verify user owns the team or has permission to edit
            team_response = supabase.table('team')\
                .select('user_id_owner, icon_url')\
                .eq('team_ID', team_ID)\
                .execute()
            
            if not team_response.data:
                return {'success': False, 'error': 'Team not found.'}
            
            team_owner_id = team_response.data[0]['user_id_owner']
            if team_owner_id != current_user_id:
                return {'success': False, 'error': 'You do not have permission to edit this team.'}

            # Handle icon upload/removal
            current_icon_url = team_response.data[0].get('icon_url')
            icon_url = current_icon_url  # Keep current by default
            
            if icon_file:
                new_icon_url = Team.upload_team_icon(icon_file)
                if new_icon_url:
                    icon_url = new_icon_url
            elif remove_icon:
                icon_url = None

            # Prepare update data
            update_data = {
                'team_name': team_name,
                'description': description,
            }
            if icon_url != current_icon_url:  # Only update if changed
                update_data['icon_url'] = icon_url

            # Update team info in Supabase (only if there are changes)
            if update_data:
                update_response = supabase.table('team')\
                    .update(update_data)\
                    .eq('team_ID', team_ID)\
                    .execute()

                if not update_response.data:
                    return {'success': False, 'error': 'Failed to update team information.'}

            # Add debug logging
            print(f"DEBUG: Team owner ID: {team_owner_id}")
            print(f"DEBUG: Members to add: {team_members}")
            print(f"DEBUG: Members to remove: {members_to_remove}")

            # Handle member additions
            if team_members:
                print(f"DEBUG: Processing {len(team_members)} members to add")
                for user_id in team_members:
                    # Skip if trying to add owner (they're already a member)
                    if user_id == team_owner_id:
                        print(f"DEBUG: Skipping owner {user_id}")
                        continue
                    
                    # Verify user exists in database
                    user_check = supabase.table('user')\
                        .select('user_ID, username')\
                        .eq('user_ID', user_id)\
                        .execute()
                    
                    if not user_check.data:
                        print(f"ERROR: User {user_id} does not exist in database")
                        continue
                    else:
                        print(f"DEBUG: User {user_id} exists: {user_check.data[0]['username']}")
                    
                    # Check if user is already an active member
                    existing_member = supabase.table('user_team')\
                        .select('*')\
                        .eq('user_id', user_id)\
                        .eq('team_ID', team_ID)\
                        .is_('left_at', None)\
                        .execute()
                    
                    # Only add if not already an active member
                    if not existing_member.data:
                        try:
                            print(f"DEBUG: Attempting to add member {user_id} to team")
                            # Add new member with better error handling
                            add_result = supabase.table('user_team')\
                                .insert({
                                    'user_id': user_id,
                                    'team_ID': team_ID,
                                    'joined_at': 'now()'
                                })\
                                .execute()
                            
                            if add_result.data:
                                print(f"SUCCESS: Added member {user_id} to team")
                            else:
                                # Check if it's actually a duplicate despite our check
                                print(f"WARNING: No data returned when adding member {user_id}")
                                
                        except Exception as e:
                            error_str = str(e)
                            # Check for various duplicate error messages
                            if any(dup_indicator in error_str.lower() for dup_indicator in 
                                ['duplicate key', 'already exists', 'unique constraint', '23505']):
                                print(f"INFO: Member {user_id} already exists in team")
                                # Continue with other members
                                continue
                            elif 'server disconnected' in error_str.lower():
                                print(f"WARNING: Server disconnected when adding member {user_id}, but member may have been added")
                                # Assume success and continue
                                continue
                            else:
                                print(f"ERROR adding member {user_id}: {e}")
                                # For non-duplicate errors, continue with other members
                                continue
                    else:
                        print(f"INFO: Member {user_id} is already in the team")
            
            # Handle member removals
            if members_to_remove:
                print(f"DEBUG: Processing {len(members_to_remove)} members to remove")
                for user_id in members_to_remove:
                    # Don't allow removing the team owner
                    if user_id != team_owner_id:
                        try:
                            # Mark member as left instead of deleting
                            remove_result = supabase.table('user_team')\
                                .update({'left_at': 'now()'})\
                                .eq('user_id', user_id)\
                                .eq('team_ID', team_ID)\
                                .is_('left_at', None)\
                                .execute()
                                
                            if not remove_result.data:
                                print(f"Warning: Failed to remove member {user_id} from team")
                                
                        except Exception as e:
                            print(f"Error removing member {user_id}: {e}")
                            # Continue with other removals even if one fails

            return {'success': True, 'message': 'Team updated successfully'}

        except Exception as e:
            print(f"Error updating team: {e}")
            return {'success': False, 'error': str(e)}
    
    # Set Active Team and reflect across other apps
    @staticmethod
    def set_active_team(django_user, team_ID):
        """Set user's active team"""
        try:
            # Get the Supabase user ID
            supabase_user_id = Team.get_supabase_user_id(django_user)
            if not supabase_user_id:
                return {'success': False, 'error': 'User not found in database'}

            # Verify user is member of the team
            membership_check = supabase.table('user_team')\
                .select('*')\
                .eq('user_id', supabase_user_id)\
                .eq('team_ID', team_ID)\
                .is_('left_at', None)\
                .execute()
            
            if not membership_check.data:
                return {'success': False, 'error': 'Not a member of this team'}
            
            # Update user's active team - THIS IS THE CRITICAL LINE
            update_response = supabase.table('user')\
                .update({'active_team_id': team_ID})\
                .eq('user_ID', supabase_user_id)\
                .execute()
            
            if update_response.data:
                return {'success': True, 'message': f'Active team set to {team_ID}'}
            else:
                return {'success': False, 'error': 'Failed to update active team'}
                
        except Exception as e:
            print(f"Error setting active team: {e}")
            return {'success': False, 'error': str(e)}
        
    @staticmethod
    def get_active_team(django_user):
        """Get user's active team - SIMPLE VERSION"""
        try:
            supabase_user_id = Team.get_supabase_user_id(django_user)
            if not supabase_user_id:
                return None

            user_response = supabase.table('user')\
                .select('active_team_id')\
                .eq('user_ID', supabase_user_id)\
                .execute()
            
            if not user_response.data or not user_response.data[0].get('active_team_id'):
                return None
                
            active_team_id = user_response.data[0]['active_team_id']
            
            team_response = supabase.table('team')\
                .select('team_ID, team_name, description, icon_url, user_id_owner')\
                .eq('team_ID', active_team_id)\
                .execute()
            
            if team_response.data:
                return team_response.data[0]
            
            return None
            
        except Exception as e:
            print(f"Error getting active team: {e}")
            return None

    @staticmethod
    def get_active_team_id(django_user):
        """Get only the active team ID"""
        try:
            active_team = Team.get_active_team(django_user)
            return active_team['team_ID'] if active_team else None
        except Exception as e:
            print(f"Error getting active team ID: {e}")
            return None

    @staticmethod
    def initialize_active_team(django_user):
        """Set first available team as active if none is set"""
        try:
            # Check if user already has an active team
            current_active = Team.get_active_team(django_user)
            if current_active:
                return current_active['team_ID']

            # Get user's teams
            teams = Team.get_user_teams(django_user)
            if teams and len(teams) > 0:
                # Set first team as active
                first_team_id = teams[0]['team_ID']
                result = Team.set_active_team(django_user, first_team_id)
                if result.get('success'):
                    return first_team_id
            
            return None
            
        except Exception as e:
            print(f"Error initializing active team: {e}")
            return None
class UserTeam:
    """UserTeam model handling user-team relationships"""
    
    @staticmethod
    def get_users_without_teams(team_id=None):
        """Get users who don't belong to the specified team (or any team if no team_id provided)"""
        try:
            # Get all users from Supabase
            all_users_response = supabase.table('user')\
                .select('user_ID, username, email, profile_picture')\
                .execute()
            
            if team_id:
                # Get users who are in the SPECIFIC team
                team_users_response = supabase.table('user_team')\
                    .select('user_id')\
                    .eq('team_ID', team_id)\
                    .is_('left_at', None)\
                    .execute()
                
                team_user_ids = {member['user_id'] for member in team_users_response.data} if team_users_response.data else set()
                
                # Filter users who are NOT in this specific team
                available_users = [
                    user for user in all_users_response.data 
                    if user['user_ID'] not in team_user_ids
                ]
            else:
                # Original behavior: get users not in any team
                team_users_response = supabase.table('user_team')\
                    .select('user_id')\
                    .is_('left_at', None)\
                    .execute()
                
                team_user_ids = {member['user_id'] for member in team_users_response.data} if team_users_response.data else set()
                
                # Filter users who are not in any team
                available_users = [
                    user for user in all_users_response.data 
                    if user['user_ID'] not in team_user_ids
                ]
            
            # Ensure profile pictures use full URLs
            for user in available_users:
                if user.get('profile_picture') and user['profile_picture'].startswith('/'):
                    user['profile_picture'] = f"{SUPABASE_URL}/storage/v1/object/public/{user['profile_picture']}"
                elif not user.get('profile_picture'):
                    user['profile_picture'] = '/static/images/default-avatar.png'
            
            return available_users
            
        except Exception as e:
            print(f"Error getting users without teams: {e}")
            return []