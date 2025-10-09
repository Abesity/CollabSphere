from django.urls import path
from . import views

urlpatterns = [
    path("checkins/modal/", views.checkins_modal, name="checkins_modal"),
]
