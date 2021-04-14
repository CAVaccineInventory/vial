from django.db import migrations

from ..baseconverter import pid


def populate_public_id(apps, schema_editor):
    Provider = apps.get_model("core", "Provider")
    for provider in Provider.objects.exclude(public_id__startswith="rec"):
        provider.public_id = "p" + pid.from_int(provider.pk)
        provider.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0086_provider_airtable_id_fixes"),
    ]

    operations = [
        migrations.RunPython(
            populate_public_id, reverse_code=lambda apps, schema_editor: None
        ),
    ]
