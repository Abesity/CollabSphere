from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("admin_dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("profile/", views.profile_view, name="profile"),
]

