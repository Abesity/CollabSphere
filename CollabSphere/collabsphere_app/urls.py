from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("admin_dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("verify_checkin_status/", views.verify_checkin_status, name="verify_checkin_status"),    
    path('debug-checkins/', views.debug_checkins, name='debug_checkins'),
]

