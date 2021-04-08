import os
from argparse import ArgumentParser
from typing import Any, Dict, List, Sequence

from core import exporter
from core.exporter.storage import (
    DebugWriter,
    GoogleStorageWriter,
    LocalWriter,
    StorageWriter,
)
from core.management.base import BeelineCommand
from sentry_sdk import capture_exception

DEPLOYS: Dict[str, List[StorageWriter]] = {
    "testing": [
        LocalWriter("local/legacy"),
        LocalWriter("local/api/v1"),
    ],
    "staging": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync-staging"),
        GoogleStorageWriter("vaccinateca-api-staging", "v1"),
    ],
    "production": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync"),
        GoogleStorageWriter("vaccinateca-api", "v1"),
    ],
}


class Command(BeelineCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--only-version",
            type=int,
            action="append",
            help="Specify which API version to write out",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--noop",
            action="store_true",
            help="Print the output to STDOUT, instead of writing out anywhere",
        )
        group.add_argument(
            "--bucket",
            help="Upload to a specific bucket",
        )

    def handle(self, *args: Any, **options: Any):
        deploy_env = DEPLOYS[os.environ.get("DEPLOY", "testing")]

        if options["noop"]:
            deploy_env = [
                DebugWriter("legacy"),
                DebugWriter("api/v1"),
            ]
        elif options["bucket"]:
            deploy_env = [
                GoogleStorageWriter(options["bucket"], "legacy"),
                GoogleStorageWriter(options["bucket"], "api/v1"),
            ]

        versions: Sequence[int] = range(0, len(deploy_env))
        if options.get("only_version"):
            versions = sorted(options["only_version"])

        with exporter.dataset() as ds:
            for v in versions:
                try:
                    exporter.api(v, ds).write(deploy_env[v])
                except Exception as e:
                    capture_exception(e)
                    print(f"Failed to export version {v}: {e}")
