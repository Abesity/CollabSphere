# To fetch profile pic from navbar
from supabase import create_client
from django.conf import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def user_profile(request):
    """
    Injects user profile data into templates for logged-in users.
    """
    # Be defensive: some callers (e.g., RequestFactory in tests or
    # shell renderings) may not attach a `user` attribute to the
    # request object. Guard against that to avoid TemplateSyntaxError
    # / AttributeError during template rendering.
    if not hasattr(request, 'user') or not getattr(request.user, 'is_authenticated', False):
        return {}

    user_id = request.session.get("user_ID")
    if not user_id:
        return {}

    try:
        response = supabase.table("user").select("*").eq("user_ID", int(user_id)).execute()
        user_data = response.data[0] if response.data else {}
    except Exception:
        user_data = {}

    return {
        "user_data": user_data
    }
