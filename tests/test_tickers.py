import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver, UnknownTicker, cik_padded

TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}
URL = "https://www.sec.gov/files/company_tickers.json"


def make_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=TICKERS_JSON)

    return EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))


def test_cik_padded():
    assert cik_padded(320193) == "0000320193"


def test_resolve_is_case_insensitive():
    r = TickerResolver(make_client(), URL)
    assert r.resolve("aapl") == 320193
    assert r.resolve("MSFT") == 789019


def test_unknown_ticker_raises():
    r = TickerResolver(make_client(), URL)
    with pytest.raises(UnknownTicker):
        r.resolve("ZZZZ")
