from django.db import migrations


def add_review_tag(apps, schema_editor):
    ReportReviewTag = apps.get_model("core", "ReportReviewTag")
    ReportReviewTag.objects.get_or_create(
        tag="Approved",
        description="Use this tag to mark a report as approved, removing the is_pending_review flag",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_report_is_pending_review"),
    ]

    operations = [
        migrations.RunPython(
            add_review_tag, reverse_code=lambda apps, schema_editor: None
        ),
    ]
