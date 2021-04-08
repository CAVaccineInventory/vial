import core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0062_add_review_tag_called_approved"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="vaccinespotter_location_id",
            field=core.fields.CharTextField(
                blank=True,
                help_text="This location's ID on vaccinespotter.org",
                max_length=65000,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="vaccinefinder_location_id",
            field=core.fields.CharTextField(
                blank=True,
                help_text="This location's ID on vaccinefinder.org",
                max_length=65000,
                null=True,
            ),
        ),
    ]
