"""
URL configuration for CollabSphere project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def root_redirect(request):
    # If the user is logged in, go straight to the dashboard (home)
    if request.user.is_authenticated:
        return redirect('home')
    # Otherwise, send them to the login page
    return redirect('login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect),  
    path('home/', include('collabsphere_app.urls')), 
    path("tasks/", include("tasks_app_collabsphere.urls")),
    path('', include('registration_app_collabsphere.urls')),  
    path('checkins/', include('checkins_app_collabsphere.urls')),
    path('teams/', include('teams_app_collabsphere.urls')),
    path('notifications/', include('notifications_app_collabsphere.urls')),
    path('events/', include('events_app_collabsphere.urls')),
]
