from factory import Faker, Iterator, LazyAttribute, Maybe, lazy_attribute, random
from factory.django import DjangoModelFactory
from faker import Faker as DirectFaker

from .models import County, Location, LocationType, Reporter, State

direct_faker = DirectFaker(["en_US"])


class ReporterFactory(DjangoModelFactory):
    class Meta:
        model = Reporter

    external_id = Faker("hexify", text="auth0:auth0|^^^^^^^^^^^^^^^^^^^^^^^^")

    name = Faker("name")
    email = Faker("ascii_safe_email")
    auth0_role_names = Faker(
        "random_element",
        elements=["Volunteer Caller", "CC1 callers", "CC: Helpware"],
    )


class LocationFactory(DjangoModelFactory):
    class Meta:
        model = Location

    class Params:
        geo_data = Faker("local_latlng")
        has_url = Faker("boolean", chance_of_getting_true=0.1)
        # Sadly, postalcode_in_state doesn't like territories
        state_abbr = Faker("state_abbr", include_territories=False)

    name = Faker("company")
    phone_number = Faker("phone_number")
    street_address = Faker("street_address")
    # City will match with the lat/lng, but not the state/county/zipcode
    city = LazyAttribute(lambda o: o.geo_data[2])

    @lazy_attribute
    def state(self) -> State:
        return State.objects.get(abbreviation=self.state_abbr)

    # County will match with the state but not zipcode/lat/lng
    @lazy_attribute
    def county(self) -> County:
        return random.randgen.choice(self.state.counties.all())

    # Zipcode will match with the state but not county/lat/lng
    @lazy_attribute
    def zip_code(self) -> str:
        return direct_faker.postalcode_in_state(state_abbr=self.state_abbr)

    # A hodgepodge of things!
    @lazy_attribute
    def full_address(self) -> str:
        return f"{self.street_address}\n{self.city}, {self.state} {self.zip_code}"

    latitude = LazyAttribute(lambda o: o.geo_data[0])
    longitude = LazyAttribute(lambda o: o.geo_data[1])

    # Only 10% of locations have a URL
    website = Maybe("has_url", Faker("url"))

    location_type = Iterator(LocationType.objects.all())
