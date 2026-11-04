"""Add reversible indexes for the existing task explorer's predicates/order."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0058_support_cases')]

    operations = [
        migrations.AddIndex(
            model_name='checklist',
            index=models.Index(fields=['project', '-updated_at', 'id'], name='ck_project_updated_page'),
        ),
        migrations.AddIndex(
            model_name='workassignment',
            index=models.Index(fields=['project', 'checklist', '-created_at', 'id'], name='wa_project_task_page'),
        ),
    ]
