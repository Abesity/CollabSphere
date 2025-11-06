# notification_triggers.py
"""
This module defines notification rules (triggers) for event-related actions.
It does not directly send notifications — it just evaluates which should fire.
"""

class EventNotificationTriggers:
    @staticmethod
    def evaluate_all_triggers(event_data, context):
        """
        Evaluates all possible event triggers and returns a list of triggered notifications.
        :param event_data: dict containing event details (event_ID, title, date, etc.)
        :param context: dict describing the action (action type, actor, changes, etc.)
        :return: list of triggered notifications
        """
        action = context.get('action')
        triggered = []

        if action == 'create':
            triggered.append({
                'trigger_type': 'event_created',
                'message': f"New event '{event_data.get('title', 'Untitled')}' has been created.",
                'event_ID': event_data.get('event_ID')
            })

        elif action == 'update':
            changed_fields = context.get('changed_fields', [])
            if 'date' in changed_fields or 'time' in changed_fields:
                triggered.append({
                    'trigger_type': 'event_rescheduled',
                    'message': f"Event '{event_data.get('title', 'Untitled')}' has been rescheduled.",
                    'event_ID': event_data.get('event_ID')
                })
            elif 'title' in changed_fields or 'description' in changed_fields:
                triggered.append({
                    'trigger_type': 'event_updated',
                    'message': f"Event '{event_data.get('title', 'Untitled')}' details were updated.",
                    'event_ID': event_data.get('event_ID')
                })

        elif action == 'delete':
            triggered.append({
                'trigger_type': 'event_deleted',
                'message': f"Event '{event_data.get('title', 'Untitled')}' has been deleted.",
                'event_ID': event_data.get('event_ID')
            })

        return triggered
