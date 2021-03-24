import csv
from io import StringIO

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


def export_as_csv_action(description="Export selected rows to CSV"):
    def export_as_csv(modeladmin, request, queryset):
        def rows(queryset):

            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)
            columns = [field.name for field in modeladmin.model._meta.fields]

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
                csvwriter.writerow(getattr(row, column) for column in columns)
                yield read_and_flush()

        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = (
            "attachment; filename=%s.csv" % modeladmin.model.__name__
        )

        return response

    export_as_csv.short_description = description
    return export_as_csv
