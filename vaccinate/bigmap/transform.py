def address_to_full_address(address):
    if "street2" in address:
        return "{}\n{}\n{}, {} {}".format(
            address["street1"],
            address["street2"],
            address["city"],
            address["state"],
            address["zip"],
        )
    else:
        return "{}\n{}, {} {}".format(
            address["street1"], address["city"], address["state"], address["zip"]
        )


def concat_address_lines(address):
    if "street2" in address:
        return "{}\n{}".format(address["street1"], address["street2"])
    else:
        return address["street1"]


BANKING_CONTACT_METHOD = "booking"


def source_to_location(normalized_location):
    location = {}
    if normalized_location.get("name") is not None:
        location["name"] = normalized_location.get("name")

    if normalized_location.get("address") is not None:
        location["full_address"] = address_to_full_address(
            normalized_location["address"]
        )
        location["street_address"] = concat_address_lines(
            normalized_location["address"]
        )
        location["city"] = normalized_location["address"]["city"]
        location["state"] = normalized_location["address"][
            "state"
        ]  # needs foreign key lookup
        location["zip_code"] = normalized_location["address"]["zip"]

    if normalized_location.get("location") is not None:
        # Geo data
        location["latitude"] = normalized_location["location"]["latitude"]
        location["longitude"] = normalized_location["location"]["longitude"]

    phone_number = None
    website = None
    if normalized_location.get("contact") is not None:
        # Structured as two loops over the possible contact info, since we want:
        # 1. A phone number (website) if there is only one over all contact methods.
        # 2. The one associated with BANKING_CONTACT_METHOD if there is one.

        for contact_method in normalized_location["contact"]:
            if phone_number is None and contact_method.get("phone") is not None:
                phone_number = contact_method.get("phone")
            if website is None and contact_method.get("website") is not None:
                website = contact_method.get("website")

        # Loop to fill with BANKING_CONTACT_METHOD
        for contact_method in normalized_location["contact"]:
            if contact_method.get("contact_type") == BANKING_CONTACT_METHOD:
                if contact_method.get("phone") is not None:
                    phone_number = contact_method.get("phone")
                if contact_method.get("website") is not None:
                    website = contact_method.get("website")

    location["phone_number"] = phone_number
    location["website"] = website

    return location
