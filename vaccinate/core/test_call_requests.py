from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Union

import pytest
from core.models import AppointmentTag, CallRequest, Location, Reporter, State
from django.db.models.query import QuerySet
from django.utils import timezone
from time_machine import Coordinates


@pytest.mark.django_db()
def test_backfill_queue(ten_locations: List[Location]) -> None:
    def requests_with_reports() -> Dict[int, int]:
        report_count: Dict[int, int] = defaultdict(int)
        call_requests = CallRequest.available_requests()
        for call_request in call_requests:
            report_count[call_request.location.reports.count()] += 1
        return report_count

    assert CallRequest.available_requests().count() == 0
    CallRequest.backfill_queue(3)
    assert CallRequest.available_requests().count() == 3
    assert CallRequest.objects.count() == 3
    CallRequest.objects.all().delete()

    # Try again but mark half of the locations as 'called'; we should
    # only get uncalled locations
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    web = AppointmentTag.objects.get(slug="web")
    for i in range(5):
        ten_locations[i].reports.create(
            created_at=datetime.now() - timedelta(days=i),
            reported_by=reporter,
            report_source="ca",
            appointment_tag=web,
        )
    assert CallRequest.available_requests().count() == 0
    CallRequest.backfill_queue(5)
    assert CallRequest.available_requests().count() == 5
    assert CallRequest.objects.count() == 5
    assert requests_with_reports() == {0: 5}
    CallRequest.objects.all().delete()

    # Try again but ask for 8 locations; we should get 8 locations in
    # the queue, with 3 of them having reports
    assert CallRequest.available_requests().count() == 0
    CallRequest.backfill_queue(8)
    assert CallRequest.available_requests().count() == 8
    assert CallRequest.objects.count() == 8
    assert requests_with_reports() == {0: 5, 1: 3}

    # Specifically, it should be the _oldest_ reports, which are indexes 4, 3, and 2.
    assert CallRequest.objects.filter(location=ten_locations[4]).count()
    assert CallRequest.objects.filter(location=ten_locations[3]).count()
    assert CallRequest.objects.filter(location=ten_locations[2]).count()
    CallRequest.objects.all().delete()

    # Even when everything has a report, we don't error
    for location in ten_locations[5:10]:
        location.reports.create(
            reported_by=reporter,
            report_source="ca",
            appointment_tag=web,
        )
    assert CallRequest.available_requests().count() == 0
    CallRequest.backfill_queue(10)
    assert CallRequest.available_requests().count() == 10
    assert CallRequest.objects.count() == 10
    assert requests_with_reports() == {1: 10}


@pytest.mark.django_db()
def test_backfill_overfill_queue(ten_locations: List[Location]) -> None:
    # Ask for more locations than there are; we should get no duplicates
    assert CallRequest.available_requests().count() == 0
    CallRequest.backfill_queue(20)
    assert CallRequest.available_requests().count() == 10
    assert CallRequest.objects.count() == 10

    # Even when everything is already queued
    CallRequest.backfill_queue(20)
    assert CallRequest.available_requests().count() == 10
    assert CallRequest.objects.count() == 10


@pytest.mark.django_db()
def test_backfill_state(ten_locations: List[Location]) -> None:
    # Update several locations to be in CA (yes, this will lead to
    # counties' states being inconsistent) and ensure we can get both
    # CA and OR out still.
    for loc in ten_locations[0:10:2]:
        loc.state = State.objects.filter(abbreviation="CA").get()
        loc.save()

    # We should only get 5 locations
    CallRequest.backfill_queue(10, state="CA")
    assert CallRequest.objects.count() == 5
    assert CallRequest.objects.filter(location__state__abbreviation="CA").count() == 5


def enqueue(
    what: Union[Location, List[Location], QuerySet[Location]], **kwargs: Any
) -> List[CallRequest]:
    if isinstance(what, QuerySet):
        qs = what
    elif isinstance(what, List):
        qs = Location.objects.filter(id__in=[loc.id for loc in what])
    else:
        qs = Location.objects.filter(id=what.id)
    return CallRequest.insert(locations=qs, reason="New location", **kwargs)


@pytest.mark.django_db()
def test_enqueue(ten_locations: List[Location]) -> None:
    # Simple enqueue
    assert CallRequest.available_requests().count() == 0
    inserted = enqueue(ten_locations[0])
    assert len(inserted) == 1
    assert CallRequest.objects.count() == 1
    assert CallRequest.available_requests().count() == 1

    # Re-enqueing doesn't work
    inserted = enqueue(ten_locations[0])
    assert len(inserted) == 0
    assert CallRequest.objects.count() == 1
    assert CallRequest.available_requests().count() == 1

    # Marking it as resolved allows it to be enqueued again
    CallRequest.objects.all().update(completed=True)
    assert CallRequest.objects.count() == 1
    assert CallRequest.available_requests().count() == 0
    inserted = enqueue(ten_locations[0])
    assert len(inserted) == 1
    assert CallRequest.objects.count() == 2
    assert CallRequest.available_requests().count() == 1

    # Enqueueing multiple locations works
    inserted = enqueue(ten_locations[1:4])
    assert len(inserted) == 3
    assert CallRequest.objects.count() == 5
    assert CallRequest.available_requests().count() == 4

    # Enqueueing some locations which overlap with existing locations
    # enqueues just the new ones
    inserted = enqueue(ten_locations[0:8])
    assert len(inserted) == 4
    assert CallRequest.objects.count() == 9
    assert CallRequest.available_requests().count() == 8


