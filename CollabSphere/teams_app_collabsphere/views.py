# views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Team, UserTeam
from .forms import CreateTeamForm, EditTeamForm
# Import the new notification triggers class
from .notification_triggers import TeamNotificationTriggers


@login_required
def teams(request):
    """Main teams view that displays all teams the user belongs to"""
    try:
        # Get search query
        search_query = request.GET.get('q', '').strip()

        # Get current user's teams using the model method - pass the user object
        teams_data = Team.get_user_teams(request.user)

        # Filter teams based on search query
        if search_query:
            search_lower = search_query.lower()
            filtered_teams = []
            for team in teams_data:
                # Search in team name, description, and owner
                team_name = team.get('team_name', '').lower()
                description = team.get('description', '').lower()
                owner_username = team.get('owner', {}).get('username', '').lower() if team.get('owner') else ''

                if (search_lower in team_name or
                    search_lower in description or
                    search_lower in owner_username):
                    filtered_teams.append(team)
            teams_data = filtered_teams

        context = {
            'teams': teams_data,
            'search_query': search_query,
            'create_team_form': CreateTeamForm()  # Add form to context
        }

        return render(request, 'teams.html', context)

    except Exception as e:
        print(f"Error loading teams: {e}")
        context = {
            'teams': [],
            'error': 'Unable to load teams at this time.',
            'create_team_form': CreateTeamForm()  # Add form to context even on error
        }
        return render(request, 'teams.html', context)


