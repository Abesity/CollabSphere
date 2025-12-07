from django.conf import settings
from supabase import create_client
from django.utils import timezone
from datetime import datetime
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
            # Include assigned user metadata for templates (join on assigned_to -> user.user_ID)
            response = supabase.table("tasks").select(
                "*, assigned_user:assigned_to(user_ID, username, email, full_name, profile_picture)"
            ).order("date_created", desc=True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching all tasks: {str(e)}")
            return []
    
    @staticmethod
    def get_task_by_id(task_id):
        """Get a single task by ID."""
        try:
            response = supabase.table("tasks").select(
                "*, assigned_user:assigned_to(user_ID, username, email, full_name, profile_picture)"
            ).eq("task_id", int(task_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching task {task_id}: {str(e)}")
            return None
    
    @staticmethod
    def create_task(task_data):
        """Create a new task in Supabase."""
        try:
            response = supabase.table("tasks").insert(task_data).execute()
            created = response.data[0] if response.data else None
            # Return enriched task with assigned_user metadata
            if created and created.get('task_id'):
                return AdminSupabaseService.get_task_by_id(created['task_id'])
            return created
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            raise
    
    @staticmethod
    def update_task(task_id, update_data):
        """Update a task in Supabase."""
        try:
            response = supabase.table("tasks").update(update_data).eq("task_id", int(task_id)).execute()
            # Return enriched task
            return AdminSupabaseService.get_task_by_id(task_id)
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
                "checkin_id, user_id, mood_rating, notes, date_submitted, status, user:user_id(username, email, profile_picture)"
            ).order("date_submitted", desc=True).execute()
            rows = response.data or []

            # Normalize profile_picture URLs for template usage
            from django.conf import settings as _settings
            SUPABASE_URL = getattr(_settings, 'SUPABASE_URL', None)
            normalized = []
            for r in rows:
                try:
                    user_meta = r.get('user') or {}
                    pic = user_meta.get('profile_picture') if isinstance(user_meta, dict) else None
                    if pic and isinstance(pic, str):
                        if pic.startswith('/') and SUPABASE_URL:
                            user_meta['profile_picture'] = f"{SUPABASE_URL}/storage/v1/object/public/{pic.lstrip('/')}"
                        else:
                            # if it's already a full URL or empty, keep as is
                            user_meta['profile_picture'] = pic
                    else:
                        # default avatar
                        user_meta['profile_picture'] = '/static/images/default-avatar.png'

                    r['user'] = user_meta
                except Exception:
                    pass
                normalized.append(r)

            return normalized
        except Exception as e:
            logger.error(f"Error fetching all check-ins: {str(e)}")
            return []

    @staticmethod
    def create_checkin(user_id, mood_rating, status, notes):
        """Create a wellbeing checkin as admin."""
        try:
            payload = {
                'user_id': int(user_id),
                'mood_rating': int(mood_rating) if mood_rating else None,
                'status': status or 'Okay',
                'notes': notes or '',
                'date_submitted': timezone.now().isoformat(),
            }
            response = supabase.table('wellbeingcheckin').insert(payload).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating checkin: {e}")
            raise

    @staticmethod
    def update_checkin(checkin_id, update_data):
        try:
            response = supabase.table('wellbeingcheckin').update(update_data).eq('checkin_id', int(checkin_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating checkin {checkin_id}: {e}")
            raise

    @staticmethod
    def delete_checkin(checkin_id):
        try:
            supabase.table('wellbeingcheckin').delete().eq('checkin_id', int(checkin_id)).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting checkin {checkin_id}: {e}")
            return False
    
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
            
            # Get mood distribution (client-side aggregation because .group() may not be supported)
            try:
                mood_rows = supabase.table("wellbeingcheckin").select("mood_rating").execute()
                mood_stats = {}
                if mood_rows.data:
                    for item in mood_rows.data:
                        key = item.get('mood_rating')
                        mood_stats[key] = mood_stats.get(key, 0) + 1
                else:
                    mood_stats = {}
            except Exception as e:
                logger.warning(f"Failed to compute mood distribution via select: {e}")
                mood_stats = {}
            
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
            # If the joined-select returned nothing (sometimes RLS or join issues), fall back to a simple select
            if not recent_checkins.data:
                logger.debug("No recent_checkins from joined select; falling back to simple select")
                fallback = supabase.table("wellbeingcheckin").select(
                    "checkin_id, user_id, mood_rating, notes, date_submitted"
                ).order("date_submitted", desc=True).limit(5).execute()
                stats['recent_checkins'] = fallback.data or []
            else:
                stats['recent_checkins'] = recent_checkins.data or []
            
            # Today's activities
            today = timezone.now().date().isoformat()
            today_users = supabase.table("user").select("*").gte("created_at", f"{today}T00:00:00").execute()
            stats['users_today'] = len(today_users.data) if today_users.data else 0
            
            today_tasks = supabase.table("tasks").select("*").gte("date_created", f"{today}T00:00:00").execute()
            stats['tasks_today'] = len(today_tasks.data) if today_tasks.data else 0
            
            # Team events
            recent_events = supabase.table("calendarevent").select(
                "event_id, title, description, start_time, end_time, user_id, team_ID, user:user_id(username)"
            ).order("start_time", desc=True).limit(5).execute()

            # Handle possible join issues
            if not recent_events.data:
                fallback_events = supabase.table("calendarevent").select(
                    "event_id, title, start_time, end_time, user_id, team_ID"
                ).order("start_time", desc=True).limit(5).execute()
                events_list = fallback_events.data or []
            else:
                events_list = recent_events.data or []

            # Parse ISO timestamps into Python datetimes and normalize keys for templates
            parsed_events = []
            for ev in (events_list or []):
                try:
                    ev_start = ev.get('start_time')
                    ev_end = ev.get('end_time')
                    if isinstance(ev_start, str):
                        ev_dt_start = datetime.fromisoformat(ev_start.replace('Z', '+00:00'))
                    else:
                        ev_dt_start = ev_start
                    if isinstance(ev_end, str):
                        ev_dt_end = datetime.fromisoformat(ev_end.replace('Z', '+00:00'))
                    else:
                        ev_dt_end = ev_end

                    # Ensure keys/templates compatibility
                    ev_parsed = ev.copy()
                    ev_parsed['start_time'] = ev_dt_start
                    ev_parsed['end_time'] = ev_dt_end
                    ev_parsed['start_date'] = ev_dt_start
                    # Provide `id` for templates/JS expecting it and `organizer` structure
                    ev_parsed['id'] = ev_parsed.get('event_id')
                    user_meta = ev_parsed.get('user') or {}
                    ev_parsed['organizer'] = {
                        'username': user_meta.get('username') if isinstance(user_meta, dict) else None,
                        'avatar': None,
                    }
                    parsed_events.append(ev_parsed)
                except Exception as e:
                    logger.warning(f"Failed to parse event timestamps: {e}")
                    parsed_events.append(ev)

            stats['recent_events'] = parsed_events
            
            
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
            events = response.data or []

            # Parse timestamps to datetime objects and normalize fields for templates
            parsed = []
            for ev in events:
                try:
                    ev_start = ev.get('start_time')
                    ev_end = ev.get('end_time')
                    if isinstance(ev_start, str):
                        ev_dt_start = datetime.fromisoformat(ev_start.replace('Z', '+00:00'))
                    else:
                        ev_dt_start = ev_start
                    if isinstance(ev_end, str):
                        ev_dt_end = datetime.fromisoformat(ev_end.replace('Z', '+00:00'))
                    else:
                        ev_dt_end = ev_end

                    ev_parsed = ev.copy()
                    ev_parsed['start_time'] = ev_dt_start
                    ev_parsed['end_time'] = ev_dt_end
                    ev_parsed['start_date'] = ev_dt_start
                    ev_parsed['id'] = ev_parsed.get('event_id')
                    user_meta = ev_parsed.get('user') or {}
                    ev_parsed['organizer'] = {
                        'username': user_meta.get('username') if isinstance(user_meta, dict) else None,
                        'avatar': None,
                    }
                    parsed.append(ev_parsed)
                except Exception as e:
                    logger.warning(f"Failed to parse event in get_all_events: {e}")
                    parsed.append(ev)

            return parsed
        except Exception as e:
            logger.error(f"Error fetching all events: {str(e)}")
            return []

    @staticmethod
    def create_event(event_data):
        """Create a calendar event in Supabase."""
        try:
            response = supabase.table('calendarevent').insert(event_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise

    @staticmethod
    def update_event(event_id, update_data):
        """Update an existing calendar event."""
        try:
            response = supabase.table('calendarevent').update(update_data).eq('event_id', int(event_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating event {event_id}: {e}")
            raise

    @staticmethod
    def delete_event(event_id):
        """Delete a calendar event."""
        try:
            supabase.table('calendarevent').delete().eq('event_id', int(event_id)).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting event {event_id}: {e}")
            return False
    
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
        

    # Additional crud 
    @staticmethod
    def get_checkin_by_id(checkin_id):
        """Get a single check-in by ID."""
        try:
            response = supabase.table("wellbeingcheckin").select(
                "checkin_id, user_id, mood_rating, notes, date_submitted, status, user:user_id(username, email, profile_picture)"
            ).eq("checkin_id", int(checkin_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching check-in {checkin_id}: {str(e)}")
            return None

    # In the EVENT MANAGEMENT section
    @staticmethod
    def get_event_by_id(event_id):
        """Get a single event by ID."""
        try:
            response = supabase.table("calendarevent").select(
                "event_id, title, description, start_time, end_time, user_id, team_ID, user:user_id(username, email)"
            ).eq("event_id", int(event_id)).execute()
            event = response.data[0] if response.data else None
            
            if event:
                # Parse timestamps
                start_time = event.get('start_time')
                end_time = event.get('end_time')
                if isinstance(start_time, str):
                    event['start_time'] = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                if isinstance(end_time, str):
                    event['end_time'] = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            return event
        except Exception as e:
            logger.error(f"Error fetching event {event_id}: {str(e)}")
            return None       
        
    @staticmethod
    def get_user_active_teams(user_id):
        """Get all active teams a user belongs to."""
        try:
            response = supabase.table("user_team").select(
                "team_ID, left_at"
            ).eq("user_id", int(user_id)).is_("left_at", None).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error getting user active teams: {str(e)}")
            return []

    @staticmethod
    def check_user_in_team(user_id, team_id):
        """Check if user is already an active member of a team."""
        try:
            response = supabase.table("user_team").select("*").eq("user_id", int(user_id)) \
                .eq("team_ID", int(team_id)).is_("left_at", None).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking user in team: {str(e)}")
            return False

    @staticmethod
    def add_team_member(team_id, user_id):
        """Add a user to a team with validation."""
        try:
            # Check if user is already in the team
            if AdminSupabaseService.check_user_in_team(user_id, team_id):
                raise Exception(f"User {user_id} is already a member of team {team_id}")
            
            # Check if user is in other active teams
            active_teams = AdminSupabaseService.get_user_active_teams(user_id)
            if active_teams:
                # User is already in another active team
                raise Exception(f"User {user_id} is already a member of another active team")
            
            # Add user to team
            member_data = {
                "team_ID": int(team_id),
                "user_id": int(user_id),
                "joined_at": timezone.now().isoformat()
            }
            response = supabase.table("user_team").insert(member_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error adding team member: {str(e)}")
            raise

    @staticmethod
    def remove_team_member(team_id, user_id):
        """Remove a user from a team (mark as left)."""
        try:
            # Mark user as left instead of deleting record
            update_data = {
                "left_at": timezone.now().isoformat()
            }
            response = supabase.table("user_team").update(update_data).eq("team_ID", int(team_id)) \
                .eq("user_id", int(user_id)).is_("left_at", None).execute()
            
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error removing team member: {str(e)}")
            raise
    
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
        """Get all active members of a team."""
        try:
            # First get all user-team relationships for this team
            response = supabase.table("user_team").select(
                "user_id, joined_at, left_at"
            ).eq("team_ID", int(team_id)).execute()
            
            team_memberships = response.data or []
            
            # Filter for active members (where left_at is null)
            active_memberships = [m for m in team_memberships if not m.get('left_at')]
            
            # Get user details for each active member
            members = []
            for membership in active_memberships:
                user_id = membership.get('user_id')
                if user_id:
                    user_response = supabase.table("user").select(
                        "user_ID, username, email, full_name, profile_picture"
                    ).eq("user_ID", int(user_id)).execute()
                    
                    if user_response.data:
                        user_data = user_response.data[0]
                        # Add membership info to user data
                        user_data['joined_at'] = membership.get('joined_at')
                        user_data['left_at'] = membership.get('left_at')
                        members.append(user_data)
            
            return members
        except Exception as e:
            logger.error(f"Error fetching team members for team {team_id}: {str(e)}")
            return []

    @staticmethod
    def get_team_members_detailed(team_id):
        """Get team members with detailed membership info."""
        try:
            response = supabase.table("user_team").select(
                "user_id, joined_at, left_at, user:user_id(user_ID, username, email, full_name, profile_picture)"
            ).eq("team_ID", int(team_id)).execute()
            
            memberships = response.data or []
            
            # Format the data for easier use
            formatted_members = []
            for membership in memberships:
                if membership.get('user'):
                    member_data = membership['user'].copy()
                    member_data['joined_at'] = membership.get('joined_at')
                    member_data['left_at'] = membership.get('left_at')
                    member_data['is_active'] = not bool(membership.get('left_at'))
                    formatted_members.append(member_data)
            
            return formatted_members
        except Exception as e:
            logger.error(f"Error fetching detailed team members for team {team_id}: {str(e)}")
            # Fall back to simpler method
            return AdminSupabaseService.get_team_members(team_id)

    @staticmethod
    def get_team_with_members(team_id):
        """Get team data with all its members."""
        try:
            team = AdminSupabaseService.get_team_by_id(team_id)
            if not team:
                return None
            
            members = AdminSupabaseService.get_team_members_detailed(team_id)
            team['members'] = members
            team['active_members'] = [m for m in members if not m.get('left_at')]
            team['member_count'] = len(team['active_members'])
            team['total_members'] = len(members)  # Including inactive
            
            return team
        except Exception as e:
            logger.error(f"Error fetching team with members {team_id}: {str(e)}")
            return None

    @staticmethod
    def create_team(team_data):
        """Create a new team."""
        try:
            # Ensure required fields
            if 'team_name' not in team_data:
                raise ValueError("Team name is required")
            
            # Add creation timestamp if not provided
            if 'created_at' not in team_data:
                team_data['created_at'] = timezone.now().isoformat()
            
            response = supabase.table("team").insert(team_data).execute()
            created_team = response.data[0] if response.data else None
            
            # If team has an owner specified, add them as a member
            if created_team and 'user_id_owner' in team_data and team_data['user_id_owner']:
                AdminSupabaseService._add_team_member_internal(
                    created_team['team_ID'], 
                    team_data['user_id_owner']
                )
            
            return created_team
        except Exception as e:
            logger.error(f"Error creating team: {str(e)}")
            raise

    @staticmethod
    def update_team(team_id, update_data):
        """Update a team in Supabase."""
        try:
            response = supabase.table("team").update(update_data).eq("team_ID", int(team_id)).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error updating team {team_id}: {str(e)}")
            raise

    @staticmethod
    def delete_team(team_id):
        """Delete a team from Supabase."""
        try:
            # First check if team exists
            team = AdminSupabaseService.get_team_by_id(team_id)
            if not team:
                return False
            
            # Clear active_team_id for any users with this active team
            supabase.table("user").update({'active_team_id': None}).eq('active_team_id', team_id).execute()
            
            # Delete calendar events for this team
            supabase.table('calendarevent').delete().eq('team_ID', team_id).execute()
            
            # Delete tasks for this team
            supabase.table('tasks').delete().eq('team_ID', team_id).execute()
            
            # Delete user_team relationships for this team
            supabase.table('user_team').delete().eq('team_ID', team_id).execute()
            
            # Finally delete the team
            supabase.table('team').delete().eq('team_ID', team_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting team {team_id}: {str(e)}")
            return False

    @staticmethod
    def is_user_in_team(user_id, team_id):
        """Check if user is already an active member of a team."""
        try:
            response = supabase.table("user_team").select("*").eq("user_id", int(user_id)) \
                .eq("team_ID", int(team_id)).is_("left_at", None).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking user in team: {str(e)}")
            return False

    @staticmethod
    def get_user_teams(user_id):
        """Get all active teams a user belongs to."""
        try:
            response = supabase.table("user_team").select(
                "team_ID, joined_at, left_at, team:team_ID(team_name, team_description, user_id_owner)"
            ).eq("user_id", int(user_id)).is_("left_at", None).execute()
            
            teams = []
            for item in (response.data or []):
                if item.get('team'):
                    team_info = item['team']
                    team_info['joined_at'] = item.get('joined_at')
                    team_info['membership_id'] = item.get('id')  # If available
                    teams.append(team_info)
            
            return teams
        except Exception as e:
            logger.error(f"Error getting user teams: {str(e)}")
            return []

    @staticmethod
    def _add_team_member_internal(team_id, user_id):
        """Internal method to add a user to a team (used by other methods)."""
        try:
            # Check if user exists
            user = AdminSupabaseService.get_user_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} does not exist")
            
            # Check if team exists
            team = AdminSupabaseService.get_team_by_id(team_id)
            if not team:
                raise ValueError(f"Team {team_id} does not exist")
            
            # Check if user is already in the team
            if AdminSupabaseService.is_user_in_team(user_id, team_id):
                logger.warning(f"User {user_id} is already a member of team {team_id}")
                # Return existing membership info
                response = supabase.table("user_team").select("*").eq("user_id", int(user_id)) \
                    .eq("team_ID", int(team_id)).is_("left_at", None).execute()
                return response.data[0] if response.data else None
            
            # Add user to team
            member_data = {
                "team_ID": int(team_id),
                "user_id": int(user_id),
                "joined_at": timezone.now().isoformat()
            }
            
            response = supabase.table("user_team").insert(member_data).execute()
            logger.info(f"Added user {user_id} to team {team_id}")
            
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error adding team member: {str(e)}")
            raise

    @staticmethod
    def add_member_to_team(team_id, user_id):
        """Public method to add a user to a team (for admin interface)."""
        return AdminSupabaseService._add_team_member_internal(team_id, user_id)

    @staticmethod
    def _remove_team_member_internal(team_id, user_id):
        """Internal method to remove a user from a team."""
        try:
            # First check if the membership exists
            response = supabase.table("user_team").select("*").eq("user_id", int(user_id)) \
                .eq("team_ID", int(team_id)).is_("left_at", None).execute()
            
            if not response.data:
                logger.warning(f"User {user_id} is not an active member of team {team_id}")
                return None
            
            # Mark user as left
            update_data = {
                "left_at": timezone.now().isoformat()
            }
            
            update_response = supabase.table("user_team").update(update_data).eq("team_ID", int(team_id)) \
                .eq("user_id", int(user_id)).is_("left_at", None).execute()
            
            logger.info(f"Removed user {user_id} from team {team_id}")
            
            return update_response.data[0] if update_response.data else None
        except Exception as e:
            logger.error(f"Error removing team member: {str(e)}")
            raise

    @staticmethod
    def remove_member_from_team(team_id, user_id):
        """Public method to remove a user from a team (for admin interface)."""
        return AdminSupabaseService._remove_team_member_internal(team_id, user_id)

    @staticmethod
    def search_teams(query):
        """Search teams by name or description."""
        try:
            response = supabase.table("team").select("*").or_(
                f"team_name.ilike.%{query}%,team_description.ilike.%{query}%"
            ).execute()
            
            teams = response.data or []
            
            # Get member count for each team
            for team in teams:
                members = AdminSupabaseService.get_team_members(team['team_ID'])
                team['member_count'] = len(members)
            
            return teams
        except Exception as e:
            logger.error(f"Error searching teams: {str(e)}")
            return []

    @staticmethod
    def get_team_statistics(team_id):
        """Get statistics for a team."""
        try:
            team = AdminSupabaseService.get_team_with_members(team_id)
            if not team:
                return None
            
            stats = {
                'total_members': team.get('total_members', 0),
                'active_members': team.get('member_count', 0),
                'team_info': {
                    'team_name': team.get('team_name'),
                    'created_at': team.get('created_at'),
                    'description': team.get('team_description')
                }
            }
            
            # Get task count for this team
            try:
                tasks_response = supabase.table("tasks").select("task_id", count="exact").eq("team_ID", team_id).execute()
                stats['task_count'] = tasks_response.count or 0
            except Exception:
                stats['task_count'] = 0
            
            # Get event count for this team
            try:
                events_response = supabase.table("calendarevent").select("event_id", count="exact").eq("team_ID", team_id).execute()
                stats['event_count'] = events_response.count or 0
            except Exception:
                stats['event_count'] = 0
            
            return stats
        except Exception as e:
            logger.error(f"Error getting team statistics: {str(e)}")
            return None

    @staticmethod
    def transfer_team_ownership(team_id, new_owner_id):
        """Transfer team ownership to another user."""
        try:
            # Check if new owner is a team member
            if not AdminSupabaseService.is_user_in_team(new_owner_id, team_id):
                raise ValueError(f"User {new_owner_id} is not a member of team {team_id}")
            
            # Update team owner
            update_data = {
                "user_id_owner": int(new_owner_id),
                "updated_at": timezone.now().isoformat()
            }
            
            response = supabase.table("team").update(update_data).eq("team_ID", int(team_id)).execute()
            
            if response.data:
                logger.info(f"Transferred ownership of team {team_id} to user {new_owner_id}")
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error transferring team ownership: {str(e)}")
            raise
    

    @staticmethod
    def upload_team_icon(file, team_id=None):
        """Upload a team icon to Supabase storage and return the public URL."""
        try:
            import time
            file_extension = file.name.split('.')[-1] if '.' in file.name else 'png'
            
            # Generate unique filename
            if team_id:
                file_path = f"team_{team_id}_{int(time.time())}.{file_extension}"
            else:
                file_path = f"temp_{int(time.time())}_{file.name}"
            
            file_bytes = file.read()
            
            # Upload to Supabase storage
            bucket = supabase.storage.from_("team_icons")
            
            try:
                # Try to upload with explicit filename
                bucket.upload(file_path, file_bytes)
            except Exception as upload_error:
                # If bucket doesn't exist, create it first
                try:
                    supabase.storage.create_bucket("team_icons", {
                        "public": True,
                        "file_size_limit": 5242880,  # 5MB
                        "allowed_mime_types": ["image/jpeg", "image/png", "image/gif", "image/webp"]
                    })
                    bucket.upload(file_path, file_bytes)
                except Exception as create_error:
                    logger.error(f"Failed to create bucket or upload: {create_error}")
                    raise Exception(f"Failed to upload team icon: {create_error}")
            
            # Get public URL
            public_url = bucket.get_public_url(file_path)
            return public_url
        except Exception as e:
            logger.error(f"Error uploading team icon to Supabase: {str(e)}")
            raise Exception(f"Failed to upload team icon: {str(e)}")
    
    @staticmethod
    def delete_team_icon(icon_url):
        """Delete a team icon from Supabase storage."""
        try:
            if not icon_url or "team_icons" not in icon_url:
                return False
            
            # Extract file path from URL
            from urllib.parse import urlparse
            parsed = urlparse(icon_url)
            file_path = parsed.path.split("/team_icons/")[-1]
            
            if file_path:
                bucket = supabase.storage.from_("team_icons")
                bucket.remove([file_path])
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting team icon: {str(e)}")
            return False
                