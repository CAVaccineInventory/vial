from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/177


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
        try:
            dn_latest_report_including_pending = reports[0]
        except IndexError:
            dn_latest_report_including_pending = None
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
        try:
            dn_latest_non_skip_report = [
                r
                for r in reports
                if not r.is_pending_review
                and not any(t for t in r.availability_tags.all() if t.group == "skip")
            ][0]
        except IndexError:
            dn_latest_non_skip_report = None
        location.dn_latest_report = dn_latest_report
        location.dn_latest_report_including_pending = dn_latest_report_including_pending
        location.dn_latest_yes_report = dn_latest_yes_report
        location.dn_latest_skip_report = dn_latest_skip_report
        location.dn_latest_non_skip_report = dn_latest_non_skip_report
        location.dn_skip_report_count = len(
            [
                r
                for r in reports
                if not r.is_pending_review
                and any(t for t in r.availability_tags.all() if t.group == "skip")
            ]
        )
        location.dn_yes_report_count = len(
            [
                r
                for r in reports
                if not r.is_pending_review
                and any(t for t in r.availability_tags.all() if t.group == "yes")
            ]
        )
        location.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0069_more_location_denormalizations"),
    ]

    operations = [
        migrations.RunPython(
            populate_denormalized_reports, reverse_code=lambda apps, schema_editor: None
        ),
    ]
