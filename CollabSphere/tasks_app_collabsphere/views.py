from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from datetime import datetime
import traceback

from .models import Task, Comment, TaskPermissions
from .notification_triggers import TaskNotificationTriggers


# TASKS VIEW (Modal)
@login_required
def tasks(request):
    """
    Renders the Create Task modal (tasks.html)
    """
    from teams_app_collabsphere.models import Team
    
    # Ensure user has an active team initialized
    Team.initialize_active_team(request.user)
    
    # Get active team info
    active_team_id = Task.get_user_active_team_id(request.user)
    team_members = Task.get_active_team_members(request.user)
    
    # Get team name if there's an active team
    team_name = None
    if active_team_id:
        team_name = Task.get_team_name(active_team_id)
    
    # Debug output
    print(f"DEBUG: Active team ID: {active_team_id}")
    print(f"DEBUG: Team name: {team_name}")
    print(f"DEBUG: Team members count: {len(team_members)}")
    
    context = {
        "task_id": 1,
        "team_id": active_team_id,
        "team_name": team_name,  # Add team name to context
        "team_members": team_members,
        "has_active_team": active_team_id is not None
    }
    return render(request, "tasks.html", context)

@login_required
def task_create(request):
    """Handle POST to create a new task and redirect to home."""
    if request.method != "POST":
        return redirect("home")

    # Get active team info first
    active_team_id = Task.get_user_active_team_id(request.user)
    team_members = Task.get_active_team_members(request.user)
    
    # Debug
    print(f"DEBUG task_create: Active team ID: {active_team_id}")
    
    title = request.POST.get("taskName", "").strip()
    description = request.POST.get("description") or None
    assign_to_raw = request.POST.get("assignTo")

    try:
        assigned_to = int(assign_to_raw) if assign_to_raw else None
    except ValueError:
        assigned_to = None

    # Verify assigned user is in active team
    assigned_to_username = None
    if assigned_to:
        members = Task.get_active_team_members(request.user)
        match = next((m for m in members if m["id"] == assigned_to), None)
        if match:
            assigned_to_username = match["username"]
        else:
            # Security: If user tries to assign to someone not in team, clear assignment
            assigned_to = None
            assigned_to_username = None

    # Get active team ID for the task
    active_team_id = Task.get_user_active_team_id(request.user)

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
        "team_id": active_team_id,  # Set to active team ID
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
            'task_id': task_result[0]['task_id'] if task_result and len(task_result) > 0 else None,
            'team_id': active_team_id
        }
        
        try:
            from notifications_app_collabsphere.views import create_task_notification
            create_task_notification(notification_data, sender_user=request.user)
        except:
            pass
    
    # Evaluate notification triggers for task creation
    if task_result and len(task_result) > 0:
        task_data = {
            'task_id': task_result[0]['task_id'],
            'title': title,
            'assigned_to': assigned_to,
            'due_date': payload['due_date'],
            'status': payload['status'],
            'priority': payload['priority'],
            'team_id': active_team_id
        }
        
        trigger_context = {
            'action': 'create'
        }
        
        try:
            triggered_notifications = TaskNotificationTriggers.evaluate_all_triggers(
                task_data,
                trigger_context
            )
            
            for trigger in triggered_notifications:
                print(f"🔔 TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        except Exception as e:
            print(f"⚠️ Error evaluating task triggers: {e}")
    
    return redirect("home")

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

    # Get members from the task's team or active team
    task_team_id = task_data.get('team_id')
    if task_team_id:
        # Get members from the specific task's team
        team_members = Task.get_team_members(task_team_id)
    else:
        # Fallback to active team members
        team_members = Task.get_active_team_members(request.user)

    context = {
        "task": task_data,
        "team_members": team_members,
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

    # Store old values for comparison
    old_status = task_data.get("status")
    old_title = task_data.get("title")
    old_description = task_data.get("description")
    old_due_date = task_data.get("due_date")
    old_priority = task_data.get("priority")
    old_assigned_to = task_data.get("assigned_to")

    assign_to_raw = request.POST.get("assignTo")
    try:
        assigned_to = int(assign_to_raw) if assign_to_raw else None
    except ValueError:
        assigned_to = None

    # Verify assigned user is in the task's team or active team
    assigned_to_username = None
    if assigned_to:
        task_team_id = task_data.get('team_id')
        if task_team_id:
            members = Task.get_team_members(task_team_id)
        else:
            members = Task.get_active_team_members(request.user)
            
        match = next((m for m in members if m["id"] == assigned_to), None)
        if match:
            assigned_to_username = match["username"]
        else:
            # Security: Clear assignment if user not in team
            assigned_to = None
            assigned_to_username = None
    
    if assigned_to:
        members = Task.fetch_team_members()
        match = next((m for m in members if m["id"] == assigned_to), None)
        if match:
            assigned_to_username = match["username"]

    new_status = request.POST.get("status") or "Pending"
    new_title = request.POST.get("taskName", "").strip()
    new_description = request.POST.get("description") or None
    new_due_date = request.POST.get("dueDate") or None
    new_priority = request.POST.get("priority") in ["on", "true", "True"]

    payload = {
        "title": new_title,
        "description": new_description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "status": new_status,
        "completion": int(request.POST.get("completion") or 0),
        "start_date": request.POST.get("startDate") or None,
        "due_date": new_due_date,
        "priority": new_priority,
    }

    Task.update(task_id, payload)
    
    # Evaluate notification triggers for task update
    try:
        changed_fields = []
        if old_title != new_title:
            changed_fields.append('title')
        if old_description != new_description:
            changed_fields.append('description')
        if old_due_date != new_due_date:
            changed_fields.append('due_date')
        if old_priority != new_priority:
            changed_fields.append('priority')
        if old_assigned_to != assigned_to:
            changed_fields.append('assigned_to')
        if old_status != new_status:
            changed_fields.append('status')
        
        updated_task_data = {
            'task_id': task_id,
            'title': new_title,
            'assigned_to': assigned_to,
            'due_date': new_due_date,
            'status': new_status,
            'priority': new_priority
        }
        
        action = 'complete' if old_status != 'completed' and new_status == 'completed' else 'update'
        
        trigger_context = {
            'action': action,
            'old_status': old_status,
            'changed_fields': changed_fields
        }
        
        triggered_notifications = TaskNotificationTriggers.evaluate_all_triggers(
            updated_task_data,
            trigger_context
        )
        
        for trigger in triggered_notifications:
            print(f"🔔 TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
    except Exception as e:
        print(f"⚠️ Error evaluating task triggers: {e}")
    
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


# ADD COMMENT OR REPLY
@login_required
@require_http_methods(["POST"])
def add_comment(request, task_id):
    """AJAX endpoint to add a comment or reply to a task."""
    try:
        print(f"🔵 add_comment called for task_id={task_id}")
        print(f"🔵 Request method: {request.method}")
        print(f"🔵 Is AJAX: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
        
        content = request.POST.get("content", "").strip()
        parent_id = request.POST.get("parent_id")
        
        print(f"🔵 Content: {content[:50] if content else 'None'}")
        print(f"🔵 Parent ID: {parent_id}")
        
        if not content:
            print("❌ No content provided")
            return JsonResponse({"success": False, "error": "Content required"}, status=400)

        # Convert parent_id to int if provided
        try:
            parent_id = int(parent_id) if parent_id else None
            print(f"🔵 Converted parent_id: {parent_id}")
        except (ValueError, TypeError):
            parent_id = None
            print(f"⚠️ Could not convert parent_id, setting to None")

        task_data = Task.get(task_id)
        if not task_data:
            print(f"❌ Task not found: {task_id}")
            return JsonResponse({"success": False, "error": "Task not found"}, status=404)

        if not TaskPermissions.user_can_access(task_data, request.user.username, request.session.get("user_ID")):
            print(f"❌ User not authorized")
            return JsonResponse({"success": False, "error": "Forbidden"}, status=403)

        print(f"🔵 Adding comment to database...")
        result = Comment.add(task_id, request.user.username, content, parent_id)

        if "error" in result:
            print(f"❌ Database error: {result['error']}")
            return JsonResponse({"success": False, "error": result["error"]}, status=500)
        
        print(f"✅ Comment added successfully: {result}")
        
        # Evaluate notification triggers for comment
        try:
            comment_author_id = request.session.get("user_ID")
            
            trigger_context = {
                'action': 'comment',
                'comment_author_id': comment_author_id
            }
            
            comment_task_data = {
                'task_id': task_id,
                'title': task_data.get('title', 'Task')
            }
            
            triggered_notifications = TaskNotificationTriggers.evaluate_all_triggers(
                comment_task_data,
                trigger_context
            )
            
            for trigger in triggered_notifications:
                print(f"🔔 TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        except Exception as e:
            print(f"⚠️ Error evaluating comment triggers: {e}")

        return JsonResponse({
            "success": True,
            "username": result.get("username"),
            "content": result.get("content"),
            "created_at": result.get("created_at"),
            "comment_id": result.get("comment_id"),
            "parent_id": result.get("parent_id")
        })
        
    except Exception as e:
        print(f"❌ EXCEPTION in add_comment: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"}, status=500)


# DELETE COMMENT
@login_required
@require_http_methods(["POST"])
def delete_comment(request, comment_id):
    """AJAX endpoint to delete a comment. Only the comment owner may delete their comment."""
    try:
        print(f"delete_comment called for comment_id={comment_id} by user={request.user.username}")
        
        comment = Comment.get(comment_id)
        if not comment:
            return JsonResponse({"success": False, "error": "Comment not found"}, status=404)

        if comment.get("username") != request.user.username:
            return JsonResponse({"success": False, "error": "Forbidden"}, status=403)

        success = Comment.delete(comment_id)
        if not success:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": False, "error": "Failed to delete comment"}, status=500)
            return redirect(request.META.get('HTTP_REFERER', '/'))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"success": True, "comment_id": comment_id})

        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Exception as e:
        print(f"❌ EXCEPTION in delete_comment: {str(e)}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)