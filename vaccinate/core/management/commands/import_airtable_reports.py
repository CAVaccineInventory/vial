import orjson
from core.import_utils import import_airtable_report, load_airtable_backup
from core.models import AvailabilityTag
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--github-token",
            help="GitHub access token to use to access the airtable-data-backup repo",
        )
        parser.add_argument(
            "--json-file",
            help="Path to JSON file on disk, to avoid making an HTTPS request to GitHub",
        )

    def handle(self, *args, **options):
        json_file = options["json_file"]
        github_token = options["github_token"]
        if not (json_file or github_token) or (json_file and github_token):
            raise CommandError(
                "Pass one of either --json-file or --github-token, but not both"
            )
        if github_token:
            content = load_airtable_backup("backups/Reports.json", token=github_token)
        else:
            content = open(json_file).read()
        reports = orjson.loads(content)
        # Load these once to avoid loading them on every call to
        # the import_availability_report function
        availability_tags = AvailabilityTag.objects.all()
        for report in reports:
            try:
                import_airtable_report(report, availability_tags)
            except AssertionError as e:
                print("Skipping {}, reason={}".format(report["airtable_id"], str(e)))
                continue
