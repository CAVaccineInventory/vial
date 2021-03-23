from django.db import migrations


def delete_test_reports(apps, schema_editor):
    # https://github.com/CAVaccineInventory/vial/issues/137
    Report = apps.get_model("core", "Report")
    Report.objects.filter(is_test_data=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0047_fix_napa_airtable_id"),
    ]
    operations = [
        migrations.RunPython(
            delete_test_reports, reverse_code=lambda apps, schema_editor: None
        )
    ]
