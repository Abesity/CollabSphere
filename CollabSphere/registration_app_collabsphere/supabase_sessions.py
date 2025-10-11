from supabase import create_client
from django.conf import settings
from datetime import datetime

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def record_login(user_id):
    supabase.table("login").insert({
        "user_ID": user_id,
        "login_time": datetime.utcnow().isoformat() 
    }).execute()


def record_logout(user_id: int):
    """Update the most recent login record by adding a logout timestamp."""
    latest = supabase.table("login").select("login_ID").eq("user_ID", user_id).is_("logout_time", None).execute()
    if latest.data:
        login_id = latest.data[-1]["login_ID"]
        supabase.table("login").update({
            "logout_time": datetime.utcnow().isoformat()
        }).eq("login_ID", login_id).execute()
