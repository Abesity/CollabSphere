from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications_app_collabsphere'

    def ready(self):
        # import signals so they get registered
        try:
            import notifications_app_collabsphere.signals  # noqa: F401
        except Exception as e:
            # Avoid breaking app import if signals import fails; log to console
            print("Error importing notification signals:", e)
