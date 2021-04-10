import datetime
import re

import pytest
from django.contrib.messages import get_messages
from django.utils import timezone

from .models import (
    AppointmentTag,
    AvailabilityTag,
    CallRequest,
    CallRequestReason,
    Location,
    Reporter,
    State,
)


def test_admin_create_location_sets_public_id(admin_client):
    assert Location.objects.count() == 0
    response = admin_client.post(
        "/admin/core/location/add/",
        {
            "name": "hello",
            "state": State.objects.get(abbreviation="OR").id,
            "location_type": "1",
            "latitude": "0",
            "longitude": "0",
            "_save": "Save",
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
            "_selected_action": [l.id for l in locations_to_queue],
        },
    )
    assert response2.status_code == 302
    assert response2.url == "/admin/core/location/"
    messages = list(get_messages(response2.wsgi_request))
    assert len(messages) == 1
    assert (
        messages[0].message
        == 'Added 2 location to queue with reason: Data corrections tip. Skipped 1 location marked "do not call"'
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
            )
        )
    assert CallRequest.objects.count() == 0
    # Add them to the call queue
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [l.id for l in locations],
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
        )
        for i in range(1, 4)
    ]
    admin_client.post(
        "/admin/core/location/",
        {
            "action": "add_to_call_request_queue_data_corrections_tip",
            "_selected_action": [l.id for l in locations],
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
        claimed_until=now + datetime.timedelta(minutes=20),
    )
    claimed_5 = CallRequest.objects.create(
        location=ten_locations[4],
        call_request_reason=reason,
        vesting_at=now,
        claimed_by=reporter,
        claimed_until=now + datetime.timedelta(minutes=20),
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
            "_selected_action": [l.id for l in ten_locations],
        },
    )
    # Ensure they have predictable vesting_at values
    CallRequest.objects.all().update(vesting_at="2021-03-24 15:11:23")
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
            "id,location_id,location,vesting_at,claimed_by_id,claimed_by,claimed_until,call_request_reason_id,call_request_reason,completed,completed_at,priority_group,priority,tip_type,tip_report_id,tip_report\r\n"
            "1,10,Location 10,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "2,9,Location 9,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "3,8,Location 8,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "4,7,Location 7,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "5,6,Location 6,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "6,5,Location 5,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "7,4,Location 4,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "8,3,Location 3,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "9,2,Location 2,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
            "10,1,Location 1,2021-03-24 15:11:23+00:00,,,,4,Data corrections tip,False,,99,0,,,\r\n"
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
    )
    plus_65 = AvailabilityTag.objects.get(slug="vaccinating_65_plus")
    plus_50 = AvailabilityTag.objects.get(slug="vaccinating_50_plus")
    report.availability_tags.add(plus_65)
    report.availability_tags.add(plus_50)
    report.refresh_from_db()
    with django_assert_num_queries(9):
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
            "id,location_id,location,is_pending_review,soft_deleted,soft_deleted_because,report_source,appointment_tag_id,appointment_tag,appointment_details,public_notes,internal_notes,reported_by_id,reported_by,created_at,call_request_id,call_request,airtable_id,airtable_json,public_id,availability_tags\r\n"
            '{},{},Location 1,True,False,,ca,3,web,,,,{},auth0:reporter,{},,,,,{},"Vaccinating 65+, Vaccinating 50+"\r\n'.format(
                report.id,
                report.location_id,
                reporter.id,
                str(report.created_at),
                report.public_id,
            )
        )


def test_adding_review_note_with_approved_tag_approves_report(
    admin_client, ten_locations
):
    location = ten_locations[0]
    reporter = Reporter.objects.get_or_create(external_id="auth0:claimer")[0]
    web = AppointmentTag.objects.get(slug="web")
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
            "review_notes-0-note": "",
            "review_notes-0-tags": "1",
            "review_notes-0-id": "",
            "review_notes-0-report": report.pk,
            # This is needed to avoid the following validation error:
            # 'ManagementForm data is missing or has been tampered with'
            "review_notes-TOTAL_FORMS": "1",
            "review_notes-INITIAL_FORMS": "0",
            "review_notes-MIN_NUM_FORMS": "0",
            "review_notes-MAX_NUM_FORMS": "1000",
            # These are needed so that the review note is properly saved:
            "review_notes-__prefix__-note": "",
            "review_notes-__prefix__-id": "",
            "review_notes-__prefix__-report": report.pk,
        },
    )
    assert response.status_code == 302
    report.refresh_from_db()
    # Check that the report had a note added
    review_note = report.review_notes.first()
    assert list(review_note.tags.values_list("tag", flat=True)) == ["Approved"]
    # is_pending_review should have been turned off
    assert not report.is_pending_review
