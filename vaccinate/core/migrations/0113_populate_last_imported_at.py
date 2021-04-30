from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0112_sourcelocation_last_imported_at"),
    ]

    operations = [
        migrations.RunSQL(
            sql="update source_location set last_imported_at = created_at",
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
