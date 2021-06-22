import datetime
import re

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel
from django.utils import timezone

from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    Location,
    LocationReviewTag,
    Reporter,
    ReportReviewTag,
    State,
)


def test_admin_create_location_sets_public_id_and_created_by(admin_client):
    assert Location.objects.count() == 0
    response = admin_client.post(
        "/admin/core/location/add/",
        {
            "name": "hello",
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "vaccines_offered": "[]",
            "_save": "Save",
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "location_review_notes-TOTAL_FORMS": "1",
            "location_review_notes-INITIAL_FORMS": "0",
            "location_review_notes-MIN_NUM_FORMS": "0",
            "location_review_notes-MAX_NUM_FORMS": "1000",
        },
    )
    # 200 means the form is being re-displayed with errors
    assert response.status_code == 302
    location = Location.objects.order_by("-id")[0]
    assert location.name == "hello"
    assert location.state.id == State.objects.get(abbreviation="OR").pk
    assert location.location_type.id == 1
    assert location.pid.startswith("l")
    assert location.public_id == location.pid
    assert location.created_by.username == "admin"


def test_create_location_sets_pending_review_with_wbtrainee_role(
    admin_client, admin_user
):
    assert Location.objects.count() == 0
    group = Group.objects.get_or_create(name="WB Trainee")[0]
    admin_user.groups.add(group)

    response = admin_client.post(
        "/admin/core/location/add/",
        {
            "name": "CVS",
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "vaccines_offered": "[]",
            "_save": "Save",
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "location_review_notes-TOTAL_FORMS": "1",
            "location_review_notes-INITIAL_FORMS": "0",
            "location_review_notes-MIN_NUM_FORMS": "0",
            "location_review_notes-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 302
    location = Location.objects.order_by("-id")[0]
    assert location.name == "CVS"
    assert location.created_by.username == "admin"
    assert location.is_pending_review


def test_adding_review_note_with_approved_tag_approves_location(
    admin_client, ten_locations
):
    location = ten_locations[0]
    approved_tag = LocationReviewTag.objects.get_or_create(tag="Approved")[0]
    location.is_pending_review = True
    location.save()

    response = admin_client.post(
        f"/admin/core/location/{location.pk}/change/",
        {
            "name": location.name,
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "vaccines_offered": "[]",
            "is_pending_review": "on",
            "location_review_notes-0-note": "Test",
            "location_review_notes-0-tags": approved_tag.pk,
            "location_review_notes-0-id": "",
            "location_review_notes-0-location": location.pk,
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "location_review_notes-TOTAL_FORMS": "1",
            "location_review_notes-INITIAL_FORMS": "0",
            "location_review_notes-MIN_NUM_FORMS": "0",
            "location_review_notes-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 302
    location.refresh_from_db()
    review_note = location.location_review_notes.first()
    tag_name = review_note.tags.values_list("tag", flat=True).get()
    assert tag_name == "Approved"
    assert not location.is_pending_review


def test_approving_and_saving_removes_pending_review_on_location(
    admin_client, ten_locations
):
    # You can create a review tag before you submit a review
    LocationReviewTag.objects.create(tag="Approved")
    location = ten_locations[0]
    location.is_pending_review = True
    location.save()

    response = admin_client.post(
        f"/admin/core/location/{location.pk}/change/",
        {
            "name": location.name,
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "vaccines_offered": "[]",
            "is_pending_review": "off",
            "_approve_location": "Approve+and+Save+location",
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "location_review_notes-TOTAL_FORMS": "1",
            "location_review_notes-INITIAL_FORMS": "0",
            "location_review_notes-MIN_NUM_FORMS": "0",
            "location_review_notes-MAX_NUM_FORMS": "1000",
        },
    )

    assert response.status_code == 302
    location.refresh_from_db()
    assert not location.is_pending_review
    review_note = location.location_review_notes.first()
    tag_name = review_note.tags.values_list("tag", flat=True).get()
    assert tag_name == "Approved"


def test_admin_location_actions_for_queue(admin_client, ten_locations):
    assert CallRequest.objects.count() == 0
    assert Location.objects.count() == 10
    locations_to_queue = ten_locations[:3]
    # Make one of those locations 'do not call'
    do_not_call_location = locations_to_queue[0]
    do_not_call_location.do_not_call = True
    do_not_call_location.save()
    # /admin/core/location/ should have 10 locations + actions menu
    response = admin_client.get("/admin/core/location/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    for fragment in (
        '<option value="add_to_call_request_queue_stale_report">Add to queue: Stale report</option>',
        '<option value="add_to_call_request_queue_new_location">Add to queue: New location</option>',
        '<option value="add_to_call_request_queue_eva_tip">Add to queue: Eva tip</option>',
        '<option value="add_to_call_request_queue_data_corrections_tip">Add to queue: Data corrections tip</option>',
    ):
        assert fragment in html
    # Now try submitting the form, with three items selected
    response2 = admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [location.id for location in locations_to_queue],
        },
    )
    assert response2.status_code == 302
    assert response2.url == "/admin/core/location/"
    messages = list(get_messages(response2.wsgi_request))
    assert len(messages) == 1
    assert (
        messages[0].message
        == "Added 2 location to queue with reason: Data corrections tip. Skipped 1 location"
    )
    # Call requests should have been created
    assert CallRequest.objects.count() == 2
    assert set(CallRequest.objects.values_list("location_id", flat=True)) == set(
        location.id for location in locations_to_queue[1:]
    )
    # If we filter locations by "?currently_queued=yes" we should see them
    response3 = admin_client.get("/admin/core/location/?currently_queued=yes")
    assert response3.status_code == 200
    listed_locations = set(
        re.compile(r">(Location \d+)<").findall(response3.content.decode("utf-8"))
    )
    assert listed_locations == {"Location 3", "Location 2"}


def test_clear_claims_action(admin_client):
    locations = []
    for i in range(1, 4):
        locations.append(
            Location.objects.create(
                name="Location {}".format(i),
                state_id=State.objects.get(abbreviation="OR").id,
                location_type_id=1,
                latitude=30,
                longitude=40,
                phone_number="(555) 555-5555",
            )
        )
    assert CallRequest.objects.count() == 0
    # Add them to the call queue
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [location.id for location in locations],
        },
    )
    assert CallRequest.objects.count() == 3
    assert CallRequest.available_requests().count() == 3
    # Claim all three
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    CallRequest.objects.all().update(
        claimed_by=reporter,
        claimed_until=timezone.now() + datetime.timedelta(minutes=10),
    )
    assert CallRequest.available_requests().count() == 0
    # Now clear two of them
    response = admin_client.post(
        "/admin/core/callrequest/?status=all",
        {
            "action": "clear_claims",
            "_selected_action": [cr.id for cr in CallRequest.objects.all()[:2]],
        },
    )
    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 2
    assert messages[1].message == "Cleared claims for 2 call requests"
    assert CallRequest.available_requests().count() == 2


