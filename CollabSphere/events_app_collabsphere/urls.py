from django.urls import path
from . import views

urlpatterns = [
    path("", views.events_calendar, name="events_calendar"),
    path("create/", views.create_event, name="create_event"),
    path("get-events/", views.get_events, name="get_events"),
    path("delete/<int:event_id>/", views.delete_event, name="delete_event"),
]