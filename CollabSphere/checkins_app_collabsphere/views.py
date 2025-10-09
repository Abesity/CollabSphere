from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from supabase import create_client
from django.conf import settings
from django.utils import timezone

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


@login_required(login_url='login')
def checkins_modal(request):
    """Return and handle wellbeing modal only (AJAX modal)."""
    user = request.user

    # 🧠 Handle POST (form submission)
    if request.method == "POST":
        mood_rating = request.POST.get("mood_rating")
        status = request.POST.get("status")
        notes = request.POST.get("notes")

        try:
            supabase.table("checkins").insert({
                "user_id": user.id,
                "mood_rating": mood_rating,
                "status": status,
                "notes": notes,
                "date_submitted": timezone.now().isoformat()
            }).execute()
            return JsonResponse({"success": True, "message": "Check-in submitted successfully!"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    # 🧠 Handle GET (display modal)
    try:
        response = (
            supabase.table("checkins")
            .select("*")
            .eq("user_id", user.id)
            .order("date_submitted", desc=True)
            .limit(5)
            .execute()
        )
        recent_checkins = response.data
    except Exception:
        recent_checkins = []

    return render(request, "partials/checkins_modal.html", {
        "fullname": f"{user.first_name} {user.last_name}".strip() or user.username,
        "recent_checkins": recent_checkins,
    })
