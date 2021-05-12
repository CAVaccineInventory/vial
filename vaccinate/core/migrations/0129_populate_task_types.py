from django.db import migrations

task_types = (
    "Potential duplicate",
    "Confirm website",
    "Confirm address",
    "Confirm hours",
)


def populate_task_types(apps, schema_editor):
    TaskType = apps.get_model("core", "TaskType")
    for name in task_types:
        TaskType.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0128_task_tasktype"),
    ]

    operations = [
        migrations.RunPython(
            populate_task_types, reverse_code=lambda apps, schema_editor: None
        ),
    ]
