from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from datetime import datetime

from .models import Task, Comment, TaskPermissions


# TASKS VIEW (Modal
@login_required
def tasks(request):
    """
    Renders the Create Task modal (tasks.html)
    """
    team_members = Task.fetch_team_members()
    context = {
        "task_id": 1,
        "team_id": 101,
        "team_members": team_members,
    }
    return render(request, "tasks.html", context)


# CREATE TASK
@login_required
def task_create(request):
    """Handle POST to create a new task and redirect to home."""
    if request.method != "POST":
        return redirect("home")

    title = request.POST.get("taskName", "").strip()
    description = request.POST.get("description") or None
    assign_to_raw = request.POST.get("assignTo")

    try:
        assigned_to = int(assign_to_raw) if assign_to_raw else None
    except ValueError:
        assigned_to = None

    assigned_to_username = None
    if assigned_to:
        members = Task.fetch_team_members()
        match = next((m for m in members if m["id"] == assigned_to), None)
        if match:
            assigned_to_username = match["username"]

    payload = {
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "created_by": request.user.username,
        "date_created": datetime.now().isoformat(),
        "status": request.POST.get("status") or "Pending",
        "completion": int(request.POST.get("completion") or 0),
        "start_date": request.POST.get("startDate") or None,
        "due_date": request.POST.get("dueDate") or None,
        "priority": request.POST.get("priority") in ["on", "true", "True"],
        "team_id": None,
    }

    task_result = Task.create(payload)
    
    # Create notification if task was created and has an assignee
    if task_result and assigned_to:
        notification_data = {
            'title': title,
            'description': description,
            'assigned_to': assigned_to,
            'assigned_to_username': assigned_to_username,
            'created_by': request.user.username,
            'due_date': payload['due_date'],
            'task_id': task_result[0]['task_id'] if task_result and len(task_result) > 0 else None
        }
        
    from notifications_app_collabsphere.views import create_task_notification
    create_task_notification(notification_data, sender_user=request.user)
    
    return redirect("home")


# TASK DETAIL
@login_required
def task_detail(request, task_id):
    """Display a single task's details (read-only modal)."""
    username = request.user.username
    user_id = request.session.get("user_ID")

    task_data = Task.get(task_id)
    if not task_data:
        return redirect("home")

    if not TaskPermissions.user_can_access(task_data, username, user_id):
        return redirect("home")

    for key in ("date_created", "start_date", "due_date"):
        val = task_data.get(key)
        if val and isinstance(val, str) and "T" in val:
            task_data[key] = val.split("T")[0]

    context = {
        "task": task_data,
        "team_members": Task.fetch_team_members(),
        "comments": Task.fetch_comments(task_id),
    }
    return render(request, "task_detail.html", context)



# UPDATE TASK
@login_required
def task_update(request, task_id):
    """Handle POST to update a task."""
    if request.method != "POST":
        return redirect("home")

    task_data = Task.get(task_id)
    if not task_data or task_data.get("created_by") != request.user.username:
        return redirect("home")

    assign_to_raw = request.POST.get("assignTo")
    try:
        assigned_to = int(assign_to_raw) if assign_to_raw else None
    except ValueError:
        assigned_to = None

    assigned_to_username = None
    if assigned_to:
        members = Task.fetch_team_members()
        match = next((m for m in members if m["id"] == assigned_to), None)
        if match:
            assigned_to_username = match["username"]

    payload = {
        "title": request.POST.get("taskName", "").strip(),
        "description": request.POST.get("description") or None,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "status": request.POST.get("status") or "Pending",
        "completion": int(request.POST.get("completion") or 0),
        "start_date": request.POST.get("startDate") or None,
        "due_date": request.POST.get("dueDate") or None,
        "priority": request.POST.get("priority") in ["on", "true", "True"],
    }

    Task.update(task_id, payload)
    return redirect("home")


# DELETE TASK

@login_required
def task_delete(request, task_id):
    """Handle POST to delete a task."""
    task_data = Task.get(task_id)
    if not task_data or task_data.get("created_by") != request.user.username:
        return redirect("home")

    Task.delete(task_id)
    return redirect("home")


# ADD COMMENT
@login_required
def add_comment(request, task_id):
    """AJAX endpoint to add a comment to a task."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    content = request.POST.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "Content required"}, status=400)

    task_data = Task.get(task_id)
    if not task_data:
        return JsonResponse({"error": "Task not found"}, status=404)

    if not TaskPermissions.user_can_access(task_data, request.user.username, request.session.get("user_ID")):
        return JsonResponse({"error": "Forbidden"}, status=403)

    result = Comment.add(task_id, request.user.username, content)

    if "error" in result:
        return JsonResponse(result, status=500)

    return JsonResponse(result)


# DELETE COMMENT
@login_required
def delete_comment(request, comment_id):
    """AJAX endpoint to delete a comment. Only the comment owner may delete their comment."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    # Debug logging to help verify requests from the client
    try:
        print(f"delete_comment called for comment_id={comment_id} by user={request.user.username}")
    except Exception:
        print("delete_comment called (could not read user)")

    # Fetch the comment and verify ownership
    comment = Comment.get(comment_id)
    if not comment:
        return JsonResponse({"error": "Comment not found"}, status=404)

    if comment.get("username") != request.user.username:
        return JsonResponse({"error": "Forbidden"}, status=403)

    success = Comment.delete(comment_id)
    if not success:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"error": "Failed to delete comment"}, status=500)
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # If this is an AJAX request, return JSON so the client can update the UI without a reload.
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "comment_id": comment_id})

    # Otherwise (regular form POST), redirect back to the page that submitted the form.
    return redirect(request.META.get('HTTP_REFERER', '/'))
