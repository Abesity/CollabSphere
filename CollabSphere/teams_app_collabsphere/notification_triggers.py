from django.conf import settings
from django.utils import timezone
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class TeamNotificationTriggers:
    """
    Defines all notification triggers for team management.
    
    TRIGGER LIST:
    1. TEAM_CREATED - New team created
    2. MEMBER_ADDED - User added to team
    3. MEMBER_REMOVED - User removed from team
    4. TEAM_UPDATED - Team details changed
    5. OWNER_CHANGED - Team ownership transferred
    6. TEAM_DELETED - Team deleted
    """
    
    # ========================================
    # TRIGGER 1: TEAM CREATED
    # ========================================
    @staticmethod
    def check_team_created(team_data, creator_id, member_ids):
        """
        Trigger: New team created
        Condition: Team successfully created
        Priority: MEDIUM
        Recipients: All team members (excluding creator)
        """
        return {
            'triggered': True,
            'trigger_type': 'TEAM_CREATED',
            'priority': 'medium',
            'message': f'New team created: {team_data.get("team_name", "Untitled Team")}',
            'recipients': ['team_members'],
            'team_id': team_data.get('team_ID'),
            'team_name': team_data.get('team_name'),
            'creator_id': creator_id,
            'member_ids': member_ids,
            'exclude_user': creator_id  # Don't notify creator
        }
    
    # ========================================
    # TRIGGER 2: MEMBER ADDED
    # ========================================
    @staticmethod
    def check_member_added(team_data, added_member_ids, added_by_user_id):
        """
        Trigger: User(s) added to team
        Condition: New member(s) added to existing team
        Priority: MEDIUM
        Recipients: Newly added members
        """
        if added_member_ids and len(added_member_ids) > 0:
            return {
                'triggered': True,
                'trigger_type': 'MEMBER_ADDED',
                'priority': 'medium',
                'message': f'Added to team: {team_data.get("team_name", "Untitled Team")}',
                'recipients': ['added_members'],
                'team_id': team_data.get('team_ID'),
                'team_name': team_data.get('team_name'),
                'added_member_ids': added_member_ids,
                'added_by': added_by_user_id
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 3: MEMBER REMOVED
    # ========================================
    @staticmethod
    def check_member_removed(team_data, removed_member_ids, removed_by_user_id):
        """
        Trigger: User(s) removed from team
        Condition: Member(s) removed from team
        Priority: MEDIUM
        Recipients: Removed members
        """
        if removed_member_ids and len(removed_member_ids) > 0:
            return {
                'triggered': True,
                'trigger_type': 'MEMBER_REMOVED',
                'priority': 'medium',
                'message': f'Removed from team: {team_data.get("team_name", "Untitled Team")}',
                'recipients': ['removed_members'],
                'team_id': team_data.get('team_ID'),
                'team_name': team_data.get('team_name'),
                'removed_member_ids': removed_member_ids,
                'removed_by': removed_by_user_id
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 4: TEAM UPDATED
    # ========================================
    @staticmethod
    def check_team_updated(team_data, changed_fields, updated_by_user_id):
        """
        Trigger: Team details updated
        Condition: Important fields changed (team_name, description)
        Priority: LOW
        Recipients: All team members (excluding updater)
        """
        important_fields = ['team_name', 'description']
        
        # Check if any important field was changed
        has_important_changes = any(field in changed_fields for field in important_fields)
        
        if has_important_changes:
            return {
                'triggered': True,
                'trigger_type': 'TEAM_UPDATED',
                'priority': 'low',
                'message': f'Team updated: {", ".join(changed_fields)}',
                'recipients': ['team_members'],
                'team_id': team_data.get('team_ID'),
                'team_name': team_data.get('team_name'),
                'changed_fields': changed_fields,
                'updated_by': updated_by_user_id,
                'exclude_user': updated_by_user_id  # Don't notify updater
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 5: OWNER CHANGED
    # ========================================
    @staticmethod
    def check_owner_changed(team_data, old_owner_id, new_owner_id):
        """
        Trigger: Team ownership transferred
        Condition: Team owner changed
        Priority: HIGH
        Recipients: New owner + Old owner + All team members
        """
        if old_owner_id != new_owner_id:
            return {
                'triggered': True,
                'trigger_type': 'OWNER_CHANGED',
                'priority': 'high',
                'message': f'Team ownership transferred: {team_data.get("team_name", "Untitled Team")}',
                'recipients': ['new_owner', 'old_owner', 'team_members'],
                'team_id': team_data.get('team_ID'),
                'team_name': team_data.get('team_name'),
                'old_owner_id': old_owner_id,
                'new_owner_id': new_owner_id
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 6: TEAM DELETED
    # ========================================
    @staticmethod
    def check_team_deleted(team_data, deleted_by_user_id):
        """
        Trigger: Team deleted
        Condition: Team removed from system
        Priority: HIGH
        Recipients: All team members (excluding deleter)
        """
        return {
            'triggered': True,
            'trigger_type': 'TEAM_DELETED',
            'priority': 'high',
            'message': f'Team deleted: {team_data.get("team_name", "Untitled Team")}',
            'recipients': ['team_members'],
            'team_id': team_data.get('team_ID'),
            'team_name': team_data.get('team_name'),
            'deleted_by': deleted_by_user_id,
            'exclude_user': deleted_by_user_id  # Don't notify deleter
        }
    
    # ========================================
    # HELPER: Detect Member Changes
    # ========================================
    @staticmethod
    def detect_member_changes(old_member_ids, new_member_ids):
        """
        Compare old and new member lists to detect additions and removals.
        
        Args:
            old_member_ids: List of member IDs before update
            new_member_ids: List of member IDs after update
        
        Returns:
            Dict with 'added' and 'removed' member ID lists
        """
        old_set = set(old_member_ids) if old_member_ids else set()
        new_set = set(new_member_ids) if new_member_ids else set()
        
        added = list(new_set - old_set)
        removed = list(old_set - new_set)
        
        return {
            'added': added,
            'removed': removed,
            'has_changes': len(added) > 0 or len(removed) > 0
        }
    
    # ========================================
    # HELPER: Get Team Members
    # ========================================
    @staticmethod
    def get_team_member_ids(team_id):
        """
        Get all member IDs for a team.
        
        Args:
            team_id: Team ID
        
        Returns:
            List of user IDs
        """
        try:
            response = (
                supabase.table("user_team")
                .select("user_id")
                .eq("team_ID", team_id)
                .execute()
            )
            
            return [member['user_id'] for member in response.data]
        except Exception as e:
            print(f"Error fetching team members: {e}")
            return []
    
    # ========================================
    # MAIN EVALUATION FUNCTION
    # ========================================
    @staticmethod
    def evaluate_all_triggers(team_data, trigger_context=None):
        """
        Evaluate all triggers and return list of triggered notifications.
        
        Args:
            team_data: Dict with team information
            trigger_context: Dict with additional context:
                - action: 'create', 'update', 'delete'
                - creator_id: ID of user who created team
                - member_ids: List of member IDs (for create)
                - old_member_ids: Previous member list (for update)
                - new_member_ids: Updated member list (for update)
                - changed_fields: List of changed fields (for update)
                - old_owner_id: Previous owner (for owner change)
                - updated_by: ID of user who made update
        
        Returns:
            List of trigger results that were triggered
        """
        triggered_results = []
        context = trigger_context or {}
        action = context.get('action', 'create')
        
        # Check Trigger 1: Team Created
        if action == 'create':
            creator_id = context.get('creator_id')
            member_ids = context.get('member_ids', [])
            
            result = TeamNotificationTriggers.check_team_created(
                team_data, 
                creator_id, 
                member_ids
            )
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 2 & 3: Member Added/Removed
        if action == 'update':
            old_member_ids = context.get('old_member_ids', [])
            new_member_ids = context.get('new_member_ids', [])
            updated_by = context.get('updated_by')
            
            # Detect member changes
            member_changes = TeamNotificationTriggers.detect_member_changes(
                old_member_ids, 
                new_member_ids
            )
            
            # Trigger 2: Members Added
            if member_changes['added']:
                result = TeamNotificationTriggers.check_member_added(
                    team_data, 
                    member_changes['added'], 
                    updated_by
                )
                if result['triggered']:
                    triggered_results.append(result)
            
            # Trigger 3: Members Removed
            if member_changes['removed']:
                result = TeamNotificationTriggers.check_member_removed(
                    team_data, 
                    member_changes['removed'], 
                    updated_by
                )
                if result['triggered']:
                    triggered_results.append(result)
        
        # Check Trigger 4: Team Updated
        if action == 'update':
            changed_fields = context.get('changed_fields', [])
            updated_by = context.get('updated_by')
            
            result = TeamNotificationTriggers.check_team_updated(
                team_data, 
                changed_fields, 
                updated_by
            )
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 5: Owner Changed
        if action == 'update':
            old_owner_id = context.get('old_owner_id')
            new_owner_id = team_data.get('owner_id')
            
            if old_owner_id and new_owner_id:
                result = TeamNotificationTriggers.check_owner_changed(
                    team_data, 
                    old_owner_id, 
                    new_owner_id
                )
                if result['triggered']:
                    triggered_results.append(result)
        
        # Check Trigger 6: Team Deleted
        if action == 'delete':
            deleted_by = context.get('deleted_by')
            
            result = TeamNotificationTriggers.check_team_deleted(
                team_data, 
                deleted_by
            )
            if result['triggered']:
                triggered_results.append(result)
        
        return triggered_results