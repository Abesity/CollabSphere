from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

@login_required
def teams(request):
    if not request.user.is_authenticated:
        messages.warning(request, "You must be logged in to view this page.")
        return redirect("login")  
    
    return render(request, "teams.html")
