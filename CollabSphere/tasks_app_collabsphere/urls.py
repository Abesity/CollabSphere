from django.urls import path
from . import views

urlpatterns = [
    path("", views.tasks, name="tasks"),  # Loads the task creation modal
    path("create/", views.task_create, name="task_create"),
    # Accept both /tasks/<id>/detail/ and /tasks/<id>/ to display the task detail modal
    path("<int:task_id>/detail/", views.task_detail, name="task_detail"),  # GET detail modal HTML
    path("<int:task_id>/", views.task_detail, name="task_detail_short"),
    path("<int:task_id>/update/", views.task_update, name="task_update"),  # POST to update
    path("<int:task_id>/delete/", views.task_delete, name="task_delete"),  # POST to delete
    path('<int:task_id>/comment/', views.add_comment, name='add_comment'),  #for adding comments
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
]