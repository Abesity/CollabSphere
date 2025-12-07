from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from datetime import datetime, date
import traceback

from django.contrib import messages

from .models import Task, Comment, TaskPermissions
from .notification_triggers import TaskNotificationTriggers
from notifications_app_collabsphere.views import (
    create_comment_notifications,
    create_comment_reply_notification,
    create_task_completion_notification,
    create_task_status_notification,
)

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
        "team_ID": active_team_id,
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

    # Validate dates are not in the past
    start_date = request.POST.get("startDate") or None
    due_date = request.POST.get("dueDate") or None
    today = date.today().isoformat()
    
    if start_date and start_date < today:
        messages.warning(request, "Tasks cannot be created for dates earlier than today.")
        return redirect("home")
    
    if due_date and due_date < today:
        messages.warning(request, "Tasks cannot be created for dates earlier than today.")
        return redirect("home")

    payload = {
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "created_by": request.user.username,
        "date_created": datetime.now().isoformat(),
        "status": request.POST.get("status") or "Pending",
        "completion": int(request.POST.get("completion") or 0),
        "start_date": start_date,
        "due_date": due_date,
        "priority": request.POST.get("priority") in ["on", "true", "True"],
        "team_ID": active_team_id,  # Set to active team ID
    }

    print(f"DEBUG: Creating task with payload: {payload}")
    task_result = Task.create(payload)
    print(f"DEBUG: Task creation result: {task_result}")
    
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
            'team_ID': active_team_id
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
            'team_ID': active_team_id
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
                print(f" TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        except Exception as e:
            print(f" Error evaluating task triggers: {e}")
    
    return redirect("home")
@login_required
def task_detail(request, task_id):
    """Display a single task's details (read-only modal)."""
    username = request.user.username
    user_id = request.session.get("user_ID")

    task_data = Task.get(task_id)
    if not task_data:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Task not found'}, status=404)
        return redirect("home")

    if not TaskPermissions.user_can_access(task_data, username, user_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Not authorized to view this task'}, status=403)
        return redirect("home")

    for key in ("date_created", "start_date", "due_date"):
        val = task_data.get(key)
        if val and isinstance(val, str) and "T" in val:
            task_data[key] = val.split("T")[0]

    # Get active team info
    active_team_id = Task.get_user_active_team_id(request.user)
    team_name = Task.get_team_name(active_team_id) if active_team_id else None
    
    # Get members from the task's team or active team
    task_team_id = task_data.get('team_ID')  # Note: uppercase ID from database
    if task_team_id:
        # Get members from the specific task's team
        team_members = Task.get_team_members(task_team_id)
        # Use the task's team name if available
        team_name = Task.get_team_name(task_team_id) or team_name
    else:
        # Fallback to active team members
        team_members = Task.get_active_team_members(request.user)

    context = {
        "task": task_data,
        "team_members": team_members,
        "comments": Task.fetch_comments(task_id),
        "team_id": active_team_id,  # Add this
        "team_name": team_name,     # Add this
        "has_active_team": active_team_id is not None  # Add this
    }
    
    # Return modal-only markup for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, "task_detail_edit.html", context)
    
    return render(request, "task_detail_edit.html", context)

# UPDATE TASK
@login_required
def task_update(request, task_id):
    """Handle POST to update a task."""
    if request.method != "POST":
        return redirect("home")

    task_data = Task.get(task_id)
    if not task_data:
        return redirect("home")

    session_user_id = request.session.get("user_ID")
    existing_assignee_id = task_data.get('assigned_to')
    existing_assignee_username = task_data.get('assigned_to_username')
    is_creator = task_data.get("created_by") == request.user.username
    is_assigned_user = (
        (existing_assignee_id and session_user_id == existing_assignee_id)
        or (existing_assignee_username and existing_assignee_username == request.user.username)
    )

    if not (is_creator or is_assigned_user):
        return redirect("home")

    # Store old values for comparison
    old_status = task_data.get("status")
    old_title = task_data.get("title")
    old_description = task_data.get("description")
    old_due_date = task_data.get("due_date")
    old_priority = task_data.get("priority")
    old_assigned_to = task_data.get("assigned_to")
    old_completion = task_data.get("completion")

    assigned_to_username = existing_assignee_username
    if is_creator:
        assign_to_raw = request.POST.get("assignTo")
        try:
            assigned_to = int(assign_to_raw) if assign_to_raw else None
        except ValueError:
            assigned_to = None

        if assigned_to:
            task_team_id = task_data.get('team_ID')
            if task_team_id:
                members = Task.get_team_members(task_team_id)
            else:
                members = Task.get_active_team_members(request.user)
                
            match = next((m for m in members if m["id"] == assigned_to), None)
            if match:
                assigned_to_username = match["username"]
            else:
                assigned_to = None
                assigned_to_username = None

        if assigned_to:
            members = Task.fetch_team_members()
            match = next((m for m in members if m["id"] == assigned_to), None)
            if match:
                assigned_to_username = match["username"]
    else:
        assigned_to = existing_assignee_id

    requested_status = request.POST.get("status")
    allowed_statuses = {"Pending", "In Progress", "Completed"}
    new_status = requested_status if requested_status in allowed_statuses else (old_status or "Pending")

    if not is_creator:
        allowed_assignee_statuses = {"In Progress", "Completed"}
        if new_status not in allowed_assignee_statuses:
            new_status = old_status

    completion_raw = request.POST.get("completion")
    try:
        posted_completion = int(completion_raw) if completion_raw is not None else None
    except ValueError:
        posted_completion = None

    if is_creator:
        new_title = request.POST.get("taskName", "").strip()
        new_description = request.POST.get("description") or None
        new_due_date = request.POST.get("dueDate") or None
        new_priority = request.POST.get("priority") in ["on", "true", "True"]
        start_date_value = request.POST.get("startDate") or None
    else:
        new_title = old_title
        new_description = old_description
        new_due_date = task_data.get("due_date")
        new_priority = old_priority
        start_date_value = task_data.get("start_date")

    if posted_completion is not None:
        new_completion = posted_completion
    else:
        new_completion = old_completion or 0

    today = date.today().isoformat()

    assignee_for_revert_check = existing_assignee_id or assigned_to
    if assignee_for_revert_check and old_status and old_status != 'Pending' and new_status == 'Pending':
        message = "Assigned tasks cannot revert to Pending after work has started."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "message": message}, status=400)
        messages.warning(request, message)
        return redirect("home")
    
    if new_due_date and new_due_date < today:
        message = "Due date cannot be before today."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "message": message}, status=400)
        messages.warning(request, message)
        return redirect("home")

    status_changed = old_status != new_status
    payload = {
        "title": new_title,
        "description": new_description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "status": new_status,
        "completion": new_completion,
        "start_date": start_date_value,
        "due_date": new_due_date,
        "priority": new_priority,
    }

    Task.update(task_id, payload)

    current_assignee = assigned_to if assigned_to is not None else existing_assignee_id
    actor_is_assignee = False
    if current_assignee and session_user_id == current_assignee:
        actor_is_assignee = True
    elif request.user.username in {
        task_data.get('assigned_to_username'),
        assigned_to_username,
    }:
        actor_is_assignee = True

    completion_changed = (old_completion or 0) != new_completion
    if completion_changed and actor_is_assignee and not is_creator:
        try:
            completion_notification_payload = {
                'task_id': task_id,
                'title': new_title or task_data.get('title'),
                'created_by': task_data.get('created_by'),
                'completion': new_completion,
            }
            create_task_completion_notification(
                completion_notification_payload,
                sender_user=request.user,
                completion_value=new_completion,
            )
        except Exception as notify_error:
            print(f" Error creating completion notification: {notify_error}")

    if status_changed and new_status in {'In Progress', 'Completed'} and actor_is_assignee:
        try:
            status_notification_payload = {
                'task_id': task_id,
                'title': new_title or task_data.get('title'),
                'created_by': task_data.get('created_by'),
                'status': new_status,
            }
            create_task_status_notification(
                status_notification_payload,
                sender_user=request.user,
                new_status=new_status,
            )
        except Exception as notify_error:
            print(f" Error creating status notification: {notify_error}")

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
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({"success": True, "message": "Task saved successfully."})

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
@login_required
@require_http_methods(["POST"])
def add_comment(request, task_id):
    """AJAX endpoint to add a comment or reply to a task."""
    try:
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        print(f" add_comment called for task_id={task_id}")
        print(f" Request method: {request.method}")
        print(f" Is AJAX: {is_ajax}")
        
        content = request.POST.get("content", "").strip()
        parent_id = request.POST.get("parent_id")
        
        print(f" Content: {content[:50] if content else 'None'}")
        print(f" Parent ID: {parent_id}")
        
        if not content:
            print(" No content provided")
            error = {"success": False, "error": "Content required"}
            if is_ajax:
                return JsonResponse(error, status=400)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        # Convert parent_id to int if provided
        try:
            parent_id = int(parent_id) if parent_id else None
            print(f" Converted parent_id: {parent_id}")
        except (ValueError, TypeError):
            parent_id = None
            print(f" Could not convert parent_id, setting to None")

        task_data = Task.get(task_id)
        if not task_data:
            print(f" Task not found: {task_id}")
            error = {"success": False, "error": "Task not found"}
            if is_ajax:
                return JsonResponse(error, status=404)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        if not TaskPermissions.user_can_access(task_data, request.user.username, request.session.get("user_ID")):
            print(f" User not authorized")
            error = {"success": False, "error": "Forbidden"}
            if is_ajax:
                return JsonResponse(error, status=403)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        print(f" Adding comment to database...")
        result = Comment.add(task_id, request.user.username, content, parent_id)

        if "error" in result:
            print(f" Database error: {result['error']}")
            error = {"success": False, "error": result["error"]}
            if is_ajax:
                return JsonResponse(error, status=500)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        print(f" Comment added successfully: {result}")

        parent_comment = Comment.get(parent_id) if parent_id else None
        comment_task_data = {
            'task_id': task_id,
            'title': task_data.get('title', 'Task')
        }

        reply_notification_recipient = None
        if parent_comment:
            try:
                reply_notification_recipient = create_comment_reply_notification(
                    comment_task_data,
                    parent_comment,
                    sender_user=request.user,
                    comment_content=content
                )
            except Exception as reply_error:
                print(f" Error creating reply notification: {reply_error}")

        # Create notifications for relevant users
        try:
            recipients = []

            assigned_to = task_data.get('assigned_to')
            assigned_to_username = task_data.get('assigned_to_username')
            if assigned_to or assigned_to_username:
                recipients.append({
                    'user_ID': assigned_to,
                    'username': assigned_to_username
                })

            creator_username = task_data.get('created_by')
            if creator_username:
                recipients.append(creator_username)

            commenter_usernames = Comment.get_commenter_usernames(task_id)
            commenter_usernames.discard(request.user.username)
            for username in commenter_usernames:
                recipients.append(username)

            excluded_ids = {reply_notification_recipient.id} if reply_notification_recipient else None

            create_comment_notifications(
                comment_task_data,
                recipients,
                sender_user=request.user,
                comment_content=content,
                exclude_recipient_ids=excluded_ids
            )
        except Exception as notify_error:
            print(f" Error creating comment notifications: {notify_error}")

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
                print(f" TRIGGERED: {trigger['trigger_type']} - {trigger['message']}")
        except Exception as e:
            print(f" Error evaluating comment triggers: {e}")

        success_payload = {
            "success": True,
            "username": result.get("username"),
            "content": result.get("content"),
            "created_at": result.get("created_at"),
            "comment_id": result.get("comment_id"),
            "parent_id": result.get("parent_id")
        }

        if is_ajax:
            return JsonResponse(success_payload)

        messages.success(request, "Comment posted successfully!")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    except Exception as e:
        print(f" EXCEPTION in add_comment: {str(e)}")
        print(f" Traceback: {traceback.format_exc()}")
        error = {"success": False, "error": f"Server error: {str(e)}"}
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(error, status=500)
        messages.error(request, error["error"])
        return redirect(request.META.get('HTTP_REFERER', '/'))


# DELETE COMMENT
@login_required
@require_http_methods(["POST"])
def delete_comment(request, comment_id):
    """Handle comment deletion via AJAX or standard form submission."""
    try:
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        comment = Comment.get(comment_id)
        if not comment:
            error = {"success": False, "error": "Comment not found"}
            if is_ajax:
                return JsonResponse(error, status=404)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        if comment.get("username") != request.user.username:
            error = {"success": False, "error": "Forbidden"}
            if is_ajax:
                return JsonResponse(error, status=403)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        success = Comment.delete(comment_id)
        if not success:
            error = {"success": False, "error": "Failed to delete comment"}
            if is_ajax:
                return JsonResponse(error, status=500)
            messages.error(request, error["error"])
            return redirect(request.META.get('HTTP_REFERER', '/'))

        if is_ajax:
            return JsonResponse({"success": True, "comment_id": comment_id})

        messages.success(request, "Comment deleted successfully.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    except Exception as e:
        print(f" EXCEPTION in delete_comment: {str(e)}")
        print(f" Traceback: {traceback.format_exc()}")
        error = {"success": False, "error": str(e)}
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(error, status=500)
        messages.error(request, error["error"])
        return redirect(request.META.get('HTTP_REFERER', '/'))