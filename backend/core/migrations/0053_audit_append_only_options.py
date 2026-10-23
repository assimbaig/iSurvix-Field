from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('core', '0052_temporary_login_throttle')]

    operations = [
        migrations.AlterModelOptions(
            name='governanceaudit',
            options={'base_manager_name': 'objects', 'ordering': ['-created_at', '-pk']},
        ),
    ]
