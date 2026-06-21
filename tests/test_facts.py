import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.facts import get_company_facts

TICKERS_JSON = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}

COMPANYFACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [
                    {"end": "2022-09-24", "val": 394328000000, "form": "10-K", "fy": 2022, "fp": "FY"},
                    {"end": "2023-09-30", "val": 383285000000, "form": "10-K", "fy": 2023, "fp": "FY"},
                ]}
            },
            "NetIncomeLoss": {
                "units": {"USD": [
                    {"end": "2023-09-30", "val": 96995000000, "form": "10-K", "fy": 2023, "fp": "FY"},
                ]}
            },
            "EarningsPerShareBasic": {
                "units": {"USD/shares": [
                    {"end": "2023-09-30", "val": 6.16, "form": "10-K", "fy": 2023, "fp": "FY"},
                ]}
            },
        }
    },
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


def test_get_company_facts_picks_latest_period():
    client, resolver = make_deps()
    result = get_company_facts(client, "https://data.sec.gov", resolver, "AAPL")
    assert result["ticker"] == "AAPL"
    assert result["cik"] == 320193
    assert result["entity_name"] == "Apple Inc."
    rev = result["metrics"]["revenue"]
    assert rev["value"] == 383285000000
    assert rev["period"] == "2023-09-30"
    assert rev["form"] == "10-K"


def test_get_company_facts_includes_eps_and_net_income():
    client, resolver = make_deps()
    m = get_company_facts(client, "https://data.sec.gov", resolver, "AAPL")["metrics"]
    assert m["net_income"]["value"] == 96995000000
    assert m["eps_basic"]["value"] == 6.16
    assert m["eps_basic"]["unit"] == "USD/shares"


def test_revenue_falls_back_to_secondary_tag():
    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    facts = {
        "cik": 320193, "entityName": "Apple Inc.",
        "facts": {"us-gaap": {
            "Revenues": {"units": {"USD": [
                {"end": "2023-09-30", "val": 383285000000, "form": "10-K"}]}},
        }},
    }

    def handler(request):
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json=facts)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    result = get_company_facts(client, "https://data.sec.gov", resolver, "AAPL")
    assert result["metrics"]["revenue"]["value"] == 383285000000
