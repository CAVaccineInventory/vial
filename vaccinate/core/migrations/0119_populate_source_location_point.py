from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0118_source_location_point"),
    ]

    operations = [
        migrations.RunSQL(
            sql="update source_location set point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326);",
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
