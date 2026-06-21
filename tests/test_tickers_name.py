import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver, normalize_company_name

CT = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
    "1": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"},
    "2": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    "3": {"cik_str": 1652044, "ticker": "GOOGL", "title": "ALPHABET INC"},
}


def test_normalize_strips_suffixes_and_punctuation():
    assert normalize_company_name("Apple Inc.") == "APPLE"
    assert normalize_company_name("Amazon.com Inc") == "AMAZON"
    assert normalize_company_name("Berkshire Hathaway Inc Class B") == "BERKSHIRE HATHAWAY"
    assert normalize_company_name("Alphabet Inc") == "ALPHABET"


def _resolver():
    def handler(request):
        return httpx.Response(200, json=CT)
    client = EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))
    return TickerResolver(client, "https://example/company_tickers.json")


def test_resolve_name_hit_and_miss():
    r = _resolver()
    assert r.resolve_name("Apple Inc")["ticker"] == "AAPL"
    assert r.resolve_name("Amazon.com Inc")["ticker"] == "AMZN"
    assert r.resolve_name("Berkshire Hathaway Inc Class B")["cik"] == 1067983
    assert r.resolve_name("Nonexistent Holdings Ltd") is None
