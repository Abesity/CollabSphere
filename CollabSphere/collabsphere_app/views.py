from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from supabase import create_client
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.contrib import messages
from .forms import ProfileForm


supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

@login_required(login_url='login')
def home(request):
        user_id = request.session.get("user_ID")
        if not user_id:
            messages.error(request, "You must log in first.")
            return redirect("login")

        user = request.user

        # Fetch latest user data from Supabase
        try:
            response = supabase.table("user").select("*").eq("user_ID", int(user_id)).execute()
            user_data = response.data[0] if response.data else {}
        except Exception as e:
            messages.error(request, f"Error fetching user data: {e}")
            user_data = {}

        # Determine greeting based on current hour
        now = timezone.localtime(timezone.now())
        current_hour = now.hour
        if 5 <= current_hour < 12:
            greeting = "Good morning"
        elif 12 <= current_hour < 18:
            greeting = "Good afternoon"
        elif 18 <= current_hour < 24:
            greeting = "Good evening"
        else:
            greeting = "Hello"

        # Today's date
        today_date = now.date()

        # Check-in logic
        try:
            response = (
                supabase.table("wellbeingcheckin")
                .select("checkin_id, date_submitted, user_id")
                .eq("user_id", int(user_id))
                .execute()
            )
            # Filter for today's date
            today_checkins = [c for c in response.data if c.get('date_submitted', '').startswith(today_date.isoformat())]
            has_checked_in_today = len(today_checkins) > 0
        except Exception as e:
            print(f"Error fetching check-ins: {e}")
            has_checked_in_today = False

        # Fetch user tasks
        try:
            tasks_response = (
                supabase.table("tasks")
                .select("*")
                .eq("created_by", user.username)
                .order("date_created", desc=True)
                .execute()
            )
            user_tasks = tasks_response.data or []
        except Exception as e:
            print(f"Error fetching tasks: {e}")
            user_tasks = []

        active_tasks_count = len(user_tasks)

        context = {
            "greeting": greeting,
            "user_name": user.username,
            "user_data": user_data,  # Pass Supabase data for navbar/profile
            "has_checked_in_today": has_checked_in_today,
            "tasks": user_tasks,
            "active_tasks": active_tasks_count,
        }

        # Render page and prevent caching
        response = render(request, "home.html", context)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@require_GET
@login_required
def verify_checkin_status(request):
    user = request.user
    today = timezone.now().date()

    try:
        # Example logic using Supabase or any ORM:
        res = supabase.table("user").select("user_ID").eq("email", user.email).single().execute()
        user_id = res.data["user_ID"]

        existing = (
            supabase.table("wellbeingcheckin")
            .select("date_submitted")
            .eq("user_id", user_id)
            .gte("date_submitted", today.isoformat())
            .execute()
        )

        has_checked_in_today = len(existing.data) > 0
        return JsonResponse({"has_checked_in_today": has_checked_in_today})
    except Exception as e:
        print("Error verifying check-in:", e)
        return JsonResponse({"has_checked_in_today": False})
    
@require_GET
@login_required
def debug_checkins(request):
    """Debug endpoint to see all check-ins for the user"""
    user = request.user
    
    # Get ALL check-ins for this user to see what exists
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("*")
        .eq("user_id", user.id)
        .order("date_submitted", desc=True)
        .execute()
    )
    
    debug_info = {
        'user_id': user.id,
        'total_checkins': len(response.data),
        'checkins': response.data,
        'today_date': timezone.now().date().isoformat()
    }
    
    return JsonResponse(debug_info)


def admin_dashboard(request):
    response = supabase.table("users").select("*").execute()
    users = response.data

    return render(request, "admin_dashboard.html", {"users": users})

@login_required(login_url='login')
def profile_view(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        messages.error(request, "You must log in first.")
        return redirect("login")

    try:
        response = supabase.table("user").select("*").eq("user_ID", user_id).execute()
        user_data = response.data[0] if response.data else {}
    except Exception as e:
        messages.error(request, f"Error fetching user data: {e}")
        return redirect("home")

    form = ProfileForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():  # ✅ Only update if form passes validation
            update_data = {}
            changed_fields = []

            # Only update fields that changed
            for field in ["username", "full_name", "email", "title"]:
                value = form.cleaned_data.get(field)
                if value and value != user_data.get(field):
                    update_data[field] = value
                    changed_fields.append(field)

            # Handle profile picture
            profile_pic = form.cleaned_data.get("profile_picture")
            if profile_pic:
                file_path = f"profile_pictures/{user_id}_{profile_pic.name}"
                file_bytes = profile_pic.read()
                bucket = supabase.storage.from_("profile_pictures")
                try:
                    try:
                        bucket.upload(file_path, file_bytes)
                    except Exception:
                        bucket.update(file_path, file_bytes)
                    public_url = bucket.get_public_url(file_path)
                    if public_url:
                        update_data["profile_picture"] = public_url
                        changed_fields.append("profile_picture")
                except Exception as e:
                    messages.error(request, f"Profile picture upload failed: {e}")
                    return render(request, "profile.html", {"form": form, "user_data": user_data})

            if not update_data:
                messages.info(request, "No changes were made.")
                return render(request, "profile.html", {"form": form, "user_data": user_data})

            # Save updates to Supabase
            try:
                supabase.table("user").update(update_data).eq("user_ID", int(user_id)).execute()
                # Custom success messages per field
                readable = {"username":"Username", "full_name":"Full name", "email":"Email", "title":"Title", "profile_picture":"Profile picture"}
                if len(changed_fields) == 1:
                    messages.success(request, f"{readable[changed_fields[0]]} updated successfully!")
                elif len(changed_fields) == 2:
                    a, b = [readable[f] for f in changed_fields]
                    messages.success(request, f"{a} and {b} updated successfully!")
                else:
                    names = [readable[f] for f in changed_fields]
                    msg = ", ".join(names[:-1]) + f", and {names[-1]} updated successfully!"
                    messages.success(request, msg)
            except Exception as e:
                messages.error(request, f"Update failed: {e}")

            return redirect("profile")

        else:
            # Form invalid → show errors in template/SweetAlert
            messages.error(request, "Please fix the errors below before saving.")

    return render(request, "profile.html", {"form": form, "user_data": user_data})