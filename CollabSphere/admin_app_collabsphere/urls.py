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
    
    # API Endpoints
    path('api/user-stats/', views.api_user_stats, name='api_user_stats'),
    path('api/system-stats/', views.api_system_stats, name='api_system_stats'),
    path('api/checkin-stats/', views.api_checkin_stats, name='api_checkin_stats'),
    
    # Export Endpoints
    path('export/users/', views.export_users, name='export_users'),
    path('export/tasks/', views.export_tasks, name='export_tasks'),
]