@pytest.mark.django_db()
def test_call_enqueue_request_validity() -> None:
    def insert_fails(**kwargs: Any) -> bool:
        args = {
            "name": "Location {}".format(repr(kwargs)),
            "phone_number": "(555) 555-5555",
            "state_id": State.objects.get(abbreviation="OR").id,
            "location_type_id": 1,
            "latitude": 30,
            "longitude": 40,
        }
        args.update(kwargs)
        return enqueue(Location.objects.create(**args)) == []

    # Various things that exempt a location from being called
    assert insert_fails(do_not_call=True)
    assert insert_fails(soft_deleted=True)
    assert insert_fails(phone_number="")
    assert insert_fails(phone_number=None)
    assert insert_fails(preferred_contact_method="research_online")


@pytest.mark.django_db()
def test_call_remove_invalid_location(ten_locations: List[Location]) -> None:
    # Enqueue a _valid_, location, and ensure that changing any of the
    # above removes it
    def change_removes(**kwargs: Any) -> bool:
        location = Location.objects.create(
            name="Location {}".format(repr(kwargs)),
            phone_number="(555) 555-5555",
            state_id=State.objects.get(abbreviation="OR").id,
            location_type_id=1,
            latitude=30,
            longitude=40,
        )
        enqueue(location)
        for k, v in kwargs.items():
            setattr(location, k, v)
        location.save()
        return CallRequest.objects.filter(location=location).count() == 0

    assert change_removes(do_not_call=True)
    assert change_removes(soft_deleted=True)
    assert change_removes(phone_number="")
    assert change_removes(phone_number=None)
    assert change_removes(preferred_contact_method="research_online")

    # Ensure that completed call requests are not removed
    enqueue(ten_locations)
    CallRequest.objects.update(completed=True)
    assert CallRequest.objects.count() == 10
    assert CallRequest.available_requests().count() == 0
    enqueue(ten_locations)
    assert CallRequest.objects.count() == 20
    assert CallRequest.available_requests().count() == 10
    for location in ten_locations:
        location.do_not_call = True
        location.save()
    # We should only be left with the completed ones from earlier, and
    # none should be available.
    assert CallRequest.objects.count() == 10
    assert CallRequest.available_requests().count() == 0


@pytest.mark.django_db()
def test_get_call_request(
    ten_locations: List[Location], time_machine: Coordinates
) -> None:
    # Can't get anything from an empty queue; Note that in these
    # tests, MIN_CALL_REQUEST_QUEUE_ITEMS=0, which disables backfill.

    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    assert CallRequest.get_call_request(claim_for=reporter) is None

    # We can pick a call request off; doing so makes it no longer
    # available
    current_time = timezone.make_aware(datetime(2021, 5, 7, 10, 0, 0))
    time_machine.move_to(current_time)
    enqueue(ten_locations)
    assert CallRequest.available_requests().count() == 10
    call_request = CallRequest.get_call_request(claim_for=reporter)
    assert call_request.claimed_by == reporter
    assert call_request.claimed_until >= current_time + timedelta(hours=1)
    assert CallRequest.available_requests().count() == 9

    # We can pick a call request off with no reporter; this leaves it unclaimed
    call_request = CallRequest.get_call_request()
    assert call_request
    assert call_request.claimed_by is None
    assert call_request.claimed_until is None
    assert CallRequest.available_requests().count() == 9

    # All of our ten_locations are in OR; we we ask for an OR site, we
    # get one
    call_request = CallRequest.get_call_request(claim_for=reporter, state="OR")
    assert call_request
    assert call_request.location.state.abbreviation == "OR"

    # Update several locations to be in CA (yes, this will lead to
    # counties' states being inconsistent) and ensure we can get both
    # CA and OR out still.
    for loc in ten_locations[:5]:
        loc.state = State.objects.filter(abbreviation="CA").get()
        loc.save()

    call_request = CallRequest.get_call_request(claim_for=reporter, state="CA")
    assert call_request.location.state.abbreviation == "CA"
    call_request = CallRequest.get_call_request(claim_for=reporter, state="OR")
    assert call_request.location.state.abbreviation == "OR"

    # If we're not limited by state, we'll get both:
    seen_states = {}
    while CallRequest.available_requests().count() > 0:
        call_request = CallRequest.get_call_request(claim_for=reporter)
        seen_states[call_request.location.state.abbreviation] = True
    assert seen_states == {"OR": True, "CA": True}
    assert CallRequest.get_call_request(claim_for=reporter) is None

    # If we move ahead by two hours, we have available requests again,
    # and we can get them
    current_time += timedelta(hours=2)
    time_machine.move_to(current_time)
    assert CallRequest.available_requests().count() == 10
    assert CallRequest.get_call_request(claim_for=reporter) is not None


