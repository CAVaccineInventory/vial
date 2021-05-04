from bigmap.transform import BANKING_CONTACT_METHOD, source_to_location


def test_one_contact_method():
    source = {
        "id": "foo:123",
        "source": {"source": "foo", "id": "123", "data": {}},
        "contact": [{"website": "http://example.com"}, {"phone": "555-555-5555"}],
    }
    location = source_to_location(source)
    assert location["phone_number"] == "555-555-5555"
    assert location["website"] == "http://example.com"


def test_split_contact_method():
    source = {
        "id": "foo:123",
        "source": {"source": "foo", "id": "123", "data": {}},
        "contact": [{"website": "http://example.com"}, {"phone": "555-555-5555"}],
    }
    location = source_to_location(source)
    assert location["phone_number"] == "555-555-5555"
    assert location["website"] == "http://example.com"


def test_banking_override_method():
    source = {
        "id": "foo:123",
        "source": {"source": "foo", "id": "123", "data": {}},
        "contact": [
            {"website": "http://example.com"},
            {"phone": "555-555-5555"},
            {
                "contact_type": BANKING_CONTACT_METHOD,
                "phone": "555-555-5556",
            },
            {
                "contact_type": BANKING_CONTACT_METHOD,
                "website": "http://example2.com",
            },
        ],
    }
    location = source_to_location(source)
    assert location["phone_number"] == "555-555-5556"
    assert location["website"] == "http://example2.com"


def test_default_to_first_method():
    source = {
        "id": "foo:123",
        "source": {"source": "foo", "id": "123", "data": {}},
        "contact": [
            {"website": "http://example.com"},
            {"phone": "555-555-5555"},
            {"phone": "555-555-5556"},
            {"website": "http://example2.com"},
        ],
    }
    location = source_to_location(source)
    assert location["phone_number"] == "555-555-5555"
    assert location["website"] == "http://example.com"


def test_missing_zip():
    source = {
        "id": "foo:123",
        "source": {"source": "foo", "id": "123", "data": {}},
        "address": {
            "street1": "123 Main St",
            "street2": "Suite 4",
            "city": "New York",
            "state": "NY",
        },
    }
    location = source_to_location(source)
    assert location["full_address"] is None
    assert location["street_address"] == "123 Main St\nSuite 4"
