from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0114_report_pending_review_because"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                update concordance_identifier
                set authority = replace(authority, ':', '_')
                where authority like '%:%'
            """,
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
