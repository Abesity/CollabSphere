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
    # Delete local Django notifications and sync with Supabase
    qs = Notification.objects.filter(recipient=request.user)
    Notification.delete_from_supabase(qs)
    qs.delete()
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
    """Create a notification for a task assignment."""
    if not task_data:
        return

    assigned_to = task_data.get('assigned_to')
    assigned_to_username = task_data.get('assigned_to_username')

    recipient = _resolve_recipient({'user_ID': assigned_to, 'username': assigned_to_username})
    if not recipient:
        print(f"Notification: recipient not found for assigned_to={assigned_to}")
        return

    task_id = task_data.get('task_id') or task_data.get('id')
    title = task_data.get('title') or 'Task'
    description = task_data.get('description')
    due_date = task_data.get('due_date')

    # Message format
    message_text = f"{title} was assigned to you"
    title_text = title

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender_user,
            notification_type='task',
            title=title_text,
            message=message_text,
            description=description,
            deadline=due_date,
            related_object_id=task_id,
            related_object_url=f"/tasks/{task_id}/" if task_id else None,
        )
        Notification.sync_to_supabase(notification)
    except Exception as e:
        print(f"Error creating task notification: {e}")


def create_team_notification(team_data, member_value, sender_user=None):
    """Create a notification when a user is added to a team.

    `member_value` can be a Django user, a supabase id, or a dict from Supabase.
    """
    print(f"Creating team notification with data: {team_data}, members: {member_value}")

    # Allow member_value to be a list of members
    members = member_value if isinstance(member_value, (list, tuple)) else [member_value]

    # Extract team info from dict
    team_name = team_data.get('team_name', '')
    team_id = team_data.get('team_ID')
    description = team_data.get('description')

    print(f"Extracted team info - name: {team_name}, id: {team_id}, members to notify: {len(members)}")

    for member in members:
        recipient = _resolve_recipient(member)
        if not recipient:
            print(f"Notification: recipient not found for team member {member}")
            continue

        # Message as requested: "[Team Name] Added you [username] and Recieved."
        username = getattr(recipient, 'username', str(member))
        message_text = f"Added you {username}."
        title_text = f"You are added to team: {team_name}"

        try:
            notification = Notification.objects.create(
                recipient=recipient,
                sender=sender_user,
                notification_type='team',
                title=title_text,
                message=message_text,
                description=description,
                related_object_id=team_id,
                related_object_url=f"/teams/{team_id}/" if team_id else None,
            )
            Notification.sync_to_supabase(notification)
        except Exception as e:
            print(f"Error creating team notification: {e}")


def create_comment_notifications(task_data, recipients, sender_user=None, comment_content="", exclude_recipient_ids=None):
    """Create notifications for task comment activity.

    Args:
        task_data (dict): Includes task_id and title.
        recipients (iterable): Values resolvable by _resolve_recipient (user, dict, username, supabase id).
        sender_user (User): Django user who authored the comment.
        comment_content (str): Text of the comment for the notification body.
        exclude_recipient_ids (set[int]): Optional Django user IDs to skip when sending.
    """
    if not task_data or not recipients:
        return

    task_title = task_data.get('title') or 'Task'
    task_id = task_data.get('task_id')
    related_url = f"/tasks/{task_id}/detail/" if task_id else None
    preview = (comment_content or '').strip() or 'New comment posted.'

    seen_recipient_ids = set()
    excluded_ids = exclude_recipient_ids or set()

    for recipient_value in recipients:
        recipient = _resolve_recipient(recipient_value)
        if not recipient:
            continue
        if recipient.id in excluded_ids:
            continue
        if sender_user and recipient.id == sender_user.id:
            continue
        if recipient.id in seen_recipient_ids:
            continue

        seen_recipient_ids.add(recipient.id)

        try:
            notification = Notification.objects.create(
                recipient=recipient,
                sender=sender_user,
                notification_type='comment',
                title=f"New comment on {task_title}",
                message=preview[:255],
                description=comment_content,
                related_object_id=task_id,
                related_object_url=related_url,
            )
            Notification.sync_to_supabase(notification)
        except Exception as e:
            print(f"Error creating comment notification: {e}")


def create_comment_reply_notification(task_data, parent_comment, sender_user=None, comment_content=""):
    """Notify the parent comment author about a direct reply.

    Returns the recipient user instance if a notification was created, else None.
    """
    if not task_data or not parent_comment:
        return None

    parent_username = parent_comment.get('username')
    parent_user_id = parent_comment.get('user_id') or parent_comment.get('user_ID')

    recipient_value = {
        'username': parent_username,
        'user_ID': parent_user_id
    }
    recipient = _resolve_recipient(recipient_value)

    if not recipient or (sender_user and recipient.id == sender_user.id):
        return None

    task_title = task_data.get('title') or 'Task'
    task_id = task_data.get('task_id')
    related_url = f"/tasks/{task_id}/detail/" if task_id else None
    preview = (comment_content or '').strip() or 'New reply posted.'
    reply_author = getattr(sender_user, 'username', 'Someone')

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender_user,
            notification_type='comment',
            title=f"{reply_author} replied to your comment on {task_title}",
            message=preview[:255],
            description=comment_content,
            related_object_id=task_id,
            related_object_url=related_url,
        )
        Notification.sync_to_supabase(notification)
        return recipient
    except Exception as e:
        print(f"Error creating comment reply notification: {e}")
        return None


def create_task_status_notification(task_data, sender_user=None, new_status=None):
    """Notify the task creator that the status changed."""
    if not task_data:
        return

    creator_username = task_data.get('created_by')
    if not creator_username:
        return

    recipient = _resolve_recipient(creator_username)
    if not recipient or (sender_user and recipient.id == sender_user.id):
        return

    task_id = task_data.get('task_id')
    task_title = task_data.get('title') or 'Task'
    status_label = new_status or task_data.get('status') or 'updated'
    related_url = f"/tasks/{task_id}/detail/" if task_id else None

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender_user,
            notification_type='task',
            title=f"{task_title} status updated",
            message=f"Status changed to {status_label}",
            related_object_id=task_id,
            related_object_url=related_url,
        )
        Notification.sync_to_supabase(notification)
    except Exception as e:
        print(f"Error creating task status notification: {e}")


def create_task_completion_notification(task_data, sender_user=None, completion_value=None):
    """Notify the task creator when completion percentage changes."""
    if not task_data:
        return

    creator_username = task_data.get('created_by')
    if not creator_username:
        return

    recipient = _resolve_recipient(creator_username)
    if not recipient or (sender_user and recipient.id == sender_user.id):
        return

    task_id = task_data.get('task_id')
    task_title = task_data.get('title') or 'Task'
    completion_label = completion_value if completion_value is not None else task_data.get('completion')
    related_url = f"/tasks/{task_id}/detail/" if task_id else None

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender_user,
            notification_type='task',
            title=f"{task_title} progress updated",
            message=f"Completion changed to {completion_label}%",
            related_object_id=task_id,
            related_object_url=related_url,
        )
        Notification.sync_to_supabase(notification)
    except Exception as e:
        print(f"Error creating task completion notification: {e}")
