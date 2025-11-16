from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications_app_collabsphere'

    def ready(self):
        try:
            import notifications_app_collabsphere.signals
        except Exception as e:
            print("Error importing notification signals:", e)
