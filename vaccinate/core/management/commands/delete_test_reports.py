from core.models import Report
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    "Delete all test data from the Report table"

    def handle(self, *args, **options):
        print("Deleted: {}".format(Report.objects.filter(is_test_data=True).delete()))
