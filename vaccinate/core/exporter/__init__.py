import datetime
import os
from contextlib import contextmanager
from typing import Callable, Dict, Generator, Iterator, List, Optional

import beeline
import orjson
from api.search import search_locations
from api.serialize import split_geojson_by_state
from core import models
from core.exporter.storage import GoogleStorageWriter, LocalWriter, StorageWriter
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Count, F, Q, QuerySet
from django.test.client import RequestFactory
from sentry_sdk import capture_exception

DEPLOYS: Dict[str, List[StorageWriter]] = {
    "testing": [
        LocalWriter("local/legacy"),
        LocalWriter("local/api/v1"),
    ],
    # TODO: These bucket names and paths have been changed to not
    # overlap with the current production airtable exporter.  They
    # will need to change to:
    "staging": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync-staging"),
        GoogleStorageWriter("vaccinateca-api-staging", "v1"),
    ],
    "production": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync"),
        GoogleStorageWriter("vaccinateca-api", "v1"),
    ],
}


VTS_DEPLOYS: Dict[str, StorageWriter] = {
    # vial/vaccinate/local
    "testing": LocalWriter("local/api/vaccinatethestates"),
    # https://staging-api.vaccinatethestates.com/
    "staging": GoogleStorageWriter("vaccinatethestates-api-staging", "v0"),
    # https://api.vaccinatethestates.com/
    "production": GoogleStorageWriter("vaccinatethestates-api", "v0"),
}


def api_export_vaccinate_the_states() -> bool:
    json_request = RequestFactory().get(
        "/api/searchLocations?all=1&exportable=1&format=v0preview"
    )
    json_request.user = AnonymousUser()
    json_request.skip_jwt_auth = True  # type: ignore[attr-defined]
    json_request.skip_api_logging = True  # type: ignore[attr-defined]
    json_response = search_locations(json_request)
    assert json_response.status_code == 200, str(json_response)

    # Next the GeoJSON version
    geojson_request = RequestFactory().get(
        "/api/searchLocations?all=1&exportable=1&format=v0preview-geojson"
    )
    geojson_request.user = AnonymousUser()
    geojson_request.skip_jwt_auth = True  # type: ignore[attr-defined]
    geojson_request.skip_api_logging = True  # type: ignore[attr-defined]
    geojson_response = search_locations(geojson_request)
    assert geojson_response.status_code == 200, str(geojson_response)

    # This one we deserialize so we can later split by state
    geojson = orjson.loads(b"".join(geojson_response.streaming_content))

    deploy = os.environ.get("DEPLOY", "testing")
    if deploy == "unknown":  # Cloud Build
        deploy = "testing"
    writer = VTS_DEPLOYS[deploy]
    ok = True
    try:
        writer.write("locations.json", json_response.streaming_content)
        writer.write("locations.geojson", iter([orjson.dumps(geojson)]))
        for state, state_geojson in split_geojson_by_state(geojson):
            writer.write(
                "{}.geojson".format(state), iter([orjson.dumps(state_geojson)])
            )

    except Exception as e:
        capture_exception(e)
        ok = False

    return ok


def api_export() -> bool:
    deploy_env = DEPLOYS[os.environ.get("DEPLOY", "testing")]
    ok = True
    with dataset() as ds:
        for version, writer in enumerate(deploy_env):
            try:
                api(version, ds).write(writer)
            except Exception as e:
                capture_exception(e)
                ok = False
    return ok


class Dataset:
    locations: QuerySet[models.Location]
    counties: QuerySet[models.County]
    providers: QuerySet[models.Provider]


