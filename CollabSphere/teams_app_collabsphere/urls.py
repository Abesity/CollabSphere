from django.urls import path
from . import views

urlpatterns = [
    path("", views.teams_list, name="teams"),
    path("create/", views.create_team, name="create_team"),
    path("switch/<int:team_id>/", views.switch_team, name="switch_team"),
]
