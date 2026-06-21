import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.config import Settings
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.facts import get_company_facts, get_financial_statement, EntityTypeError

TICKERS_JSON = {"0": {"cik_str": 884394, "ticker": "SPY", "title": "SPDR S&P 500 ETF TRUST"}}
FUND_SUBMISSIONS = {"filings": {"recent": {"form": ["NPORT-P", "NPORT-P/A"]}}}


def make_ctx():
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "companyfacts" in p:
            return httpx.Response(404)            # ETF has no XBRL facts
        if "submissions" in p:
            return httpx.Response(200, json=FUND_SUBMISSIONS)
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return settings, client, TickerResolver(client, settings.tickers_url)


def test_company_facts_on_fund_raises_entity_type_error():
    s, c, r = make_ctx()
    with pytest.raises(EntityTypeError) as ei:
        get_company_facts(c, s.base_data, r, "SPY")
    assert "get_etf_holdings" in str(ei.value)


def test_financial_statement_on_fund_raises_entity_type_error():
    s, c, r = make_ctx()
    with pytest.raises(EntityTypeError):
        get_financial_statement(c, s.base_data, r, "SPY", "income", "annual")


def make_double_404_ctx():
    """Both companyfacts AND submissions return 404 — classify_entity raises too."""
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        # companyfacts → 404, submissions → 404 as well
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return settings, client, TickerResolver(client, settings.tickers_url)


def test_routing_fallback_when_classify_also_raises():
    """When companyfacts → 404 and submissions → 404, routing must degrade gracefully
    and re-raise the ORIGINAL companyfacts EdgarHTTPError — not the classify error.
    The original error message contains 'companyfacts'."""
    from edgarmcp.http_client import EdgarHTTPError
    s, c, r = make_double_404_ctx()
    with pytest.raises(EdgarHTTPError) as ei:
        get_company_facts(c, s.base_data, r, "SPY")
    assert "companyfacts" in str(ei.value), (
        f"Expected original companyfacts error but got: {ei.value}"
    )
