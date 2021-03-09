import pytest

ACAO = "Access-Control-Allow-Origin"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,http_origin,should_have_cors",
    (
        ("/", None, False),
        ("/", "https://example.com", False),
        ("/api/submitReport", None, False),
        ("/api/submitReport", "https://example.com", True),
        ("/api/requestCall", None, False),
        ("/api/requestCall", "https://example.com", True),
    ),
)
def test_cors(client, path, http_origin, should_have_cors):
    kwargs = {}
    if http_origin:
        kwargs["HTTP_ORIGIN"] = http_origin
    response = client.get(path, **kwargs)
    headers = dict(response.items())
    if should_have_cors:
        assert ACAO in headers
        assert headers[ACAO] == "*"
    else:
        assert ACAO not in headers
