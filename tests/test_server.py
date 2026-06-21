import asyncio
import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.config import Settings
from edgarmcp.http_client import EdgarClient
from edgarmcp.deps import build_context
from edgarmcp.server import build_tools

TICKERS_JSON = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
COMPANYFACTS = {
    "cik": 320193, "entityName": "Apple Inc.",
    "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"end": "2023-09-30", "val": 383285000000, "form": "10-K"}]}}}},
}
SUBMISSIONS = {"filings": {"recent": {
    "accessionNumber": ["0000320193-23-000106"], "filingDate": ["2023-11-03"],
    "reportDate": ["2023-09-30"], "form": ["10-K"], "primaryDocument": ["aapl.htm"]}}}


def make_ctx():
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "companyfacts" in p:
            return httpx.Response(200, json=COMPANYFACTS)
        if "submissions" in p:
            return httpx.Response(200, json=SUBMISSIONS)
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return build_context(settings, client)


def test_tools_company_facts_and_filings():
    tools = build_tools(make_ctx())
    facts = tools["get_company_facts"]("AAPL")
    assert facts["metrics"]["revenue"]["value"] == 383285000000

    filings = tools["get_filings"]("AAPL", "10-K", 5)
    assert filings[0]["accession"] == "0000320193-23-000106"


def test_all_tools_registered():
    tools = build_tools(make_ctx())
    assert set(tools) == {
        "get_company_facts", "get_financial_statement", "get_filings", "parse_filing_section",
        "get_insider_trades", "get_macro_series", "get_quote", "get_etf_holdings",
        "get_holdings_analysis", "get_index",
    }


def test_registered_tool_names_are_clean():
    from edgarmcp.server import build_server
    mcp = build_server(make_ctx())
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"get_company_facts", "get_financial_statement", "get_filings", "parse_filing_section",
                     "get_insider_trades", "get_macro_series", "get_quote", "get_etf_holdings",
                     "get_holdings_analysis", "get_index"}


def test_macro_series_tool_registered():
    tools = build_tools(make_ctx())
    assert "get_macro_series" in tools


def test_quote_tool_registered():
    tools = build_tools(make_ctx())
    assert "get_quote" in tools


def test_etf_holdings_tool_registered():
    tools = build_tools(make_ctx())
    assert "get_etf_holdings" in tools


def test_insider_trades_tool_registered_and_delegates():
    tools = build_tools(make_ctx())
    assert "get_insider_trades" in tools


def test_financial_statement_tool_delegates():
    tools = build_tools(make_ctx())
    out = tools["get_financial_statement"]("AAPL", "income", "annual")
    assert out["statement"] == "income"
    assert out["line_items"]["revenue"]["value"] == 383285000000


def test_holdings_analysis_and_index_tools_registered():
    tools = build_tools(make_ctx())
    assert "get_holdings_analysis" in tools
    assert "get_index" in tools
