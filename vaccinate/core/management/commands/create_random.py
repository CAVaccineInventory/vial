from argparse import ArgumentParser, ArgumentTypeError

from core.factories import LocationFactory, ReporterFactory
from core.models import County
from django.core.management.base import BaseCommand
from django.db import transaction


def check_positive(value):
    try:
        value = int(value)
        if value <= 0:
            raise ArgumentTypeError("{} is not a positive integer".format(value))
    except ValueError:
        raise Exception("{} is not an integer".format(value))
    return value


class Command(BaseCommand):
    help = "Generates test data"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--locations",
            type=check_positive,
            default=0,
            help="How many locations to create",
        )
        parser.add_argument(
            "--reporters",
            type=check_positive,
            default=0,
            help="How many reporters to create",
        )

    @transaction.atomic
    def handle(self, *args, **options: int):
        if not (options["locations"] or options["reporters"]):
            print("Provide either --locations or --reporters")
            return

        if options["locations"]:
            if County.objects.count() == 58:
                print(
                    "Run ./manage.py import_counties to generate counties for all of the US first"
                )
                return
            for _ in range(options["locations"]):
                LocationFactory()

        for _ in range(options["reporters"]):
            ReporterFactory()
