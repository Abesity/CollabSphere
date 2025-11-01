from django.urls import path
from . import views

urlpatterns = [
    path("", views.events_calendar, name="events_calendar"),
]

