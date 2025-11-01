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
    # Delete local Django notifications
    qs = Notification.objects.filter(recipient=request.user)

    # Also delete corresponding rows in Supabase if supabase_id or supabase mapping exists
    try:
        from django.conf import settings
        from supabase import create_client

        SUPABASE_URL = settings.SUPABASE_URL
        SUPABASE_KEY = settings.SUPABASE_KEY
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Prefer deleting by supabase_id if present
        supabase_ids = list(qs.exclude(supabase_id__isnull=True).values_list('supabase_id', flat=True))
        if supabase_ids:
            supabase.table('notifications').delete().in_('notification_id', supabase_ids).execute()
        else:
            # Fallback: delete by recipient supabase id
            recipient_supabase_id = getattr(request.user, 'supabase_id', None)
            if recipient_supabase_id:
                supabase.table('notifications').delete().eq('recipient', int(recipient_supabase_id)).execute()
    except Exception as e:
        print(f"Error deleting notifications from Supabase: {e}")

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

    sender = sender_user

    task_id = task_data.get('task_id') or task_data.get('id')
    title = task_data.get('title') or 'Task'
    description = task_data.get('description')
    due_date = task_data.get('due_date')

    # Message format
    message_text = f"{title} was assigned to you"
    title_text = title

    try:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='task',
            title=title_text,
            message=message_text,
            description=description,
            deadline=due_date,
            related_object_id=task_id,
            related_object_url=f"/tasks/{task_id}/" if task_id else None,
        )
    except Exception as e:
        print(f"Error creating task notification: {e}")

    # Supabase sync (identical to team notification)
    try:
        from django.conf import settings
        from supabase import create_client
        import traceback

        SUPABASE_URL = settings.SUPABASE_URL
        SUPABASE_KEY = settings.SUPABASE_KEY
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("ERROR: Missing Supabase configuration - check SUPABASE_URL and SUPABASE_KEY in settings")
            return

        recipient_supabase_id = getattr(recipient, 'supabase_id', None)
        if not recipient_supabase_id:
            print(f"ERROR: Cannot create Supabase notification - recipient {recipient} has no supabase_id")
            return

        sender_supabase_id = None
        if sender:
            sender_supabase_id = getattr(sender, 'supabase_id', None)

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        sup_payload = {
            'recipient': int(recipient_supabase_id),
            'sender': int(sender_supabase_id) if sender_supabase_id else None,
            'notification_type': 'task',
            'title': title_text[:255] if title_text else '',
            'message': message_text[:255] if message_text else '',
            'description': description[:1000] if description else None,
            'read': False,
            'related_object_id': int(task_id) if task_id else None,
            'related_object_url': f"/tasks/{task_id}/" if task_id else None,
        }

        print(f"DEBUG: Attempting Supabase task notification insert with payload: {sup_payload}")

        res = supabase.table('notifications').insert(sup_payload).execute()
        print(f"DEBUG: Supabase response: {res}")

        if getattr(res, 'data', None):
            inserted = res.data[0]
            sup_id = inserted.get('notification_id') or inserted.get('id')
            if sup_id:
                try:
                    n = Notification.objects.filter(recipient=recipient, title=title_text).order_by('-created_at').first()
                    if n:
                        n.supabase_id = sup_id
                        n.save()
                        print(f"DEBUG: Updated Django task notification {n.id} with supabase_id {sup_id}")
                except Exception as inner_e:
                    print(f"ERROR: Failed to update Django notification with supabase_id: {inner_e}")
            else:
                print("ERROR: Supabase insert succeeded but no notification_id returned")
        else:
            print(f"ERROR: No data in Supabase response: {res}")
    except Exception as e:
        print(f"ERROR: Failed to sync task notification to Supabase: {str(e)}")
        traceback.print_exc()


def create_team_notification(team_data, member_value, sender_user=None):
    """Create a notification when a user is added to a team.

    `member_value` can be a Django user, a supabase id, or a dict from Supabase.
    """
    print(f"Creating team notification with data: {team_data}, members: {member_value}")

    # Allow member_value to be a list of members
    members = member_value if isinstance(member_value, (list, tuple)) else [member_value]

    # Extract team info from dict
    team_name = team_data.get('team_name', '')  # Simpler access, we know it's a dict now
    team_id = team_data.get('team_ID')
    description = team_data.get('description')

    print(f"Extracted team info - name: {team_name}, id: {team_id}, members to notify: {len(members)}")

    sender = sender_user

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
            Notification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type='team',
                title=title_text,
                message=message_text,
                description=description,
                related_object_id=team_id,
                related_object_url=f"/teams/{team_id}/" if team_id else None,
            )
        except Exception as e:
            print(f"Error creating team notification: {e}")

        # Persist team notification to Supabase as well
        try:
            from django.conf import settings
            from supabase import create_client
            import traceback

            SUPABASE_URL = settings.SUPABASE_URL
            SUPABASE_KEY = settings.SUPABASE_KEY
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("ERROR: Missing Supabase configuration - check SUPABASE_URL and SUPABASE_KEY in settings")
                continue

            recipient_supabase_id = getattr(recipient, 'supabase_id', None)
            if not recipient_supabase_id:
                print(f"ERROR: Cannot create Supabase notification - recipient {recipient} has no supabase_id")
                continue

            sender_supabase_id = None
            if sender:
                sender_supabase_id = getattr(sender, 'supabase_id', None)

            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

            sup_payload = {
                'recipient': int(recipient_supabase_id),
                'sender': int(sender_supabase_id) if sender_supabase_id else None,
                'notification_type': 'team',
                'title': title_text[:255] if title_text else '',
                'message': message_text[:255] if message_text else '',
                'description': description[:1000] if description else None,
                'read': False,
                'related_object_id': int(team_id) if team_id else None,
                'related_object_url': f"/teams/{team_id}/" if team_id else None,
            }

            print(f"DEBUG: Attempting Supabase team notification insert with payload: {sup_payload}")
            res = supabase.table('notifications').insert(sup_payload).execute()
            print(f"DEBUG: Supabase response: {res}")

            if getattr(res, 'data', None):
                inserted = res.data[0]
                sup_id = inserted.get('notification_id') or inserted.get('id')
                if sup_id:
                    try:
                        n = Notification.objects.filter(recipient=recipient, title=title_text).order_by('-created_at').first()
                        if n:
                            n.supabase_id = sup_id
                            n.save()
                            print(f"DEBUG: Updated Django team notification {n.id} with supabase_id {sup_id}")
                    except Exception as inner_e:
                        print(f"ERROR: Failed to update Django notification with supabase_id: {inner_e}")
                else:
                    print("ERROR: Supabase insert succeeded but no notification_id returned")
            else:
                print(f"ERROR: No data in Supabase response: {res}")
        except Exception as e:
            print(f"ERROR: Failed to sync team notification to Supabase: {str(e)}")
            traceback.print_exc()

