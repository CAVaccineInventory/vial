# Generated by Django 3.2.4 on 2021-07-02 23:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0154_add_vts_priorty_to_county"),
    ]

    operations = [
        migrations.AlterField(
            model_name="county",
            name="vts_priorty",
            field=models.IntegerField(
                blank=True, null=True, unique=True, verbose_name="VTS priorty"
            ),
        ),
    ]