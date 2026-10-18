from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('core','0020_company_memberships'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='ChecklistAIReview', fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('model',models.CharField(max_length=160)),('snapshot_digest',models.CharField(max_length=64)),
        ('status',models.CharField(default='running',max_length=20)),('findings',models.JSONField(default=list)),
        ('error',models.CharField(blank=True,max_length=240)),('shared',models.BooleanField(default=False)),
        ('shared_at',models.DateTimeField(null=True)),('created_at',models.DateTimeField(auto_now_add=True)),
        ('checklist',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='ai_reviews',to='core.checklist')),
        ('requested_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='+',to=settings.AUTH_USER_MODEL)),
        ('shared_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='+',to=settings.AUTH_USER_MODEL)),
    ])]
