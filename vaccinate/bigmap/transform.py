from vaccine_feed_ingest_schema.schema import NormalizedLocation


def address_to_full_address(address):
    if address.city is None or address.state is None or address.zip is None:
        return None

    if "street2" in address:
        return f"{address.street1}\n{address.street2}\n{address.city}, {address.state} {address.zip}"
    else:
        return f"{address.street1}\n{address.city}, {address.state} {address.zip}"


def concat_address_lines(address):
    if address.street2 is not None:
        return f"{address.street1}\n{address.street2}"
    else:
        return address.street1


BANKING_CONTACT_METHOD = "booking"


def source_to_location(normalized_location):
    normalized_location = NormalizedLocation(**normalized_location)
    location = {
        "name": normalized_location.name,
    }

    if normalized_location.address is not None:
        location["full_address"] = address_to_full_address(normalized_location.address)
        location["street_address"] = concat_address_lines(normalized_location.address)
        location["city"] = normalized_location.address.city
        location[
            "state"
        ] = normalized_location.address.state  # needs foreign key lookup
        location["zip_code"] = normalized_location.address.zip

    if normalized_location.location is not None:
        # Geo data
        location["latitude"] = normalized_location.location.latitude
        location["longitude"] = normalized_location.location.longitude

    phone_number = None
    website = None
    if normalized_location.contact is not None:
        # Structured as two loops over the possible contact info, since we want:
        # 1. A phone number (website) if there is only one over all contact methods.
        # 2. The one associated with BANKING_CONTACT_METHOD if there is one.

        for contact_method in normalized_location.contact:
            if phone_number is None and contact_method.phone is not None:
                phone_number = contact_method.phone
            if website is None and contact_method.website is not None:
                website = contact_method.website

        # Loop to fill with BANKING_CONTACT_METHOD
        for contact_method in normalized_location.contact:
            if contact_method.contact_type == BANKING_CONTACT_METHOD:
                if contact_method.phone is not None:
                    phone_number = contact_method.phone
                if contact_method.website is not None:
                    website = contact_method.website

    location["phone_number"] = phone_number
    location["website"] = website

    return location
