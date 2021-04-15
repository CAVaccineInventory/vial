from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0089_importrun_sourcelocation"),
    ]

    operations = [
        CreateExtension(name="fuzzystrmatch"),
    ]
