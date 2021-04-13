from django.utils import timezone
from reversion.models import Revision

from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    County,
    Location,
    LocationType,
    Reporter,
    State,
)


def test_admin_tools_superuser_only(client, django_user_model):
    # No logged out users
    assert client.get("/admin/tools/").status_code == 302
    # No non-staff users
    user = django_user_model.objects.create_user(username="not-staff")
    client.force_login(user)
    assert client.get("/admin/tools/").status_code == 302
    # No staff users who are not super-users
    staff_user = django_user_model.objects.create_user(username="staff", is_staff=True)
    client.force_login(staff_user)
    assert client.get("/admin/tools/").status_code == 302
    # Super-users are allowed
    super_user = django_user_model.objects.create_user(
        username="super", is_staff=True, is_superuser=True
    )
    client.force_login(super_user)
    assert client.get("/admin/tools/").status_code == 200


def test_admin_tools_import_counties(admin_client, requests_mock):
    requests_mock.get(
        "https://us-counties.datasette.io/counties/county_fips.csv?_stream=on&_size=max",
        text=(
            "state,state_fips,county_fips,county_name\n"
            "AK,02,02013,Aleutians East\n"
            "AK,02,02016,Aleutians West"
        ),
    )
    assert County.objects.filter(state__abbreviation="AK").count() == 0
    admin_client.post("/admin/tools/", {"command": "import_counties"})
    assert County.objects.filter(state__abbreviation="AK").count() == 2


def test_import_airtable_county_details(admin_client, requests_mock):
    requests_mock.get(
        "https://example.com/counties.json",
        json=[
            {
                "airtable_id": "rec0QOd7EXzSuZZvN",
                "County vaccination reservations URL": "https://example.com/reservations",
                "population": 200,
                "age_floor_without_restrictions": 50,
                "Internal notes": "These are internal notes",
                "Notes": "These are public notes",
            }
        ],
    )
    response = admin_client.post(
        "/admin/tools/", {"airtable_counties_url": "https://example.com/counties.json"}
    )
    assert response.status_code == 200
    assert b"Updated details for 1 counties" in response.content
    county = County.objects.get(airtable_id="rec0QOd7EXzSuZZvN")
    assert county.vaccine_reservations_url == "https://example.com/reservations"
    assert county.population == 200
    assert county.age_floor_without_restrictions == 50
    assert county.internal_notes == "These are internal notes"
    assert county.public_notes == "These are public notes"


def test_command_redirects_to_tools(admin_client):
    response = admin_client.get("/admin/commands/")
    assert response.status_code == 302
    assert response.url == "/admin/tools/"


def test_merge_locations(admin_client):
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    ca = State.objects.get(abbreviation="CA")
    winner = Location.objects.create(
        county=county,
        state=ca,
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    winner.reports.create(
        report_source="ca",
        appointment_tag=AppointmentTag.objects.get(slug="web"),
        appointment_details="blah",
        reported_by=reporter,
    )
    loser = Location.objects.create(
        county=county,
        state=ca,
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    loser.reports.create(
        report_source="ca",
        appointment_tag=AppointmentTag.objects.get(slug="web"),
        appointment_details="blah",
        reported_by=reporter,
    )
    assert winner.reports.count() == 1
    assert loser.reports.count() == 1
    assert loser.duplicate_of is None
    assert not loser.soft_deleted
    assert Revision.objects.count() == 0
    # Now merge them
    winner.refresh_from_db()  # To get correct public_id
    loser.refresh_from_db()
    args = {
        "winner": winner.public_id,
        "loser": loser.public_id,
    }
    response = admin_client.post("/admin/merge-locations/", args, follow=False)
    assert response.status_code == 302
    winner.refresh_from_db()
    loser.refresh_from_db()
    assert winner.reports.count() == 2
    assert loser.reports.count() == 0
    assert loser.duplicate_of == winner
    assert loser.soft_deleted
    # And a Revision should have been created
    assert Revision.objects.count() == 1
    revision = Revision.objects.get()
    assert (
        revision.comment
        == f"Merged locations, winner = {winner.public_id}, loser = {loser.public_id}"
    )


def test_bulk_delete_reports(admin_client, ten_locations):
    county = County.objects.get(fips_code="06079")  # San Luis Obispo
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="CA"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    reports = []
    for _ in range(4):
        report = location.reports.create(
            reported_by=reporter,
            report_source="ca",
            appointment_tag=web,
        )
        report.availability_tags.add(plus_65)
        report.refresh_from_db()  # To get public_id
        reports.append(report)
    assert location.reports.count() == 4
    location.refresh_from_db()
    assert location.dn_yes_report_count == 4
    # Bulk delete the first two
    response = admin_client.post(
        "/admin/bulk-delete-reports/",
        {"report_ids": ",".join(r.public_id for r in reports[:2])},
    )
    assert response.status_code == 200
    assert (
        b"Delete complete - 1 affected locations have been updated" in response.content
    )
    assert location.reports.count() == 2
    location.refresh_from_db()
    assert location.dn_yes_report_count == 2


def test_bulk_call_requests(admin_client, ten_locations):
    location = ten_locations[0]
    call_request = location.call_requests.create(
        call_request_reason=CallRequestReason.objects.get(short_reason="New location"),
        vesting_at=timezone.now(),
    )
    assert CallRequest.objects.count() == 1
    response = admin_client.post(
        "/admin/bulk-delete-call-requests/", {"call_request_ids": call_request.id}
    )
    assert response.status_code == 200
    assert b"Deleted 1 call request" in response.content
    assert CallRequest.objects.count() == 0


def test_location_edit_redirect(admin_client):
    county = County.objects.get(fips_code="06079")
    location = Location.objects.create(
        county=county,
        state=State.objects.get(abbreviation="CA"),
        name="SLO Pharmacy",
        phone_number="555 555-5555",
        full_address="5 5th Street",
        location_type=LocationType.objects.get(name="Pharmacy"),
        latitude=35.279,
        longitude=-120.664,
    )
    location.refresh_from_db()
    response = admin_client.get("/admin/edit-location/{}/".format(location.public_id))
    assert response.url == "/admin/core/location/{}/change/".format(location.pk)
