from django.db import migrations

SQL = """
with scraped_opening_hours as (
  select distinct on (matched_location_id)
    id as source_location_id,
    matched_location_id,
    json_extract_path(import_json::json, 'opening_hours') as opening_hours,
    last_imported_at
  from
    source_location
  where
    source_name = 'vaccinefinder_org'
    and json_array_length(json_extract_path(import_json::json, 'opening_hours')) > 0
    and matched_location_id is not null
  order by matched_location_id, last_imported_at
)
update location
  set
    hours_json = scraped_opening_hours.opening_hours,
    hours_json_last_updated_at=scraped_opening_hours.last_imported_at,
    hours_json_provenance_source_location_id=scraped_opening_hours.source_location_id
  from
    scraped_opening_hours
  where
    location.id = scraped_opening_hours.matched_location_id
"""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0156_hours_json"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
