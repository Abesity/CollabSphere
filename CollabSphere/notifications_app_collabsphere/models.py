from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from supabase import create_client
import traceback

User = get_user_model()

# Initialize Supabase client
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('task', 'Task Assignment'),
        ('team', 'Team Invitation'),
        ('comment', 'Task Comment'),
    )

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    description = models.TextField(null=True, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField(null=True, blank=True)
    related_object_id = models.IntegerField(null=True)
    related_object_url = models.CharField(max_length=255, null=True, blank=True) # Added blank=True
    supabase_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        # Use default table name (app_label_modelname). Removed custom db_table to support SQLite.

    def __str__(self):
        return f"{self.notification_type} notification for {self.recipient.username}"

    def get_absolute_url(self):
        # Fallback if no URL is set
        if not self.related_object_url:
            return '#' 
        return self.related_object_url
        
    @classmethod
    def sync_to_supabase(cls, notification):
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            if not SUPABASE_URL or not SUPABASE_KEY:
                print("ERROR: Missing Supabase configuration - check SUPABASE_URL and SUPABASE_KEY in settings")
                return

            recipient_supabase_id = getattr(notification.recipient, 'supabase_id', None)
            if not recipient_supabase_id:
                print(f"ERROR: Cannot create Supabase notification - recipient {notification.recipient} has no supabase_id")
                return

            sender_supabase_id = None
            if notification.sender:
                sender_supabase_id = getattr(notification.sender, 'supabase_id', None)

            sup_payload = {
                'recipient': int(recipient_supabase_id),
                'sender': int(sender_supabase_id) if sender_supabase_id else None,
                'notification_type': notification.notification_type,
                'title': notification.title[:255] if notification.title else '',
                'message': notification.message[:255] if notification.message else '',
                'description': notification.description[:1000] if notification.description else None,
                'read': notification.read,
                'related_object_id': notification.related_object_id,
                'related_object_url': notification.related_object_url,
            }

            print(f"DEBUG: Attempting Supabase notification insert with payload: {sup_payload}")
            res = supabase.table('notifications').insert(sup_payload).execute()
            print(f"DEBUG: Supabase response: {res}")

            if getattr(res, 'data', None):
                inserted = res.data[0]
                sup_id = inserted.get('notification_id') or inserted.get('id')
                if sup_id:
                    notification.supabase_id = sup_id
                    notification.save()
                    print(f"DEBUG: Updated Django notification {notification.id} with supabase_id {sup_id}")
                else:
                    print("ERROR: Supabase insert succeeded but no notification_id returned")
            else:
                print(f"ERROR: No data in Supabase response: {res}")
        except Exception as e:
            print(f"ERROR: Failed to sync notification to Supabase: {str(e)}")
            traceback.print_exc()

    @classmethod
    def delete_from_supabase(cls, notification_queryset):
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            # Prefer deleting by supabase_id if present
            supabase_ids = list(notification_queryset.exclude(supabase_id__isnull=True).values_list('supabase_id', flat=True))
            if supabase_ids:
                supabase.table('notifications').delete().in_('notification_id', supabase_ids).execute()
            else:
                # Fallback: delete by recipient supabase id
                recipient = notification_queryset.first().recipient if notification_queryset.exists() else None
                if recipient and recipient.supabase_id:
                    supabase.table('notifications').delete().eq('recipient', int(recipient.supabase_id)).execute()
        except Exception as e:
            print(f"Error deleting notifications from Supabase: {e}")
            traceback.print_exc()