def test_claim_bump_to_top_bottom_actions(admin_client):
    locations = [
        Location.objects.create(
            name="Location {}".format(i),
            state_id=State.objects.get(abbreviation="OR").id,
            location_type_id=1,
            latitude=30,
            longitude=40,
            phone_number="(555) 555-5555",
        )
        for i in range(1, 4)
    ]
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [location.id for location in locations],
        },
    )
    cr3, cr2, cr1 = CallRequest.objects.values_list("pk", flat=True)
    assert list(CallRequest.objects.values_list("pk", "priority")) == [
        (cr3, 0),
        (cr2, 0),
        (cr1, 0),
    ]
    # Bump number 1 to the top
    admin_client.post(
        "/admin/core/callrequest/",
        {
            "action": "bump_to_top",
            "_selected_action": [cr1],
        },
    )
    assert list(CallRequest.objects.values_list("pk", "priority")) == [
        (cr1, 1),
        (cr3, 0),
        (cr2, 0),
    ]
    # And bump number 3 to the bottom
    admin_client.post(
        "/admin/core/callrequest/",
        {
            "action": "bump_to_bottom",
            "_selected_action": [cr3],
        },
    )
    assert list(CallRequest.objects.values_list("pk", "priority")) == [
        (cr1, 1),
        (cr2, 0),
        (cr3, -1),
    ]


