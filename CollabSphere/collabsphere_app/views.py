from django.shortcuts import render, redirect
from django.http import HttpResponse
from supabase import create_client
from django.conf import settings
 
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
 
def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
 
        supabase.table("users").insert({
            "username": username,
            "email": email,
            "password": password
        }).execute()
 
        return HttpResponse("Registration successful!")
    return render(request, "register.html")
 
 
def login(request):
    if request.method == "POST":
        email = request.POST["email"]
        password = request.POST["password"]
 
        response = supabase.table("users").select("*").eq("email", email).execute()
 
        if response.data and response.data[0]["password"] == password:
            return HttpResponse("Login successful!")
        else:
            return HttpResponse("Invalid credentials!")
 
    return render(request, "login.html")

def home(request):
    return render(request, 'home.html') 