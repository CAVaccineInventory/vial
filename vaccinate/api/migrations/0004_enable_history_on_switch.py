# from django.core.management import call_command
from django.db import migrations


def create_initial_revisions(apps, schema_editor):
    # call_command("createinitialrevisions", "api.Switch")
    # This broke the test suite, so I have disabled it
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_switch"),
        ("reversion", "0001_squashed_0004_auto_20160611_1202"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_revisions, reverse_code=lambda apps, schema_editor: None
        )
    ]
