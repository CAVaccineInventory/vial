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
    if "name" in normalized_location:
        location["name"] = normalized_location["name"]

    if "address" in normalized_location:
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

    if "location" in normalized_location:
        # Geo data
        location["latitude"] = normalized_location["location"]["latitude"]
        location["longitude"] = normalized_location["location"]["longitude"]

    if "contact" in normalized_location:
        for contact_method in normalized_location["contact"]:
            if contact_method["contact_type"] == BANKING_CONTACT_METHOD:
                location["phone_number"] = contact_method.get("phone")

    return location
