from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
import json
from .models import AdminSupabaseService
import logging
from datetime import datetime
from teams_app_collabsphere.models import Team as UserTeamModel

logger = logging.getLogger(__name__)


# Decorator to check if user is admin / custom admin only hardcoded
def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Allow admin session access OR Django staff access
        if request.session.get("admin_logged_in") or request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # If not authenticated at all, redirect to login
        if not request.user.is_authenticated and not request.session.get("admin_logged_in"):
            # Store the intended destination
            next_url = request.path
            return redirect(f'/login/?next={next_url}')
        
        # If authenticated but not admin/staff
        messages.error(request, "You don't have permission to access the admin panel.")
        return redirect('home')
    
    return _wrapped_view

# -------------------------------
# DASHBOARD VIEWS
# -------------------------------

@admin_required
def admin_dashboard(request):
    """Admin dashboard overview."""
    stats = AdminSupabaseService.get_system_stats()
    
    context = {
        'stats': stats,
        'total_users': stats.get('total_users', 0),
        'total_tasks': stats.get('total_tasks', 0),
        'total_teams': stats.get('total_teams', 0),
        'total_checkins': stats.get('total_checkins', 0),
        'users_today': stats.get('users_today', 0),
        'total_events': stats.get('total_events', 0), 
        'tasks_today': stats.get('tasks_today', 0),
        'recent_users': stats.get('recent_users', []),
        'recent_tasks': stats.get('recent_tasks', []),
        'recent_checkins': stats.get('recent_checkins', []),
        'recent_events': stats.get('recent_events', []), 
        'active_page': 'dashboard',
    }
    return render(request, 'dashboard.html', context)

# -------------------------------
# USER MANAGEMENT VIEWS
# -------------------------------


@admin_required
def user_management(request):
    """List all users with management options."""
    users = AdminSupabaseService.get_all_users()
    
    context = {
        'users': users,
        'total_users': len(users),
        'active_page': 'users',
    }
    return render(request, 'user_management.html', context)


@admin_required
def user_detail(request, user_id):
    """View user details."""
    user = AdminSupabaseService.get_user_by_id(user_id)
    
    if not user:
        messages.error(request, f"User with ID {user_id} not found.")
        return redirect('admin_app_collabsphere:user_management')
    
    context = {
        'user': user,
        'active_page': 'users',
    }
    return render(request, 'user_detail.html', context)

