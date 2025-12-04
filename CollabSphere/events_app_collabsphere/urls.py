from django.urls import path
from . import views

urlpatterns = [
    # Calendar view
    path("", views.events_calendar, name="events_calendar"),
    
    # Regular event CRUD
    path("create/", views.create_event, name="create_event"),
    path("get-events/", views.get_events, name="get_events"),
    path("get/<int:event_id>/", views.get_event, name="get_event"),
    path("update/<int:event_id>/", views.update_event, name="update_event"),
    path("delete/<int:event_id>/", views.delete_event, name="delete_event"),
    path("join/<int:event_id>/", views.join_event, name="join_event"),
    path("leave/<int:event_id>/", views.leave_event, name="leave_event"),
    
    # Conflict checking
    path("check-conflicts/", views.check_event_conflicts, name="check_event_conflicts"),
    
    # Recurring event management
    path("recurring/", views.get_recurring_events, name="get_recurring_events"),
    path("recurring/update/<int:event_id>/", views.update_recurring_event, name="update_recurring_event"),
    path("recurring/delete/<int:event_id>/", views.delete_recurring_event, name="delete_recurring_event"),
]