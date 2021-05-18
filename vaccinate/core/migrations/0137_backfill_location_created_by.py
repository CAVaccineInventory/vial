from django.db import migrations

# This sets created_by based on reversion comments
SQL1 = """
with location_reporters as (select
  reporter.id,
  reporter.user_id,
  reversion_version.object_id as location_id,
  (regexp_match(reversion_revision.comment, '.*Reporter (.*)'))[1] as reporter_repr
from reversion_version
  join reversion_revision
    on reversion_revision.id = reversion_version.revision_id
  join reporter
    on (regexp_match(reversion_revision.comment, '.*Reporter (.*)'))[1] = reporter.name
where
  reversion_revision.comment like '/api/createLocationFromSourceLocation Reporter %')
update location
  set
    created_by_id = location_reporters.user_id
  from
    location_reporters
  where
    location.id = cast(location_reporters.location_id as integer)
"""
# This sets created_by based on the Django admin log
SQL2 = """
with location_users as (select
  django_admin_log.object_id,
  django_admin_log.user_id
from django_admin_log
  where action_flag = 1
  and content_type_id in (select id from django_content_type where app_label = 'core' and model = 'location'))
update location
  set
    created_by_id = location_users.user_id
  from
    location_users
  where
    location.id = cast(location_users.object_id as integer)
"""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0136_create_user_for_every_reporter"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[SQL1, SQL2],
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
