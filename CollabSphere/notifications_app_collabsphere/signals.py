# notifications_app_collabsphere/signals.py
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Notification
from tasks_app_collabsphere.models import Task
from teams_app_collabsphere.models import Team, UserTeam  # adjust if your membership model name differs

User = get_user_model()

@receiver(post_save, sender=Task)
def task_assignment_notification(sender, instance, created, **kwargs):
    """
    When a task is created or updated: if assigned_to is set and it's different from the previous value,
    create a notification for the assigned user.
    """
    # We will check instance.assigned_to exists (should be user id or user object depending on model)
    try:
        assigned = getattr(instance, 'assigned_to', None)
        # if assigned is an integer PK or a user object:
        if assigned:
            # If assigned is integer then get User instance
            if isinstance(assigned, int):
                try:
                    recipient = User.objects.get(pk=assigned)
                except User.DoesNotExist:
                    return
            else:
                recipient = assigned  # assume a User instance

            # Create notification
            Notification.objects.create(
                recipient=recipient,
                sender=instance.created_by if hasattr(instance, 'created_by') else None,
                notification_type='task',
                title=f"Task assigned: {instance.title}",
                message=f"You were assigned to task '{instance.title}'.",
                related_task=instance,
                related_object_url=f"/tasks/{instance.task_id}/"  # adjust url path as needed
            )
    except Exception as e:
        print("task_assignment_notification error:", e)


@receiver(post_save, sender=Team)
def team_created_notification(sender, instance, created, **kwargs):
    """
    Optionally notify owner or newly added members when a team is created.
    (We also handle member-add with UserTeam below.)
    """
    if created:
        # Notify owner they created the team (optional)
        try:
            if hasattr(instance, 'user_id_owner') and instance.user_id_owner:
                owner = User.objects.filter(pk=instance.user_id_owner).first()
                if owner:
                    Notification.objects.create(
                        recipient=owner,
                        sender=None,
                        notification_type='team',
                        title=f"Team created: {instance.team_name}",
                        message=f"You created the team '{instance.team_name}'.",
                        related_team=instance,
                        related_object_url=f"/teams/{instance.team_ID}/"
                    )
        except Exception as e:
            print("team_created_notification error:", e)


# If your team membership is handled by a separate model (UserTeam), listen to post_save on that model:
try:
    @receiver(post_save, sender=UserTeam)
    def user_added_to_team(sender, instance, created, **kwargs):
        """
        When a UserTeam row is created (user added to team), create a notification for the user.
        """
        if created:
            try:
                user = instance.user  # adjust field names if different
                team = instance.team
                if user and team:
                    # Do not notify the owner who added themselves; this keeps parity with your earlier logic
                    Notification.objects.create(
                        recipient=user,
                        sender=team.user_id_owner if hasattr(team, 'user_id_owner') else None,
                        notification_type='team',
                        title=f"Added to team: {team.team_name}",
                        message=f"You were added to '{team.team_name}'.",
                        related_team=team,
                        related_object_url=f"/teams/{team.team_ID}/"
                    )
            except Exception as e:
                print("user_added_to_team error:", e)
except Exception:
    # If UserTeam cannot be imported, skip this receiver — it's optional
    pass