@admin_required
def user_create(request):
    """Create a new user."""
    form_errors = {}
    roles = AdminSupabaseService.get_all_roles()  # Get available roles
    
    if request.method == 'POST':
        try:
            # Get form data
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            role_id = request.POST.get('role_id')
            
            # Validation
            if not username:
                form_errors['username'] = "Username is required"
            if not email:
                form_errors['email'] = "Email is required"
            elif AdminSupabaseService.check_email_exists(email):
                messages.error(request, f"Email '{email}' already exists in the system.")
                context = {
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'email_exists': email,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            if not password:
                form_errors['password'] = "Password is required"
            elif password != confirm_password:
                form_errors['confirm_password'] = "Passwords do not match"
            elif len(password) < 8:
                form_errors['password'] = "Password must be at least 8 characters long"
            
            # Check for existing users BEFORE attempting creation
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Check Django users
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Username '{username}' already exists in Django authentication system.")
                context = {
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'username_exists': username,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            if User.objects.filter(email=email).exists():
                messages.error(request, f"Email '{email}' already exists in Django authentication system.")
                context = {
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'email_exists': email,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            # Check Supabase users
            if AdminSupabaseService.check_email_exists(email):
                messages.error(request, f"Email '{email}' already exists in Supabase.")
                context = {
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'email_exists': email,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            # Validate role_id if provided
            if role_id:
                # Check if role exists in database
                role_exists = any(r['role_id'] == int(role_id) for r in roles)
                if not role_exists:
                    messages.warning(request, f"Selected role ID {role_id} does not exist in database.")
                    role_id = None  # Don't assign invalid role
            
            if form_errors:
                context = {
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            # Prepare user data - password will be hashed automatically
            user_data = {
                'username': username,
                'email': email,
                'password': password,  # Plain password - will be hashed by create_user_with_hashed_password
                'full_name': request.POST.get('full_name', ''),
                'title': request.POST.get('title', ''),
                'created_at': timezone.now().isoformat(),
            }
            
            # Handle role - only if it exists
            if role_id:
                # Verify the role exists in the fetched roles
                if any(r['role_id'] == int(role_id) for r in roles):
                    user_data['role_id'] = int(role_id)
                else:
                    logger.warning(f"Attempted to assign non-existent role_id: {role_id}")
            
            # Create user in BOTH Supabase and Django using the hashed password method
            created_user = AdminSupabaseService.create_user_with_hashed_password(user_data)
            
            if created_user:
                # Now create Django user with the same credentials
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                # Create Django user
                django_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,  # Django will hash this with its own algorithm
                )
                django_user.supabase_id = created_user['user_ID']
                django_user.save()
                
                # Handle profile picture upload
                profile_picture = request.FILES.get('profile_picture')
                if profile_picture:
                    try:
                        profile_url = AdminSupabaseService.upload_file_to_supabase(
                            profile_picture, 
                            created_user['user_ID']
                        )
                        
                        # Update user with profile picture URL
                        update_data = {'profile_picture': profile_url}
                        AdminSupabaseService.update_user(created_user['user_ID'], update_data)
                        created_user['profile_picture'] = profile_url
                        
                    except Exception as e:
                        logger.error(f"Error uploading profile picture: {str(e)}")
                        # Don't fail user creation because of picture upload error
                
                messages.success(request, f"User {created_user['username']} created successfully in both systems.")
                return redirect('admin_app_collabsphere:user_detail', user_id=created_user['user_ID'])
            else:
                messages.error(request, "Failed to create user.")
                
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            error_msg = str(e)
            if 'duplicate key' in error_msg.lower() or '23505' in error_msg:
                if 'email' in error_msg.lower():
                    messages.error(request, f"Email '{email}' already exists in the system.")
                    context = {
                        'active_page': 'users',
                        'form_errors': form_errors,
                        'email_exists': email,
                        'roles': roles,
                    }
                else:
                    messages.error(request, "Username or email already exists.")
            elif 'role_id_fkey' in error_msg.lower() or '23503' in error_msg:
                messages.error(request, "Selected role does not exist. Please choose a valid role or leave it blank.")
            else:
                messages.error(request, f"Error creating user: {error_msg}")
    
    context = {
        'active_page': 'users',
        'form_errors': form_errors,
        'roles': roles,
    }
    return render(request, 'user_form.html', context)

@admin_required
def user_edit(request, user_id):
    """Edit an existing user."""
    user = AdminSupabaseService.get_user_by_id(user_id)
    
    if not user:
        messages.error(request, f"User with ID {user_id} not found.")
        return redirect('admin_app_collabsphere:user_management')
    
    form_errors = {}
    roles = AdminSupabaseService.get_all_roles()  # Get available roles
    
    if request.method == 'POST':
        try:
            update_data = {
                'username': request.POST.get('username'),
                'full_name': request.POST.get('full_name', ''),
                'title': request.POST.get('title', ''),
            }
            
            # Check if email is being changed
            new_email = request.POST.get('email')
            if new_email != user.get('email'):
                if AdminSupabaseService.check_email_exists(new_email):
                    messages.error(request, f"Email '{new_email}' already exists in the system.")
                    context = {
                        'user': user,
                        'active_page': 'users',
                        'form_errors': form_errors,
                        'email_exists': new_email,
                        'roles': roles,
                    }
                    return render(request, 'user_form.html', context)
                update_data['email'] = new_email
            
            # Update password only if provided
            password = request.POST.get('password')
            if password:
                if password != request.POST.get('confirm_password', ''):
                    form_errors['confirm_password'] = "Passwords do not match"
                else:
                    # Hash the password before storing in Supabase
                    import hashlib
                    hashed_password = hashlib.sha256(password.encode()).hexdigest()
                    update_data['password'] = hashed_password
            
            # Handle role
            role_id = request.POST.get('role_id')
            if role_id:
                # Check if role exists
                role_exists = any(r['role_id'] == int(role_id) for r in roles)
                if role_exists:
                    update_data['role_id'] = int(role_id)
                else:
                    messages.warning(request, "Selected role does not exist.")
                    role_id = None
            else:
                # Set role_id to NULL if no role selected
                update_data['role_id'] = None
            
            # Handle profile picture
            profile_picture = request.FILES.get('profile_picture')
            if profile_picture:
                # Upload new profile picture
                profile_url = AdminSupabaseService.upload_file_to_supabase(profile_picture, user_id)
                update_data['profile_picture'] = profile_url
            elif request.POST.get('remove_picture'):
                # Remove profile picture
                update_data['profile_picture'] = None
            
            if form_errors:
                context = {
                    'user': user,
                    'active_page': 'users',
                    'form_errors': form_errors,
                    'roles': roles,
                }
                return render(request, 'user_form.html', context)
            
            updated_user = AdminSupabaseService.update_user(user_id, update_data)
            
            if updated_user:
                messages.success(request, f"User {updated_user['username']} updated successfully.")
                return redirect('admin_app_collabsphere:user_detail', user_id=user_id)
            else:
                messages.error(request, "Failed to update user.")
                
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            error_msg = str(e)
            if 'role_id_fkey' in error_msg.lower() or '23503' in error_msg:
                messages.error(request, "Selected role does not exist. Please choose a valid role.")
            else:
                messages.error(request, f"Error updating user: {error_msg}")
    
    context = {
        'user': user,
        'active_page': 'users',
        'form_errors': form_errors,
        'roles': roles,
    }
    return render(request, 'user_form.html', context)

@admin_required
@require_POST
def user_delete(request, user_id):
    """Delete a user."""
    try:
        success = AdminSupabaseService.delete_user(user_id)
        
        if success:
            messages.success(request, "User deleted successfully.")
        else:
            messages.error(request, "Failed to delete user.")
    except Exception as e:
        messages.error(request, f"Error deleting user: {str(e)}")
    
    return redirect('admin_app_collabsphere:user_management')

# -------------------------------
# TASK MANAGEMENT VIEWS
# -------------------------------


@admin_required
def task_management(request):
    """List all tasks."""
    tasks = AdminSupabaseService.get_all_tasks()
    
    context = {
        'tasks': tasks,
        'total_tasks': len(tasks),
        'active_page': 'tasks',
    }
    return render(request, 'task_management.html', context)


@admin_required
def task_detail(request, task_id):
    """View task details."""
    task = AdminSupabaseService.get_task_by_id(task_id)
    
    if not task:
        messages.error(request, f"Task with ID {task_id} not found.")
        return redirect('admin_app_collabsphere:task_management')
    
    context = {
        'task': task,
        'active_page': 'tasks',
    }
    return render(request, 'task_detail.html', context)

# -------------------------------
# TEAM MANAGEMENT VIEWS
# -------------------------------


@admin_required
def team_management(request):
    """List all teams."""
    teams = AdminSupabaseService.get_all_teams()
    
    context = {
        'teams': teams,
        'total_teams': len(teams),
        'active_page': 'teams',
    }
    return render(request, 'team_management.html', context)


@admin_required
def team_detail(request, team_id):
    """View team details with members."""
    team = AdminSupabaseService.get_team_by_id(team_id)
    
    if not team:
        messages.error(request, f"Team with ID {team_id} not found.")
        return redirect('admin_app_collabsphere:team_management')
    
    members = AdminSupabaseService.get_team_members(team_id)
    
    # Normalize member IDs safely — some member entries may not include a nested 'user_id'
    member_ids = []
    for member in (members or []):
        user = member.get('user') if isinstance(member, dict) else None
        if not user:
            continue
        # accept several possible key names for the ID and skip if missing
        uid = user.get('user_id') if isinstance(user, dict) else None
        if uid is None:
            uid = user.get('id') if isinstance(user, dict) else None
        if uid is None:
            uid = user.get('userID') if isinstance(user, dict) else None
        if uid is None:
            continue
        member_ids.append(str(uid))

    context = {
        'team': team,
        'members': members,
        'member_ids': member_ids,
        'active_page': 'teams',
    }
    return render(request, 'team_detail.html', context)

# -------------------------------
# WELLBEING MANAGEMENT VIEWS
# -------------------------------


@admin_required
def wellbeing_management(request):
    """List all wellbeing check-ins."""
    checkins = AdminSupabaseService.get_all_checkins()
    stats = AdminSupabaseService.get_checkin_stats()
    
    context = {
        'checkins': checkins,
        'total_checkins': stats.get('total', 0),
        'checkins_today': stats.get('today', 0),
        'mood_distribution': stats.get('mood_distribution', {}),
        'active_page': 'wellbeing',
    }
    return render(request, 'wellbeing_management.html', context)

# -------------------------------
# SEARCH VIEWS
# -------------------------------


@admin_required
@require_GET
def search(request):
    """Search across users and tasks."""
    query = request.GET.get('q', '')
    
    users = []
    tasks = []
    
    if query:
        users = AdminSupabaseService.search_users(query)
        tasks = AdminSupabaseService.search_tasks(query)
    
    context = {
        'query': query,
        'users': users,
        'tasks': tasks,
        'total_results': len(users) + len(tasks),
        'active_page': 'search',
    }
    return render(request, 'search_results.html', context)

# -------------------------------
# Event MANAGEMENT VIEWS
# -------------------------------
@admin_required
def event_management(request):
    """List all calendar events."""
    events = AdminSupabaseService.get_all_events()
    # Compute simple stats expected by the template
    today = timezone.now().date()
    events_today = 0
    upcoming_count = 0
    completed_count = 0
    for ev in (events or []):
        try:
            st = ev.get('start_time')
            en = ev.get('end_time')
            if hasattr(st, 'date') and st.date() == today:
                events_today += 1
            if hasattr(st, 'date') and st.date() > today:
                upcoming_count += 1
            if hasattr(en, 'date') and en.date() < today:
                completed_count += 1
        except Exception:
            continue

    # Provide list of all users for the Create Event modal attendees
    try:
        all_users = AdminSupabaseService.get_all_users()
    except Exception:
        all_users = []

    context = {
        'events': events,
        'total_events': len(events),
        'events_today': events_today,
        'upcoming_events': upcoming_count,
        'completed_events': completed_count,
        'all_users': all_users,
        'active_page': 'events',
    }
    return render(request, 'event_management.html', context)


# -------------------------------
# API VIEWS (JSON endpoints)
# -------------------------------


@admin_required
@require_GET
def api_user_stats(request):
    """API endpoint for user statistics."""
    stats = AdminSupabaseService.get_user_registration_stats(days=30)
    return JsonResponse({'data': stats})


@admin_required
@require_GET
def api_system_stats(request):
    """API endpoint for system statistics."""
    stats = AdminSupabaseService.get_system_stats()
    return JsonResponse(stats)


@admin_required
@require_GET
def api_checkin_stats(request):
    """API endpoint for check-in statistics."""
    stats = AdminSupabaseService.get_checkin_stats()
    return JsonResponse(stats)

@admin_required
@require_GET
def api_event_details(request, event_id):
    """API endpoint for event details."""
    try:
        event = AdminSupabaseService.get_event_by_id(event_id)
        if not event:
            return JsonResponse({'error': 'Event not found'}, status=404)
        
        # Format response for the modal
        data = {
            'id': event['event_id'],
            'title': event.get('title', ''),
            'description': event.get('description', ''),
            'event_type': event.get('event_type', 'meeting'),
            'priority': event.get('priority', 'medium'),
            'status': event.get('status', 'upcoming'),
            'start_date': event.get('start_time', '').strftime('%Y-%m-%d') if event.get('start_time') else '',
            'start_time': event.get('start_time', '').strftime('%H:%M') if event.get('start_time') else '',
            'end_date': event.get('end_time', '').strftime('%Y-%m-%d') if event.get('end_time') else '',
            'end_time': event.get('end_time', '').strftime('%H:%M') if event.get('end_time') else '',
            'location': event.get('location', ''),
            'organizer': event.get('user', {}).get('username', 'Unknown') if isinstance(event.get('user'), dict) else 'Unknown',
            'organizer_initial': (event.get('user', {}).get('username', 'U')[0].upper()) if isinstance(event.get('user'), dict) else 'U',
            'organizer_email': event.get('user', {}).get('email', '') if isinstance(event.get('user'), dict) else '',
            'attendees': []  # You'll need to implement attendee fetching
        }
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error fetching event details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# -------------------------------
# ADDITIONAL API VIEWS
# -------------------------------


@admin_required
@require_GET
def api_teams(request):
    """Return all teams as JSON."""
    try:
        teams = AdminSupabaseService.get_all_teams() or []
        return JsonResponse({'teams': teams})
    except Exception as e:
        logger.error(f"Error fetching teams: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_team_detail(request, team_id):
    """Return a single team by ID as JSON."""
    try:
        team = AdminSupabaseService.get_team_by_id(team_id)
        if not team:
            return JsonResponse({'error': 'Team not found'}, status=404)
        return JsonResponse({'team': team})
    except Exception as e:
        logger.error(f"Error fetching team {team_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_events(request):
    """Return all events as JSON."""
    try:
        events = AdminSupabaseService.get_all_events() or []
        return JsonResponse({'events': events})
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_tasks(request):
    """Return all tasks as JSON."""
    try:
        tasks = AdminSupabaseService.get_all_tasks() or []
        return JsonResponse({'tasks': tasks})
    except Exception as e:
        logger.error(f"Error fetching tasks: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_task_detail(request, task_id):
    """Return a single task by ID as JSON."""
    try:
        task = AdminSupabaseService.get_task_by_id(task_id)
        if not task:
            return JsonResponse({'error': 'Task not found'}, status=404)
        return JsonResponse({'task': task})
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_checkins(request):
    """Return all wellbeing check-ins as JSON."""
    try:
        checkins = AdminSupabaseService.get_all_checkins() or []
        return JsonResponse({'checkins': checkins})
    except Exception as e:
        logger.error(f"Error fetching checkins: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@admin_required
@require_GET
def api_checkin_detail(request, checkin_id):
    """Return a single check-in by ID as JSON."""
    try:
        checkin = AdminSupabaseService.get_checkin_by_id(checkin_id)
        if not checkin:
            return JsonResponse({'error': 'Checkin not found'}, status=404)
        return JsonResponse({'checkin': checkin})
    except Exception as e:
        logger.error(f"Error fetching checkin {checkin_id}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    

# -------------------------------
# EXPORT VIEWS
# -------------------------------


@admin_required
@require_GET
def export_users(request):
    """Export users as JSON or CSV."""
    format = request.GET.get('format', 'json')
    
    if format == 'csv':
        data = AdminSupabaseService.export_users(format='csv')
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        return response
    else:
        data = AdminSupabaseService.export_users(format='json')
        return JsonResponse({'users': data})


@admin_required
@require_GET
def export_tasks(request):
    """Export tasks as JSON or CSV."""
    format = request.GET.get('format', 'json')
    
    if format == 'csv':
        data = AdminSupabaseService.export_tasks(format='csv')
        response = HttpResponse(data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="tasks_export.csv"'
        return response
    else:
        data = AdminSupabaseService.export_tasks(format='json')
        return JsonResponse({'tasks': data})
    

# -------------------------------
# TASK CRUD VIEWS (Complete)
# -------------------------------

@admin_required
def task_create(request):
    """Create a new task."""
    users = AdminSupabaseService.get_all_users()
    
    if request.method == 'POST':
        try:
            task_data = {
                'title': request.POST.get('title'),
                'description': request.POST.get('description', ''),
                'date_created': timezone.now().isoformat(),
                'status': 'Pending',
                'completion': 0,
                'is_archived': False,
            }
            
            # Handle assigned user
            assigned_to = request.POST.get('assigned_to')
            if assigned_to:
                task_data['assigned_to'] = int(assigned_to)
                user = AdminSupabaseService.get_user_by_id(assigned_to)
                if user:
                    task_data['assigned_to_username'] = user.get('username')
            
            # Handle start and due dates
            start_date = request.POST.get('start_date')
            if start_date:
                task_data['start_date'] = start_date

            due_date = request.POST.get('due_date')
            if due_date:
                task_data['due_date'] = due_date
            
            # Handle priority
            task_data['priority'] = 'priority' in request.POST
            
            created_task = AdminSupabaseService.create_task(task_data)
            
            if created_task:
                messages.success(request, f"Task '{created_task['title']}' created successfully.")
                return redirect('admin_app_collabsphere:task_detail', task_id=created_task['task_id'])
            else:
                messages.error(request, "Failed to create task.")
                
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            messages.error(request, f"Error creating task: {str(e)}")
    
    context = {
        'users': users,
        'active_page': 'tasks',
    }
    return render(request, 'task_form.html', context)

@admin_required
def task_edit(request, task_id):
    """Edit an existing task."""
    task = AdminSupabaseService.get_task_by_id(task_id)
    users = AdminSupabaseService.get_all_users()
    
    if not task:
        messages.error(request, f"Task with ID {task_id} not found.")
        return redirect('admin_app_collabsphere:task_management')
    
    if request.method == 'POST':
        try:
            update_data = {
                'title': request.POST.get('title'),
                'description': request.POST.get('description', ''),
                'status': request.POST.get('status', 'Pending'),
            }
            
            # Handle assigned user
            assigned_to = request.POST.get('assigned_to')
            if assigned_to:
                update_data['assigned_to'] = int(assigned_to)
                user = AdminSupabaseService.get_user_by_id(assigned_to)
                if user:
                    update_data['assigned_to_username'] = user.get('username')
            elif assigned_to == '':
                update_data['assigned_to'] = None
                update_data['assigned_to_username'] = None
            
            # Handle start and due dates
            start_date = request.POST.get('start_date')
            if start_date:
                update_data['start_date'] = start_date
            elif start_date == '':
                update_data['start_date'] = None

            due_date = request.POST.get('due_date')
            if due_date:
                update_data['due_date'] = due_date
            elif due_date == '':
                update_data['due_date'] = None
            
            # Handle priority
            update_data['priority'] = 'priority' in request.POST
            
            # Handle completion
            completion = request.POST.get('completion')
            if completion:
                update_data['completion'] = int(completion)
            
            updated_task = AdminSupabaseService.update_task(task_id, update_data)
            
            if updated_task:
                messages.success(request, f"Task '{updated_task['title']}' updated successfully.")
                return redirect('admin_app_collabsphere:task_detail', task_id=task_id)
            else:
                messages.error(request, "Failed to update task.")
                
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}")
            messages.error(request, f"Error updating task: {str(e)}")
    
    context = {
        'task': task,
        'users': users,
        'active_page': 'tasks',
    }
    return render(request, 'task_form.html', context)

@admin_required
@require_POST
def task_delete(request, task_id):
    """Delete a task."""
    try:
        success = AdminSupabaseService.delete_task(task_id)
        
        if success:
            messages.success(request, "Task deleted successfully.")
        else:
            messages.error(request, "Failed to delete task.")
    except Exception as e:
        messages.error(request, f"Error deleting task: {str(e)}")
    
    return redirect('admin_app_collabsphere:task_management')

# -------------------------------
# EVENT CRUD VIEWS
# -------------------------------

@admin_required
def event_detail(request, event_id):
    """View event details."""
    event = AdminSupabaseService.get_event_by_id(event_id)
    
    if not event:
        messages.error(request, f"Event with ID {event_id} not found.")
        return redirect('admin_app_collabsphere:event_management')
    
    # Fetch team information
    team_info = None
    team_members = []
    
    if event.get('team_ID'):
        # Get team details
        team_info = AdminSupabaseService.get_team_by_id(event['team_ID'])
        
        # Get team members
        team_members = AdminSupabaseService.get_team_members(event['team_ID'])
    
    if team_info:
        event['team'] = team_info
    else:
        event['team'] = {'team_name': None}
    
    context = {
        'event': event,
        'team_info': team_info,  
        'team_members': team_members,
        'active_page': 'events',
    }
    return render(request, 'event_detail.html', context)

@admin_required
def event_detail(request, event_id):
    """View event details."""
    event = AdminSupabaseService.get_event_by_id(event_id)
    
    if not event:
        messages.error(request, f"Event with ID {event_id} not found.")
        return redirect('admin_app_collabsphere:event_management')
    
    # Fetch team members for this event
    team_members = []
    team_info = None
    
    if event.get('team_ID'):
        # Get team members
        team_members = AdminSupabaseService.get_team_members(event['team_ID'])
        
        # Get team info
        team_info = AdminSupabaseService.get_team_by_id(event['team_ID'])
    
    context = {
        'event': event,
        'team_members': team_members,
        'team_info': team_info,
        'active_page': 'events',
    }
    return render(request, 'event_detail.html', context)

@admin_required
def event_create(request):
    """Create a new event - ADMIN VERSION (team required)."""
    users = AdminSupabaseService.get_all_users()
    teams = AdminSupabaseService.get_all_teams()
    
    if request.method == 'POST':
        try:
            # Validate event data
            errors = validate_event_data(request.POST)
            if errors:
                for error in errors:
                    messages.error(request, error)
                context = {
                    'users': users,
                    'teams': teams,
                    'active_page': 'events',
                }
                return render(request, 'event_form.html', context)
            
            # Prepare event data
            event_data = {
                'title': request.POST.get('title'),
                'description': request.POST.get('description', ''),
            }
            
            # Handle start and end times
            start_date = request.POST.get('start_date')
            start_time = request.POST.get('start_time')
            if start_date and start_time:
                event_data['start_time'] = f"{start_date}T{start_time}:00"
            
            end_date = request.POST.get('end_date')
            end_time = request.POST.get('end_time')
            if end_date and end_time:
                event_data['end_time'] = f"{end_date}T{end_time}:00"
            
            # Handle user (organizer) - optional
            user_id = request.POST.get('user_id')
            if user_id:
                event_data['user_id'] = int(user_id)
            
            # Handle team - REQUIRED
            team_id = request.POST.get('team_id')
            event_data['team_ID'] = int(team_id)
            
            # Create the event
            created_event = AdminSupabaseService.create_event(event_data)
            
            if created_event:
                messages.success(request, f"Event '{created_event['title']}' created successfully.")
                return redirect('admin_app_collabsphere:event_detail', event_id=created_event['event_id'])
            else:
                messages.error(request, "Failed to create event.")
                
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            messages.error(request, f"Error creating event: {str(e)}")
    
    context = {
        'users': users,
        'teams': teams,
        'active_page': 'events',
    }
    return render(request, 'event_form.html', context)

@admin_required
def event_edit(request, event_id):
    """Edit an existing event."""
    event = AdminSupabaseService.get_event_by_id(event_id)
    users = AdminSupabaseService.get_all_users()
    teams = AdminSupabaseService.get_all_teams()
    
    if not event:
        messages.error(request, f"Event with ID {event_id} not found.")
        return redirect('admin_app_collabsphere:event_management')
    
    # Format dates for form
    if event.get('start_time'):
        if isinstance(event['start_time'], datetime):
            event['form_start_date'] = event['start_time'].date().isoformat()
            event['form_start_time'] = event['start_time'].time().strftime('%H:%M')
    
    if event.get('end_time'):
        if isinstance(event['end_time'], datetime):
            event['form_end_date'] = event['end_time'].date().isoformat()
            event['form_end_time'] = event['end_time'].time().strftime('%H:%M')
    
    if request.method == 'POST':
        try:
            update_data = {
                'title': request.POST.get('title'),
                'description': request.POST.get('description', ''),
            }
            
            # Validate team selection
            team_id = request.POST.get('team_id')
            if not team_id:
                messages.error(request, "A team must be selected for the event.")
                context = {
                    'event': event,
                    'users': users,
                    'teams': teams,
                    'active_page': 'events',
                }
                return render(request, 'event_form.html', context)
            
            # Handle start and end times
            start_date = request.POST.get('start_date')
            start_time = request.POST.get('start_time')
            if start_date and start_time:
                update_data['start_time'] = f"{start_date}T{start_time}:00"
            
            end_date = request.POST.get('end_date')
            end_time = request.POST.get('end_time')
            if end_date and end_time:
                update_data['end_time'] = f"{end_date}T{end_time}:00"
            
            # Handle user
            user_id = request.POST.get('user_id')
            if user_id:
                update_data['user_id'] = int(user_id)
            elif user_id == '':
                update_data['user_id'] = None
            
            # Handle team - REQUIRED
            update_data['team_ID'] = int(team_id)
            
            updated_event = AdminSupabaseService.update_event(event_id, update_data)
            
            if updated_event:
                messages.success(request, f"Event '{updated_event['title']}' updated successfully.")
                return redirect('admin_app_collabsphere:event_detail', event_id=event_id)
            else:
                messages.error(request, "Failed to update event.")
                
        except Exception as e:
            logger.error(f"Error updating event: {str(e)}")
            messages.error(request, f"Error updating event: {str(e)}")
    
    context = {
        'event': event,
        'users': users,
        'teams': teams,
        'active_page': 'events',
    }
    return render(request, 'event_form.html', context)


@admin_required
@require_POST
def delete_event(request, event_id):
    """Delete an event."""
    try:
        success = AdminSupabaseService.delete_event(event_id)
        
        if success:
            messages.success(request, "Event deleted successfully.")
        else:
            messages.error(request, "Failed to delete event.")
    except Exception as e:
        messages.error(request, f"Error deleting event: {str(e)}")
    
    return redirect('admin_app_collabsphere:event_management')

# -------------------------------
# CHECKIN CRUD VIEWS
# -------------------------------

# Add this function to your views.py (somewhere after wellbeing_management)

@admin_required
def create_checkin(request):
    """Create a new check-in."""
    users = AdminSupabaseService.get_all_users()
    
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            mood_rating = request.POST.get('mood_rating')
            status = request.POST.get('status', 'Okay')
            notes = request.POST.get('notes', '')
            date_submitted = request.POST.get('date_submitted') or timezone.now().date().isoformat()
            
            checkin_data = {
                'user_id': int(user_id),
                'mood_rating': int(mood_rating) if mood_rating else None,
                'status': status,
                'notes': notes,
                'date_submitted': date_submitted,
            }
            
            created_checkin = AdminSupabaseService.create_checkin(user_id, mood_rating, status, notes)
            
            if created_checkin:
                messages.success(request, "Check-in created successfully.")
                return redirect('admin_app_collabsphere:checkin_detail', checkin_id=created_checkin['checkin_id'])
            else:
                messages.error(request, "Failed to create check-in.")
                
        except Exception as e:
            logger.error(f"Error creating check-in: {str(e)}")
            messages.error(request, f"Error creating check-in: {str(e)}")
    
    context = {
        'users': users,
        'active_page': 'wellbeing',
    }
    return render(request, 'checkin_form.html', context)


@admin_required
def checkin_detail(request, checkin_id):
    """View check-in details."""
    checkin = AdminSupabaseService.get_checkin_by_id(checkin_id)
    
    if not checkin:
        messages.error(request, f"Check-in with ID {checkin_id} not found.")
        return redirect('admin_app_collabsphere:wellbeing_management')
    
    context = {
        'checkin': checkin,
        'active_page': 'wellbeing',
    }
    return render(request, 'checkin_detail.html', context)

@admin_required
def checkin_edit(request, checkin_id):
    """Edit an existing check-in."""
    checkin = AdminSupabaseService.get_checkin_by_id(checkin_id)
    users = AdminSupabaseService.get_all_users()
    
    if not checkin:
        messages.error(request, f"Check-in with ID {checkin_id} not found.")
        return redirect('admin_app_collabsphere:wellbeing_management')
    
    if request.method == 'POST':
        try:
            update_data = {
                'mood_rating': int(request.POST.get('mood_rating')) if request.POST.get('mood_rating') else None,
                'notes': request.POST.get('notes', ''),
                'status': request.POST.get('status', 'Okay'),
                'date_submitted': request.POST.get('date_submitted') or timezone.now().date().isoformat(),
            }
            
            # Handle user change
            user_id = request.POST.get('user_id')
            if user_id:
                update_data['user_id'] = int(user_id)
            
            updated_checkin = AdminSupabaseService.update_checkin(checkin_id, update_data)
            
            if updated_checkin:
                messages.success(request, "Check-in updated successfully.")
                return redirect('admin_app_collabsphere:checkin_detail', checkin_id=checkin_id)
            else:
                messages.error(request, "Failed to update check-in.")
                
        except Exception as e:
            logger.error(f"Error updating check-in: {str(e)}")
            messages.error(request, f"Error updating check-in: {str(e)}")
    
    context = {
        'checkin': checkin,
        'users': users,
        'active_page': 'wellbeing',
    }
    return render(request, 'checkin_form.html', context)

@admin_required
@require_POST
def delete_checkin(request, checkin_id):
    """Delete a check-in."""
    try:
        success = AdminSupabaseService.delete_checkin(checkin_id)
        
        if success:
            messages.success(request, "Check-in deleted successfully.")
        else:
            messages.error(request, "Failed to delete check-in.")
    except Exception as e:
        messages.error(request, f"Error deleting check-in: {str(e)}")
    
    return redirect('admin_app_collabsphere:wellbeing_management')

# -------------------------------
# TEAM CRUD VIEWS
# -------------------------------

@admin_required
def team_create(request):
    """Create a new team."""
    users = AdminSupabaseService.get_all_users()
    
    if request.method == 'POST':
        try:
            # Prepare team data according to schema
            team_data = {
                'team_name': request.POST.get('team_name', '').strip(),
                'description': request.POST.get('description', '').strip(),
                'joined_at': timezone.now().isoformat(),  
                'icon_url': 'https://example.com/default-team-icon.png',  
            }
            
            # Handle owner
            user_id_owner = request.POST.get('user_id_owner', '').strip()
            if user_id_owner:
                team_data['user_id_owner'] = int(user_id_owner)
            else:
                messages.error(request, "Team owner is required.")
                return redirect('admin_app_collabsphere:team_create')
            
            # Handle icon upload
            icon_file = request.FILES.get('team_icon')
            if icon_file:
                try:
                    icon_url = AdminSupabaseService.upload_team_icon(icon_file)
                    team_data['icon_url'] = icon_url
                except Exception as e:
                    logger.error(f"Error uploading icon: {e}")
                    messages.warning(request, f"Could not upload icon: {str(e)}")
            
            # Get selected members
            members_input = request.POST.get('members', '')
            selected_member_ids = []
            if members_input:
                raw_ids = members_input.split(',')
                for raw_id in raw_ids:
                    clean_id = raw_id.strip()
                    if clean_id and clean_id.isdigit():
                        selected_member_ids.append(clean_id)
            
            # Ensure owner is in selected members
            if str(team_data['user_id_owner']) not in selected_member_ids:
                selected_member_ids.append(str(team_data['user_id_owner']))
            
            # Create the team
            team = AdminSupabaseService.create_team(team_data)
            
            if team:
                team_id = team['team_ID']
                
                # Add members to team
                for member_id in selected_member_ids:
                    try:
                        AdminSupabaseService.add_member_to_team(team_id, int(member_id))
                    except Exception as e:
                        error_msg = str(e)
                        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                            logger.warning(f"Member {member_id} already in team")
                        else:
                            logger.error(f"Error adding member {member_id}: {e}")
                            messages.warning(request, f"Failed to add user {member_id}: {error_msg}")
                
                messages.success(request, f"Team '{team['team_name']}' created successfully.")
                return redirect('admin_app_collabsphere:team_detail', team_id=team_id)
            else:
                messages.error(request, "Failed to create team.")
                
        except Exception as e:
            logger.error(f"Error creating team: {str(e)}")
            messages.error(request, f"Error creating team: {str(e)}")
    
    context = {
        'users': users,
        'member_ids': [],  
        'active_page': 'teams',
    }
    return render(request, 'team_form.html', context)

@admin_required
def team_edit(request, team_id):
    """Edit an existing team - FIXED VERSION"""
    team = AdminSupabaseService.get_team_by_id(team_id)
    users = AdminSupabaseService.get_all_users()
    members = AdminSupabaseService.get_team_members(team_id)
    
    # Extract user IDs from members - FIXED FOR ADMIN SERVICE
    member_ids = []
    for member in (members or []):
        if isinstance(member, dict):
            # AdminSupabaseService returns members with 'user_ID' key
            user_id = member.get('user_ID')
            if user_id:
                # Ensure it's a string for template comparison
                member_ids.append(str(user_id))
    
    # DEBUG LOGGING
    print(f"DEBUG team_edit: team_id={team_id}")
    print(f"DEBUG team_edit: members count={len(members) if members else 0}")
    print(f"DEBUG team_edit: member_ids={member_ids}")
    
    # Also check what users we have
    user_ids_in_users = [str(u.get('user_ID')) for u in users if u.get('user_ID')]
    print(f"DEBUG team_edit: User IDs in users list: {user_ids_in_users}")
    
    # Find which member IDs exist in users list
    existing_member_ids = []
    for member_id in member_ids:
        if member_id in user_ids_in_users:
            existing_member_ids.append(member_id)
        else:
            print(f"WARNING: Member ID {member_id} not found in users list!")
    
    print(f"DEBUG team_edit: Existing member IDs: {existing_member_ids}")
    
    if not team:
        messages.error(request, f"Team with ID {team_id} not found.")
        return redirect('admin_app_collabsphere:team_management')
    
    if request.method == 'POST':
        try:
            update_data = {
                'team_name': request.POST.get('team_name'),
                'description': request.POST.get('description', ''),
            }
            
            # Handle owner change
            user_id_owner = request.POST.get('user_id_owner')
            if user_id_owner:
                update_data['user_id_owner'] = int(user_id_owner)
            
            # Handle icon
            icon_file = request.FILES.get('team_icon')
            remove_icon = request.POST.get('remove_icon') == 'on'
            
            if icon_file:
                try:
                    icon_url = AdminSupabaseService.upload_team_icon(icon_file, team_id)
                    update_data['icon_url'] = icon_url
                except Exception as e:
                    logger.error(f"Error uploading icon: {e}")
                    messages.warning(request, f"Could not upload icon: {str(e)}")
            elif remove_icon:
                update_data['icon_url'] = 'https://example.com/default-team-icon.png'
            
            # Update team basic info
            updated_team = AdminSupabaseService.update_team(team_id, update_data)
            
            if updated_team:
                # Get selected members from form
                members_input = request.POST.get('members', '')
                selected_member_ids = []
                if members_input:
                    raw_ids = members_input.split(',')
                    for raw_id in raw_ids:
                        clean_id = raw_id.strip()
                        if clean_id and clean_id.isdigit():
                            selected_member_ids.append(clean_id)
                
                print(f"DEBUG team_edit POST: selected_member_ids={selected_member_ids}")
                
                # Ensure owner is in selected members
                if user_id_owner and str(user_id_owner) not in selected_member_ids:
                    selected_member_ids.append(str(user_id_owner))
                
                # Update team members
                current_member_set = set(member_ids)
                new_member_set = set(selected_member_ids)
                
                print(f"DEBUG team_edit: current_member_set={current_member_set}")
                print(f"DEBUG team_edit: new_member_set={new_member_set}")
                
                # Members to add
                members_to_add = new_member_set - current_member_set
                print(f"DEBUG team_edit: members_to_add={members_to_add}")
                
                for member_id in members_to_add:
                    try:
                        AdminSupabaseService.add_member_to_team(team_id, int(member_id))
                        print(f"DEBUG: Added member {member_id} to team {team_id}")
                    except Exception as e:
                        error_msg = str(e)
                        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                            logger.warning(f"Member {member_id} already in team")
                        else:
                            logger.error(f"Error adding member {member_id}: {e}")
                            messages.warning(request, f"Failed to add user {member_id}: {error_msg}")
                
                # Members to remove (except owner)
                members_to_remove = current_member_set - new_member_set
                print(f"DEBUG team_edit: members_to_remove={members_to_remove}")
                
                for member_id in members_to_remove:
                    # Don't remove the owner
                    if user_id_owner and member_id != str(user_id_owner):
                        try:
                            AdminSupabaseService.remove_member_from_team(team_id, int(member_id))
                            print(f"DEBUG: Removed member {member_id} from team {team_id}")
                        except Exception as e:
                            logger.error(f"Error removing member {member_id}: {e}")
                            messages.warning(request, f"Failed to remove user {member_id}: {str(e)}")
                    elif member_id == str(user_id_owner):
                        messages.info(request, "Team owner cannot be removed from the team.")
                
                messages.success(request, f"Team '{updated_team['team_name']}' updated successfully.")
                return redirect('admin_app_collabsphere:team_detail', team_id=team_id)
            else:
                messages.error(request, "Failed to update team.")
                
        except Exception as e:
            logger.error(f"Error updating team: {str(e)}")
            messages.error(request, f"Error updating team: {str(e)}")
    
    context = {
        'team': team,
        'users': users,
        'current_member_ids': existing_member_ids,  # Use filtered list
        'active_page': 'teams',
    }
    return render(request, 'team_form.html', context)

@admin_required
@require_POST
def team_delete(request, team_id):
    """Delete a team."""
    try:
        success = AdminSupabaseService.delete_team(team_id)
        
        if success:
            messages.success(request, "Team deleted successfully.")
        else:
            messages.error(request, "Failed to delete team.")
    except Exception as e:
        messages.error(request, f"Error deleting team: {str(e)}")
    
    return redirect('admin_app_collabsphere:team_management')

#helper for event data
def validate_event_data(request_data, is_update=False, existing_event=None):
        """Validate event data for creation or update."""
        errors = []
        
        # Check required fields
        if not request_data.get('title'):
            errors.append("Event title is required")
        
        # Check team selection
        team_id = request_data.get('team_id')
        if not team_id:
            errors.append("A team must be selected for the event")
        
        # Check if team exists
        if team_id:
            team = AdminSupabaseService.get_team_by_id(team_id)
            if not team:
                errors.append(f"Selected team (ID: {team_id}) does not exist")
        
        # Validate dates if provided
        start_date = request_data.get('start_date')
        start_time = request_data.get('start_time')
        end_date = request_data.get('end_date')
        end_time = request_data.get('end_time')
        
        if start_date and start_time:
            try:
                start_datetime_str = f"{start_date}T{start_time}:00"
                datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid start date/time format")
        
        if end_date and end_time:
            try:
                end_datetime_str = f"{end_date}T{end_time}:00"
                datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
            except ValueError:
                errors.append("Invalid end date/time format")
        
        # Check that end time is after start time if both provided
        if start_date and start_time and end_date and end_time:
            try:
                start_str = f"{start_date}T{start_time}:00"
                end_str = f"{end_date}T{end_time}:00"
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                if end_dt <= start_dt:
                    errors.append("End time must be after start time")
            except ValueError:
                pass  
        
        return errors