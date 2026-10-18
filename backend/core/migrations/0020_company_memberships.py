from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion


def preserve_legacy_scope(apps,schema_editor):
    alias=schema_editor.connection.alias
    Company=apps.get_model('core','Company')
    Project=apps.get_model('core','Project')
    Profile=apps.get_model('core','Profile')
    Membership=apps.get_model('core','ProjectMembership')
    if not Project.objects.using(alias).exists():
        return
    company,_=Company.objects.using(alias).get_or_create(name='Local legacy workspace',defaults={'description':'Organizational placeholder for projects created before company classification; project access remains explicitly scoped.'})
    Project.objects.using(alias).filter(company__isnull=True).update(company=company)
    for profile in Profile.objects.using(alias).exclude(project__isnull=True).iterator():
        project=Project.objects.using(alias).get(pk=profile.project_id)
        if profile.company_id is None:
            Profile.objects.using(alias).filter(pk=profile.pk).update(company_id=project.company_id)
        Membership.objects.using(alias).get_or_create(user_id=profile.user_id,project_id=profile.project_id,defaults={'is_active':True,'is_primary':True})



class Migration(migrations.Migration):
    dependencies=[('core','0019_client_review_routing'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='Company',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('name',models.CharField(max_length=160,unique=True)),
            ('description',models.TextField(blank=True)),
            ('created_at',models.DateTimeField(auto_now_add=True))],options={'ordering':['name']}),
        migrations.AddField(model_name='project',name='company',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='projects',to='core.company')),
        migrations.AddField(model_name='profile',name='company',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='profiles',to='core.company')),
        migrations.CreateModel(name='ProjectMembership',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('is_active',models.BooleanField(default=True)),('is_primary',models.BooleanField(default=False)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='project_memberships',to=settings.AUTH_USER_MODEL)),
            ('project',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='memberships',to='core.project')),
            ('granted_by',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='granted_project_memberships',to=settings.AUTH_USER_MODEL))],
            options={'constraints':[models.UniqueConstraint(fields=('user','project'),name='unique_user_project_membership')]}),
        migrations.RunPython(preserve_legacy_scope,migrations.RunPython.noop),
    ]
