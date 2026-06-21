import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.facts import get_financial_statement, UnknownStatement

TICKERS_JSON = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}

COMPANYFACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            {"end": "2023-09-30", "val": 383285000000, "form": "10-K"},
            {"end": "2023-07-01", "val": 81797000000, "form": "10-Q"},
        ]}},
        "NetIncomeLoss": {"units": {"USD": [
            {"end": "2023-09-30", "val": 96995000000, "form": "10-K"},
        ]}},
    }},
}


def make_deps():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json=COMPANYFACTS)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    return client, resolver


def test_income_statement_annual():
    client, resolver = make_deps()
    out = get_financial_statement(client, "https://data.sec.gov", resolver, "AAPL", "income", "annual")
    assert out["statement"] == "income"
    assert out["period"] == "annual"
    assert out["line_items"]["revenue"]["value"] == 383285000000
    assert out["line_items"]["net_income"]["value"] == 96995000000
    assert out["ticker"] == "AAPL"
    assert out["line_items"]["revenue"]["end"] == "2023-09-30"


def test_income_statement_quarterly_filters_by_form():
    client, resolver = make_deps()
    out = get_financial_statement(client, "https://data.sec.gov", resolver, "AAPL", "income", "quarterly")
    assert out["line_items"]["revenue"]["value"] == 81797000000
    assert out["line_items"]["revenue"]["form"] == "10-Q"


def test_unknown_statement_raises():
    client, resolver = make_deps()
    with pytest.raises(UnknownStatement):
        get_financial_statement(client, "https://data.sec.gov", resolver, "AAPL", "nonsense")


def test_unknown_period_raises():
    client, resolver = make_deps()
    with pytest.raises(UnknownStatement):
        get_financial_statement(client, "https://data.sec.gov", resolver, "AAPL", "income", "badperiod")