@pytest.mark.django_db()
def test_get_call_request_priorities(ten_locations: List[Location]) -> None:
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    enqueue(ten_locations)
    for i in range(10):
        CallRequest.objects.filter(location=ten_locations[i]).update(
            priority_group=(i % 2) + 5,
            priority=i + 11,
        )
    seen_priorities: List[Tuple[int, int]] = []
    while CallRequest.available_requests().count():
        call_request = CallRequest.get_call_request(claim_for=reporter)
        seen_priorities.append((call_request.priority_group, call_request.priority))

    # Start with the lowest priority group, but the highest piority
    # within that; then go down the pririties inside the group.
    assert seen_priorities == [
        (5, 19),
        (5, 17),
        (5, 15),
        (5, 13),
        (5, 11),
        (6, 20),
        (6, 18),
        (6, 16),
        (6, 14),
        (6, 12),
    ]


@pytest.mark.django_db()
def test_call_mark_completed(
    ten_locations: List[Location], time_machine: Coordinates
) -> None:
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    current_time = timezone.make_aware(datetime(2021, 5, 7, 10, 0, 0))
    time_machine.move_to(current_time)

    # Enqueue after the time_machine change, so they get the right vested_at
    enqueue(ten_locations)
    assert CallRequest.available_requests().count() == 10
    call_request = CallRequest.get_call_request(claim_for=reporter)
    assert CallRequest.available_requests().count() == 9

    # We we submit a report for that location, it closes the call request
    web = AppointmentTag.objects.get(slug="web")
    report = call_request.location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    call_request.refresh_from_db()
    assert not call_request.completed
    assert call_request.completed_at is None
    assert CallRequest.objects.count() == 10
    assert CallRequest.available_requests().count() == 9

    CallRequest.mark_completed_by(report)
    assert CallRequest.objects.count() == 10
    assert CallRequest.available_requests().count() == 9
    call_request.refresh_from_db()
    assert call_request.completed
    assert call_request.completed_at is not None
    assert call_request.completed_at >= current_time
    assert report.call_request == call_request

    # Submit a report for the same location again; it has no
    # call_request, and leaves things as-is.
    report = call_request.location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    CallRequest.mark_completed_by(report)
    call_request.refresh_from_db()
    assert report.call_request is None
    assert CallRequest.objects.count() == 10
    assert CallRequest.available_requests().count() == 9


@pytest.mark.django_db()
def test_call_mark_completed_skip(ten_locations, time_machine: Coordinates) -> None:
    reporter = Reporter.objects.get_or_create(external_id="test:1")[0]
    current_time = timezone.make_aware(datetime(2021, 5, 7, 10, 0, 0))
    time_machine.move_to(current_time)

    web = AppointmentTag.objects.get(slug="web")

    # Put a skip on a location with no call report
    report = ten_locations[0].reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )
    assert CallRequest.objects.count() == 0
    vesting_at = current_time + timedelta(hours=1)
    CallRequest.mark_completed_by(report, enqueue_again_at=vesting_at)
    assert CallRequest.objects.count() == 1
    call_request = CallRequest.objects.all().get()
    assert call_request.location == report.location
    assert call_request.vesting_at == vesting_at
    assert call_request.tip_type == CallRequest.TipType.SCOOBY
    assert call_request.tip_report == report
    assert call_request.priority_group == 99
    assert call_request.priority == 0
    assert CallRequest.available_requests().count() == 0
    assert CallRequest.get_call_request(claim_for=reporter) is None

    # Jump forward after it vests, and we can claim it
    current_time += timedelta(hours=2)
    time_machine.move_to(current_time)
    assert CallRequest.available_requests().count() == 1
    assert CallRequest.get_call_request(claim_for=reporter) == call_request
    CallRequest.objects.all().delete()

    # Make two priority groups
    enqueue(ten_locations)
    for i in range(10):
        CallRequest.objects.filter(location=ten_locations[i]).update(
            priority_group=17,
            priority=i + 11,
        )
    call_request = CallRequest.get_call_request(claim_for=reporter)
    assert call_request.priority_group == 17
    assert call_request.priority == 20
    report = call_request.location.reports.create(
        reported_by=reporter,
        report_source="ca",
        appointment_tag=web,
    )

    # When we skip, we become the _lowest_ priority within the group
    CallRequest.mark_completed_by(
        report, enqueue_again_at=current_time + timedelta(hours=1)
    )
    assert CallRequest.objects.count() == 11
    assert CallRequest.available_requests().count() == 9
    call_request = CallRequest.objects.filter(
        completed=False, location=report.location
    ).get()
    assert call_request.priority_group == 17
    assert call_request.priority == 10
