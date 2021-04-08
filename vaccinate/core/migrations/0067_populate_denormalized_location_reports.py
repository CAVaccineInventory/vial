from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/193


def populate_denormalized_reports(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    for location in Location.objects.exclude(reports__isnull=True).distinct():
        reports = list(
            location.reports.all()
            .prefetch_related("availability_tags")
            .order_by("created_at")
        )
        try:
            dn_latest_report = [r for r in reports if not r.is_pending_review][0]
        except IndexError:
            dn_latest_report = None
        dn_latest_report_including_pending = reports[0]
        try:
            dn_latest_yes_report = [
                r
                for r in reports
                if not r.is_pending_review
                and any(t for t in r.availability_tags.all() if t.group == "yes")
            ][0]
        except IndexError:
            dn_latest_yes_report = None
        try:
            dn_latest_skip_report = [
                r
                for r in reports
                if not r.is_pending_review
                and any(t for t in r.availability_tags.all() if t.group == "skip")
            ][0]
        except IndexError:
            dn_latest_skip_report = None
        location.dn_latest_report = dn_latest_report
        location.dn_latest_report_including_pending = dn_latest_report_including_pending
        location.dn_latest_yes_report = dn_latest_yes_report
        location.dn_latest_skip_report = dn_latest_skip_report
        location.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0066_location_denormalized_latest_reports"),
    ]

    operations = [
        migrations.RunPython(
            populate_denormalized_reports, reverse_code=lambda apps, schema_editor: None
        ),
    ]
