# Generated by Django 3.1.7 on 2021-03-01 22:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_unique_slug_on_reporter"),
    ]

    operations = [
        migrations.AlterField(
            model_name="report",
            name="appointment_tag",
            field=models.ForeignKey(
                help_text="a single appointment tag, indicating how appointments are made",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="core.appointmenttag",
            ),
        ),
        migrations.AlterField(
            model_name="report",
            name="availability_tags",
            field=models.ManyToManyField(
                db_table="call_report_availability_tag",
                related_name="reports",
                to="core.AvailabilityTag",
            ),
        ),
        migrations.AlterField(
            model_name="report",
            name="call_request",
            field=models.ForeignKey(
                blank=True,
                help_text="the call request that this report was based on, if any.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="core.callrequest",
            ),
        ),
        migrations.AlterField(
            model_name="report",
            name="location",
            field=models.ForeignKey(
                help_text="a report must have a location",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="core.location",
            ),
        ),
        migrations.AlterField(
            model_name="report",
            name="reported_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reports",
                to="core.reporter",
            ),
        ),
    ]
