from .models import County


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
