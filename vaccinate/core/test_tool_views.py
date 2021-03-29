from .models import County, Location, LocationType, State, Reporter, AppointmentTag
from reversion.models import Revision


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
