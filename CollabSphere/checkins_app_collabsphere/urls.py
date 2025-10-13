from django.urls import path
from . import views

urlpatterns = [
    path('modal/', views.checkins_modal, name='checkins_modal'),
    path('dashboard/', views.wellbeing_dashboard, name='wellbeing_dashboard'),
]
