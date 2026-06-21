# EdgarMCP

[![PyPI](https://img.shields.io/pypi/v/mcp-edgar.svg)](https://pypi.org/project/mcp-edgar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/birthday-tools/edgarmcp/actions/workflows/ci.yml/badge.svg)](https://github.com/birthday-tools/edgarmcp/actions/workflows/ci.yml)

An MCP server that gives AI agents clean, normalized access to financial data:
company fundamentals and insider trades from [SEC EDGAR](https://www.sec.gov/edgar),
macro series from [FRED](https://fred.stlouisfed.org/), real-time quotes via the
Tradernet WebSocket feed, ETF/fund holdings from SEC NPORT-P, look-through analytics,
and index snapshots.

Raw sources (XBRL, bulky filing HTML, ownership XML) are expensive and error-prone for
agents — they burn tokens and trip up on parsing. EdgarMCP returns agent-ready JSON.

## Installation

```bash
pip install mcp-edgar
```

This installs the `edgarmcp` console script (a stdio MCP server).

## Quick start

Add it to an MCP client. For Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "edgarmcp": {
      "command": "edgarmcp",
      "env": {
        "FRED_API_KEY": "your-free-fred-key",
        "OPENFIGI_API_KEY": "optional-openfigi-key"
      }
    }
  }
}
```

Both keys are optional: without `FRED_API_KEY` the FRED-backed tools degrade gracefully;
without `OPENFIGI_API_KEY` holding resolution runs in anonymous mode.

## Tools

| Tool | Purpose |
|---|---|
| `get_company_facts(ticker)` | Normalized fundamentals (revenue, EPS, margins, debt) |
| `get_financial_statement(ticker, statement, period)` | Income/balance/cashflow as structured JSON |
| `get_filings(ticker, form_type, limit)` | Recent SEC filings (10-K/10-Q/8-K) with metadata and document URLs |
| `parse_filing_section(url, section)` | Extract a 10-K section (Risk Factors, MD&A) as clean text |
| `get_insider_trades(ticker, limit)` | Form 3/4/5 insider transactions (who, role, buy/sell, volume) |
| `get_macro_series(series_id, start, end)` | FRED macro series (rates, inflation, unemployment) with metadata |
| `get_quote(ticker)` | Real-time L1 quote (last/bid/ask/volume) via the Tradernet WebSocket feed |
| `get_etf_holdings(ticker, limit)` | ETF/fund holdings (top by weight) + AUM, NAV, asset/country mix from SEC NPORT-P |
| `get_holdings_analysis(symbol, limit)` | Look-through of an ETF/index: sector breakdown + weighted net-margin/ROE with coverage |
| `get_index(index)` | Index snapshot (S&P 500, NASDAQ-100, Dow, NASDAQ Composite): level from FRED, tracking ETF, holdings preview |

## Configuration

| Variable | Description | Default |
|---|---|---|
| `EDGAR_USER_AGENT` | User-Agent for SEC requests | `EdgarMCP/0.1 (contact: info+sec@birthday.tools)` |
| `EDGAR_RATE_LIMIT` | Requests per second | `10` |
| `EDGAR_CACHE_DIR` | File cache directory | `edgar_cache` |
| `FRED_API_KEY` | Free FRED key for `get_macro_series` / index levels | — |
| `OPENFIGI_API_KEY` | Optional OpenFIGI key for higher CUSIP/ISIN rate limit | — |

Variables are read from the environment; locally you can put them in a `.env` file.

## Architecture

Three isolated layers: a platform-independent **data layer** (HTTP client with a host
allowlist, ticker/name/CUSIP/ISIN resolution, XBRL normalizers, filing/ownership/NPORT-P
parsers, FRED, the Tradernet WebSocket client, OpenFIGI identifier mapping, look-through
and index analytics); a **cache layer** (aggressive caching of immutable filings and FIGI
mappings; mutable FRED series are not cached); and a thin **MCP layer**. The data layer
knows nothing about MCP and ports unchanged between a marketplace and self-hosting.

## Security

- Outbound requests are restricted to an HTTPS host allowlist (SSRF defense), centralized
  across all sources (SEC, FRED, OpenFIGI).
- Ownership and NPORT XML is parsed with `defusedxml` (XXE / billion-laughs defense).
- Secrets (FRED / OpenFIGI keys) are redacted from error messages and never placed in URLs
  or cache keys.
- Real-time quotes come from Tradernet's public anonymous WebSocket feed
  (`wss://wss.tradernet.com/`); a dedicated client with a hardcoded URL.
- CUSIP/ISIN holding resolution goes through OpenFIGI (`api.openfigi.com`, allowlisted);
  on failure it falls back to name matching.

## Data licenses

SEC EDGAR data is public domain, used with a descriptive `User-Agent` and the 10 req/s
limit. FRED data is provided by the Federal Reserve Bank of St. Louis under its
[terms of use](https://fred.stlouisfed.org/legal/). Real-time quotes come from Tradernet's
public anonymous WebSocket feed. CUSIP/ISIN → ticker mapping uses
[OpenFIGI](https://www.openfigi.com/) (Bloomberg; free tier, 25 req/min anonymous,
250 req/min with a key).

## License

[MIT](LICENSE) © 2026 birthday.tools
