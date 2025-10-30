from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from django.contrib.auth import get_user_model

from .forms import ProfileForm
from .models import SupabaseService

User = get_user_model()  # CustomUser from registration_app_collabsphere


@login_required(login_url='login')
def home(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        messages.error(request, "You must log in first.")
        return redirect("login")

    user = request.user
    user_data = SupabaseService.get_user_by_id(int(user_id))

    # Greeting
    now = timezone.localtime(timezone.now())
    hour = now.hour
    greeting = (
        "Good morning" if 5 <= hour < 12
        else "Good afternoon" if 12 <= hour < 18
        else "Good evening" if 18 <= hour < 24
        else "Hello"
    )

    # Check-ins and tasks
    has_checked_in_today = SupabaseService.get_today_checkins(user_id)
    tasks_data = SupabaseService.get_user_tasks(user_id, user.username)

    context = {
        "greeting": greeting,
        "user_name": user.username,
        "user_data": user_data,
        "has_checked_in_today": has_checked_in_today,
        "tasks": tasks_data["all_tasks"],
        "active_tasks": len(tasks_data["all_tasks"]),
        "created_tasks_count": len(tasks_data["created_tasks"]),
        "assigned_tasks_count": len(tasks_data["assigned_tasks"]),
    }

    response = render(request, "home.html", context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@require_GET
@login_required
def verify_checkin_status(request):
    user = request.user
    user_data = SupabaseService.get_user_by_email(user.email)
    if not user_data:
        return JsonResponse({"has_checked_in_today": False})

    has_checked_in_today = SupabaseService.verify_checkin_today(user_data["user_ID"])
    return JsonResponse({"has_checked_in_today": has_checked_in_today})


@require_GET
@login_required
def debug_checkins(request):
    user = request.user
    all_checkins = SupabaseService.get_all_checkins(user.id)
    return JsonResponse({
        "user_id": user.id,
        "total_checkins": len(all_checkins),
        "checkins": all_checkins,
        "today_date": timezone.now().date().isoformat(),
    })


def admin_dashboard(request):
    users = SupabaseService.get_all_users()
    return render(request, "admin_dashboard.html", {"users": users})


@login_required(login_url='login')
def profile_view(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        messages.error(request, "You must log in first.")
        return redirect("login")

    user_data = SupabaseService.get_user_by_id(user_id)
    form = ProfileForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            update_data, changed_fields = {}, []
            for field in ["username", "full_name", "email", "title"]:
                value = form.cleaned_data.get(field)
                if value and value != user_data.get(field):
                    update_data[field] = value
                    changed_fields.append(field)

            profile_pic = form.cleaned_data.get("profile_picture")
            if profile_pic:
                try:
                    public_url = SupabaseService.upload_profile_picture(user_id, profile_pic)
                    update_data["profile_picture"] = public_url
                    changed_fields.append("profile_picture")
                except Exception as e:
                    messages.error(request, f"Profile picture upload failed: {e}")
                    return render(request, "profile.html", {"form": form, "user_data": user_data})

            if not update_data:
                messages.info(request, "No changes were made.")
                return render(request, "profile.html", {"form": form, "user_data": user_data})

            try:
                SupabaseService.update_user_profile(user_id, update_data)
                readable = {
                    "username": "Username",
                    "full_name": "Full name",
                    "email": "Email",
                    "title": "Title",
                    "profile_picture": "Profile picture",
                }
                if len(changed_fields) == 1:
                    messages.success(request, f"{readable[changed_fields[0]]} updated successfully!")
                else:
                    names = [readable[f] for f in changed_fields]
                    msg = ", ".join(names[:-1]) + f", and {names[-1]} updated successfully!"
                    messages.success(request, msg)
            except Exception as e:
                messages.error(request, f"Update failed: {e}")
            return redirect("profile")
        else:
            messages.error(request, "Please fix the errors below before saving.")

    return render(request, "profile.html", {"form": form, "user_data": user_data})
