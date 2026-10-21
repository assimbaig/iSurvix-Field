from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0049_outbound_survey_worker')]
    operations = [
        migrations.AddField(model_name='remotesurveylease', name='versions', field=models.JSONField(default=dict)),
    ]
