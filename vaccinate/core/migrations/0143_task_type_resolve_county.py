from django.db import migrations


def create_task_type(apps, schema_editor):
    TaskType = apps.get_model("core", "TaskType")
    TaskType.objects.get_or_create(name="Resolve county")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0142_alter_location_preferred_contact_method"),
    ]

    operations = [
        migrations.RunPython(
            create_task_type, reverse_code=lambda apps, schema_editor: None
        ),
    ]
