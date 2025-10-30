from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .services.team_service import TeamService


@login_required
def teams_list(request):
    """Render the team dashboard showing all teams of the user."""
    user_teams = TeamService.list_user_teams(request.user.id)
    context = {"teams": user_teams}
    return render(request, "teams.html", context)


@login_required
def create_team(request):
    """Handle team creation through modal submission."""
    if request.method == "POST":
        name = request.POST.get("team_name")
        description = request.POST.get("description", "")
        icon_file = request.FILES.get("icon_url")

        if not name:
            messages.error(request, "Team name is required.")
            return redirect("teams")

        TeamService.create_team(request, name, description, icon_file)
        return redirect("teams")

    return render(request, "create_team.html")


@login_required
def switch_team(request, team_id):
    """Switch user's active team (AJAX)."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    if TeamService.switch_team(request, team_id):
        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=400)