@pytest.mark.parametrize(
    "query_string,expected",
    [
        ("", [1, 2, 3]),
        ("?status=claimed", [4, 5]),
        ("?status=scheduled", [6, 7]),
        ("?status=completed", [8, 9, 10]),
        ("?status=all", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    ],
)
def test_call_request_filters(admin_client, ten_locations, query_string, expected):
    # Create call requests with various characteristics
    now = timezone.now()
    reason = CallRequestReason.objects.get(short_reason="New location")
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    ready_1 = CallRequest.objects.create(
        location=ten_locations[0], call_request_reason=reason, vesting_at=now
    )
    ready_2 = CallRequest.objects.create(
        location=ten_locations[1], call_request_reason=reason, vesting_at=now
    )
    ready_3 = CallRequest.objects.create(
        location=ten_locations[2], call_request_reason=reason, vesting_at=now
    )
    claimed_4 = CallRequest.objects.create(
        location=ten_locations[3],
        call_request_reason=reason,
        vesting_at=now,
        claimed_by=reporter,
        claimed_until=now + datetime.timedelta(minutes=60),
    )
    claimed_5 = CallRequest.objects.create(
        location=ten_locations[4],
        call_request_reason=reason,
        vesting_at=now,
        claimed_by=reporter,
        claimed_until=now + datetime.timedelta(minutes=60),
    )
    scheduled_6 = CallRequest.objects.create(
        location=ten_locations[5],
        call_request_reason=reason,
        vesting_at=now + datetime.timedelta(hours=1),
    )
    scheduled_7 = CallRequest.objects.create(
        location=ten_locations[6],
        call_request_reason=reason,
        vesting_at=now + datetime.timedelta(hours=1),
    )
    completed_8 = CallRequest.objects.create(
        location=ten_locations[7],
        call_request_reason=reason,
        vesting_at=now,
        completed=True,
    )
    completed_9 = CallRequest.objects.create(
        location=ten_locations[8],
        call_request_reason=reason,
        vesting_at=now,
        completed=True,
    )
    completed_10 = CallRequest.objects.create(
        location=ten_locations[9],
        call_request_reason=reason,
        vesting_at=now,
        completed=True,
    )
    lookups = {
        1: ready_1,
        2: ready_2,
        3: ready_3,
        4: claimed_4,
        5: claimed_5,
        6: scheduled_6,
        7: scheduled_7,
        8: completed_8,
        9: completed_9,
        10: completed_10,
    }
    response = admin_client.get("/admin/core/callrequest/{}".format(query_string))
    call_request_ids = {
        int(r[1].split('<a href="/admin/core/callrequest/')[1].split("/change/")[0])
        for r in response.context["results"]
    }
    expected_ids = {lookups[e].pk for e in expected}
    assert call_request_ids == expected_ids


# Using reset_sequences for predictable IDs in CSV output
@pytest.mark.django_db(transaction=True, reset_sequences=True)
def test_admin_export_csv(admin_client, django_assert_num_queries, ten_locations):
    # Add those locations to the call queue
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [location.id for location in ten_locations],
        },
    )
    # Ensure they have predictable created_at and vesting_at values
    CallRequest.objects.all().update(
        created_at="2021-03-24 13:11:23", vesting_at="2021-03-24 15:11:23"
    )
    with django_assert_num_queries(9):
        response = admin_client.post(
            "/admin/core/callrequest/",
            {
                "action": "export_as_csv",
                "_selected_action": [cr.id for cr in CallRequest.objects.all()],
            },
        )
        csv_bytes = b"".join(chunk for chunk in response.streaming_content)
        csv_string = csv_bytes.decode("utf-8")
        assert csv_string == (
            "id,location_id,location,created_at,vesting_at,claimed_by_id,claimed_by,claimed_until,call_request_reason_id,call_request_reason,completed,completed_at,priority_group,priority,tip_type,tip_report_id,tip_report\r\n"
            "1,1,Location 1,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "2,2,Location 2,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "3,3,Location 3,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "4,4,Location 4,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "5,5,Location 5,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "6,6,Location 6,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "7,7,Location 7,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "8,8,Location 8,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "9,9,Location 9,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "10,10,Location 10,2021-03-24 13:11:23+00:00,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
        )


