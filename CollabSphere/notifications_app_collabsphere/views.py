from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from .models import Notification


@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, 'notifications_list.html', {'notifications': notifications})


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.read = True
    notification.save()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, read=False).update(read=True)
    return JsonResponse({'status': 'success', 'message': 'All notifications marked as read'})


@login_required
@require_POST
def clear_inbox(request):
    Notification.objects.filter(recipient=request.user).delete()
    return JsonResponse({'status': 'success', 'message': 'Inbox cleared'})


@login_required
def get_unread_count(request):
    count = Notification.objects.filter(recipient=request.user, read=False).count()
    return JsonResponse({'count': count})


def _resolve_recipient(value):
    """Resolve a recipient to a Django user instance.

    value may be:
      - a Django user instance -> returned
      - an integer/string supabase user_ID -> match CustomUser.supabase_id
      - a username string -> match username
      - a dict from Supabase with user_ID/username keys
    """
    User = get_user_model()
    # If already a user instance
    try:
        from django.contrib.auth import get_user_model as _gum
        # simple duck-typing check
        if hasattr(value, 'is_authenticated'):
            return value
    except Exception:
        pass

    # Dict-like
    if isinstance(value, dict):
        if value.get('user_ID'):
            supabase_id = str(value.get('user_ID'))
            user = User.objects.filter(supabase_id=supabase_id).first()
            if user:
                return user
        if value.get('username'):
            user = User.objects.filter(username=value.get('username')).first()
            if user:
                return user

    # Numeric or string - try supabase_id first
    if isinstance(value, (int, str)):
        supabase_id = str(value)
        user = User.objects.filter(supabase_id=supabase_id).first()
        if user:
            return user
        # fallback to username
        user = User.objects.filter(username=value).first()
        if user:
            return user

    return None


def create_task_notification(task_data, sender_user=None):
    """Create a notification for a task assignment.

    Accepts a dict-like `task_data` (from Supabase) or an object with similar attributes.
    """
    if not task_data:
        return

    # normalize accessors
    def _get(k):
        if isinstance(task_data, dict):
            return task_data.get(k)
        return getattr(task_data, k, None)

    assigned_to = _get('assigned_to')
    if not assigned_to:
        return

    # require task_id for linking
    task_id = _get('task_id') or _get('id')
    title = _get('title') or 'Task'
    description = _get('description')
    due_date = _get('due_date')
    created_by = _get('created_by')
    assigned_to_username = _get('assigned_to_username')

    # Resolve recipient
    recipient = _resolve_recipient({'user_ID': assigned_to, 'username': assigned_to_username})
    if not recipient:
        print(f"Notification: recipient not found for assigned_to={assigned_to}")
        return

    # Resolve sender
    sender = None
    if sender_user:
        sender = sender_user
    elif created_by:
        sender = _resolve_recipient(created_by)

    # Avoid notifying the actor themselves
    if sender and recipient and getattr(sender, 'id', None) == getattr(recipient, 'id', None):
        return

    try:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='task',
            title=title,
            message=f"{title} was assigned to you",
            description=description,
            deadline=due_date,
            related_object_id=task_id,
            related_object_url=f"/tasks/{task_id}/" if task_id else None,
        )
    except Exception as e:
        print(f"Error creating notification: {e}")


def create_team_notification(team_data, member_value, sender_user=None):
    """Create a notification when a user is added to a team.

    `member_value` can be a Django user, a supabase id, or a dict from Supabase.
    """
    recipient = _resolve_recipient(member_value)
    if not recipient:
        print(f"Notification: recipient not found for team member {member_value}")
        return

    team_name = None
    team_id = None
    description = None
    if isinstance(team_data, dict):
        team_name = team_data.get('team_name') or team_data.get('name')
        team_id = team_data.get('team_ID') or team_data.get('id')
        description = team_data.get('description')
    else:
        team_name = getattr(team_data, 'team_name', None) or getattr(team_data, 'name', None)
        team_id = getattr(team_data, 'team_ID', None) or getattr(team_data, 'id', None)
        description = getattr(team_data, 'description', None)

    # Resolve sender
    sender = sender_user
    try:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='team',
            title=f"Added to team: {team_name}",
            message=f"You have been added to {team_name}",
            description=description,
            related_object_id=team_id,
            related_object_url=f"/teams/{team_id}/" if team_id else None,
        )
    except Exception as e:
        print(f"Error creating team notification: {e}")

