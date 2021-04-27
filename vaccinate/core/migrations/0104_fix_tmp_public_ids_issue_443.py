from django.db import migrations

from ..baseconverter import pid

# https://github.com/CAVaccineInventory/vial/issues/443


def fix_bad_public_ids(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    for id in Location.objects.filter(public_id__startswith="tmp:").values_list(
        "pk", flat=True
    ):
        Location.objects.filter(pk=id).update(public_id="l" + pid.from_int(id))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0103_reporter_display_name"),
    ]

    operations = [
        migrations.RunPython(
            fix_bad_public_ids, reverse_code=lambda apps, schema_editor: None
        ),
    ]
