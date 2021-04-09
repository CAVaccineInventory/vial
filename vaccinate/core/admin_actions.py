import csv
from io import StringIO

from django.db.models.fields.related import ForeignKey
from django.http import StreamingHttpResponse


def keyset_pagination_iterator(input_queryset, batch_size=500):
    all_queryset = input_queryset.order_by("pk")
    last_pk = None
    while True:
        queryset = all_queryset
        if last_pk is not None:
            queryset = all_queryset.filter(pk__gt=last_pk)
        queryset = queryset[:batch_size]
        for row in queryset:
            last_pk = row.pk
            yield row
        if not queryset:
            break


def export_as_csv_action(
    description="Export selected rows to CSV",
    customize_queryset=None,
    extra_columns=None,
    extra_columns_factory=None,
):
    extra_columns = extra_columns or []
    customize_queryset = customize_queryset or (lambda qs: qs)

    def export_as_csv(modeladmin, request, queryset):
        def rows(queryset):
            queryset = customize_queryset(queryset)
            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)
            columns = []
            for field in modeladmin.model._meta.fields:
                if isinstance(field, ForeignKey):
                    columns.extend([field.attname, field.name])
                else:
                    columns.append(field.name)
            if extra_columns:
                columns.extend(extra_columns)

            def read_and_flush():
                csvfile.seek(0)
                data = csvfile.read()
                csvfile.seek(0)
                csvfile.truncate()
                return data

            header = False

            if not header:
                header = True
                csvwriter.writerow(columns)
                yield read_and_flush()

            for row in keyset_pagination_iterator(queryset):
                csv_row = [
                    getattr(row, column)
                    for column in columns
                    if column not in extra_columns
                ]
                if extra_columns_factory:
                    csv_row.extend(extra_columns_factory(row))
                csvwriter.writerow(csv_row)
                yield read_and_flush()

        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = (
            "attachment; filename=%s.csv" % modeladmin.model.__name__
        )

        return response

    export_as_csv.short_description = description
    return export_as_csv
