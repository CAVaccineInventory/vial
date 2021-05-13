import itertools
import json
from collections import namedtuple
from typing import Dict

import beeline
from core.expansions import VaccineFinderInventoryExpansion
from core.models import Location
from django.db.models.query import QuerySet

OutputFormat = namedtuple(
    "OutputFormat",
    # transform_bach runs once against a batch that has been prepared by calling transform on each item
    (
        "prepare_queryset",
        "start",
        "transform",
        "transform_batch",
        "serialize",
        "separator",
        "end",
        "content_type",
    ),
)


def build_stream(
    qs, stream_qs, formatter, beeline_trace_name, transform_batch_size=100
):
    trace_id = None
    parent_id = None
    bl = beeline.get_beeline()
    if bl:
        trace_id = bl.tracer_impl.get_active_trace_id()
        parent_id = bl.tracer_impl.get_active_span().id

    @beeline.traced(beeline_trace_name, trace_id=trace_id, parent_id=parent_id)
    def stream():
        if callable(formatter.start):
            yield formatter.start(qs)
        else:
            yield formatter.start
        started = False
        for record_batch in chunks(stream_qs, transform_batch_size):
            records = formatter.transform_batch(
                [formatter.transform(record) for record in record_batch]
            )
            for record in records:
                if started and formatter.separator:
                    yield formatter.separator
                started = True
                yield formatter.serialize(record)
        yield formatter.end(qs)

    return stream


def location_json_queryset(queryset: QuerySet[Location]) -> QuerySet[Location]:
    return (
        queryset.select_related(
            "state",
            "county",
            "location_type",
            "provider__provider_type",
        ).prefetch_related("concordances")
    ).only(
        "public_id",
        "name",
        "state__abbreviation",
        "latitude",
        "longitude",
        "location_type__name",
        "import_ref",
        "phone_number",
        "full_address",
        "city",
        "county__name",
        "google_places_id",
        "vaccinefinder_location_id",
        "vaccinespotter_location_id",
        "zip_code",
        "hours",
        "website",
        "preferred_contact_method",
        "provider__name",
        "provider__provider_type__name",
        "dn_latest_non_skip_report",
    )


def location_json(
    location: Location, include_soft_deleted: bool = False
) -> Dict[str, object]:
    data = {
        "id": location.public_id,
        "name": location.name,
        "state": location.state.abbreviation,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "location_type": location.location_type.name,
        "import_ref": location.import_ref,
        "phone_number": location.phone_number,
        "full_address": location.full_address,
        "city": location.city,
        "county": location.county.name if location.county else None,
        "google_places_id": location.google_places_id,
        "vaccinefinder_location_id": location.vaccinefinder_location_id,
        "vaccinespotter_location_id": location.vaccinespotter_location_id,
        "zip_code": location.zip_code,
        "hours": location.hours,
        "website": location.website,
        "preferred_contact_method": location.preferred_contact_method,
        "provider": {
            "name": location.provider.name,
            "type": location.provider.provider_type.name,
        }
        if location.provider
        else None,
        "concordances": [str(c) for c in location.concordances.all()],
    }
    if include_soft_deleted:
        data["soft_deleted"] = location.soft_deleted
    return data


def location_geojson(location: Location) -> Dict[str, object]:
    properties = location_json(location)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [float(location.longitude), float(location.latitude)],
        },
    }


def location_v0_json(location: Location) -> Dict[str, object]:
    return {
        "id": location.public_id,
        "name": location.name,
        "state": location.state.abbreviation,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "location_type": location.location_type.name,
        "phone_number": location.phone_number,
        "full_address": location.full_address,
        "city": location.city,
        "county": location.county.name if location.county else None,
        "zip_code": location.zip_code,
        "hours": {"unstructured": location.hours},
        "website": location.website,
        "vaccines_offered": [],
        "concordances": [str(c) for c in location.concordances.all()],
        "last_verified_by_vts": location.dn_latest_non_skip_report.created_at.isoformat()
        if location.dn_latest_non_skip_report
        else None,
        "vts_url": "https://www.vaccinatethestates.com/?lng={}&lat={}#{}".format(
            location.longitude, location.latitude, location.public_id
        ),
    }


def location_formats(preload_vaccinefinder=False):
    formats = make_formats(location_json, location_geojson)
    expansion = VaccineFinderInventoryExpansion(preload_vaccinefinder)

    def transform_batch(batch):
        lookups = expansion.expand(batch)
        for record in batch:
            record["vaccines_offered"] = lookups.get(record["id"]) or []
        return batch

    formats["v0preview"] = OutputFormat(
        prepare_queryset=lambda qs: qs.select_related("dn_latest_non_skip_report"),
        start=(
            '{"usage": {"notice": "Please contact Vaccinate The States and let '
            "us know if you plan to rely on or publish this data. This "
            "data is provided with best-effort accuracy. If you are "
            "displaying this data, we expect you to display it responsibly. "
            'Please do not display it in a way that is easy to misread.",'
            '"contact": {"partnersEmail": "api@vaccinatethestates.com"}},'
            '"content": ['
        ),
        transform=lambda l: location_v0_json(l),
        transform_batch=transform_batch,
        serialize=json.dumps,
        separator=",",
        end=lambda qs: "]}",
        content_type="application/json",
    )
    return formats


def make_formats(json_convert, geojson_convert):
    return {
        "json": OutputFormat(
            prepare_queryset=lambda qs: qs,
            start='{"results": [',
            transform=lambda l: json_convert(l),
            transform_batch=lambda batch: batch,
            serialize=json.dumps,
            separator=",",
            end=lambda qs: '], "total": TOTAL}'.replace("TOTAL", str(qs.count())),
            content_type="application/json",
        ),
        "geojson": OutputFormat(
            prepare_queryset=lambda qs: qs,
            start='{"type": "FeatureCollection", "features": [',
            transform=lambda l: geojson_convert(l),
            transform_batch=lambda batch: batch,
            serialize=json.dumps,
            separator=",",
            end=lambda qs: "]}",
            content_type="application/json",
        ),
        "nlgeojson": OutputFormat(
            prepare_queryset=lambda qs: qs,
            start="",
            transform=lambda l: geojson_convert(l),
            transform_batch=lambda batch: batch,
            serialize=json.dumps,
            separator="\n",
            end=lambda qs: "",
            content_type="text/plain",
        ),
    }


def chunks(sequence, size):
    iterator = iter(sequence)
    for item in iterator:
        yield itertools.chain([item], itertools.islice(iterator, size - 1))