def test_custom_csv_export_for_reports(
    admin_client, ten_locations, django_assert_num_queries
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        is_pending_review=True,
        originally_pending_review=True,
        airtable_json={"foo": "bar"},
    )
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    plus_50 = AvailabilityTag.objects.get(slug="vaccinating_50_plus")
    report.availability_tags.add(plus_65)
    report.availability_tags.add(plus_50)
    report.refresh_from_db()
    with django_assert_num_queries(13):
        response = admin_client.post(
            "/admin/core/report/",
            {
                "action": "export_as_csv",
                "_selected_action": [report.id],
            },
        )
        csv_bytes = b"".join(chunk for chunk in response.streaming_content)
        csv_string = csv_bytes.decode("utf-8")
        assert csv_string == (
            "id,location_id,location,is_pending_review,originally_pending_review,pending_review_because,claimed_by_id,claimed_by,claimed_at,soft_deleted,soft_deleted_because,report_source,appointment_tag_id,appointment_tag,appointment_details,public_notes,internal_notes,restriction_notes,vaccines_offered,website,full_address,hours,planned_closure,reported_by_id,reported_by,created_at,call_request_id,call_request,airtable_id,airtable_json,public_id,availability_tags\r\n"
            '{},{},Location 1,True,True,,,,,False,,ca,3,web,,,,,,,,,,{},auth0:reporter,{},,,,"{{""foo"":""bar""}}",{},"Vaccinating 50+, Vaccinating 65+"\r\n'.format(
                report.id,
                report.location_id,
                reporter.id,
                str(report.created_at),
                report.public_id,
            )
        )


def test_csv_export_for_locations_with_phone_and_website(admin_client, ten_locations):
    for location in ten_locations:
        i = location.name.split(" ")[1]
        location.website = "https://example.com/{}".format(i)
        location.phone_number = "(555) 555-555{}".format(i)
        location.save()
    response = admin_client.post(
        "/admin/core/location/",
        {
            "action": "export_as_csv_phone_website",
            "_selected_action": [location.id for location in ten_locations],
        },
    )
    csv_bytes = b"".join(chunk for chunk in response.streaming_content)
    csv_string = csv_bytes.decode("utf-8")
    expected_public_ids = [location.public_id for location in ten_locations]
    assert csv_string == (
        "Name,Phone number,Website,Location ID\r\n"
        "Location 1,(555) 555-5551,https://example.com/1,{}\r\n"
        "Location 2,(555) 555-5552,https://example.com/2,{}\r\n"
        "Location 3,(555) 555-5553,https://example.com/3,{}\r\n"
        "Location 4,(555) 555-5554,https://example.com/4,{}\r\n"
        "Location 5,(555) 555-5555,https://example.com/5,{}\r\n"
        "Location 6,(555) 555-5556,https://example.com/6,{}\r\n"
        "Location 7,(555) 555-5557,https://example.com/7,{}\r\n"
        "Location 8,(555) 555-5558,https://example.com/8,{}\r\n"
        "Location 9,(555) 555-5559,https://example.com/9,{}\r\n"
        "Location 10,(555) 555-55510,https://example.com/10,{}\r\n"
    ).format(*expected_public_ids)


