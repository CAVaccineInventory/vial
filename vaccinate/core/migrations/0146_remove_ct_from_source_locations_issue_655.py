from django.db import migrations


def remove_ct_from_source_locations(apps, schema_editor):
    ConcordanceIdentifier = apps.get_model("core", "ConcordanceIdentifier")
    ConcordanceIdentifier.source_locations.through.objects.filter(
        concordanceidentifier__authority__in=("ct_covidvaccinefinder_gov", "ct_gov")
    ).delete()
    ConcordanceIdentifier.objects.filter(
        authority__in=("ct_covidvaccinefinder_gov", "ct_gov")
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0145_add_and_backfill_is_pending_review"),
    ]

    operations = [
        migrations.RunPython(
            remove_ct_from_source_locations,
            reverse_code=lambda apps, schema_editor: None,
        ),
    ]
