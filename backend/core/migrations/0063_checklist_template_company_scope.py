from django.db import migrations, models
import django.db.models.deletion


def assign_unambiguous_template_companies(apps, schema_editor):
    Template = apps.get_model('core', 'ChecklistTemplate')
    Project = apps.get_model('core', 'Project')
    Checklist = apps.get_model('core', 'Checklist')
    db = schema_editor.connection.alias

    for template in Template.objects.using(db).all().iterator():
        definition = template.definition if isinstance(template.definition, dict) else {}
        # Catalog standards remain platform-wide shared sources, never tenants'
        # editable property, even if a historical project happens to use one.
        if definition.get('standard_catalog'):
            continue
        companies = set(Project.objects.using(db).filter(checklist_template_id=template.pk)
                        .exclude(company_id__isnull=True).values_list('company_id', flat=True))
        companies.update(Checklist.objects.using(db).filter(checklist_template_id=template.pk)
                         .exclude(project__company_id__isnull=True)
                         .values_list('project__company_id', flat=True))
        # Do not infer ownership from the creator's current company: accounts
        # can be reassigned, and that would silently transfer legacy records.
        # Creator-only legacy drafts remain private to their creator until an
        # owner explicitly classifies them.
        if len(companies) == 1:
            Template.objects.using(db).filter(pk=template.pk).update(company_id=next(iter(companies)))


class Migration(migrations.Migration):
    dependencies = [('core', '0062_release_notice_acknowledgement')]

    operations = [
        migrations.AddField(
            model_name='checklisttemplate',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='checklist_templates', to='core.company'),
        ),
        migrations.RunPython(assign_unambiguous_template_companies, migrations.RunPython.noop),
    ]
