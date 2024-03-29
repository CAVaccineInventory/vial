# Generated by Django 3.1.8 on 2021-04-14 22:38

import core.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0083_provider_public_id_now_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderPhase",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", core.fields.CharTextField(max_length=65000, unique=True)),
            ],
            options={
                "db_table": "provider_phase",
            },
        ),
        migrations.AddField(
            model_name="provider",
            name="phases",
            field=models.ManyToManyField(
                blank=True,
                db_table="provider_provider_phase",
                related_name="providers",
                to="core.ProviderPhase",
            ),
        ),
    ]
