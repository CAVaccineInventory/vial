from django.db import migrations

from ..baseconverter import pid


def populate_public_id(apps, schema_editor):
    Provider = apps.get_model("core", "Provider")
    for provider in Provider.objects.filter(public_id__isnull=True):
        provider.public_id = pid.from_int(provider.pk)
        provider.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0081_provider_extra_fields"),
    ]

    operations = [
        migrations.RunPython(
            populate_public_id, reverse_code=lambda apps, schema_editor: None
        ),
    ]
