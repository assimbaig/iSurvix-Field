from django.conf import settings
from django.db import migrations, models
from django.db.models import F
import django.db.models.deletion
import django.utils.timezone


def preserve_session_activity(apps, schema_editor):
    # Legacy open sessions last showed activity when they were created. Do not
    # manufacture a fresh heartbeat that would hide an abandoned upload.
    apps.get_model('core', 'SurveyUploadSession').objects.update(heartbeat_at=F('created_at'))


class Migration(migrations.Migration):
    dependencies = [('core', '0047_checklist_disabled_state'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='surveyuploadsession', name='heartbeat_at',
                            field=models.DateTimeField(default=django.utils.timezone.now)),
        migrations.AddField(model_name='surveyuploadsession', name='active_until', field=models.DateTimeField(null=True)),
        migrations.AddField(model_name='surveyuploadsession', name='active_batches', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='surveyuploadsession', name='interrupted_at', field=models.DateTimeField(null=True)),
        migrations.AddField(model_name='surveyuploadsession', name='recovered_by',
                            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                related_name='recovered_survey_upload_sessions', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='surveyuploadsession', name='recovery_reason', field=models.CharField(blank=True, max_length=1000)),
        migrations.RunPython(preserve_session_activity, migrations.RunPython.noop),
        migrations.CreateModel(name='SurveyUploadSessionEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('action', models.CharField(max_length=32)),
            ('reason', models.CharField(blank=True, max_length=1000)),
            ('payload', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ('session', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='core.surveyuploadsession')),
        ], options={'abstract': False}),
    ]
