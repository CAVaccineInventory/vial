#!/usr/bin/env python3

import datetime
import re
from collections import defaultdict
from typing import Dict, Optional

from core.models import AvailabilityTag, Location
from django.http import HttpResponse
from prometheus_client import (  # type: ignore
    CollectorRegistry,
    Gauge,
    Histogram,
    generate_latest,
)


class LocationMetricsReport:
    registry: CollectorRegistry
    total_locations: Gauge
    total_reports: Gauge
    total_yesses: Gauge
    total_nos: Gauge
    ago_hours: Histogram

    now: datetime.datetime

    def __init__(self) -> None:
        prefix = "vial_"
        self.registry = CollectorRegistry()
        self.total_locations = Gauge(
            f"{prefix}locations_total_total",
            "Total number of locations",
            registry=self.registry,
        )
        self.total_reports = Gauge(
            f"{prefix}locations_reports_total",
            "Total number of reports",
            registry=self.registry,
        )
        self.total_yeses = Gauge(
            f"{prefix}locations_yeses_total",
            "Total number of 'Yes' reports",
            labelnames=["walkin", "min_age"],
            registry=self.registry,
        )
        self.total_nos = Gauge(
            f"{prefix}locations_nos_total",
            "Total number of 'No' reports",
            labelnames=["why"],
            registry=self.registry,
        )
        self.ago_hours = Histogram(
            f"{prefix}locations_report_stale_hours",
            "How long ago the report came",
            buckets=range(0, 24 * 7 * 3, 6),
            labelnames=["yes"],
            registry=self.registry,
        )

        self.age_tags = AvailabilityTag.objects.filter(
            group="yes", name__regex=r"^Vaccinating \d+\+$"
        )
        self.no_reasons = AvailabilityTag.objects.filter(group="no")
        self.terminal_nos = [
            AvailabilityTag.objects.get(name="No vaccine inventory"),
            AvailabilityTag.objects.get(name="Will never be a vaccination site"),
        ]

    def age_of_tag(self, tag: AvailabilityTag) -> Optional[str]:
        match = re.match(r"Vaccinating (\d+)\+", tag.name)
        if match:
            return match[1]
        return None

    def serve(self) -> HttpResponse:
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.total_locations.set(len(Location.objects.all()))

        yeses: Dict[bool, Dict[str, int]] = {
            True: defaultdict(int),
            False: defaultdict(int),
        }
        nos: Dict[str, int] = defaultdict(int)
        locations_with_reports = (
            Location.objects.filter(dn_latest_non_skip_report_id__isnull=False)
            .select_related("dn_latest_non_skip_report")
            .prefetch_related("dn_latest_non_skip_report__availability_tags")
        )
        for loc in locations_with_reports:
            self.observe_location(loc, yeses, nos)
        self.total_reports.set(len(locations_with_reports))

        for walkin in (True, False):
            self.total_yeses.labels(walkin, "None").set(yeses[walkin]["None"])
            for age_tag in sorted(self.age_tags, key=lambda t: t.name):
                age = self.age_of_tag(age_tag)
                assert age
                self.total_yeses.labels(walkin, age).set(yeses[walkin][age])

        for reason in self.no_reasons:
            self.total_nos.labels(reason.name).set(nos[reason.name])

        return HttpResponse(
            content=generate_latest(registry=self.registry),
            content_type="text/plain",
        )

    def observe_location(
        self,
        loc: Location,
        yeses: Dict[bool, Dict[str, int]],
        nos: Dict[str, int],
    ) -> None:
        assert loc.dn_latest_non_skip_report
        is_yes = loc.dn_latest_non_skip_report_id == loc.dn_latest_yes_report_id
        tags = loc.dn_latest_non_skip_report.availability_tags
        terminal_no = False
        if is_yes:
            walkin = len(tags.filter(group="yes", name="Walk-ins accepted")) > 0
            age = "None"
            for tag in sorted(tags.all(), key=lambda t: t.name):
                this_age = self.age_of_tag(tag)
                if this_age:
                    age = this_age
                    break
            yeses[walkin][age] += 1
        else:
            for reason in tags.filter(group="no"):
                nos[reason.name] += 1
                if reason in self.terminal_nos:
                    terminal_no = True
                break

        # We only care about freshness for non-terminal nos.
        if not terminal_no:
            self.ago_hours.labels(is_yes).observe(
                (self.now - loc.dn_latest_non_skip_report.created_at).total_seconds()
                / 60
                / 60
            )
