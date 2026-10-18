from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies=[('core','0021_checklist_ai_review'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='checklist',name='intake_metadata',field=models.JSONField(blank=True,default=dict)),
        migrations.CreateModel(name='AssignmentIntakeBatch',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('source_filename',models.CharField(max_length=255)),('source_sha256',models.CharField(max_length=64)),
            ('rows',models.JSONField(default=list)),('errors',models.JSONField(default=list)),('schema_fingerprints',models.JSONField(default=dict)),
            ('status',models.CharField(default='preview',max_length=20)),('result_ids',models.JSONField(default=list)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('expires_at',models.DateTimeField()),('committed_at',models.DateTimeField(blank=True,null=True)),
            ('requested_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to=settings.AUTH_USER_MODEL))])]
