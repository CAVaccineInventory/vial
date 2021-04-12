import datetime

from django.contrib.admin import DateFieldListFilter
from django.utils import timezone


class DateYesterdayFieldListFilter(DateFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)

        self.links = list(self.links)
        self.links.insert(
            2,
            (
                "Yesterday",
                {
                    self.lookup_kwarg_since: str(yesterday),
                    self.lookup_kwarg_until: str(today),
                },
            ),
        )
