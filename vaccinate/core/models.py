import datetime
import uuid

import pytz
from django.db import models
from django.db.models import Q
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

    def __str__(self):
        return self.name

    class Meta:
        db_table = "provider"


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
    facebook_page = CharTextField(null=True, blank=True)
    twitter_page = CharTextField(null=True, blank=True)
    vaccine_reservations_url = CharTextField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    vaccine_dashboard_url = CharTextField(null=True, blank=True)
    vaccine_data_url = CharTextField(null=True, blank=True)
    vaccine_arcgis_url = CharTextField(null=True, blank=True)
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
    full_address = CharTextField(
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
        choices=(("yes", "yes"), ("no", "no"), ("skip", "skip")),
        null=True,
    )
    notes = CharTextField(null=True, blank=True)
    disabled = models.BooleanField(default=False)

    previous_names = models.JSONField(
        default=list,
        help_text="Any previous names used for this tag, used for keeping import scripts working",
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
        on_delete=models.PROTECT,
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

    @classmethod
    def available_requests(cls, qs=None):
        if qs is None:
            qs = cls.objects
        now = timezone.now()
        return (
            qs.filter(
                Q(vesting_at__lte=now) & Q(claimed_until__isnull=True)
                | Q(claimed_until__lte=now)
            )
            .filter(location__state__abbreviation="OR")
            .exclude(
                location__reports__created_at__gte=(
                    timezone.now() - datetime.timedelta(days=1)
                )
            )
        )


class PublishedReport(models.Model):
    """
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
