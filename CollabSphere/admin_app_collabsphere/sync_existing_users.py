import os
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Use the correct settings module name (lowercase package folder)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collabsphere.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from supabase import create_client

User = get_user_model()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def sync_existing_users():
    """Sync existing Supabase users to Django."""
    try:
        # Get all users from Supabase
        response = supabase.table("user").select("*").execute()
        supabase_users = response.data or []
        
        print(f"Found {len(supabase_users)} users in Supabase")
        
        created_count = 0
        updated_count = 0
        
        for supabase_user in supabase_users:
            try:
                # Check if Django user already exists by username
                django_user = User.objects.filter(username=supabase_user['username']).first()
                
                if not django_user:
                    # Check by email
                    django_user = User.objects.filter(email=supabase_user['email']).first()
                
                if django_user:
                    # Update existing user with supabase_id
                    if django_user.supabase_id != supabase_user['user_ID']:
                        django_user.supabase_id = supabase_user['user_ID']
                        django_user.save()
                        updated_count += 1
                        print(f"Updated: {supabase_user['username']}")
                else:
                    # Create new Django user
                    django_user = User.objects.create_user(
                        username=supabase_user['username'],
                        email=supabase_user['email'],
                        password='temporary_password',  # Users will need to reset
                    )
                    django_user.supabase_id = supabase_user['user_ID']
                    django_user.save()
                    created_count += 1
                    print(f"Created: {supabase_user['username']}")
                    
            except Exception as e:
                print(f"Error syncing user {supabase_user.get('username', 'Unknown')}: {str(e)}")
        
        print(f"\nSync complete!")
        print(f"Created: {created_count} new Django users")
        print(f"Updated: {updated_count} existing Django users")
        
    except Exception as e:
        print(f"Error in sync: {str(e)}")

if __name__ == "__main__":
    sync_existing_users()