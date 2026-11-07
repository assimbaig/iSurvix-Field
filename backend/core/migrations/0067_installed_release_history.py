from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('core','0066_data_exports')]
    operations=[migrations.CreateModel(name='InstalledRelease',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('release_key',models.CharField(max_length=80,unique=True)),
        ('version',models.CharField(max_length=32)),
        ('title',models.CharField(max_length=180)),
        ('release_date',models.DateField()),
        ('changes',models.JSONField(default=list)),
        ('first_seen_at',models.DateTimeField(auto_now_add=True)),
    ],options={'ordering':['-first_seen_at','-pk']})]
