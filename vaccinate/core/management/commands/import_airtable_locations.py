import json

from core.import_utils import import_airtable_location, load_airtable_backup
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
            content = load_airtable_backup("backups/Locations.json", token=github_token)
        else:
            content = open(json_file).read()
        locations = json.loads(content)
        for location in locations:
            try:
                import_airtable_location(location)
            except AssertionError as e:
                print(
                    "Skipping {} [name={}], reason={}".format(
                        location["airtable_id"], location.get("Name"), str(e)
                    )
                )
                continue
