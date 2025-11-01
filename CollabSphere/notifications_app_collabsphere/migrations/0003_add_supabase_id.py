"""Add supabase_id field to Notification

Generated manually to add the supabase_id integer field for linking to Supabase notifications table.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications_app_collabsphere', '0002_notification_deadline_notification_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='supabase_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
