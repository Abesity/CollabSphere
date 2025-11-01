from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('task', 'Task Assignment'),
        ('team', 'Team Invitation'),
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