from django.db import migrations


def add_review_tag(apps, schema_editor):
    LocationReviewTag = apps.get_model("core", "LocationReviewTag")
    LocationReviewTag.objects.get_or_create(tag="Approved")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0152_update_location_field_help_text"),
    ]

    operations = [
        migrations.RunPython(
            add_review_tag, reverse_code=lambda apps, schema_editor: None
        ),
    ]
