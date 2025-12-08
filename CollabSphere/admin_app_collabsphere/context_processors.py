from admin_app_collabsphere.models import AdminSupabaseService

def admin_stats(request):
    if request.user.is_authenticated and request.user.is_staff:
        admin_manager = AdminSupabaseService()
        stats = admin_manager.get_system_stats()
        
        return {
            'total_users': stats.get('total_users', 0),
            'total_tasks': stats.get('total_tasks', 0),
            'total_teams': stats.get('total_teams', 0),
            'total_checkins': stats.get('total_checkins', 0),
        }
    return {}