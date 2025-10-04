from django.urls import path
from . import views

urlpatterns = [
    path("", views.tasks, name="tasks"),              # View all tasks
    # path("add/", views.task_add, name="task_add"),            # Add new task
    # path("<int:task_id>/edit/", views.task_edit, name="task_edit"),  # Edit task
    # path("<int:task_id>/delete/", views.task_delete, name="task_delete"),  # Delete task
]
