import json

import httpx
from core.import_utils import (
    import_vaccinefinder_location,
    load_vaccinefinder_locations,
)
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="Path within the repo to .json file or directory containing JSON files",
        )
        parser.add_argument(
            "--github-token",
            help="GitHub access token to use to access the vaccine-feeds/raw-feed-data repo",
        )

    def handle(self, *args, **options):
        path = options["path"]
        github_token = options["github_token"]
        locations = load_vaccinefinder_locations(path, github_token)
        for location in locations:
            try:
                import_vaccinefinder_location(location)
            except Exception as inner_e:
                print(
                    "Skipping {} {}, reason={}".format(
                        location["guid"], location["name"], str(inner_e)
                    )
                )
