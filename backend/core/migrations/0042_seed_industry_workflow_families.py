from django.db import migrations


def seed_families(apps,schema_editor):
    Industry=apps.get_model('core','IndustryCatalog')
    for family in ('telecom','construction'):
        Industry.objects.using(schema_editor.connection.alias).filter(code=family).update(workflow_family=family)


class Migration(migrations.Migration):
    dependencies=[('core','0041_industry_descriptions_and_families')]
    operations=[migrations.RunPython(seed_families,migrations.RunPython.noop)]