@beeline.traced(name="core.exporter.dataset")
@contextmanager
def dataset() -> Generator[Dataset, None, None]:
    """Fetches a consistent view of the rows to be serialized.

    Serializers may further filter this list down if they wish."""
    with transaction.atomic():
        ds = Dataset()
        # The sheer width of the number of columns being pulled out of
        # the database is a significant fractino of the time (~5s/6s)
        # to run the query.  Limiting the columns to just those that
        # are necessary accalerates this significantly -- with the
        # caveat that if any /other/ column is requested, it adds O(n)
        # additional queries, at significant cost!
        ds.locations = (
            models.Location.objects.filter(state__abbreviation="CA", soft_deleted=False)
            .exclude(
                dn_latest_non_skip_report__planned_closure__lt=datetime.date.today()
            )
            .select_related("dn_latest_non_skip_report__appointment_tag")
            .select_related("county")
            .select_related("location_type")
            .select_related("provider")
            .prefetch_related("dn_latest_non_skip_report__availability_tags")
        ).only(
            "public_id",
            "name",
            "county__name",
            "full_address",
            "latitude",
            "longitude",
            "location_type__name",
            "vaccinefinder_location_id",
            "vaccinespotter_location_id",
            "google_places_id",
            "county__vaccine_reservations_url",
            "dn_latest_non_skip_report__appointment_tag__slug",
            "dn_latest_non_skip_report__appointment_details",
            "dn_latest_non_skip_report__location_id",
            "dn_latest_non_skip_report__created_at",
            "dn_latest_non_skip_report__public_notes",
            "website",
            "provider__name",
            "provider__appointments_url",
        )

        ds.counties = (
            models.County.objects.filter(state__abbreviation="CA")
            .annotate(
                locations_with_reports=Count(
                    "locations",
                    filter=Q(locations__dn_latest_non_skip_report_id__isnull=False),
                )
            )
            .annotate(
                locations_with_latest_yes=Count(
                    "locations",
                    filter=Q(
                        locations__dn_latest_non_skip_report_id=F(
                            "locations__dn_latest_yes_report_id"
                        ),
                    ),
                )
            )
        )
        ds.providers = (
            models.Provider.objects.all()
            .select_related("provider_type")
            .prefetch_related("phases")
        )

        yield ds


def nonnull_row(row: Dict[str, object]) -> Dict[str, object]:
    """Emulate Airtable's standard of not providing keys whose values are null or the empty string."""
    for k, v in row.copy().items():
        if v is None or v == "":
            del row[k]
    return row


def remove_null_values(
    f: Callable[..., List[Dict[str, object]]]
) -> Callable[..., List[Dict[str, object]]]:
    """Decorator to ensure that the list of rows has all nulls values removed."""
    return lambda *args, **kwargs: [nonnull_row(r) for r in f(*args, **kwargs)]


def data_to_content_stream(data: object) -> Iterator[bytes]:
    yield orjson.dumps(data)


class APIProducer:
    ds: Dataset

    def __init__(self, ds: Dataset):
        self.ds = ds

    def write(self, sw: StorageWriter) -> None:
        ...


