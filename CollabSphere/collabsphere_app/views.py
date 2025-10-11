from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from supabase import create_client
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.contrib import messages

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

@login_required(login_url='login')
def home(request):
    user = request.user
    now = timezone.localtime(timezone.now())  
    current_hour = now.hour 

    # Determine greeting 
    if 5 <= current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 18:
        greeting = "Good afternoon"
    elif 18 <= current_hour < 24:
        greeting = "Good evening"
    else:
        greeting = "Hello"

    # Get today's date in the correct timezone
    today_date = timezone.localtime(timezone.now()).date()
    
    print(f"DEBUG - User: {user.id}, Today's date: {today_date}")
    
    # Query for check-ins - use date comparison only
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("checkin_id, date_submitted, user_id")
        .eq("user_id", user.id)
        .eq("date_submitted", today_date.isoformat())
        .execute()
    )
    
    # Debug logging
    print(f"Check-ins found: {len(response.data)}")
    for checkin in response.data:
        print(f"Check-in: ID={checkin.get('checkin_id')}, Date={checkin.get('date_submitted')}")
    
    # Alternative: Try a more flexible date comparison
    if len(response.data) == 0:
        print("Trying alternative date comparison...")
        # Sometimes the date might be stored differently, try a contains approach
        all_response = (
            supabase
            .table("wellbeingcheckin")
            .select("checkin_id, date_submitted, user_id")
            .eq("user_id", user.id)
            .execute()
        )
        
        today_str = today_date.isoformat()
        today_checkins = [c for c in all_response.data if c.get('date_submitted', '').startswith(today_str)]
        print(f"Alternative check found: {len(today_checkins)}")
        
        has_checked_in_today = len(today_checkins) > 0
    else:
        has_checked_in_today = len(response.data) > 0

    # Teams yet to be implemented, so team_id is always None
    # Fetch tasks belonging to the logged-in user
    try:
        tasks_response = (
            supabase
            .table("tasks")
            .select("*")
            .eq("created_by", user.username)
            .order("date_created", desc=True)
            .execute()
        )
        user_tasks = tasks_response.data or [] 
        print(f"Tasks fetched for {user.username}: {len(user_tasks)}") 
    except Exception as e: 
        print(f"Error fetching tasks: {e}") 
        user_tasks = []
    
    # Count active tasks
    active_tasks_count = len(user_tasks)

    # Teams yet to be implemented, so team_id is always None
    context = {
        "greeting": greeting,
        "user_name": user.username,
        "has_checked_in_today": has_checked_in_today,
        "tasks": user_tasks,
        "active_tasks": active_tasks_count,
    }

    response = render(request, "home.html", context)
    # Add headers to prevent caching
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
    


@require_GET
@login_required
def verify_checkin_status(request):
    """API endpoint to verify if user has checked in today"""
    user = request.user
    today_date = timezone.localtime(timezone.now()).date()
    
    print(f"VERIFY - User: {user.id}, Today: {today_date}")
    
    # Try exact date match first
    response = (
        supabase
        .table("wellbeingcheckin")
        .select("checkin_id, date_submitted")
        .eq("user_id", user.id)
        .eq("date_submitted", today_date.isoformat())
        .execute()
    )
    
    has_checked_in_today = len(response.data) > 0
    
    # If no exact match, try alternative approach
    if not has_checked_in_today:
        all_response = (
            supabase
            .table("wellbeingcheckin")
            .select("checkin_id, date_submitted")
            .eq("user_id", user.id)
            .execute()
        )
        
        today_str = today_date.isoformat()
        today_checkins = [c for c in all_response.data if c.get('date_submitted', '').startswith(today_str)]
        has_checked_in_today = len(today_checkins) > 0
        print(f"Alternative check found: {len(today_checkins)}")
    
    print(f"Final result: {has_checked_in_today}")
    
    return JsonResponse({
        'has_checked_in_today': has_checked_in_today,
        'user_id': user.id,
        'today_date': today_date.isoformat(),
        'checkins_found': len(response.data)
    })


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


@login_required
def profile_view(request):
    user_id = request.session.get("user_ID")
    if not user_id:
        messages.error(request, "You must log in first.")
        return redirect("login")

    # Fetch current user data
    try:
        response = supabase.table("user").select("*").eq("user_ID", user_id).execute()
        user_data = response.data[0] if response.data else {}
    except Exception as e:
        messages.error(request, f"Error fetching user data: {e}")
        return redirect("dashboard")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        title = request.POST.get("title", "").strip()
        profile_picture = request.FILES.get("profile_picture")

        update_data = {}

        # Handle profile picture upload
        if profile_picture:
            try:
                print(f"🖼️ Starting upload for: {profile_picture.name}")
                
                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if profile_picture.content_type not in allowed_types:
                    messages.error(request, "Please upload a valid image (JPEG, PNG, GIF, WebP)")
                    return redirect("profile")
                
                # Validate file size (max 5MB)
                if profile_picture.size > 5 * 1024 * 1024:
                    messages.error(request, "Image must be smaller than 5MB")
                    return redirect("profile")
                
                # Read file bytes
                file_bytes = profile_picture.read()
                
                # Create unique file path
                import time
                import os
                timestamp = int(time.time())
                name, ext = os.path.splitext(profile_picture.name)
                file_path = f"{user_id}/profile_{timestamp}{ext}"
                
                print(f"📁 Uploading to: {file_path}")
                
                # Upload to Supabase Storage
                upload_response = supabase.storage.from_("profile_pictures").upload(
                    file_path,
                    file_bytes,
                    {"content-type": profile_picture.content_type}
                )
                
                print(f"📤 Upload response: {upload_response}")
                
                # Check if upload was successful
                if hasattr(upload_response, 'error') and upload_response.error:
                    error_msg = f"Upload failed: {upload_response.error}"
                    print(f"❌ {error_msg}")
                    messages.error(request, error_msg)
                else:
                    # Success! Get the public URL
                    file_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/profile_pictures/{file_path}"
                    update_data['profile_picture'] = file_url
                    print(f"✅ Upload successful! URL: {file_url}")
                    messages.success(request, "Profile picture uploaded successfully!")
                    
            except Exception as e:
                print(f"💥 Upload exception: {e}")
                messages.error(request, f"Upload failed: {e}")

        # Handle other profile updates
        if full_name and full_name != user_data.get('full_name'):
            update_data['full_name'] = full_name
            
        if email and email != user_data.get('email'):
            update_data['email'] = email
            
        if title != user_data.get('title'):
            update_data['title'] = title

        # Update database if there are changes
        if update_data:
            try:
                user_id_int = int(user_id)
                update_response = supabase.table("user").update(update_data).eq("user_ID", user_id_int).execute()
                
                if hasattr(update_response, 'error') and update_response.error:
                    messages.error(request, f"Database error: {update_response.error}")
                else:
                    if 'profile_picture' in update_data:
                        messages.success(request, "Profile and picture updated successfully!")
                    else:
                        messages.success(request, "Profile updated successfully!")
                    
            except Exception as e:
                messages.error(request, f"Update failed: {str(e)}")
        else:
            messages.info(request, "No changes were made.")

        return redirect("profile")

    return render(request, "profile.html", {"user_data": user_data})