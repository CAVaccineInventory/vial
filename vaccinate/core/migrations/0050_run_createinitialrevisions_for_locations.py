from django.core.management import call_command
from django.db import migrations


def create_initial_revisions(apps, schema_editor):
    call_command("createinitialrevisions", "core.Location")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_delete_is_test_data_columns"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_revisions, reverse_code=lambda apps, schema_editor: None
        )
    ]
