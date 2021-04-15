from django.db import migrations


def create_switch(apps, schema_editor):
    Switch = apps.get_model("api", "Switch")
    Switch.objects.get_or_create(name="disable_api")



class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_switch_verbose_name_plural'),
    ]

    operations = [
        migrations.RunPython(
            create_switch, reverse_code=lambda apps, schema_editor: None
        ),
    ]
