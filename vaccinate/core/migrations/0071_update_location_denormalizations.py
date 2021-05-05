from django.db import migrations

# https://github.com/CAVaccineInventory/vial/issues/224


def update_denormalizations(self):
    # Copied Location model method, hence the 'self'
    reports = (
        self.reports.all().prefetch_related("availability_tags").order_by("-created_at")
    )
    try:
        dn_latest_report = [r for r in reports if not r.is_pending_review][0]
    except IndexError:
        dn_latest_report = None
    try:
        dn_latest_report_including_pending = reports[0]
    except IndexError:
        dn_latest_report_including_pending = None
    dn_latest_yes_reports = [
        r
        for r in reports
        if not r.is_pending_review
        and any(t for t in r.availability_tags.all() if t.group == "yes")
    ]
    dn_yes_report_count = len(dn_latest_yes_reports)
    if dn_latest_yes_reports:
        dn_latest_yes_report = dn_latest_yes_reports[0]
    else:
        dn_latest_yes_report = None
    dn_latest_skip_reports = [
        r
        for r in reports
        if not r.is_pending_review
        and any(t for t in r.availability_tags.all() if t.group == "skip")
    ]
    dn_skip_report_count = len(dn_latest_skip_reports)
    if dn_latest_skip_reports:
        dn_latest_skip_report = dn_latest_skip_reports[0]
    else:
        dn_latest_skip_report = None
    dn_latest_non_skip_reports = [
        r
        for r in reports
        if not r.is_pending_review
        and not any(t for t in r.availability_tags.all() if t.group == "skip")
    ]
    if dn_latest_non_skip_reports:
        dn_latest_non_skip_report = dn_latest_non_skip_reports[0]
    else:
        dn_latest_non_skip_report = None

    # Has anything changed?
    def pk_or_none(record):
        if record is None:
            return None
        return record.pk

    if (
        self.dn_latest_report_id != pk_or_none(dn_latest_report)
        or self.dn_latest_report_including_pending_id
        != pk_or_none(dn_latest_report_including_pending)
        or self.dn_latest_yes_report_id != pk_or_none(dn_latest_yes_report)
        or self.dn_latest_skip_report_id != pk_or_none(dn_latest_skip_report)
        or self.dn_latest_non_skip_report_id != pk_or_none(dn_latest_non_skip_report)
        or self.dn_skip_report_count != dn_skip_report_count
        or self.dn_yes_report_count != dn_yes_report_count
    ):
        self.dn_latest_report = dn_latest_report
        self.dn_latest_report_including_pending = dn_latest_report_including_pending
        self.dn_latest_yes_report = dn_latest_yes_report
        self.dn_latest_skip_report = dn_latest_skip_report
        self.dn_latest_non_skip_report = dn_latest_non_skip_report
        self.dn_skip_report_count = dn_skip_report_count
        self.dn_yes_report_count = dn_yes_report_count
        self.save()


def populate_denormalized_reports(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    for location in (
        Location.objects.exclude(reports__isnull=True)
        .only(
            "dn_latest_report",
            "dn_latest_report_including_pending",
            "dn_latest_yes_report",
            "dn_latest_skip_report",
            "dn_latest_non_skip_report",
            "dn_skip_report_count",
            "dn_yes_report_count",
        )
        .distinct()
    ):
        update_denormalizations(location)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0070_more_denormalization_population"),
    ]

    operations = [
        migrations.RunPython(
            populate_denormalized_reports, reverse_code=lambda apps, schema_editor: None
        ),
    ]
