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
        result = Team.switch_user_team(request.user, team_ID)

        if result.get('success'):
            request.session['current_team_ID'] = team_ID
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': result.get('error')})

    except Exception as e:
        print(f"Error switching team: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def edit_team(request, team_ID):
    """View for editing a team"""
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
        team = old_team_data or next(
            (t for t in Team.get_user_teams(request.user) if t['team_ID'] == team_ID), None
        )

        if not team:
            return JsonResponse({'success': False, 'error': 'Team not found'})

        current_members = []
        for member_data in team.get('members', []):
            try:
                if 'user' in member_data:
                    user_data = member_data['user']
                    current_members.append({
                        'user_ID': member_data.get('user_id', user_data.get('user_ID', '')),
                        'username': user_data.get('username', 'Unknown'),
                        'profile_picture': user_data.get('profile_picture', '')
                    })
                else:
                    current_members.append({
                        'user_ID': member_data.get('user_id', ''),
                        'username': member_data.get('username', 'Unknown'),
                        'profile_picture': member_data.get('profile_picture', '')
                    })
            except (KeyError, AttributeError) as e:
                print(f"Error processing member data: {e}")
                continue

        current_member_ids = ','.join(
            str(member['user_ID']) for member in current_members if member.get('user_ID')
        )

        initial_data = {
            'team_name': team.get('team_name', ''),
            'description': team.get('description', ''),
            'team_members': current_member_ids,
        }

        form = EditTeamForm(initial=initial_data)
        context = {
            'team': team,
            'current_members': current_members,
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
