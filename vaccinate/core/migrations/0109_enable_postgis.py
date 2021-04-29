from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_availabilitytag_planned_closure_report_source"),
    ]

    operations = [
        CreateExtension("postgis"),
    ]
