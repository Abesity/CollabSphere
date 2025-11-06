from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from supabase import create_client

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


class CheckinNotificationTriggers:
    """
    Defines all notification triggers for wellbeing check-ins.
    
    TRIGGER LIST:
    1. LOW_MOOD - User submits "Needs Support" status
    2. MISSED_CHECKIN - No check-in for 3+ days
    3. DECLINING_TREND - 3 consecutive declining moods
    4. CONSECUTIVE_LOW - 3+ consecutive "Needs Support" statuses
    """
    
    # ========================================
    # TRIGGER 1: LOW MOOD ALERT
    # ========================================
    @staticmethod
    def check_low_mood(checkin_data):
        """
        Trigger: Immediate low mood detection
        Condition: status == "Needs Support"
        Priority: HIGH
        Recipients: User + Manager
        """
        if checkin_data and checkin_data.get('status') == 'Needs Support':
            return {
                'triggered': True,
                'trigger_type': 'LOW_MOOD',
                'priority': 'high',
                'message': 'User indicated they need support',
                'recipients': ['user', 'manager']
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 2: MISSED CHECK-IN REMINDER
    # ========================================
    @staticmethod
    def check_missed_checkin(user_id, days_threshold=3):
        """
        Trigger: Missed check-in reminder
        Condition: No check-in for 3+ days
        Priority: MEDIUM
        Recipients: User only
        """
        cutoff_date = (timezone.now() - timedelta(days=days_threshold)).isoformat()
        
        response = (
            supabase.table("wellbeingcheckin")
            .select("checkin_id")
            .eq("user_id", user_id)
            .gte("date_submitted", cutoff_date)
            .execute()
        )
        
        if len(response.data) == 0:
            return {
                'triggered': True,
                'trigger_type': 'MISSED_CHECKIN',
                'priority': 'medium',
                'message': f'No check-in for {days_threshold}+ days',
                'recipients': ['user']
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 3: DECLINING TREND ALERT
    # ========================================
    @staticmethod
    def check_declining_trend(user_id, lookback_count=3):
        """
        Trigger: Declining mood trend
        Condition: 3 consecutive declining moods (Good -> Okay -> Needs Support)
        Priority: HIGH
        Recipients: User + Manager
        """
        response = (
            supabase.table("wellbeingcheckin")
            .select("status")
            .eq("user_id", user_id)
            .order("date_submitted", desc=True)
            .limit(lookback_count)
            .execute()
        )
        
        if len(response.data) < lookback_count:
            return {'triggered': False}
        
        # Convert status to numeric values
        mood_values = []
        for checkin in response.data:
            status = checkin.get('status')
            if status == 'Good':
                mood_values.append(2)
            elif status == 'Okay':
                mood_values.append(1)
            elif status == 'Needs Support':
                mood_values.append(0)
        
        # Check if declining (each mood lower than previous)
        is_declining = all(mood_values[i] < mood_values[i+1] for i in range(len(mood_values)-1))
        
        if is_declining:
            return {
                'triggered': True,
                'trigger_type': 'DECLINING_TREND',
                'priority': 'high',
                'message': 'Mood declining over last 3 check-ins',
                'recipients': ['user', 'manager']
            }
        return {'triggered': False}
    
    # ========================================
    # TRIGGER 4: CONSECUTIVE LOW MOODS
    # ========================================
    @staticmethod
    def check_consecutive_low_moods(user_id, consecutive_count=3):
        """
        Trigger: Multiple consecutive low moods
        Condition: 3+ consecutive "Needs Support" statuses
        Priority: CRITICAL
        Recipients: User + Manager + HR
        """
        response = (
            supabase.table("wellbeingcheckin")
            .select("status")
            .eq("user_id", user_id)
            .order("date_submitted", desc=True)
            .limit(consecutive_count)
            .execute()
        )
        
        if len(response.data) < consecutive_count:
            return {'triggered': False}
        
        # Check if all are "Needs Support"
        all_needs_support = all(
            checkin.get('status') == 'Needs Support' 
            for checkin in response.data
        )
        
        if all_needs_support:
            return {
                'triggered': True,
                'trigger_type': 'CONSECUTIVE_LOW',
                'priority': 'critical',
                'message': f'{consecutive_count}+ consecutive "Needs Support" check-ins',
                'recipients': ['user', 'manager', 'hr']
            }
        return {'triggered': False}
    
    # ========================================
    # MAIN EVALUATION FUNCTION
    # ========================================
    @staticmethod
    def evaluate_all_triggers(user_id, checkin_data=None):
        """
        Evaluate all triggers and return list of triggered notifications.
        
        Args:
            user_id: User's Supabase ID
            checkin_data: Optional dict with latest check-in data
        
        Returns:
            List of trigger results that were triggered
        """
        triggered_results = []
        
        # Check Trigger 1: Low Mood (requires checkin_data)
        if checkin_data:
            result = CheckinNotificationTriggers.check_low_mood(checkin_data)
            if result['triggered']:
                triggered_results.append(result)
        
        # Check Trigger 2: Missed Check-in
        result = CheckinNotificationTriggers.check_missed_checkin(user_id)
        if result['triggered']:
            triggered_results.append(result)
        
        # Check Trigger 3: Declining Trend
        result = CheckinNotificationTriggers.check_declining_trend(user_id)
        if result['triggered']:
            triggered_results.append(result)
        
        # Check Trigger 4: Consecutive Low Moods (requires checkin_data)
        if checkin_data:
            result = CheckinNotificationTriggers.check_consecutive_low_moods(user_id)
            if result['triggered']:
                triggered_results.append(result)
        
        return triggered_results