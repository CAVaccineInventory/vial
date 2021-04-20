import uuid
from typing import Optional

import beeline
import pytz
from django.conf import settings
from django.db import models
from django.db.models import Max, Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import dateformat, timezone

from .baseconverter import pid
from .fields import CharTextField


class LocationType(models.Model):
    """
    Represents a type of location, such as "Pharmacy" or "Hospital/Clinic"
    """

    name = CharTextField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "location_type"


class ProviderType(models.Model):
    """
    Represents a type of provider, such as "Pharmacy" for CVS or "Health Plan" for Kaiser.
    """

    name = CharTextField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "provider_type"


class ProviderPhase(models.Model):
    "Current phase, e.g. 'Not currently vaccinating'"
    name = CharTextField(unique=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "provider_phase"


class Provider(models.Model):
    """
    A provider is a larger entity that encompasses several vaccination sites. A provider will generally have its own
    vaccination policies, which at least nominally apply to all locations.
    Examples include:
    - The pharmacy chain CVS
    - The Kaiser HMO
    - LA County Fire Department-operated Super Sites in LA County
    """

    name = CharTextField(unique=True)
    contact_phone_number = CharTextField(null=True, blank=True)
    main_url = CharTextField(null=True, blank=True)
    vaccine_info_url = CharTextField(null=True, blank=True)
    vaccine_locations_url = CharTextField(null=True, blank=True)
    public_notes = models.TextField(null=True, blank=True)
    appointments_url = CharTextField(null=True, blank=True)
    provider_type = models.ForeignKey(
        ProviderType, related_name="providers", on_delete=models.PROTECT
    )
    internal_contact_instructions = models.TextField(null=True, blank=True)
    last_updated = models.DateField(null=True, blank=True)
    airtable_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Airtable record ID, if this has one",
    )
    public_id = models.SlugField(
        unique=True,
        help_text="ID that we expose outside of the application",
    )
    import_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Original JSON if this record was imported from elsewhere",
    )
    phases = models.ManyToManyField(
        ProviderPhase,
        blank=True,
        related_name="providers",
        db_table="provider_provider_phase",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "provider"

    @property
    def pid(self):
        return "p" + pid.from_int(self.pk)

    def save(self, *args, **kwargs):
        set_public_id_later = False
        if (not self.public_id) and self.airtable_id:
            self.public_id = self.airtable_id
        elif not self.public_id:
            set_public_id_later = True
            self.public_id = "tmp:{}".format(uuid.uuid4())
        super().save(*args, **kwargs)
        if set_public_id_later:
            Provider.objects.filter(pk=self.pk).update(public_id=self.pid)


class State(models.Model):
    """
    Information about a US state or territory
    """

    abbreviation = models.CharField(max_length=2, unique=True)
    name = CharTextField(unique=True)
    fips_code = models.CharField(unique=True, blank=True, null=True, max_length=2)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "state"


class County(models.Model):
    """
    Every part of California is in one of the state's 58 counties, which are also the primary unit that coordinates
    vaccinations and sets vaccination policies. A county's policies may not apply to every location in the county if the
    locations vaccines are sourced directly from the state or federal government.
    """

    fips_code = models.CharField(unique=True, max_length=5)
    name = CharTextField()
    state = models.ForeignKey(State, related_name="counties", on_delete=models.PROTECT)
    hotline_phone_number = CharTextField(null=True, blank=True)
    vaccine_info_url = CharTextField(null=True, blank=True)
    vaccine_locations_url = CharTextField(null=True, blank=True)
    official_volunteering_url = CharTextField(null=True, blank=True)
    public_notes = models.TextField(null=True, blank=True)
    internal_notes = models.TextField(null=True, blank=True)
    facebook_page = CharTextField(null=True, blank=True)
    twitter_page = CharTextField(null=True, blank=True)
    vaccine_reservations_url = CharTextField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    vaccine_dashboard_url = CharTextField(null=True, blank=True)
    vaccine_data_url = CharTextField(null=True, blank=True)
    vaccine_arcgis_url = CharTextField(null=True, blank=True)
    age_floor_without_restrictions = models.IntegerField(
        null=True, blank=True, verbose_name="Age Floor"
    )
    airtable_id = models.CharField(
        max_length=20,
        null=True,
        unique=True,
        help_text="Airtable record ID, if this has one",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "counties"
        db_table = "county"


class Location(models.Model):
    "A location is a distinct place where one can receive a COVID vaccine."
    name = CharTextField()
    phone_number = CharTextField(null=True, blank=True)
    full_address = models.TextField(
        null=True,
        blank=True,
        help_text="the entire address, including city and zip code",
    )
    street_address = CharTextField(
        null=True, blank=True, help_text="the first line of the address"
    )
    city = CharTextField(null=True, blank=True)
    state = models.ForeignKey(State, related_name="locations", on_delete=models.PROTECT)
    zip_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="can accomodate ZIP+4 in standard formatting if needed",
    )
    hours = models.TextField(blank=True, null=True)
    website = CharTextField(blank=True, null=True)
    location_type = models.ForeignKey(
        LocationType, related_name="locations", on_delete=models.PROTECT
    )
    google_places_id = CharTextField(
        null=True,
        blank=True,
        help_text="an ID that associates a location with a unique entry in the Google Places ontology",
    )
    vaccinespotter_location_id = CharTextField(
        null=True,
        blank=True,
        help_text="This location's ID on vaccinespotter.org",
    )
    vaccinefinder_location_id = CharTextField(
        null=True,
        blank=True,
        help_text="This location's ID on vaccinefinder.org",
    )
    provider = models.ForeignKey(
        Provider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locations",
        help_text="a location may or may not be associated with a provider",
    )
    county = models.ForeignKey(
        County,
        null=True,
        blank=True,
        related_name="locations",
        on_delete=models.PROTECT,
    )
    # This was originally specified as a 'coordinate point' but Django doesn't easily
    # expose the 'point' type - we could adopt GeoDjango later though but it's a heavy dependency
    latitude = models.FloatField()
    longitude = models.FloatField()
    soft_deleted = models.BooleanField(
        default=False,
        help_text="we never delete rows from this table; all deletes are soft",
    )
    soft_deleted_because = CharTextField(null=True, blank=True)
    duplicate_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="duplicate_locations",
        on_delete=models.PROTECT,
        help_text="duplicate locations are associated with a canonical location",
    )
    provenance = CharTextField(null=True, blank=True)
    internal_notes = models.TextField(null=True, blank=True)
    do_not_call = models.BooleanField(default=False)
    do_not_call_reason = models.TextField(null=True, blank=True)
    airtable_id = models.CharField(
        max_length=20,
        null=True,
        unique=True,
        help_text="Airtable record ID, if this has one",
    )
    public_id = models.SlugField(
        unique=True, help_text="ID that we expose outside of the application"
    )
    import_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Original JSON if this record was imported from elsewhere",
    )
    import_ref = models.CharField(
        max_length=100,
        db_index=True,
        null=True,
        blank=True,
        help_text="If imported, unique identifier in the system it was imported from",
    )

    preferred_contact_method = models.CharField(
        max_length=32,
        choices=(
            ("research_online", "research_online"),
            ("outbound_call", "outbound_call"),
        ),
        blank=True,
        null=True,
        help_text="Preferred method of collecting status about this location",
    )

    # Denormalized foreign keys for efficient "latest yes report" style queries
    # https://github.com/CAVaccineInventory/vial/issues/193
    # Latest report, NOT including is_pending_review reports:
    dn_latest_report = models.ForeignKey(
        "Report", related_name="+", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Latest report including is_pending_review reports:
    dn_latest_report_including_pending = models.ForeignKey(
        "Report", related_name="+", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Latest with at least one YES availability tag, NOT including is_pending_review:
    dn_latest_yes_report = models.ForeignKey(
        "Report", related_name="+", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Latest with at least one SKIP availability tag, NOT including is_pending_review:
    dn_latest_skip_report = models.ForeignKey(
        "Report", related_name="+", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Latest report that is NOT is_pending_review and does NOT have a skip tag:
    dn_latest_non_skip_report = models.ForeignKey(
        "Report", related_name="+", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Denormalized counts for non is_pendin_review reports:
    dn_skip_report_count = models.IntegerField(default=0)
    dn_yes_report_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "location"
        permissions = [
            ("merge_locations", "Can merge two locations"),
        ]

    @property
    def pid(self):
        return "l" + pid.from_int(self.pk)

    @beeline.traced("update_denormalizations")
    def update_denormalizations(self):
        reports = (
            self.reports.all()
            .exclude(soft_deleted=True)
            .prefetch_related("availability_tags")
            .order_by("-created_at")
        )
        try:
            dn_latest_report = [r for r in reports if not r.is_pending_review][0]
        except IndexError:
            dn_latest_report = None
        try:
            dn_latest_report_including_pending = reports[0]
        except IndexError:
            dn_latest_report_including_pending = None
        dn_latest_yes_reports = [
            r
            for r in reports
            if not r.is_pending_review
            and any(t for t in r.availability_tags.all() if t.group == "yes")
        ]
        dn_yes_report_count = len(dn_latest_yes_reports)
        if dn_latest_yes_reports:
            dn_latest_yes_report = dn_latest_yes_reports[0]
        else:
            dn_latest_yes_report = None
        dn_latest_skip_reports = [
            r
            for r in reports
            if not r.is_pending_review
            and any(t for t in r.availability_tags.all() if t.group == "skip")
        ]
        dn_skip_report_count = len(dn_latest_skip_reports)
        if dn_latest_skip_reports:
            dn_latest_skip_report = dn_latest_skip_reports[0]
        else:
            dn_latest_skip_report = None
        dn_latest_non_skip_reports = [
            r
            for r in reports
            if not r.is_pending_review
            and not any(t for t in r.availability_tags.all() if t.group == "skip")
        ]
        if dn_latest_non_skip_reports:
            dn_latest_non_skip_report = dn_latest_non_skip_reports[0]
        else:
            dn_latest_non_skip_report = None
        # Has anything changed?
        def pk_or_none(record):
            if record is None:
                return None
            return record.pk

        if (
            self.dn_latest_report_id != pk_or_none(dn_latest_report)
            or self.dn_latest_report_including_pending_id
            != pk_or_none(dn_latest_report_including_pending)
            or self.dn_latest_yes_report_id != pk_or_none(dn_latest_yes_report)
            or self.dn_latest_skip_report_id != pk_or_none(dn_latest_skip_report)
            or self.dn_latest_non_skip_report_id
            != pk_or_none(dn_latest_non_skip_report)
            or self.dn_skip_report_count != dn_skip_report_count
            or self.dn_yes_report_count != dn_yes_report_count
        ):
            beeline.add_context({"updates": True})
            self.dn_latest_report = dn_latest_report
            self.dn_latest_report_including_pending = dn_latest_report_including_pending
            self.dn_latest_yes_report = dn_latest_yes_report
            self.dn_latest_skip_report = dn_latest_skip_report
            self.dn_latest_non_skip_report = dn_latest_non_skip_report
            self.dn_skip_report_count = dn_skip_report_count
            self.dn_yes_report_count = dn_yes_report_count
            self.save(
                update_fields=(
                    "dn_latest_report",
                    "dn_latest_report_including_pending",
                    "dn_latest_yes_report",
                    "dn_latest_skip_report",
                    "dn_latest_non_skip_report",
                    "dn_skip_report_count",
                    "dn_yes_report_count",
                )
            )
        else:
            beeline.add_context({"updates": False})

    def save(self, *args, **kwargs):
        set_public_id_later = False
        if (not self.public_id) and self.airtable_id:
            self.public_id = self.airtable_id
        elif not self.public_id:
            set_public_id_later = True
            self.public_id = "tmp:{}".format(uuid.uuid4())
        super().save(*args, **kwargs)
        if set_public_id_later:
            Location.objects.filter(pk=self.pk).update(public_id=self.pid)


class Reporter(models.Model):
    """
    A reporter is a user.
    There are two types of reporters:
    - Auth0 users: these include reports made through our reporting apps, and SQL users who are authenticated through Auth0
    - Airtable users: these are users who are authenticated through Airtable rather than Auth0.
    """

    external_id = models.SlugField(unique=True, max_length=400)
    name = CharTextField(null=True, blank=True)
    email = CharTextField(null=True, blank=True)
    auth0_role_names = CharTextField(null=True, blank=True)

    def __str__(self):
        return self.name or self.external_id

    class Meta:
        db_table = "reporter"


class AvailabilityTag(models.Model):
    """
    A tag indicating the nature of availability at a vaccination site.
    This might be:
    - a restriction on general availability (no inventory available)
    - a restriction on who may be vaccinated (65+ only)
    - an expansion of availability (vaccinating essential workers)
    This free-form tagging interface is meant to make it easy to add new entries to our ontology as we (frequently)
    encounter new rules.
    This is modelled as a separate table so that metadata can be easily added to the tags.
    For example, the 'disabled' boolean is used to determine which tags should no longer be used, even as they exist in
    historical data.
    """

    name = CharTextField(unique=True)
    slug = models.SlugField(null=True)
    group = models.CharField(
        max_length=10,
        choices=(("yes", "yes"), ("no", "no"), ("skip", "skip"), ("other", "other")),
        null=True,
    )
    notes = CharTextField(null=True, blank=True)
    disabled = models.BooleanField(default=False)

    previous_names = models.JSONField(
        default=list,
        help_text="Any previous names used for this tag, used for keeping import scripts working",
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "availability_tag"


class AppointmentTag(models.Model):
    """
    A tag indicating whether an appointment is needed and, if so, how it should be scheduled (e.g., by phone, online, other).
    This is modelled as a separate table so that metadata can be easily added to the tags.
    For example, has_details indicates whether the appointment_details on the report should contain more information,
    such as a URL.
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=30, unique=True)
    has_details = models.BooleanField(
        default=False,
        help_text="should the report refer to the appointment details. Unfortunately we can't enforce constraints across joins.",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "appointment_tag"


class Report(models.Model):
    """
    A report on the availability of the vaccine. Could be from a phone call, or a site visit, or reading a website.
    """

    class ReportSource(models.TextChoices):
        CALLER_APP = "ca", "Caller app"
        DATA_CORRECTIONS = "dc", "Data corrections"

    location = models.ForeignKey(
        Location,
        related_name="reports",
        on_delete=models.PROTECT,
        help_text="a report must have a location",
    )
    is_pending_review = models.BooleanField(
        default=False, help_text="Reports that are pending review by our QA team"
    )
    originally_pending_review = models.BooleanField(
        null=True,
        help_text="Reports that were originally flagged as pending review",
    )
    claimed_by = models.ForeignKey(
        "auth.User",
        related_name="claimed_reports",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="QA reviewer who has claimed this report",
    )
    claimed_at = models.DateTimeField(
        help_text="When the QA reviewer claimed this report",
        blank=True,
        null=True,
    )
    soft_deleted = models.BooleanField(
        default=False,
        help_text="we never delete rows from this table; all deletes are soft",
    )
    soft_deleted_because = CharTextField(null=True, blank=True)
    report_source = models.CharField(
        max_length=2,
        choices=ReportSource.choices,
        default=ReportSource.CALLER_APP,
    )
    appointment_tag = models.ForeignKey(
        AppointmentTag,
        related_name="reports",
        on_delete=models.PROTECT,
        help_text="a single appointment tag, indicating how appointments are made",
    )
    appointment_details = CharTextField(
        null=True,
        blank=True,
        help_text="appointment details (e.g., a URL). Should not be used if the appointment_tag's has_details is false.",
    )
    public_notes = models.TextField(null=True, blank=True)
    internal_notes = models.TextField(null=True, blank=True)
    reported_by = models.ForeignKey(
        Reporter, related_name="reports", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="the time when the report was submitted. We will interpret this as a validity time",
    )
    call_request = models.ForeignKey(
        "CallRequest",
        null=True,
        blank=True,
        related_name="reports",
        on_delete=models.SET_NULL,
        help_text="the call request that this report was based on, if any.",
    )

    availability_tags = models.ManyToManyField(
        AvailabilityTag,
        related_name="reports",
        db_table="call_report_availability_tag",
    )

    airtable_id = models.CharField(
        max_length=20,
        null=True,
        unique=True,
        help_text="Airtable record ID, if this has one",
    )
    airtable_json = models.JSONField(null=True, blank=True)
    public_id = models.SlugField(
        unique=True, help_text="ID that we expose outside of the application"
    )

    def created_at_utc(self):
        tz = pytz.UTC
        created_at_utc = timezone.localtime(self.created_at, tz)
        return dateformat.format(created_at_utc, "jS M Y fA e")

    def availability(self):
        # Used by the admin list view
        return ", ".join(t.name for t in self.availability_tags.all())

    def based_on_call_request(self):
        return self.call_request is not None

    def full_appointment_details(self, location: Optional[Location] = None):
        # We often call this from contexts where the report was
        # prefetched off of a location, and fetching self.location
        # would be another DB query within a tight loop; support
        # passing it in as an extra arg.
        if location is not None:
            assert location.id == self.location_id
        else:
            location = self.location

        # Do not access self.location below; use location instead.
        if self.appointment_details:
            return self.appointment_details
        elif location.county and self.appointment_tag.slug == "county_website":
            return location.county.vaccine_reservations_url
        elif self.appointment_tag.slug == "myturn_ca_gov":
            return "https://myturn.ca.gov/"
        elif location.website:
            return location.website
        elif location.provider and location.provider.appointments_url:
            return location.provider.appointments_url
        return None

    class Meta:
        db_table = "report"

    def __str__(self):
        return "Call to {} by {} at {}".format(
            self.location, self.reported_by, self.created_at
        )

    @property
    def pid(self):
        return "r" + pid.from_int(self.pk)

    def save(self, *args, **kwargs):
        set_public_id_later = False
        if (not self.public_id) and self.airtable_id:
            self.public_id = self.airtable_id
        elif not self.public_id:
            set_public_id_later = True
            self.public_id = "tmp:{}".format(uuid.uuid4())
        super().save(*args, **kwargs)
        if set_public_id_later:
            Report.objects.filter(pk=self.pk).update(public_id=self.pid)
        self.location.update_denormalizations()

    def delete(self, *args, **kwargs):
        location = self.location
        super().delete(*args, **kwargs)
        location.update_denormalizations()


class ReportReviewTag(models.Model):
    tag = models.CharField(unique=True, max_length=64)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.tag


class ReportReviewNote(models.Model):
    report = models.ForeignKey(
        Report, related_name="review_notes", on_delete=models.PROTECT
    )
    author = models.ForeignKey(
        "auth.User", related_name="review_notes", on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)
    tags = models.ManyToManyField(
        ReportReviewTag,
        related_name="review_notes",
        blank=True,
    )

    def __str__(self):
        return "{} review note on {}".format(self.author, self.report)


class EvaReport(models.Model):
    """
    A report obtained by our robotic assistant Eva. Eva only gathers a subset of the data that we would normally gather.
    """

    location = models.ForeignKey(
        Location, related_name="eva_reports", on_delete=models.PROTECT
    )
    name_from_import = CharTextField(null=True, blank=True)
    phone_number_from_import = CharTextField(null=True, blank=True)
    has_vaccines = models.BooleanField()
    hung_up = models.BooleanField()
    valid_at = models.DateTimeField(
        help_text="the time when Eva's report was made (or our best estimate"
    )
    uploaded_at = models.DateTimeField(
        help_text="this is the time when we uploaded Eva's report. It might not even be on the same day that the report was filed"
    )
    airtable_id = models.CharField(
        max_length=20,
        null=True,
        unique=True,
        help_text="Airtable record ID, if this has one",
    )

    def __str__(self):
        return "Eva call to {} at {}".format(self.location, self.valid_at)

    class Meta:
        db_table = "eva_report"


class CallRequestReason(models.Model):
    short_reason = CharTextField(unique=True)
    long_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.short_reason

    class Meta:
        db_table = "call_request_reason"


class CallRequest(models.Model):
    """
    A request to make a phone call (i.e., an entry in the call queue).
    This reifies the notion of "requesting a call" so that all of the call attempts can be tracked with full history.
    For example, if a bug in an app has us call a location repeatedly, we have the full record of why those calls were made.
    """

    class PriorityGroup(models.IntegerChoices):
        CRITICAL_1 = 1, "1-critical"
        IMPORTANT_2 = 2, "2-important"
        NORMAL_3 = 3, "3-normal"
        LOW_4 = 4, "4-low"
        NOT_PRIORITIZED_99 = 99, "99-not_prioritized"

    class TipType(models.TextChoices):
        EVA = "eva_report", "Eva report"
        SCOOBY = "scooby_report", "Scooby report"
        DATA_CORRECTIONS = "data_corrections_report", "Data corrections report"

    location = models.ForeignKey(
        Location, related_name="call_requests", on_delete=models.PROTECT
    )
    vesting_at = models.DateTimeField(
        help_text="the time at which this call request is considered 'active'. For example, a call request made by a skip will have a future vesting time."
    )
    claimed_by = models.ForeignKey(
        Reporter,
        blank=True,
        null=True,
        related_name="call_requests_claimed",
        on_delete=models.PROTECT,
        help_text="if non-null, the reporter who has currently 'claimed' this request",
    )
    claimed_until = models.DateTimeField(
        blank=True,
        null=True,
        help_text="if non-null, the time until which the report is considered claimed",
    )
    call_request_reason = models.ForeignKey(
        CallRequestReason,
        related_name="call_requests",
        on_delete=models.PROTECT,
        help_text="a tag indicating why the call was added to the queue",
    )
    completed = models.BooleanField(
        default=False, help_text="Has this call been completed"
    )
    completed_at = models.DateTimeField(
        blank=True, null=True, help_text="When this call was marked as completed"
    )
    priority_group = models.IntegerField(
        choices=PriorityGroup.choices,
        default=PriorityGroup.NOT_PRIORITIZED_99,
    )
    priority = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Priority for call queue - higher number means higher priority",
    )

    tip_type = CharTextField(
        choices=TipType.choices,
        blank=True,
        null=True,
        help_text=" the type of tip that prompted this call request, if any",
    )
    tip_report = models.ForeignKey(
        Report,
        blank=True,
        null=True,
        related_name="prompted_call_requests",
        on_delete=models.PROTECT,
        help_text="the id of the report, if any that prompted this call request",
    )

    def __str__(self):
        return "Call request to {} vesting at {}".format(self.location, self.vesting_at)

    class Meta:
        db_table = "call_request"
        # Group 1 comes before group 2 comes before group 3
        # Within those groups, lower priority scores come before higher
        # Finally we tie-break on ID optimizing for mostl recently created first
        ordering = ("priority_group", "-priority", "-id")

    @classmethod
    def available_requests(cls, qs=None):
        if qs is None:
            qs = cls.objects
        now = timezone.now()
        return (
            qs.filter(
                # Unclaimed
                Q(claimed_until__isnull=True)
                | Q(claimed_until__lte=now)
            )
            .filter(completed=False, vesting_at__lte=now)
            .exclude(
                Q(location__phone_number__isnull=True) | Q(location__phone_number="")
            )
        )

    @classmethod
    @beeline.traced("backfill_queue")
    def backfill_queue(cls, minimum=None):
        if minimum is None:
            minimum = settings.MIN_CALL_REQUEST_QUEUE_ITEMS
        num_to_create = max(0, minimum - cls.available_requests().count())
        now = timezone.now()
        beeline.add_context({"count": num_to_create})
        # Queue up that many locations, by never-called or longest-ago-called
        # We use .select_for_update(nowait=True) to try to avoid race conditions
        # where multiple calls to /api/requestCall attempt to backfill at
        # the same time.
        # Only consider existing locations that are not currently queued
        location_options = Location.objects.exclude(
            id__in=cls.available_requests().values("location_id"),
        ).filter(
            soft_deleted=False,
            do_not_call=False,
        )
        if num_to_create:
            backfill_reason = CallRequestReason.objects.get_or_create(
                short_reason="Automatic backfill"
            )[0]
            # Try for never-called
            never_called_qs = location_options.filter(
                reports__isnull=True,
                do_not_call=False,
            )[:num_to_create]
            never_called = list(never_called_qs)
            for location in never_called:
                cls.objects.create(
                    location=location,
                    vesting_at=now,
                    call_request_reason=backfill_reason,
                )
            num_to_create = max(0, num_to_create - len(never_called))
            beeline.add_context({"never_called_added": len(never_called)})
        # Do we need to create any more? If so do longest-ago-called
        if num_to_create:
            location_options.select_for_update(nowait=True)
            # Called longest ago
            called_longest_ago_qs = location_options.annotate(
                most_recent_report=Max("reports__created_at")
            ).order_by("most_recent_report")[:num_to_create]
            called_longest_ago = list(called_longest_ago_qs)
            for location in called_longest_ago:
                cls.objects.create(
                    location=location,
                    vesting_at=now,
                    call_request_reason=backfill_reason,
                )
            beeline.add_context({"called_longest_ago_added": len(called_longest_ago)})


class PublishedReport(models.Model):
    """
    NOT CURRENTLY USED
    See https://github.com/CAVaccineInventory/vial/issues/179#issuecomment-815353624

    A report that should be published to our website and API feed.
    This report is generally derived from one or more other report types, and might be created automatically or manually.
    If a report is edited for publication, the published_report should be edited to maintain the integrity of our records.
    This report represents the (possibly implicit) editorial aspects of our data pipeline.
    The relationship between published reports and the various report types may be many-to-many:
    a single report may trigger many published reports, and each published report may draw on several data sources.
    """

    location = models.ForeignKey(
        Location, related_name="published_reports", on_delete=models.PROTECT
    )
    appointment_tag = models.ForeignKey(
        AppointmentTag,
        related_name="published_reports",
        on_delete=models.PROTECT,
        help_text="a single appointment tag, indicating how appointments are made",
    )
    appointment_details = models.TextField(
        blank=True,
        null=True,
        help_text="appointment details (e.g., a URL). Should not be used if the appointment_tag's has_details is false.",
    )
    public_notes = models.TextField(blank=True, null=True)

    reported_by = models.ForeignKey(
        Reporter, related_name="published_reports", on_delete=models.PROTECT
    )
    valid_at = models.DateTimeField(
        help_text='the time that determines this report\'s time priority. Generally, only the latest report is displayed. This determines the "freshness" of the published report.'
    )
    created_at = models.DateTimeField(
        help_text="the time at which this report is created (which may be different from the time at which it is valid)"
    )

    availability_tags = models.ManyToManyField(
        AvailabilityTag,
        related_name="published_reports",
        db_table="published_report_availability_tag",
    )
    reports = models.ManyToManyField(
        Report,
        related_name="published_reports",
        db_table="published_report_reports",
    )
    eva_reports = models.ManyToManyField(
        EvaReport,
        related_name="published_reports",
        db_table="published_report_eva_report",
    )

    def __str__(self):
        return "Published report for {} valid at {}".format(
            self.location, self.valid_at
        )

    class Meta:
        db_table = "published_report"


class ImportRun(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    api_key = models.ForeignKey(
        "api.ApiKey", blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return str(self.created_at)

    class Meta:
        db_table = "import_run"


class SourceLocation(models.Model):
    "Source locations are unmodified records imported from other sources"
    import_run = models.ForeignKey(
        ImportRun,
        blank=True,
        null=True,
        related_name="imported_source_locations",
        on_delete=models.SET_NULL,
    )
    source_uid = CharTextField(
        unique=True,
        help_text="The ID within that other source, UUID etc or whatever they have - globally unique because it includes a prefix which is a copy of the source_name",
    )
    source_name = CharTextField(help_text="e.g. vaccinespotter")
    name = CharTextField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    import_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Big bag of JSON with original data",
    )
    matched_location = models.ForeignKey(
        Location,
        blank=True,
        null=True,
        related_name="matched_source_locations",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "source_location"


class ConcordanceIdentifier(models.Model):
    source = models.CharField(max_length=32)
    identifier = models.CharField(max_length=128)

    locations = models.ManyToManyField(
        Location,
        related_name="concordances",
        blank=True,
        db_table="concordance_location",
    )
    source_locations = models.ManyToManyField(
        SourceLocation,
        related_name="concordances",
        blank=True,
        db_table="concordance_source_location",
    )

    class Meta:
        unique_together = ("source", "identifier")
        db_table = "concordance_identifier"

    def __str__(self):
        return "{}:{}".format(self.source, self.identifier)


# Signals
@receiver(m2m_changed, sender=Report.availability_tags.through)
def denormalize_location(sender, instance, **kwargs):
    instance.location.update_denormalizations()
