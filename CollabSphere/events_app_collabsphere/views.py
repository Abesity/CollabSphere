from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

@require_GET
@login_required
def events_calendar(request):
    return render(request, "events_calendar.html")
