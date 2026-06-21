import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.macro import get_macro_series, MissingApiKey, FredError

SERIES_META = {"seriess": [{
    "id": "FEDFUNDS", "title": "Federal Funds Effective Rate",
    "units": "Percent", "frequency": "Monthly",
}]}
OBSERVATIONS = {"observations": [
    {"date": "2024-01-01", "value": "5.33"},
    {"date": "2024-02-01", "value": "."},
    {"date": "2024-03-01", "value": "5.33"},
]}


def make_client(extra=None):
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/fred/series":
            return httpx.Response(200, json=(extra or SERIES_META))
        if p == "/fred/series/observations":
            return httpx.Response(200, json=OBSERVATIONS)
        return httpx.Response(404)

    return EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))


def test_get_macro_series_metadata_and_observations():
    out = get_macro_series(make_client(), "https://api.stlouisfed.org", "KEY", "FEDFUNDS")
    assert out["series_id"] == "FEDFUNDS"
    assert out["title"] == "Federal Funds Effective Rate"
    assert out["units"] == "Percent"
    assert out["frequency"] == "Monthly"
    assert out["count"] == 3


def test_observations_parse_missing_sentinel():
    out = get_macro_series(make_client(), "https://api.stlouisfed.org", "KEY", "FEDFUNDS")
    obs = out["observations"]
    assert obs[0] == {"date": "2024-01-01", "value": 5.33}
    assert obs[1] == {"date": "2024-02-01", "value": None}  # "." sentinel
    assert obs[2]["value"] == 5.33


def test_missing_api_key_raises():
    with pytest.raises(MissingApiKey):
        get_macro_series(make_client(), "https://api.stlouisfed.org", "", "FEDFUNDS")


def test_fred_error_message_raises():
    err = {"error_message": "Bad Request. The series does not exist."}
    with pytest.raises(FredError):
        get_macro_series(make_client(extra=err), "https://api.stlouisfed.org", "KEY", "NOPE")


def test_api_key_not_leaked_on_http_error():
    def handler(request):
        return httpx.Response(400, text="bad request")

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    with pytest.raises(FredError) as ei:
        get_macro_series(client, "https://api.stlouisfed.org", "SUPERSECRETKEY123", "FEDFUNDS")
    msg = str(ei.value)
    assert "SUPERSECRETKEY123" not in msg
    assert "REDACTED" in msg


def test_start_end_forwarded_to_query():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/fred/series":
            return httpx.Response(200, json=SERIES_META)
        if p == "/fred/series/observations":
            seen["start"] = request.url.params.get("observation_start")
            seen["end"] = request.url.params.get("observation_end")
            return httpx.Response(200, json=OBSERVATIONS)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    get_macro_series(client, "https://api.stlouisfed.org", "KEY", "FEDFUNDS", start="2024-01-01", end="2024-03-01")
    assert seen["start"] == "2024-01-01"
    assert seen["end"] == "2024-03-01"
