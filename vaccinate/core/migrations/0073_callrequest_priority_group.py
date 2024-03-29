# Generated by Django 3.1.8 on 2021-04-10 17:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0072_soft_deleted_on_reports"),
    ]

    operations = [
        migrations.AddField(
            model_name="callrequest",
            name="priority_group",
            field=models.IntegerField(
                choices=[
                    (1, "1-critical"),
                    (2, "2-important"),
                    (3, "3-normal"),
                    (4, "4-low"),
                    (99, "99-not_prioritized"),
                ],
                default=99,
            ),
        ),
    ]
