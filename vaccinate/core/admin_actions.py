import csv
from io import StringIO

import orjson
from django.db.models.fields.related import ForeignKey
from django.http import StreamingHttpResponse

from .utils import keyset_pagination_iterator


def export_as_csv_action(
    description="Export selected rows to CSV",
    customize_queryset=None,
    extra_columns=None,
    extra_columns_factory=None,
    specific_columns=None,
    suffix=None,
):
    extra_columns = extra_columns or []
    customize_queryset = customize_queryset or (lambda qs: qs)

    def export_as_csv(modeladmin, request, queryset):
        def rows(queryset):
            queryset = customize_queryset(queryset)
            csvfile = StringIO()
            csvwriter = csv.writer(csvfile)
            columns = []
            if specific_columns:
                # Column headers are the keys of this dict
                columns = list(specific_columns.keys())
            else:
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
                if specific_columns:
                    csv_row = [
                        getattr(row, actual_column)
                        for actual_column in specific_columns.values()
                    ]
                else:
                    csv_row = [
                        getattr(row, column)
                        for column in columns
                        if column not in extra_columns
                    ]
                if extra_columns_factory:
                    csv_row.extend(extra_columns_factory(row))
                # JSONify any lists or dicts
                for i, item in enumerate(csv_row):
                    if isinstance(item, (list, dict)):
                        csv_row[i] = orjson.dumps(item).decode("utf-8")
                csvwriter.writerow(csv_row)
                yield read_and_flush()

        filename = modeladmin.model.__name__
        if suffix:
            filename += "_{}".format(suffix)
        response = StreamingHttpResponse(rows(queryset), content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=%s.csv" % filename

        return response

    export_as_csv.short_description = description
    if suffix:
        export_as_csv.__name__ = "export_as_csv_{}".format(suffix)
    return export_as_csv
