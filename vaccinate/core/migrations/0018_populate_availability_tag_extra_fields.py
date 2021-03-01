from django.db import migrations

tags_to_update = {
    # current name: new slug
    "No: only vaccinating staff": "only_staff",
    "No: not open to the public": "not_open_to_the_public",
    "No: only vaccinating health care workers": "only_health_care_workers",
    "No: no vaccine inventory": "no_vaccine_inventory",
    "No: incorrect contact information": "incorrect_contact_information",
    "No: location permanently closed": "location_permanently_closed",
    "No: will never be a vaccination site": "will_never_be_a_vaccination_site",
    "Yes: walk-ins accepted": "walk_ins_accepted",
    "Yes: appointment required": "appointment_required",
    "Yes: vaccinating 65+": "vaccinating_65_plus",
    "Yes: vaccinating 70+": "vaccinating_70_plus",
    "Yes: vaccinating 75+": "vaccinating_75_plus",
    "Yes: vaccinating 80+": "vaccinating_80_plus",
    "Yes: vaccinating 85+": "vaccinating_85_plus",
    "Yes: restricted to county residents": "restricted_to_county_residents",
    "Yes: must be a current patient": "must_be_a_current_patient",
    "Yes: must be a veteran": "must_be_a_veteran",
    "Yes: appointment calendar currently full": "appointment_calendar_currently_full",
    "Yes: coming soon": "coming_soon",
    "Skip: call back later": "skip_call_back_later",
    "No: may be a vaccination site in the future": "may_be_a_vaccination_site_in_the_future",
    "Yes: Vaccinating essential workers": "vaccinating_essential_workers",
    "Yes: restricted to city residents": "restricted_to_city_residents",
    "Yes: Scheduling second dose only": "scheduling_second_dose_only",
}


def update_availability_tags(apps, schema_editor):
    AvailabilityTag = apps.get_model("core", "AvailabilityTag")
    for current_name, new_slug in tags_to_update.items():
        tag = AvailabilityTag.objects.get_or_create(name=current_name)[0]
        group, new_name = current_name.split(": ")
        tag.group = group.lower()
        # Capitalize first letter of new_name
        new_name = new_name[0].upper() + new_name[1:]
        tag.slug = new_slug
        tag.name = new_name
        if new_name != current_name:
            tag.previous_names = [current_name]
        tag.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_availability_tag_extra_fields"),
    ]

    operations = [
        migrations.RunPython(update_availability_tags),
    ]
