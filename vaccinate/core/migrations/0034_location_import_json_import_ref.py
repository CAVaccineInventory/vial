from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_add_location_type_unknown"),
    ]

    operations = [
        migrations.AddField(
            model_name="location",
            name="import_json",
            field=models.JSONField(
                blank=True,
                help_text="Original JSON if this record was imported from elsewhere",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="location",
            name="import_ref",
            field=models.SlugField(
                blank=True,
                help_text="If imported, unique identifier in the system it was imported from",
                null=True,
            ),
        ),
    ]
