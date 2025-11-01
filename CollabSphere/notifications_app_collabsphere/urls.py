from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notifications_list, name='list'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('clear-inbox/', views.clear_inbox, name='clear_inbox'),
    path('unread-count/', views.get_unread_count, name='unread_count'),
]