class V0(APIProducer):
    def county_name(self, county: Optional[models.County]) -> str:
        if not county:
            return ""
        if county.name == "San Francisco":
            return county.name
        return county.name + " County"

    @beeline.traced(name="core.exporter.V0.get_locations")
    def get_locations(self) -> List[Dict[str, object]]:
        result = []
        with beeline.tracer("fetch"):
            locations = list(self.ds.locations)
        with beeline.tracer("iterate"):
            for location in locations:
                # We remove the nulls only here, and not as a decorator,
                # because Airtable does not remove empty values from
                # rollups, only from fields naturally on the record. (!)
                provider = location.provider.name if location.provider else None
                result.append(
                    nonnull_row(
                        {
                            "id": location.public_id,
                            "Name": location.name,
                            "Affiliation": provider,
                            "County": self.county_name(location.county),
                            "Address": location.full_address,
                            "Latitude": float(location.latitude),
                            "Longitude": float(location.longitude),
                            "Location Type": location.location_type.name,
                            "vaccinefinder_location_id": location.vaccinefinder_location_id,
                            "vaccinespotter_location_id": location.vaccinespotter_location_id,
                            "google_places_id": location.google_places_id,
                        }
                    )
                )
                latest = location.dn_latest_non_skip_report
                if latest:
                    is_yes = any(
                        [t for t in latest.availability_tags.all() if t.group == "yes"]
                    )
                    public_notes = [latest.public_notes or None] if is_yes else ""
                    tags = [
                        t.previous_names[0] if t.previous_names else t.name
                        for t in latest.availability_tags.all()
                    ]
                    result[-1].update(
                        {
                            "Has Report": 1,
                            "Appointment scheduling instructions": [
                                latest.full_appointment_details(location)
                            ],
                            "Availability Info": tags,
                            "Latest report": latest.created_at.strftime(
                                "%Y-%m-%dT%H:%M:%S.000Z"
                            ),
                            "Latest report notes": public_notes,
                            "Latest report yes?": 1 if is_yes else 0,
                        }
                    )
                else:
                    result[-1].update(
                        {
                            "Has Report": 0,
                            "Latest report notes": "",
                            "Latest report yes?": 0,
                        }
                    )
        return result

    @beeline.traced(name="core.exporter.V0.get_counties")
    @remove_null_values
    def get_counties(self) -> List[Dict[str, object]]:
        result = []
        for county in self.ds.counties:
            result.append(
                {
                    "id": county.airtable_id,
                    "County": self.county_name(county),
                    "Notes": county.public_notes,
                    "Twitter Page": county.twitter_page,
                    "Facebook Page": county.facebook_page,
                    "Official volunteering opportunities": county.official_volunteering_url,
                    "County vaccination reservations URL": county.vaccine_reservations_url,
                    "Vaccine info URL": county.vaccine_info_url,
                    "Vaccine locations URL": county.vaccine_locations_url,
                    "Total reports": county.locations_with_reports,  # type:ignore[attr-defined]
                    "Yeses": county.locations_with_latest_yes,  # type:ignore[attr-defined]
                    "age_floor_without_restrictions": county.age_floor_without_restrictions,
                }
            )
        return result

    @beeline.traced(name="core.exporter.V0.write")
    def write(self, sw: StorageWriter) -> None:
        sw.write("Locations.json", data_to_content_stream(self.get_locations()))
        sw.write("Counties.json", data_to_content_stream(self.get_counties()))


class V1(V0):
    def metadata_wrap(self, content: object) -> Dict:
        return {
            "usage": {
                "notice": "Please contact VaccinateCA and let us know if you plan to rely on or publish this data. This data is provided with best-effort accuracy. If you are displaying this data, we expect you to display it responsibly. Please do not display it in a way that is easy to misread.",
                "contact": {
                    "partnersEmail": "api@vaccinateca.com",
                },
            },
            "content": content,
        }

    @beeline.traced(name="core.exporter.V1.get_providers")
    @remove_null_values
    def get_providers(self) -> List[Dict[str, object]]:
        result = []
        for provider in self.ds.providers:
            if (
                provider.appointments_url
                or provider.vaccine_info_url
                or provider.vaccine_locations_url
                or provider.public_notes
            ):
                last_updated = (
                    provider.last_updated.strftime("%Y-%m-%d")
                    if provider.last_updated
                    else None
                )
                result.append(
                    {
                        "id": provider.public_id,
                        "Provider": provider.name,
                        "Provider network type": provider.provider_type.name,
                        "Public Notes": provider.public_notes,
                        "Appointments URL": provider.appointments_url,
                        "Vaccine info URL": provider.vaccine_info_url,
                        "Vaccine locations URL": provider.vaccine_locations_url,
                        "Last Updated": last_updated,
                        "Phase": [p.name for p in provider.phases.all()],
                    }
                )
        return result

    @beeline.traced(name="core.exporter.V1.write")
    def write(self, sw: StorageWriter):
        sw.write(
            "locations.json",
            data_to_content_stream(self.metadata_wrap(self.get_locations())),
        )
        sw.write(
            "counties.json",
            data_to_content_stream(self.metadata_wrap(self.get_counties())),
        )
        sw.write(
            "providers.json",
            data_to_content_stream(self.metadata_wrap(self.get_providers())),
        )


def api(version: int, ds: Dataset) -> APIProducer:
    if version == 0:
        return V0(ds)
    if version == 1:
        return V1(ds)
    raise ValueError(f"Invalid API version: {version}")
