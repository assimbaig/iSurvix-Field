from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies=[('core','0061_workflow_email_delivery'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(
        name='ReleaseNoticeAcknowledgement',
        fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('release_key',models.CharField(max_length=80)),
            ('acknowledged_at',models.DateTimeField(auto_now_add=True)),
            ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                related_name='release_notice_acknowledgements',to=settings.AUTH_USER_MODEL)),
        ],
        options={'constraints':[models.UniqueConstraint(fields=('user','release_key'),name='unique_user_release_notice_ack')]},
    )]
