from django.shortcuts import render, redirect
from django.conf import settings
from supabase import create_client, Client
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_GET

SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Teams yet to be implemented, so team_id is always None
def fetch_team_members():
    """Return list of dicts: {id, username} from public.user"""
    try:
        resp = supabase.table("user").select("user_ID, username").execute()
        members = getattr(resp, "data", resp) or []
        return [{"id": m["user_ID"], "username": m["username"]} for m in members]
    except Exception as e:
        print("Error fetching team members:", e)
        return []

# Teams yet to be implemented, so team_id is always None
def tasks(request):
    """
    Renders the Create Task modal (tasks.html)
    This is the same view your openTaskModal fetch() calls.
    """
    team_members = fetch_team_members()
    context = {
        "task_id": 1,
        "team_id": 101,
        "team_members": team_members,
    }
    return render(request, "tasks.html", context)

# Teams yet to be implemented, so team_id is always None
def task_create(request):
    """Handle POST to create a new task in Supabase and redirect to home."""
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
        try:
            r = supabase.table("user").select("username").eq("user_ID", assigned_to).execute()
            if getattr(r, "data", None):
                assigned_to_username = r.data[0].get("username")
        except Exception:
            assigned_to_username = None

    priority = True if request.POST.get("priority") in ["on", "true", "True"] else False
    created_by = request.POST.get("createdBy") or (request.user.username if request.user.is_authenticated else None)
    date_created = request.POST.get("dateCreated") or None
    status = request.POST.get("status") or "Pending"
    completion_raw = request.POST.get("completion") or 0
    try:
        completion = int(completion_raw)
    except ValueError:
        completion = 0
    start_date = request.POST.get("startDate") or None
    due_date = request.POST.get("dueDate") or None

    payload = {
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "created_by": created_by,
        "date_created": date_created,
        "status": status,
        "completion": completion,
        "start_date": start_date,
        "due_date": due_date,
        "priority": priority,
        "team_id": None,
    }

    try:
        res = supabase.table("tasks").insert(payload).execute()
        print("Inserted task:", getattr(res, "data", res))

        count_res = (
            supabase.table("tasks")
            .select("task_id", count="exact")
            .eq("created_by", created_by)
            .execute()
        )
        active_count = count_res.count if hasattr(count_res, "count") else len(count_res.data)

    except Exception as e:
        print("Error inserting task into Supabase:", e)

    return redirect("home")

# Teams yet to be implemented, so team_id is always None
def task_detail(request, task_id):
    """
    Return the Task Details modal HTML (rendered template), prefilled with task data.
    This view is fetched (via fetch) by clicking a task item on the dashboard.
    """
    # fetch task
    # Security: only allow access to the user's own task
    if not request.user.is_authenticated:
        return redirect("login")

    username = request.user.username

    # Check if task belongs to this user
    task_check = supabase.table("tasks").select("created_by").eq("task_id", task_id).execute()
    if not task_check.data or task_check.data[0].get("created_by") != username:
        return redirect("home")  # or return 403
    try:
        resp = supabase.table("tasks").select("*").eq("task_id", task_id).execute()
        rows = getattr(resp, "data", resp) or []
        if not rows:
            return render(request, "task_detail.html", {"task": None, "team_members": fetch_team_members()})
        task = rows[0]
    except Exception as e:
        print("Error fetching task:", e)
        task = None

    if task:
        for key in ("date_created", "start_date", "due_date"):
            val = task.get(key)
            if val and isinstance(val, str) and "T" in val:
                task[key] = val.split("T")[0]

    team_members = fetch_team_members()
    context = {"task": task, "team_members": team_members}
    return render(request, "task_detail.html", context)

# Teams yet to be implemented, so team_id is always None
def task_update(request, task_id):
    """Handle POST to update task in Supabase then redirect to home."""
    if not request.user.is_authenticated:
        return redirect("login")

    username = request.user.username

    # Check if task belongs to this user
    task_check = supabase.table("tasks").select("created_by").eq("task_id", task_id).execute()
    if not task_check.data or task_check.data[0].get("created_by") != username:
        return redirect("home")  # or return 403

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
        try:
            r = supabase.table("user").select("username").eq("user_ID", assigned_to).execute()
            if getattr(r, "data", None):
                assigned_to_username = r.data[0].get("username")
        except Exception:
            assigned_to_username = None

    priority = True if request.POST.get("priority") in ["on", "true", "True"] else False
    created_by = request.POST.get("createdBy") or (request.user.username if request.user.is_authenticated else None)
    date_created = request.POST.get("dateCreated") or None
    status = request.POST.get("status") or "Pending"
    completion_raw = request.POST.get("completion") or 0
    try:
        completion = int(completion_raw)
    except ValueError:
        completion = 0
    start_date = request.POST.get("startDate") or None
    due_date = request.POST.get("dueDate") or None

    payload = {
        "title": title,
        "description": description,
        "assigned_to": assigned_to,
        "assigned_to_username": assigned_to_username,
        "created_by": created_by,
        "date_created": date_created,
        "status": status,
        "completion": completion,
        "start_date": start_date,
        "due_date": due_date,
        "priority": priority,
    }
    
    try:
        res = supabase.table("tasks").update(payload).eq("task_id", task_id).execute()
        print("Updated task:", getattr(res, "data", res))
    except Exception as e:
        print("Error updating task:", e)

    return redirect("home")

# Teams yet to be implemented, so team_id is always None
def task_delete(request, task_id):
    """Handle POST to delete a task then redirect to home."""
    if not request.user.is_authenticated:
        return redirect("login")

    username = request.user.username

    # Check if task belongs to this user
    task_check = supabase.table("tasks").select("created_by").eq("task_id", task_id).execute()
    if not task_check.data or task_check.data[0].get("created_by") != username:
        return redirect("home")  # or return 403
    if request.method != "POST":
        return redirect("home")

    try:
        res = supabase.table("tasks").delete().eq("task_id", task_id).execute()
        print("Deleted task:", getattr(res, "data", res))

        count_res = (
            supabase.table("tasks")
            .select("task_id", count="exact")
            .eq("created_by", username)
            .execute()
        )
        active_count = count_res.count if hasattr(count_res, "count") else len(count_res.data)

    except Exception as e:
        print("Error deleting task:", e)

    return redirect("home")