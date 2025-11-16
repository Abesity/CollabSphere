from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from tasks_app_collabsphere.models import Task  
from teams_app_collabsphere.models import UserTeam, Team  
from .views import create_task_notification, create_team_notification

User = get_user_model()

@receiver(post_save, sender=Task)
def task_assignment_notification(sender, instance, created, **kwargs):
    if created and instance.assigned_to:
        task_data = {
            'task_id': instance.task_id,
            'title': instance.title,
            'description': instance.description,
            'assigned_to': instance.assigned_to_id,
            'assigned_to_username': instance.assigned_to.username,
            'due_date': instance.due_date
        }
        create_task_notification(task_data, sender_user=instance.created_by_user if hasattr(instance, 'created_by_user') else None)

@receiver(post_save, sender=UserTeam)
def team_assignment_notification(sender, instance, created, **kwargs):
    if created:
        team = instance.team
        member = instance.user
        team_data = {
            'team_name': team.team_name,
            'team_ID': team.team_ID,
            'description': team.description
        }
        create_team_notification(team_data, member_value=member, sender_user=team.user_id_owner)
