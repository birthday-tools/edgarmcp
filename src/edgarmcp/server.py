from typing import Callable

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .cache import FileCache
from .config import Settings
from .deps import Context, build_context
from .analysis import get_holdings_analysis
from .facts import get_company_facts, get_financial_statement
from .filings import get_filings
from .funds import get_etf_holdings
from .http_client import EdgarClient
from .indices import get_index
from .insider import get_insider_trades
from .macro import get_macro_series
from .parser import parse_filing_section
from .quotes import get_quote


def build_tools(ctx: Context) -> dict[str, Callable]:
    s = ctx.settings

    def company_facts(ticker: str) -> dict:
        return get_company_facts(ctx.client, s.base_data, ctx.resolver, ticker)

    def financial_statement(ticker: str, statement: str, period: str = "annual") -> dict:
        return get_financial_statement(ctx.client, s.base_data, ctx.resolver, ticker, statement, period)

    def filings(ticker: str, form_type: str | None = None, limit: int = 10) -> list[dict]:
        return get_filings(ctx.client, s.base_data, s.base_www, ctx.resolver, ticker, form_type, limit)

    def filing_section(url: str, section: str) -> str:
        return parse_filing_section(ctx.client, url, section)

    def insider_trades(ticker: str, limit: int = 10) -> list[dict]:
        return get_insider_trades(ctx.client, s.base_data, s.base_www, ctx.resolver, ticker, limit)

    def macro_series(series_id: str, start: str | None = None, end: str | None = None) -> dict:
        return get_macro_series(ctx.client, s.base_fred, s.fred_api_key, series_id, start, end)

    def quote(ticker: str) -> dict:
        return get_quote(ctx.tradernet, ticker)

    def etf_holdings(ticker: str, limit: int = 25) -> dict:
        return get_etf_holdings(ctx.client, s.base_data, s.base_www, ctx.resolver, ticker, limit)

    def holdings_analysis(symbol: str, limit: int = 25) -> dict:
        return get_holdings_analysis(ctx.client, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, ctx.resolver, symbol, limit)

    def index_info(index: str) -> dict:
        return get_index(ctx.client, s.base_data, s.base_www, s.base_fred, s.fred_api_key, s.base_figi, s.openfigi_api_key, ctx.resolver, index)

    return {
        "get_company_facts": company_facts,
        "get_financial_statement": financial_statement,
        "get_filings": filings,
        "parse_filing_section": filing_section,
        "get_insider_trades": insider_trades,
        "get_macro_series": macro_series,
        "get_quote": quote,
        "get_etf_holdings": etf_holdings,
        "get_holdings_analysis": holdings_analysis,
        "get_index": index_info,
    }


def build_server(ctx: Context) -> FastMCP:
    mcp = FastMCP("EdgarMCP")
    tools = build_tools(ctx)

    @mcp.tool(name="get_company_facts", description="Normalized fundamentals (revenue, EPS, margins, debt) for a US-listed ticker.")
    def get_company_facts_tool(ticker: str) -> dict:
        return tools["get_company_facts"](ticker)

    @mcp.tool(name="get_financial_statement", description="Structured income/balance/cashflow statement. statement: income|balance|cashflow; period: annual|quarterly.")
    def get_financial_statement_tool(ticker: str, statement: str, period: str = "annual") -> dict:
        return tools["get_financial_statement"](ticker, statement, period)

    @mcp.tool(name="get_filings", description="Recent SEC filings (10-K/10-Q/8-K) with metadata and document URLs.")
    def get_filings_tool(ticker: str, form_type: str | None = None, limit: int = 10) -> list[dict]:
        return tools["get_filings"](ticker, form_type, limit)

    @mcp.tool(name="parse_filing_section", description="Extract a 10-K section as clean plain text. section: risk_factors|mda|business.")
    def parse_filing_section_tool(url: str, section: str) -> str:
        return tools["parse_filing_section"](url, section)

    @mcp.tool(name="get_insider_trades", description="Structured SEC Form 3/4/5 insider transactions (buys/sells, reporters and roles) for a ticker.")
    def get_insider_trades_tool(ticker: str, limit: int = 10) -> list[dict]:
        return tools["get_insider_trades"](ticker, limit)

    @mcp.tool(name="get_macro_series", description="Fetch a FRED macroeconomic time series (e.g. FEDFUNDS, CPIAUCSL, UNRATE) with metadata and observations.")
    def get_macro_series_tool(series_id: str, start: str | None = None, end: str | None = None) -> dict:
        return tools["get_macro_series"](series_id, start, end)

    @mcp.tool(name="get_quote", description="Real-time L1 quote (last price, bid, ask, day volume) for a ticker via the Tradernet feed.")
    def get_quote_tool(ticker: str) -> dict:
        return tools["get_quote"](ticker)

    @mcp.tool(name="get_etf_holdings", description="ETF/fund portfolio holdings (top positions by weight) plus AUM, NAV and asset/country mix, from the SEC NPORT-P filing.")
    def get_etf_holdings_tool(ticker: str, limit: int = 25) -> dict:
        return tools["get_etf_holdings"](ticker, limit)

    @mcp.tool(name="get_holdings_analysis", description="Look-through analysis of an ETF or index (alias like SP500/QQQ): sector breakdown and weighted net-margin/ROE over the top holdings, with coverage.")
    def get_holdings_analysis_tool(symbol: str, limit: int = 25) -> dict:
        return tools["get_holdings_analysis"](symbol, limit)

    @mcp.tool(name="get_index", description="Index snapshot (S&P 500, NASDAQ-100, Dow, NASDAQ Composite): current level from FRED, tracking ETF, and top holdings preview.")
    def get_index_tool(index: str) -> dict:
        return tools["get_index"](index)

    return mcp


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    client = EdgarClient(
        settings.user_agent,
        FileCache(settings.cache_dir),
        min_interval=1.0 / settings.rate_limit_per_sec if settings.rate_limit_per_sec else 0.0,
        allowed_hosts=settings.allowed_hosts,
    )
    ctx = build_context(settings, client)
    build_server(ctx).run()


if __name__ == "__main__":
    main()
