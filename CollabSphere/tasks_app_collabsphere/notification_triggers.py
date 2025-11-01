from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class TaskNotificationTriggers:
    """
    Defines all notification triggers for task management.
    
    TRIGGER LIST:
    1. TASK_ASSIGNED - Task assigned to a user
    2. TASK_DUE_SOON - Task due within 24 hours
    3. TASK_OVERDUE - Task past due date
    4. TASK_COMPLETED - Task marked as complete
    5. TASK_UPDATED - Task details changed
    6. TASK_COMMENT - New comment added to task
    """
    
    # ========================================
    # TRIGGER 1: TASK ASSIGNED
    # ========================================
    @staticmethod
    def check_task_assigned(task_data, assigned_to_user_id):
        """
        Trigger: Task assigned to a user
        Condition: New task created with assigned user OR user assignment changed
        Priority: MEDIUM
        Recipients: Assigned user
        """
        if assigned_to_user_id:
            return {
                'triggered': True,
                'trigger_type': 'TASK_ASSIGNED',
                'priority': 'medium',
                'message': f'New task assigned: {task_data.get("title", "Untitled Task")}',
                'recipients': ['assigned_user'],
                'task_id': task_data.get('task_id'),
                'assigned_to': assigned_to_user_id
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 2: TASK DUE SOON
    # ========================================
    @staticmethod
    def check_task_due_soon(task_id, due_date, hours_threshold=24):
        """
        Trigger: Task due soon reminder
        Condition: Task due within next 24 hours AND status != 'completed'
        Priority: HIGH
        Recipients: Assigned user
        """
        if not due_date:
            return {'triggered': False}
        
        # Convert due_date to datetime if it's a string
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except:
                return {'triggered': False}
        
        now = timezone.now()
        time_until_due = due_date - now
        
        # Check if due within threshold and not completed
        if timedelta(0) < time_until_due <= timedelta(hours=hours_threshold):
            # Check task status
            response = (
                supabase.table("task")
                .select("status")
                .eq("task_id", task_id)
                .single()
                .execute()
            )
            
            if response.data and response.data.get('status') != 'completed':
                hours_remaining = int(time_until_due.total_seconds() / 3600)
                return {
                    'triggered': True,
                    'trigger_type': 'TASK_DUE_SOON',
                    'priority': 'high',
                    'message': f'Task due in {hours_remaining} hours',
                    'recipients': ['assigned_user'],
                    'task_id': task_id,
                    'hours_remaining': hours_remaining
                }
        
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 3: TASK OVERDUE
    # ========================================
    @staticmethod
    def check_task_overdue(task_id, due_date):
        """
        Trigger: Task is overdue
        Condition: Task past due date AND status != 'completed'
        Priority: CRITICAL
        Recipients: Assigned user + Manager
        """
        if not due_date:
            return {'triggered': False}
        
        # Convert due_date to datetime if it's a string
        if isinstance(due_date, str):
            try:
                due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            except:
                return {'triggered': False}
        
        now = timezone.now()
        
        # Check if overdue
        if now > due_date:
            # Check task status
            response = (
                supabase.table("task")
                .select("status")
                .eq("task_id", task_id)
                .single()
                .execute()
            )
            
            if response.data and response.data.get('status') != 'completed':
                days_overdue = (now - due_date).days
                return {
                    'triggered': True,
                    'trigger_type': 'TASK_OVERDUE',
                    'priority': 'critical',
                    'message': f'Task overdue by {days_overdue} day(s)',
                    'recipients': ['assigned_user', 'manager'],
                    'task_id': task_id,
                    'days_overdue': days_overdue
                }
        
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 4: TASK COMPLETED
    # ========================================
    @staticmethod
    def check_task_completed(task_data, old_status):
        """
        Trigger: Task marked as complete
        Condition: Status changed to 'completed'
        Priority: LOW
        Recipients: Task creator + Team members
        """
        new_status = task_data.get('status')
        
        if old_status != 'completed' and new_status == 'completed':
            return {
                'triggered': True,
                'trigger_type': 'TASK_COMPLETED',
                'priority': 'low',
                'message': f'Task completed: {task_data.get("title", "Untitled Task")}',
                'recipients': ['creator', 'team_members'],
                'task_id': task_data.get('task_id')
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 5: TASK UPDATED
    # ========================================
    @staticmethod
    def check_task_updated(task_data, changed_fields):
        """
        Trigger: Task details updated
        Condition: Important fields changed (title, description, due_date, priority)
        Priority: MEDIUM
        Recipients: Assigned user (if changed by someone else)
        """
        important_fields = ['title', 'description', 'due_date', 'priority']
        
        # Check if any important field was changed
        has_important_changes = any(field in changed_fields for field in important_fields)
        
        if has_important_changes:
            return {
                'triggered': True,
                'trigger_type': 'TASK_UPDATED',
                'priority': 'medium',
                'message': f'Task updated: {", ".join(changed_fields)}',
                'recipients': ['assigned_user'],
                'task_id': task_data.get('task_id'),
                'changed_fields': changed_fields
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 6: TASK COMMENT ADDED
    # ========================================
    @staticmethod
    def check_task_comment(task_id, comment_author_id):
        """
        Trigger: New comment added to task
        Condition: Comment created on task
        Priority: LOW
        Recipients: Assigned user + Previous commenters (excluding comment author)
        """
        return {
            'triggered': True,
            'trigger_type': 'TASK_COMMENT',
            'priority': 'low',
            'message': 'New comment on task',
            'recipients': ['assigned_user', 'commenters'],
            'task_id': task_id,
            'exclude_user': comment_author_id
        }
    
    # ========================================
    # HELPER: Get User's Overdue Tasks
    # ========================================
    @staticmethod
    def get_user_overdue_tasks(user_id):
        """
        Get all overdue tasks for a user.
        Useful for batch notifications/reminders.
        """
        now = timezone.now().isoformat()
        
        response = (
            supabase.table("task")
            .select("task_id, title, due_date, status")
            .eq("assigned_to", user_id)
            .neq("status", "completed")
            .lt("due_date", now)
            .execute()
        )
        
        return response.data or []
    
    # ========================================
    # HELPER: Get User's Due Soon Tasks
    # ========================================
    @staticmethod
    def get_user_due_soon_tasks(user_id, hours_threshold=24):
        """
        Get all tasks due soon for a user.
        Useful for daily digest notifications.
        """
        now = timezone.now()
        threshold_time = (now + timedelta(hours=hours_threshold)).isoformat()
        
        response = (
            supabase.table("task")
            .select("task_id, title, due_date, status")
            .eq("assigned_to", user_id)
            .neq("status", "completed")
            .gte("due_date", now.isoformat())
            .lte("due_date", threshold_time)
            .execute()
        )
        
        return response.data or []
    
    # ========================================
    # MAIN EVALUATION FUNCTION
    # ========================================
    @staticmethod
    def evaluate_all_triggers(task_data, trigger_context=None):
        """
        Evaluate all triggers and return list of triggered notifications.
        
        Args:
            task_data: Dict with task information
            trigger_context: Dict with additional context:
                - action: 'create', 'update', 'complete', 'comment'
                - old_status: Previous status (for updates)
                - changed_fields: List of changed fields (for updates)
                - comment_author_id: ID of comment author (for comments)
        
        Returns:
            List of trigger results that were triggered
        """
        triggered_results = []
        context = trigger_context or {}
        action = context.get('action', 'create')
        
        # Check Trigger 1: Task Assigned (on create or assignment change)
        if action in ['create', 'update']:
            assigned_to = task_data.get('assigned_to')
            if assigned_to:
                result = TaskNotificationTriggers.check_task_assigned(task_data, assigned_to)
                if result['triggered']:
                    triggered_results.append(result)
        
        # Check Trigger 2: Task Due Soon
        task_id = task_data.get('task_id')
        due_date = task_data.get('due_date')
        if task_id and due_date:
            result = TaskNotificationTriggers.check_task_due_soon(task_id, due_date)
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 3: Task Overdue
        if task_id and due_date:
            result = TaskNotificationTriggers.check_task_overdue(task_id, due_date)
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 4: Task Completed
        if action == 'complete':
            old_status = context.get('old_status')
            result = TaskNotificationTriggers.check_task_completed(task_data, old_status)
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 5: Task Updated
        if action == 'update':
            changed_fields = context.get('changed_fields', [])
            result = TaskNotificationTriggers.check_task_updated(task_data, changed_fields)
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 6: Comment Added
        if action == 'comment':
            comment_author_id = context.get('comment_author_id')
            result = TaskNotificationTriggers.check_task_comment(task_id, comment_author_id)
            if result['triggered']:
                triggered_results.append(result)
        
        return triggered_results