from django.db import migrations


def add_location_type(apps, schema_editor):
    LocationType = apps.get_model("core", "LocationType")
    LocationType.objects.get_or_create(name="Homebound")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0150_add_location_review_note_and_location_review_tag"),
    ]

    operations = [
        migrations.RunPython(add_location_type),
    ]
