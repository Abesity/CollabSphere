from django.urls import path
from . import views

app_name = 'admin_app_collabsphere'

urlpatterns = [
    # Dashboard
    path('', views.admin_dashboard, name='dashboard'),
    
    # User Management
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    
    # Task Management
    path('tasks/', views.task_management, name='task_management'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    
    # Team Management
    path('teams/', views.team_management, name='team_management'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    
    # Wellbeing Management
    path('wellbeing/', views.wellbeing_management, name='wellbeing_management'),
    
    # Search
    path('search/', views.search, name='search'),
    
    # Events - FIXED: Changed create_event to event_create to match your views.py
    path('events/', views.event_management, name='event_management'),
    path('events/create/', views.event_create, name='create_event'),  # CHANGED HERE
    path('events/<int:event_id>/delete/', views.delete_event, name='delete_event'),

    # Admin Task CRUD
    path('tasks/create/', views.task_create, name='task_create_admin'),
    path('tasks/<int:task_id>/delete/', views.task_delete, name='task_delete_admin'),

    # Admin Checkin CRUD
    path('wellbeing/create/', views.create_checkin, name='create_checkin_admin'),
    path('wellbeing/<int:checkin_id>/delete/', views.delete_checkin, name='delete_checkin_admin'),
    
    # API Endpoints
    path('api/user-stats/', views.api_user_stats, name='api_user_stats'),
    path('api/system-stats/', views.api_system_stats, name='api_system_stats'),
    path('api/checkin-stats/', views.api_checkin_stats, name='api_checkin_stats'),
    path('api/event-details/<int:event_id>/', views.api_event_details, name='api_event_details'),
    # Additional API endpoints for admin JS and integrations
    path('api/teams/', views.api_teams, name='api_teams'),
    path('api/teams/<int:team_id>/', views.api_team_detail, name='api_team_detail'),
    path('api/events/', views.api_events, name='api_events'),
    path('api/tasks/', views.api_tasks, name='api_tasks'),
    path('api/tasks/<int:task_id>/', views.api_task_detail, name='api_task_detail'),
    path('api/checkins/', views.api_checkins, name='api_checkins'),
    path('api/checkins/<int:checkin_id>/', views.api_checkin_detail, name='api_checkin_detail'),

    # Export Endpoints
    path('export/users/', views.export_users, name='export_users'),
    path('export/tasks/', views.export_tasks, name='export_tasks'),
        
    # Task Edit URL (missing from original)
    path('tasks/<int:task_id>/edit/', views.task_edit, name='task_edit_admin'),
    # Backwards-compatible names used by templates
    path('tasks/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    
    # Team CRUD URLs (missing from original)
    path('teams/create/', views.team_create, name='team_create'),
    path('teams/<int:team_id>/edit/', views.team_edit, name='team_edit'),
    path('teams/<int:team_id>/delete/', views.team_delete, name='team_delete'),
    # Backwards-compatible alias for team management templates
    path('teams/<int:team_id>/delete/', views.team_delete, name='team_delete_admin'),
    
    # Event Detail and Edit URLs (missing from original)
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('events/<int:event_id>/edit/', views.event_edit, name='event_edit'),
    
    # Checkin Detail and Edit URLs (missing from original)
    path('wellbeing/checkins/<int:checkin_id>/', views.checkin_detail, name='checkin_detail'),
    path('wellbeing/checkins/<int:checkin_id>/edit/', views.checkin_edit, name='checkin_edit'),
    # Template-compatible wellbeing names
    path('wellbeing/checkins/<int:checkin_id>/', views.checkin_detail, name='wellbeing_detail'),
    path('wellbeing/checkins/<int:checkin_id>/edit/', views.checkin_edit, name='wellbeing_edit'),
    path('wellbeing/checkins/<int:checkin_id>/delete/', views.delete_checkin, name='wellbeing_delete'),
    # Backwards-compatible name used in templates
    path('wellbeing/checkins/<int:checkin_id>/delete/', views.delete_checkin, name='checkin_delete'),
]