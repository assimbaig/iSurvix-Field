from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('core','0022_assignment_intake'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField(model_name='photoevidence',name='group',field=models.CharField(blank=True,default='',max_length=20)),
        migrations.CreateModel(name='PhotoPlacement',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('field_id',models.CharField(max_length=80)),('section_id',models.CharField(max_length=80)),
            ('status',models.CharField(default='proposed',max_length=20)),('confidence',models.CharField(default='low',max_length=10)),
            ('reason',models.TextField(blank=True)),('uncertainty',models.CharField(default='high',max_length=10)),
            ('schema_digest',models.CharField(max_length=64)),('reviewed_at',models.DateTimeField(null=True)),('created_at',models.DateTimeField(auto_now_add=True)),
            ('job',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='placements',to='core.photojob')),
            ('photo',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='placements',to='core.photoevidence')),
            ('reviewed_by',models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='+',to=settings.AUTH_USER_MODEL)),
        ],options={'constraints':[models.UniqueConstraint(fields=('photo','field_id'),name='unique_photo_field_placement')]}),
    ]
