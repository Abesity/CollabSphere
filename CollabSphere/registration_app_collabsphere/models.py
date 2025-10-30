

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class CustomUser(AbstractUser):
    supabase_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return self.username

    # -------------------------------
    # SUPABASE USER METHODS
    # -------------------------------

    @classmethod
    def get_by_email(cls, email):
        """Fetch a user record from Supabase by email."""
        result = supabase.table("user").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None

    @classmethod
    def create_supabase_user(cls, username, email, hashed_pw):
        """Insert a new user into Supabase."""
        result = supabase.table("user").insert({
            "username": username,
            "email": email,
            "password": hashed_pw
        }).execute()
        return result.data[0] if result.data else None

    @classmethod
    def email_exists(cls, email):
        """Check if an email is already in Supabase."""
        result = supabase.table("user").select("user_ID").eq("email", email).execute()
        return bool(result.data)

    @classmethod
    def username_exists(cls, username):
        """Check if a username is already in Supabase."""
        result = supabase.table("user").select("user_ID").eq("username", username).execute()
        return bool(result.data)

