from django.db import migrations


appointment_tag_slugs = {
    "County website": "county_website",
    "myturn.ca.gov": "myturn_ca_gov",
    "web": "web",
    "phone": "phone",
    "other": "other",
}


def populate_appointment_tags(apps, schema_editor):
    AppointmentTag = apps.get_model("core", "AppointmentTag")
    for name, slug in appointment_tag_slugs.items():
        tag = AppointmentTag.objects.get(name=name)
        tag.slug = slug
        tag.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_appointmenttag_slug"),
    ]

    operations = [
        migrations.RunPython(populate_appointment_tags),
    ]
