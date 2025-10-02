from django.shortcuts import render, redirect

def home(request):
    return render(request, 'home.html')

def dashboard(request):
    response = supabase.table("users").select("*").execute()
    users = response.data

    return render(request, "dashboard.html", {"users": users})

# require login here to view profile please
def profile_view(request):
    """
    Render the user profile page.
    """
    return render(request, "profile.html")