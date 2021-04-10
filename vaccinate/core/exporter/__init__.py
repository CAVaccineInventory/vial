import os
from contextlib import contextmanager
from typing import Callable, Dict, Generator, List

import beeline
from core import models
from core.exporter.storage import GoogleStorageWriter, LocalWriter, StorageWriter
from django.db import transaction
from django.db.models import Count, F, Q, QuerySet
from sentry_sdk import capture_exception

DEPLOYS: Dict[str, List[StorageWriter]] = {
    "testing": [
        LocalWriter("local/legacy"),
        LocalWriter("local/api/v1"),
    ],
    # TODO: These bucket names and paths have been changed to not
    # overlap with the current production airtable exporter.  They
    # will need to change to:
    # "staging": [
    #     GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync-staging"),
    #     GoogleStorageWriter("vaccinateca-api-staging", "v1"),
    # ],
    # "production": [
    #     GoogleStorageWriter("cavaccineinventory-sitedata", "airtable-sync"),
    #     GoogleStorageWriter("vaccinateca-api", "v1"),
    # ]
    "staging": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "vial-staging"),
        GoogleStorageWriter("vaccinateca-api-vial-staging", "v1"),
    ],
    "production": [
        GoogleStorageWriter("cavaccineinventory-sitedata", "vial"),
        GoogleStorageWriter("vaccinateca-api-vial", "v1"),
    ],
}


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
            models.Location.objects.filter(state__abbreviation="CA")
            .select_related("dn_latest_non_skip_report")
            .select_related("county")
            .select_related("location_type")
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
            "dn_latest_non_skip_report__appointment_details",
            "dn_latest_non_skip_report__created_at",
            "dn_latest_non_skip_report__public_notes",
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
        ds.providers = models.Provider.objects.all().select_related("provider_type")

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


class APIProducer:
    ds: Dataset

    def __init__(self, ds: Dataset):
        self.ds = ds

    def write(self, sw: StorageWriter) -> None:
        ...


class V0(APIProducer):
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
                county = location.county.name + " County" if location.county else ""
                result.append(
                    nonnull_row(
                        {
                            "id": location.public_id,
                            "Name": location.name,
                            "Affiliation": None,  # ???
                            "County": county,
                            "Address": location.full_address,
                            "Latitude": location.latitude,
                            "Longitude": location.longitude,
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
                    result[-1].update(
                        {
                            "Has Report": 1,
                            "Appointment scheduling instructions": latest.appointment_details,
                            "Availability Info": [
                                t.long_name for t in latest.availability_tags.all()
                            ],
                            "Latest report": latest.created_at.isoformat() + "Z",
                            "Latest report notes": [latest.public_notes or None],
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
                    "County": county.name + " County",
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

    @beeline.traced(name="core.exporter.V0.get_providers")
    @remove_null_values
    def get_providers(self) -> List[Dict[str, object]]:
        result = []
        for provider in self.ds.providers:
            result.append(
                {
                    "id": "???",  # provider.public_id ??,
                    "Provider": provider.name,
                    "Provider network type": provider.provider_type.name,
                    "Public Notes": provider.public_notes,
                    "Appointments URL": provider.appointments_url,
                    "Vaccine info URL": provider.vaccine_info_url,
                    "Vaccine locations URL": provider.vaccine_info_url,
                    "Last Updated": "???",
                    "Phase": "???",
                }
            )
        return result

    @beeline.traced(name="core.exporter.V0.write")
    def write(self, sw: StorageWriter) -> None:
        sw.write("Locations.json", self.get_locations())
        sw.write("Counties.json", self.get_counties())


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

    @beeline.traced(name="core.exporter.V1.write")
    def write(self, sw: StorageWriter):
        sw.write("locations.json", self.metadata_wrap(self.get_locations()))
        sw.write("counties.json", self.metadata_wrap(self.get_counties()))
        sw.write("providers.json", self.metadata_wrap(self.get_providers()))


def api(version: int, ds: Dataset) -> APIProducer:
    if version == 0:
        return V0(ds)
    if version == 1:
        return V1(ds)
    raise ValueError(f"Invalid API version: {version}")
