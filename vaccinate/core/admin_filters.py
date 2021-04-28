import datetime

from django.contrib.admin import DateFieldListFilter, SimpleListFilter
from django.contrib.postgres.fields import ArrayField
from django.db import connection
from django.db.models import F, IntegerField, TextField, Value
from django.db.models.expressions import Func
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


def make_csv_filter(
    filter_title, filter_parameter_name, table, column, queryset_column=None
):
    queryset_column = queryset_column or column

    class CommaSeparatedValuesFilter(SimpleListFilter):
        title = filter_title
        parameter_name = filter_parameter_name

        def lookups(self, request, model_admin):
            sql = """
                select distinct unnest(
                    regexp_split_to_array({}, ',\\s*')
                ) from {}
            """.format(
                column, table
            )
            with connection.cursor() as cursor:
                cursor.execute(sql)
                values = [r[0] for r in cursor.fetchall() if r[0]]
            return sorted(zip(values, values))

        def queryset(self, request, queryset):
            value = self.value()
            if not value:
                return queryset
            else:
                return queryset.annotate(
                    value_array_position=Func(
                        Func(
                            F(queryset_column),
                            Value(",\\s*"),
                            function="regexp_split_to_array",
                            output_field=ArrayField(TextField()),
                        ),
                        Value(value),
                        function="array_position",
                        output_field=IntegerField(),
                    )
                ).filter(value_array_position__isnull=False)

    return CommaSeparatedValuesFilter
