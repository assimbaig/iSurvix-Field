from django.db import migrations, models
import django.db.models.deletion


def proven_issuance_bindings(apps, schema_editor):
    """Retain only a tenant explicitly recorded when the credential was issued.

    Old releases omitted this fact from their issue audit. Current ownership is
    not proof of past ownership: such credentials remain NULL and require a new
    authorized token. No credential, lease, source or job is removed or resumed.
    """
    Credential = apps.get_model('core', 'RemoteWorkerCredential')
    Audit = apps.get_model('core', 'GovernanceAudit')
    Profile = apps.get_model('core', 'Profile')
    Project = apps.get_model('core', 'Project')
    alias = schema_editor.connection.alias
    for credential in Credential.objects.using(alias).filter(issuing_company__isnull=True).iterator():
        events = list(Audit.objects.using(alias).filter(action='remote_worker.provisioned',
            details__credential_id=str(credential.pk)).values('actor_id', 'project_id', 'details'))
        if not events or any(event['actor_id'] != credential.created_by_id
                or not isinstance(event['details'], dict)
                or type(event['details'].get('company_id')) is not int for event in events):
            continue
        companies = {event['details']['company_id'] for event in events}
        project_ids = set(credential.projects.using(alias).values_list('pk', flat=True))
        if len(companies) != 1 or not project_ids or {event['project_id'] for event in events} != project_ids:
            continue
        company_id = companies.pop()
        projects = list(Project.objects.using(alias).filter(pk__in=project_ids).values('company_id', 'administrator_id'))
        profile = Profile.objects.using(alias).select_related('project', 'user').filter(user_id=credential.created_by_id).first()
        if (profile is None or not profile.user.is_active or profile.user.is_superuser
                or profile.is_locked or profile.role != 'ADMIN'
                or len(projects) != len(project_ids)
                or any(project['company_id'] != company_id
                    or project['administrator_id'] != credential.created_by_id for project in projects)):
            continue
        current_company = profile.company_id or (profile.project.company_id if profile.project_id else None)
        if company_id and current_company == company_id:
            Credential.objects.using(alias).filter(pk=credential.pk, issuing_company__isnull=True).update(issuing_company_id=company_id)


class Migration(migrations.Migration):
    dependencies = [('core', '0053_audit_append_only_options')]
    operations = [
        migrations.AddField(
            model_name='remoteworkercredential', name='issuing_company',
            field=models.ForeignKey(blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='issued_worker_credentials', to='core.company')),
        migrations.RunPython(proven_issuance_bindings, migrations.RunPython.noop),
    ]
