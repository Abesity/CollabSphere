from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth import get_user_model
from .forms import RegistrationForm, LoginForm
from .utils.passwords import hash_password, verify_password
from .supabase_sessions import record_login, record_logout
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from supabase import create_client

User = get_user_model()


# -------------------------------
# LOGIN VIEW
# -------------------------------
def login(request):
    # Create a bound or unbound form instance so the template can render errors and previous input
    form = LoginForm(request.POST or None)

    if request.method == 'POST':
        # Clear any previous auth/session state to avoid mixing sessions
        try:
            auth_logout(request)
        except Exception:
            pass
        # Remove common session keys that could conflict
        for k in ('admin_logged_in', 'admin_username', 'user_ID'):
            request.session.pop(k, None)

        email = request.POST.get('email')
        password = request.POST.get('password')
        
        print(f"DEBUG: Login attempt - Email: {email}")
        
        # Check if it's the admin
        if email == 'admin@example.com' and password == 'admin123':
            # Clear any queued messages to avoid duplicates
            try:
                list(messages.get_messages(request))
            except Exception:
                pass

            request.session['admin_logged_in'] = True
            request.session['admin_username'] = 'admin'
            messages.success(request, 'Welcome back, Admin!')
            return redirect('admin_app_collabsphere:dashboard')

        # First try Django authentication
        print(f"DEBUG: Attempting Django authentication for {email}")
        user = authenticate(request, username=email, password=password)

        if user is not None:
            print(f"DEBUG: Django auth SUCCESS - User: {user.username}")
            auth_login(request, user)
            if hasattr(user, 'supabase_id') and user.supabase_id:
                request.session['user_ID'] = user.supabase_id
            # Ensure any admin session flags are cleared when a regular user logs in
            request.session.pop('admin_logged_in', None)
            request.session.pop('admin_username', None)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('home')

        print(f"DEBUG: Django auth FAILED - trying Supabase...")

        # Try Supabase authentication as fallback
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

            # Check Supabase for user
            result = supabase.table("user").select("*").eq("email", email).execute()

            if result.data:
                supabase_user = result.data[0]
                print(f"DEBUG: Found Supabase user: {supabase_user.get('username')}")

                stored_password = supabase_user.get('password', '')
                print(f"DEBUG: Stored password type: {stored_password[:50] if stored_password else 'EMPTY'}...")

                # Use your custom verify_password function
                from .utils.passwords import verify_password

                if verify_password(password, stored_password):
                    print(f"DEBUG: Password verified with custom PBKDF2")

                    # Get or create Django user
                    try:
                        django_user = User.objects.get(email=email)
                        print(f"DEBUG: Found existing Django user: {django_user.username}")

                        # CRITICAL FIX: Update the Django user's password to Django's format
                        # This ensures authenticate() will work next time
                        django_user.set_password(password)
                        django_user.supabase_id = supabase_user['user_ID']
                        django_user.save()
                        print(f"DEBUG: Updated Django user password")

                    except User.DoesNotExist:
                        print(f"DEBUG: Creating new Django user")
                        # Create new Django user
                        django_user = User.objects.create_user(
                            username=supabase_user['username'],
                            email=email,
                            password=password  # Django will hash with its algorithm
                        )
                        django_user.supabase_id = supabase_user['user_ID']
                        django_user.save()
                        print(f"DEBUG: Created new Django user: {django_user.username}")

                    # Now authenticate with the updated password
                    print(f"DEBUG: Attempting authentication with updated password...")
                    django_user = authenticate(request, username=email, password=password)

                    if django_user:
                        print(f"DEBUG: Authentication SUCCESS")
                        auth_login(request, django_user)
                        request.session['user_ID'] = supabase_user['user_ID']
                        messages.success(request, f'Welcome back, {django_user.username}!')
                        return redirect('home')
                    else:
                        print(f"DEBUG: Authentication still failing, logging in manually")
                        # Manual login as fallback
                        # First, refresh the user from database
                        django_user = User.objects.get(email=email)
                        # Set authentication backend manually
                        django_user.backend = 'django.contrib.auth.backends.ModelBackend'
                        auth_login(request, django_user)
                        request.session['user_ID'] = supabase_user['user_ID']
                        messages.success(request, f'Welcome back, {django_user.username}!')
                        return redirect('home')
                else:
                    print(f"DEBUG: Password verification failed")
                    messages.error(request, 'Invalid email or password.')
                    # Add to form non-field errors so template shows it
                    form.add_error(None, 'Invalid email or password.')
            else:
                print(f"DEBUG: User not found in Supabase")
                messages.error(request, 'User not found.')
                form.add_error(None, 'User not found.')

        except Exception as e:
            print(f"DEBUG: Error: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, 'Authentication error. Please try again.')
            form.add_error(None, 'Authentication error. Please try again.')
    
    # Render the login template with the form (bound or unbound)
    return render(request, 'login.html', {'form': form})

# -------------------------------
# REGISTER VIEW
# -------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        if User.email_exists(email):
            form.add_error("email", "Email already registered.")
        if User.username_exists(username):
            form.add_error("username", "Username already taken.")

        if not form.errors:
            hashed_pw = hash_password(password)
            new_sb_user = User.create_supabase_user(username, email, hashed_pw)

            if new_sb_user:
                user = User.objects.create(
                    username=username,
                    email=email,
                    supabase_id=new_sb_user["user_ID"]
                )
                user.set_unusable_password()
                user.save()
                return redirect("login")

    return render(request, "register.html", {"form": form})


# -------------------------------
# LOGOUT VIEW
# -------------------------------
def logout(request):
    if "user_ID" in request.session:
        record_logout(request.session["user_ID"])

    auth_logout(request)
    request.session.flush()
    return redirect("login")

# -------------------------------
# FAQ
# -------------------------------
def faq(request):
    return render(request, "faq.html")