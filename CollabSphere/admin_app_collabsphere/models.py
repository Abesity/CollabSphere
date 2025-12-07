from django.conf import settings
from supabase import create_client
from django.utils import timezone
import logging
import time
import hashlib



logger = logging.getLogger(__name__)
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class AdminSupabaseService:
    """Handles all Supabase operations for admin functionality."""
    
    # -------------------------------
    # USER MANAGEMENT
    # -------------------------------
    
    @staticmethod
    def get_all_users():
        """Fetch all users from Supabase."""
        try:
            response = supabase.table("user").select("*").order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all users: {str(e)}")
            return []
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get a single user by ID."""
        try:
            response = supabase.table("user").select("*").eq("user_ID", int(user_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def create_user(user_data):
        """Create a new user in Supabase."""
        try:
            # Ensure required fields
            required_fields = ['username', 'email', 'password']
            for field in required_fields:
                if field not in user_data:
                    raise ValueError(f"Missing required field: {field}")
            
            response = supabase.table("user").insert(user_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    @staticmethod
    def update_user(user_id, update_data):
        """Update a user in Supabase."""
        try:
            response = supabase.table("user").update(update_data).eq("user_ID", int(user_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_user(user_id):
        """Delete a user from Supabase."""
        try:
            # First check if user exists
            user = AdminSupabaseService.get_user_by_id(user_id)
            if not user:
                return False
            username = user.get('username')

            # 1) Delete event participants for this user
            try:
                supabase.table('eventsparticipant').delete().eq('user_id', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to delete event participants for user {user_id}: {e}")

            # 2) Delete notifications where user is recipient or sender
            try:
                supabase.table('notifications').delete().or_(f"recipient.eq.{user_id},sender.eq.{user_id}").execute()
            except Exception as e:
                logger.warning(f"Failed to delete notifications for user {user_id}: {e}")

            # 3) Delete wellbeing checkins
            try:
                supabase.table('wellbeingcheckin').delete().eq('user_id', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to delete wellbeing checkins for user {user_id}: {e}")

            # 4) Delete login records
            try:
                supabase.table('login').delete().eq('user_ID', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to delete login records for user {user_id}: {e}")

            # 5) Anonymize task comments authored by this user (avoid FK parent issues)
            try:
                if username:
                    supabase.table('task_comments').update({
                        'username': '[deleted]',
                        'content': '[deleted]'
                    }).eq('username', username).execute()
            except Exception as e:
                logger.warning(f"Failed to anonymize task comments for user {user_id}: {e}")

            # 6) For tasks assigned to this user, nullify assignment
            try:
                supabase.table('tasks').update({
                    'assigned_to': None,
                    'assigned_to_username': None
                }).eq('assigned_to', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to nullify task assignments for user {user_id}: {e}")

            # 7) For calendar events created by this user, nullify user_id (keep event)
            try:
                supabase.table('calendarevent').update({
                    'user_id': None
                }).eq('user_id', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to nullify calendar events for user {user_id}: {e}")

            # 8) Handle teams owned by this user: delete teams and their dependent records
            try:
                owned_teams = supabase.table('team').select('team_ID').eq('user_id_owner', int(user_id)).execute()
                owned_team_ids = [t['team_ID'] for t in (owned_teams.data or [])]
                for team_id in owned_team_ids:
                    try:
                        # Clear active_team_id for any users with this active team
                        supabase.table('user').update({'active_team_id': None}).eq('active_team_id', team_id).execute()

                        # Delete calendar events for this team
                        supabase.table('calendarevent').delete().eq('team_ID', team_id).execute()

                        # Delete tasks for this team
                        supabase.table('tasks').delete().eq('team_ID', team_id).execute()

                        # Delete user_team relationships for this team
                        supabase.table('user_team').delete().eq('team_ID', team_id).execute()

                        # Finally delete the team
                        supabase.table('team').delete().eq('team_ID', team_id).execute()
                    except Exception as e:
                        logger.warning(f"Failed to fully remove team {team_id} owned by user {user_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to enumerate/delete teams owned by user {user_id}: {e}")

            # 9) Remove this user from any teams (user_team entries)
            try:
                supabase.table('user_team').delete().eq('user_id', int(user_id)).execute()
            except Exception as e:
                logger.warning(f"Failed to delete user_team rows for user {user_id}: {e}")

            # 10) Finally delete the user record
            try:
                supabase.table('user').delete().eq('user_ID', int(user_id)).execute()
            except Exception as e:
                logger.error(f"Failed to delete user row for {user_id}: {e}")
                return False

            # Also remove the corresponding Django user if it exists (cleanup)
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                # supabase_id is stored as a string on the Django model
                django_user = User.objects.filter(supabase_id=str(user_id)).first()
                if django_user:
                    django_user.delete()
            except Exception as e:
                logger.warning(f"Failed to delete linked Django user for supabase id {user_id}: {e}")

            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def search_users(query):
        """Search users by username, email, or full name."""
        try:
            response = supabase.table("user").select("*").or_(
                f"username.ilike.%{query}%,email.ilike.%{query}%,full_name.ilike.%{query}%"
            ).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error searching users: {str(e)}")
            return []
    
    # -------------------------------
    # TASK MANAGEMENT
    # -------------------------------
    
    @staticmethod
    def get_all_tasks():
        """Fetch all tasks from Supabase."""
        try:
            response = supabase.table("tasks").select("*").order("date_created", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all tasks: {str(e)}")
            return []
    
    @staticmethod
    def get_task_by_id(task_id):
        """Get a single task by ID."""
        try:
            response = supabase.table("tasks").select("*").eq("task_id", int(task_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {str(e)}")
            return None
    
    @staticmethod
    def create_task(task_data):
        """Create a new task in Supabase."""
        try:
            response = supabase.table("tasks").insert(task_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            raise
    
    @staticmethod
    def update_task(task_id, update_data):
        """Update a task in Supabase."""
        try:
            response = supabase.table("tasks").update(update_data).eq("task_id", int(task_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating task {task_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_task(task_id):
        """Delete a task from Supabase."""
        try:
            response = supabase.table("tasks").delete().eq("task_id", int(task_id)).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {str(e)}")
            return False
    
    @staticmethod
    def search_tasks(query):
        """Search tasks by title or description."""
        try:
            response = supabase.table("tasks").select("*").or_(
                f"title.ilike.%{query}%,description.ilike.%{query}%"
            ).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error searching tasks: {str(e)}")
            return []
    
    # -------------------------------
    # TEAM MANAGEMENT
    # -------------------------------
    
    @staticmethod
    def get_all_teams():
        """Fetch all teams from Supabase."""
        try:
            response = supabase.table("team").select("*").order("joined_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all teams: {str(e)}")
            return []
    
    @staticmethod
    def get_team_by_id(team_id):
        """Get a single team by ID."""
        try:
            response = supabase.table("team").select("*").eq("team_ID", int(team_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching team {team_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_team_members(team_id):
        """Get all members of a team."""
        try:
            response = supabase.table("user_team").select(
                "user:user_id(username, email, full_name, profile_picture)"
            ).eq("team_ID", int(team_id)).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching team members for team {team_id}: {str(e)}")
            return []
    
    # -------------------------------
    # WELLBEING MANAGEMENT
    # -------------------------------
    
    @staticmethod
    def get_all_checkins():
        """Fetch all wellbeing check-ins."""
        try:
            response = supabase.table("wellbeingcheckin").select(
                "checkin_id, user_id, mood_rating, notes, date_submitted, status, user:user_id(username, email)"
            ).order("date_submitted", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all check-ins: {str(e)}")
            return []
    
    @staticmethod
    def get_checkin_stats():
        """Get statistics about check-ins."""
        try:
            # Get total check-ins
            response = supabase.table("wellbeingcheckin").select("checkin_id", count="exact").execute()
            total = response.count or 0
            
            # Get today's check-ins
            today = timezone.now().date().isoformat()
            today_response = supabase.table("wellbeingcheckin").select(
                "checkin_id"
            ).gte("date_submitted", f"{today}T00:00:00").lte("date_submitted", f"{today}T23:59:59").execute()
            today_count = len(today_response.data) if today_response.data else 0
            
            # Get mood distribution
            mood_response = supabase.table("wellbeingcheckin").select(
                "mood_rating", count="exact"
            ).group("mood_rating").execute()
            
            mood_stats = {}
            for item in mood_response.data:
                mood_stats[item['mood_rating']] = item['count']
            
            return {
                'total': total,
                'today': today_count,
                'mood_distribution': mood_stats
            }
        except Exception as e:
            logger.error(f"Error fetching check-in stats: {str(e)}")
            return {'total': 0, 'today': 0, 'mood_distribution': {}}
    
    # -------------------------------
    # SYSTEM STATISTICS
    # -------------------------------
    @staticmethod
    def get_system_stats():
        """Get comprehensive system statistics."""
        try:
            stats = {}
            
            # User counts
            users_response = supabase.table("user").select("user_ID", count="exact").execute()
            stats['total_users'] = users_response.count or 0
            
            # Task counts
            tasks_response = supabase.table("tasks").select("task_id", count="exact").execute()
            stats['total_tasks'] = tasks_response.count or 0
            
            # Team counts
            teams_response = supabase.table("team").select("team_ID", count="exact").execute()
            stats['total_teams'] = teams_response.count or 0
            
            # Check-in counts
            checkins_response = supabase.table("wellbeingcheckin").select("checkin_id", count="exact").execute()
            stats['total_checkins'] = checkins_response.count or 0
            
            # Recent activities
            recent_users = supabase.table("user").select("*").order("created_at", desc=True).limit(5).execute()
            stats['recent_users'] = recent_users.data or []
            
            recent_tasks = supabase.table("tasks").select("*").order("date_created", desc=True).limit(5).execute()
            stats['recent_tasks'] = recent_tasks.data or []
            
            # Recent check-ins
            recent_checkins = supabase.table("wellbeingcheckin").select(
                "checkin_id, user_id, mood_rating, notes, date_submitted, user:user_id(username)"
            ).order("date_submitted", desc=True).limit(5).execute()
            stats['recent_checkins'] = recent_checkins.data or []
            
            # Today's activities
            today = timezone.now().date().isoformat()
            today_users = supabase.table("user").select("*").gte("created_at", f"{today}T00:00:00").execute()
            stats['users_today'] = len(today_users.data) if today_users.data else 0
            
            today_tasks = supabase.table("tasks").select("*").gte("date_created", f"{today}T00:00:00").execute()
            stats['tasks_today'] = len(today_tasks.data) if today_tasks.data else 0
            
            return stats
        except Exception as e:
            logger.error(f"Error fetching system stats: {str(e)}")
            return {}
    
    @staticmethod
    def get_user_registration_stats(days=30):
        """Get user registration statistics for the last N days."""
        try:
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=days)
            
            # Format dates for Supabase
            start_date_str = start_date.date().isoformat()
            end_date_str = end_date.date().isoformat()
            
            response = supabase.table("user").select(
                "created_at::date as date, count(*) as count"
            ).gte("created_at", f"{start_date_str}T00:00:00").lte(
                "created_at", f"{end_date_str}T23:59:59"
            ).group("date").order("date", desc=True).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching user registration stats: {str(e)}")
            return []
    
    # -------------------------------
    # NOTIFICATIONS
    # -------------------------------
    
    @staticmethod
    def get_all_notifications():
        """Fetch all notifications."""
        try:
            response = supabase.table("notifications").select(
                "notification_id, recipient, sender, notification_type, title, message, read, created_at, deadline, user:sender(username, email)"
            ).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all notifications: {str(e)}")
            return []
    
    @staticmethod
    def send_system_notification(recipient_id, title, message, notification_type="system"):
        """Send a system notification to a user."""
        try:
            notification_data = {
                "recipient": recipient_id,
                "sender": None,  # System notification
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "read": False,
                "created_at": timezone.now().isoformat()
            }
            
            response = supabase.table("notifications").insert(notification_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error sending system notification: {str(e)}")
            return None
    
    # -------------------------------
    # EVENT MANAGEMENT
    # -------------------------------
    
    @staticmethod
    def get_all_events():
        """Fetch all calendar events."""
        try:
            response = supabase.table("calendarevent").select(
                "event_id, title, description, start_time, end_time, user_id, team_ID, user:user_id(username, email)"
            ).order("start_time", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all events: {str(e)}")
            return []
    
    # -------------------------------
    # DATA EXPORT
    # -------------------------------
    
    @staticmethod
    def export_users(format="json"):
        """Export user data."""
        try:
            users = AdminSupabaseService.get_all_users()
            
            if format == "csv":
                # Convert to CSV format
                import csv
                from io import StringIO
                
                output = StringIO()
                if users:
                    fieldnames = users[0].keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(users)
                
                return output.getvalue()
            else:
                # Default to JSON
                return users
        except Exception as e:
            logger.error(f"Error exporting users: {str(e)}")
            return []
    
    @staticmethod
    def export_tasks(format="json"):
        """Export task data."""
        try:
            tasks = AdminSupabaseService.get_all_tasks()
            
            if format == "csv":
                import csv
                from io import StringIO
                
                output = StringIO()
                if tasks:
                    fieldnames = tasks[0].keys()
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(tasks)
                
                return output.getvalue()
            else:
                return tasks
        except Exception as e:
            logger.error(f"Error exporting tasks: {str(e)}")
            return []
    # -------------------------------
    # USER EDIT
    # -------------------------------   
    # Add to AdminSupabaseService class

    @staticmethod
    def check_email_exists(email):
        """Check if email already exists in the system."""
        try:
            response = supabase.table("user").select("user_ID").eq("email", email).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking email existence: {str(e)}")
            return False
        
    @staticmethod
    def upload_file_to_supabase(file, user_id):
        """Upload a file to Supabase storage and return the public URL."""
        try:
            import time  # ADD THIS IMPORT HERE
            file_path = f"profile_pictures/{user_id}_{int(time.time())}_{file.name}"
            file_bytes = file.read()
            
            # Upload to Supabase storage
            bucket = supabase.storage.from_("profile_pictures")
            
            # Try to upload, update if exists
            try:
                bucket.upload(file_path, file_bytes)
            except Exception:
                # File might exist, try update
                bucket.update(file_path, file_bytes)
            
            # Get public URL
            public_url = bucket.get_public_url(file_path)
            return public_url
        except Exception as e:
            logger.error(f"Error uploading file to Supabase: {str(e)}")
            raise Exception(f"Failed to upload file: {str(e)}")
        
    @staticmethod
    def hash_password(password):
        """Hash password using Django's password hasher (simplified version).
        In production, you'd use Django's make_password or Supabase Auth."""
        import hashlib
        # This is a simplified example - in production use proper hashing
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def get_all_roles():
        """Get all available roles from the role table."""
        try:
            response = supabase.table("role").select("*").order("role_id", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching roles: {str(e)}")
            return []
    
    @staticmethod
    def check_email_exists(email):
        """Check if email already exists in the system."""
        try:
            response = supabase.table("user").select("user_ID").eq("email", email).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking email existence: {str(e)}")
            return False
        
    @staticmethod
    def create_user_with_django(user_data):
        """Create a new user in both Supabase and Django."""
        try:
            # First, create in Supabase
            supabase_user = AdminSupabaseService.create_user(user_data)
            
            if not supabase_user:
                return None
            
            # Then create in Django
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                # Check if Django user already exists by username
                if User.objects.filter(username=supabase_user['username']).exists():
                    # Update existing user with supabase_id
                    django_user = User.objects.get(username=supabase_user['username'])
                    django_user.supabase_id = supabase_user['user_ID']
                    django_user.save()
                    logger.info(f"Updated existing Django user: {supabase_user['username']}")
                else:
                    # Create new Django user
                    django_user = User.objects.create_user(
                        username=supabase_user['username'],
                        email=supabase_user['email'],
                        password=user_data['password'],  # Use the password from user_data
                    )
                    django_user.supabase_id = supabase_user['user_ID']
                    django_user.save()
                    logger.info(f"Created new Django user: {supabase_user['username']}")
                
                # Link them
                supabase_user['django_user_id'] = django_user.id
                return supabase_user
                
            except Exception as e:
                # If Django creation fails, rollback Supabase user
                logger.error(f"Error creating Django user: {str(e)}")
                AdminSupabaseService.delete_user(supabase_user['user_ID'])
                raise Exception(f"Failed to create Django user: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error creating user with Django: {str(e)}")
            raise
    
    @staticmethod
    def get_django_user_from_supabase(supabase_user_id):
        """Get Django user from Supabase user ID."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            return User.objects.filter(supabase_id=supabase_user_id).first()
        except Exception as e:
            logger.error(f"Error getting Django user: {str(e)}")
            return None
    
    @staticmethod
    def make_django_password(password):
        """Create a Django-compatible password hash."""
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def create_user_with_hashed_password(user_data):
        """Create a new user with automatically hashed password."""
        # Make a copy to avoid modifying original
        data = user_data.copy()
        
        # Hash password if it's not already hashed
        password = data.get('password', '')
        if password:
            # If it's already in our PBKDF2 format (starts with 'pbkdf2$'), leave it
            if not str(password).startswith('pbkdf2$'):
                # Use the project's PBKDF2 hasher to produce a compatible stored hash
                try:
                    from registration_app_collabsphere.utils.passwords import hash_password
                    data['password'] = hash_password(password)
                except Exception:
                    # Fallback: if the import fails, fall back to a SHA256 hex (less preferred)
                    import hashlib
                    data['password'] = hashlib.sha256(password.encode()).hexdigest()
        
        return AdminSupabaseService.create_user(data)
        