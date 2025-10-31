from django.urls import path
from . import views

urlpatterns = [
    path('', views.teams, name='teams'),
    path('create/', views.create_team, name='create_team'),
    path('switch/<int:team_ID>/', views.switch_team, name='switch_team'),
    path('get-users-without-teams/', views.get_users_without_teams, name='get_users_without_teams'),
    path('edit/<int:team_ID>/', views.edit_team, name='edit_team'),
    path('delete/<int:team_ID>/', views.delete_team, name='delete_team'),
]