@login_required
def create_team(request):
    """View for creating a new team (modal content)"""
    if request.method == 'POST':
        try:
            form = CreateTeamForm(request.POST, request.FILES)

            if form.is_valid():
                # Save the team using the form's save method
                result = form.save(request.user)

                if result.get('success'):
                    # --- Notification Integration START ---
                    try:
                        team_id = result['team_ID']
                        member_ids = form.cleaned_data['selected_members']
                        creator_id = request.session.get("user_ID")  # Assuming user ID is in session

                        team_data = {
                            'team_ID': team_id,
                            'team_name': form.cleaned_data['team_name'],
                            'description': form.cleaned_data['description']
                        }

                        trigger_context = {
                            'action': 'create',
                            'creator_id': creator_id,
                            'member_ids': member_ids
                        }

                        # Evaluate triggers for Team Creation
                        triggered_notifications = TeamNotificationTriggers.evaluate_all_triggers(
                            team_data,
                            trigger_context
                        )

                        # Log and dispatch (or send to a dispatch function)
                        for trigger in triggered_notifications:
                            print(f"🔔 TEAM TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
                            # Example: dispatch_notification(trigger, sender_user=request.user)

                    except Exception as e:
                        print(f"⚠️ Error evaluating team creation triggers: {e}")
                    # --- Notification Integration END ---

                    # Existing notification system (kept)
                    try:
                        member_ids = form.cleaned_data['selected_members']
                        print(f"Creating team notifications for member IDs: {member_ids}")

                        if member_ids:
                            from notifications_app_collabsphere.views import create_team_notification
                            team_data = {
                                'team_ID': result['team_ID'],
                                'team_name': form.cleaned_data['team_name'],
                                'description': form.cleaned_data['description']
                            }
                            create_team_notification(team_data, member_ids, sender_user=request.user)

                    except Exception as e:
                        print(f"Error creating team notifications: {e}")
                        # Continue even if notifications fail

                    return JsonResponse({'success': True, 'team_ID': result['team_ID']})
                else:
                    return JsonResponse({'success': False, 'error': result.get('error', 'Failed to create team')})
            else:
                # Return form validation errors
                errors = form.errors.get_json_data()
                return JsonResponse({'success': False, 'error': 'Form validation failed', 'form_errors': errors})

        except Exception as e:
            print(f"Error creating team: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    # GET request - return the modal form with form instance
    form = CreateTeamForm()
    return render(request, 'create_team.html', {'form': form})

@login_required
def get_users_without_teams(request):
    """API endpoint to get users who don't have teams (for adding members)"""
    try:
        # Get team_id from request if provided (for edit team scenario)
        team_id = request.GET.get('team_id')
        
        if team_id:
            users_data = UserTeam.get_users_without_teams(team_id=int(team_id))
        else:
            users_data = UserTeam.get_users_without_teams()

        return JsonResponse({
            'success': True,
            'users': users_data
        })
    except Exception as e:
        print(f"Error getting users without teams: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def switch_team(request, team_ID):
    """Switch the user's active team"""
    try:
        print(f"DEBUG: Switching to team {team_ID} for user {request.user.username}")
        
        # Use the set_active_team method instead of switch_user_team
        result = Team.set_active_team(request.user, team_ID)

        print(f"DEBUG: Switch result: {result}")
        
        if result.get('success'):
            # Update session as well for consistency
            request.session['current_team_ID'] = team_ID
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': result.get('error')})

    except Exception as e:
        print(f"Error switching team: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def edit_team(request, team_ID):
    try:
        old_team_data = Team.get(team_ID)
    except Exception as e:
        print(f"Error fetching old team data: {e}")
        old_team_data = None

    if request.method == 'POST':
        try:
            form = EditTeamForm(request.POST, request.FILES)

            if form.is_valid():
                result = form.save(request.user, team_ID)

                if result.get('success'):
                    try:
                        updated_by_id = request.session.get("user_ID")
                        new_team_data = Team.get(team_ID)

                        changed_fields = []
                        if new_team_data and old_team_data:
                            if old_team_data.get('team_name') != new_team_data.get('team_name'):
                                changed_fields.append('team_name')
                            if old_team_data.get('description') != new_team_data.get('description'):
                                changed_fields.append('description')

                            old_owner_id = old_team_data.get('owner_id')
                            new_owner_id = new_team_data.get('owner_id')
                            if old_owner_id != new_owner_id:
                                changed_fields.append('owner_id')

                            old_member_ids = TeamNotificationTriggers.get_team_member_ids(team_ID)
                            new_member_ids = form.cleaned_data.get('selected_members', [])
                            member_changes = TeamNotificationTriggers.detect_member_changes(old_member_ids, new_member_ids)
                            if member_changes['has_changes']:
                                changed_fields.append('members')

                            trigger_context = {
                                'action': 'update',
                                'updated_by': updated_by_id,
                                'changed_fields': changed_fields,
                                'old_owner_id': old_owner_id,
                                'old_member_ids': old_member_ids,
                                'new_member_ids': new_member_ids,
                            }

                            triggered_notifications = TeamNotificationTriggers.evaluate_all_triggers(
                                new_team_data,
                                trigger_context
                            )

                            for trigger in triggered_notifications:
                                print(f"🔔 TEAM TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")

                    except Exception as e:
                        print(f"⚠️ Error evaluating team update triggers: {e}")

                    return JsonResponse({'success': True, 'message': result.get('message', 'Team updated successfully')})
                else:
                    return JsonResponse({'success': False, 'error': result.get('error', 'Failed to update team')})
            else:
                errors = form.errors.get_json_data()
                return JsonResponse({'success': False, 'error': 'Form validation failed', 'form_errors': errors})

        except Exception as e:
            print(f"Error updating team: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

            # GET request
    try:
            # Get the team with members data
            teams_data = Team.get_user_teams(request.user)
            team = next((t for t in teams_data if t['team_ID'] == team_ID), None)

            if not team:
                return JsonResponse({'success': False, 'error': 'Team not found'})

            # Use the team.members data that's already in the correct format
            current_member_ids = ','.join(
                str(member['user_id']) for member in team.get('members', [])
            )

            initial_data = {
                'team_name': team.get('team_name', ''),
                'description': team.get('description', ''),
                'team_members': current_member_ids,
            }

            form = EditTeamForm(initial=initial_data)
            context = {
                'team': team,
                'current_members': team.get('members', []),  # This should now match team_card.html
                'current_member_ids': current_member_ids,
                'form': form
            }

            return render(request, 'edit_team.html', context)

    except Exception as e:
            print(f"Error loading edit team: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def delete_team(request, team_ID):
    """Delete a team"""
    try:
        team_data = Team.get(team_ID)

        if team_data and team_data.get("owner_id") == request.session.get("user_ID"):
            Team.delete(team_ID)

            try:
                deleted_by_id = request.session.get("user_ID")
                trigger_context = {
                    'action': 'delete',
                    'deleted_by': deleted_by_id
                }

                triggered_notifications = TeamNotificationTriggers.evaluate_all_triggers(
                    team_data,
                    trigger_context
                )

                for trigger in triggered_notifications:
                    print(f"🔔 TEAM TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")

            except Exception as e:
                print(f"⚠️ Error evaluating team deletion triggers: {e}")

            return JsonResponse({'success': True, 'message': 'Team deleted successfully'})
        else:
            return JsonResponse({'success': False, 'error': 'Team not found or unauthorized'})

    except Exception as e:
        print(f"Error deleting team: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def leave_team(request, team_ID):
    """Leave a team (for non-owners)"""
    try:
        # Get the Supabase user ID
        supabase_user_id = Team.get_supabase_user_id(request.user)
        if not supabase_user_id:
            return JsonResponse({'success': False, 'error': 'User not found in database'})

        # Verify user is member of the team and not the owner
        team_response = Team.get(team_ID)
        
        if not team_response:
            return JsonResponse({'success': False, 'error': 'Team not found'})
        
        team_owner_id = team_response.get('user_id_owner')
        
        if team_owner_id == supabase_user_id:
            return JsonResponse({'success': False, 'error': 'Team owner cannot leave the team. Transfer ownership first.'})

        # Mark user as left the team
        leave_result = Team.supabase.table('user_team')\
            .update({'left_at': 'now()'})\
            .eq('user_id', supabase_user_id)\
            .eq('team_ID', team_ID)\
            .is_('left_at', None)\
            .execute()

        if leave_result.data:
            # Notification for leaving team
            try:
                trigger_context = {
                    'action': 'update',
                    'updated_by': supabase_user_id,
                    'removed_member_ids': [supabase_user_id]
                }
                
                triggered_notifications = TeamNotificationTriggers.evaluate_all_triggers(
                    team_response,
                    trigger_context
                )

                for trigger in triggered_notifications:
                    print(f"🔔 TEAM TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")

            except Exception as e:
                print(f"⚠️ Error evaluating leave team triggers: {e}")

            return JsonResponse({'success': True, 'message': 'Successfully left the team'})
        else:
            return JsonResponse({'success': False, 'error': 'Failed to leave team'})

    except Exception as e:
        print(f"Error leaving team: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def view_team(request, team_ID):
    """View team details (read-only for non-owners)"""
    try:
        team_data = Team.get(team_ID)
        if not team_data:
            return JsonResponse({'success': False, 'error': 'Team not found'})

        current_user_supabase_id = Team.get_supabase_user_id(request.user)

        # DEBUG: Print team data to see structure
        print(f"DEBUG Team Data: {team_data}")

        # Get team members - FIXED query
        members_response = Team.supabase.table('user_team')\
            .select('user_id, user:user_id(username, profile_picture)')\
            .eq('team_ID', team_ID)\
            .is_('left_at', None)\
            .execute()

        # DEBUG: Print members response
        print(f"DEBUG Members Response: {members_response}")

        current_members = []
        for member_data in members_response.data:
            try:
                user_data = member_data.get('user', {})
                print(f"DEBUG Member Data: {member_data}")  # Debug each member
                current_members.append({
                    'user_ID': member_data.get('user_id'),
                    'username': user_data.get('username', 'Unknown'),
                    'profile_picture': user_data.get('profile_picture', '')
                })
            except (KeyError, AttributeError) as e:
                print(f"Error processing member data: {e}")
                continue

        # DEBUG: Print final current_members
        print(f"DEBUG Final current_members: {current_members}")

        context = {
            'team': team_data,
            'current_members': current_members,
            'is_owner': team_data.get('user_id_owner') == current_user_supabase_id
        }

        return render(request, 'view_team.html', context)

    except Exception as e:
        print(f"Error loading team details: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    
# Set users active team
def active_team_context(request):
    """Context processor to make active team available globally"""
    if request.user.is_authenticated:
        try:
            active_team = Team.get_active_team(request.user)
            active_team_id = active_team['team_ID'] if active_team else None
            
            # Initialize active team if none is set
            if not active_team_id:
                active_team_id = Team.initialize_active_team(request.user)
                if active_team_id:
                    active_team = Team.get_active_team(request.user)
            
            # Calculate team members count
            team_members_count = 0
            if active_team_id:
                team_members = Team.get_active_team_members(request.user)
                team_members_count = len(team_members)
            
            return {
                'active_team': active_team,
                'active_team_id': active_team_id,
                'team_members_count': team_members_count,
            }
        except Exception as e:
            print(f"Error getting active team context: {e}")
            return {
                'active_team': None, 
                'active_team_id': None,
                'team_members_count': 0,
            }
    return {
        'active_team': None, 
        'active_team_id': None,
        'team_members_count': 0,
    }

# Update the main teams view to include active team info
@login_required
def teams(request):
    """Main teams view that displays all teams the user belongs to"""
    try:
        # Get search query
        search_query = request.GET.get('q', '').strip()

        # Get current user's teams using the model method
        teams_data = Team.get_user_teams(request.user)
        
        # Get active team
        active_team = Team.get_active_team(request.user)
        active_team_id = active_team['team_ID'] if active_team else None

        # Filter teams based on search query
        if search_query:
            search_lower = search_query.lower()
            filtered_teams = []
            for team in teams_data:
                # Search in team name, description, and owner
                team_name = team.get('team_name', '').lower()
                description = team.get('description', '').lower()
                owner_username = team.get('owner', {}).get('username', '').lower() if team.get('owner') else ''

                if (search_lower in team_name or
                    search_lower in description or
                    search_lower in owner_username):
                    filtered_teams.append(team)
            teams_data = filtered_teams

        context = {
            'teams': teams_data,
            'search_query': search_query,
            'create_team_form': CreateTeamForm(),
            'active_team': active_team,
            'active_team_id': active_team_id
        }

        return render(request, 'teams.html', context)

    except Exception as e:
        print(f"Error loading teams: {e}")
        context = {
            'teams': [],
            'error': 'Unable to load teams at this time.',
            'create_team_form': CreateTeamForm(),
            'active_team': None,
            'active_team_id': None
        }
        return render(request, 'teams.html', context)