def test_adding_review_note_with_approved_tag_approves_report(
    admin_client, ten_locations
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    web = AppointmentTag.objects.get(slug="web")
    approved_tag = ReportReviewTag.objects.get_or_create(tag="Approved")[0]
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
        is_pending_review=True,
    )
    assert report.is_pending_review
    # Add a comment with that tag
    response = admin_client.post(
        "/admin/core/report/{}/change/".format(report.pk),
        {
            "location": location.pk,
            "is_pending_review": "on",
            "report_source": "ca",
            "appointment_tag": "1",
            "availability_tags": "2",
            "reported_by": reporter.pk,
            "review_notes-0-note": "Test",
            "review_notes-0-tags": approved_tag.pk,
            "review_notes-0-id": "",
            "review_notes-0-report": report.pk,
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "review_notes-TOTAL_FORMS": "1",
            "review_notes-INITIAL_FORMS": "0",
            "review_notes-MIN_NUM_FORMS": "0",
            "review_notes-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    report.refresh_from_db()
    # Check that the report had a note added
    review_note = report.review_notes.first()
    assert list(review_note.tags.values_list("tag", flat=True)) == ["Approved"]
    # is_pending_review should have been turned off
    assert not report.is_pending_review


def test_setting_is_pending_review_false_adds_note(admin_client, ten_locations):
    # https://github.com/CAVaccineInventory/vial/issues/450
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    report = location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag_id=1,
        is_pending_review=True,
    )
    assert report.is_pending_review
    assert not report.review_notes.exists()
    # Update it and turn off is_pending_review
    response = admin_client.post(
        "/admin/core/report/{}/change/".format(report.pk),
        {
            "location": location.pk,
            "is_pending_review": "",
            "report_source": "ca",
            "appointment_tag": "1",
            "availability_tags": "2",
            "reported_by": reporter.pk,
            "review_notes-TOTAL_FORMS": "1",
            "review_notes-INITIAL_FORMS": "0",
            "review_notes-MIN_NUM_FORMS": "0",
            "review_notes-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    report.refresh_from_db()
    assert not report.is_pending_review
    # Check that the report had a note added
    review_note = report.review_notes.first()
    assert review_note is not None
    assert list(review_note.tags.values_list("tag", flat=True)) == ["Approved"]


def test_bulk_approve_reports_action(admin_client, ten_locations):
    reporter = Reporter.objects.get_or_create(external_id="auth0:reporter")[0]
    web = AppointmentTag.objects.get(slug="web")
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    plus_50 = AvailabilityTag.objects.get(slug="vaccinating_50_plus")

    reports = []
    for location in ten_locations:
        report = location.reports.create(
            reported_by=reporter,
            report_source="ca",
            appointment_tag=web,
            is_pending_review=True,
            originally_pending_review=True,
        )
        report.availability_tags.add(plus_65)
        report.availability_tags.add(plus_50)
        report.refresh_from_db()
        assert report.review_notes.count() == 0
        reports.append(report)

        location.refresh_from_db()
        assert location.dn_latest_report_id is None
        assert location.dn_latest_report_including_pending_id == report.id

    # Now bulk-approve them
    admin_client.post(
        "/admin/core/report/",
        {
            "action": "bulk_approve_reports",
            "_selected_action": [report.id for report in reports],
        },
    )

    for location, report in zip(ten_locations, reports):
        location.refresh_from_db()
        assert location.dn_latest_report_id == report.id
        assert location.dn_latest_report_including_pending_id == report.id

        report.refresh_from_db()
        assert report.review_notes.count() == 1
        note = report.review_notes.first()
        assert list(note.tags.values_list("tag", flat=True)) == ["Approved"]


@pytest.mark.parametrize(
    "model,model_admin",
    [
        (model, model_admin)
        for model, model_admin in admin.site._registry.items()
        if model._meta.app_label in ("core", "api")
        and model_admin.__class__ is not admin.ModelAdmin
        and model_admin.fieldsets is not None
    ],
)
def test_admin_fieldsets_do_not_omit_fields_accidentally(model, model_admin):
    # It's easy to add new fields to a Django ORM model but forget to explicitly
    # add those new fields to the fieldset= for the relevant ModelAdmin
    # https://github.com/CAVaccineInventory/vial/issues/421
    columns = {
        f.name
        for f in model._meta.get_fields()
        if f is not model._meta.pk
        and not isinstance(f, ManyToOneRel)
        and not isinstance(f, ManyToManyRel)
    }
    admin_columns = set(
        getattr(model_admin, "deliberately_omitted_from_fieldsets", None) or []
    )
    for fieldset_name, fieldset_bits in model_admin.fieldsets:
        admin_columns.update(fieldset_bits["fields"])
    assert columns.issubset(
        admin_columns
    ), "ModelAdmin {} is missing columns {}".format(
        model_admin.__class__.__name__, columns.difference(admin_columns)
    )
