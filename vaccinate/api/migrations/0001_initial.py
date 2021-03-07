# Generated by Django 3.1.7 on 2021-03-03 20:19

import core.fields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0031_auto_20210303_2019"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiLog",
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
                (
                    "created_at",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now
                    ),
                ),
                (
                    "method",
                    core.fields.CharTextField(
                        help_text="The HTTP method", max_length=65000
                    ),
                ),
                (
                    "path",
                    core.fields.CharTextField(
                        help_text="The path, starting with /", max_length=65000
                    ),
                ),
                (
                    "query_string",
                    core.fields.CharTextField(
                        blank=True, help_text="The bit after the ?", max_length=65000
                    ),
                ),
                ("remote_ip", core.fields.CharTextField(max_length=65000)),
                (
                    "post_body",
                    models.BinaryField(
                        blank=True,
                        help_text="If the post body was not valid JSON, log it here as text",
                        null=True,
                    ),
                ),
                (
                    "post_body_json",
                    models.JSONField(
                        blank=True,
                        help_text="Post body if it was valid JSON",
                        null=True,
                    ),
                ),
                (
                    "response_status",
                    models.IntegerField(
                        help_text="HTTP status code returned by the API"
                    ),
                ),
                (
                    "response_body",
                    models.BinaryField(
                        blank=True,
                        help_text="If the response body was not valid JSON",
                        null=True,
                    ),
                ),
                (
                    "response_body_json",
                    models.JSONField(
                        blank=True, help_text="Response body if it was JSON", null=True
                    ),
                ),
                (
                    "created_report",
                    models.ForeignKey(
                        blank=True,
                        help_text="Report that was created by this API call, if any",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_by_api_logs",
                        to="core.report",
                    ),
                ),
            ],
            options={
                "db_table": "api_log",
            },
        ),
    ]
