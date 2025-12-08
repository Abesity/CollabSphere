from admin_app_collabsphere.models import AdminSupabaseService

def admin_stats(request):
    # Be defensive for requests without `user` (e.g., RequestFactory in tests)
    if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False) and getattr(request.user, 'is_staff', False):
        admin_manager = AdminSupabaseService()
        stats = admin_manager.get_system_stats()
        
        return {
            'total_users': stats.get('total_users', 0),
            'total_tasks': stats.get('total_tasks', 0),
            'total_teams': stats.get('total_teams', 0),
            'total_checkins': stats.get('total_checkins', 0),
            'total_events': stats.get('total_events', 0),
            'users_today': stats.get('users_today', 0),
        }
    return {}