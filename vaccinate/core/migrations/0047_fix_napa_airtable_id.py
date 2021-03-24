from django.db import migrations


def fix_napa(apps, schema_editor):
    # https://github.com/CAVaccineInventory/vial/issues/52#issuecomment-804492169
    County = apps.get_model("core", "County")
    County.objects.filter(airtable_id="recJ1fLYsngDaIRLG").update(
        airtable_id="recjptepZLP1mzVDC"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_rename_reports_to_report"),
    ]
    operations = [
        migrations.RunPython(fix_napa, reverse_code=lambda apps, schema_editor: None)
    ]
