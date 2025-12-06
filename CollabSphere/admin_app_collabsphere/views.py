from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
import json
from .models import AdminSupabaseService
import logging

logger = logging.getLogger(__name__)


# Decorator to check if user is admin
def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        # Hardcoded admin session allowed
        if request.session.get("admin_logged_in"):
            return view_func(request, *args, **kwargs)

        # Regular staff check
        if not request.user.is_authenticated:
            return redirect(f'/login/?next={request.path}')
        if not request.user.is_staff:
            messages.error(request, "You don't have permission to access the admin panel.")
            return redirect('home')

        return view_func(request, *args, **kwargs)

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
        'tasks_today': stats.get('tasks_today', 0),
        'recent_users': stats.get('recent_users', []),
        'recent_tasks': stats.get('recent_tasks', []),
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
    
    context = {
        'team': team,
        'members': members,
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