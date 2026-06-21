# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-06-21

### Added
- `mcp-name` provenance marker in the README so the package can be listed on the
  official MCP registry. No functional changes.

## [0.1.0] - 2026-06-21

### Added
- Initial release. 10 MCP tools over SEC EDGAR, FRED, Tradernet and OpenFIGI:
  - `get_company_facts` — normalized fundamentals (revenue, EPS, margins, debt).
  - `get_financial_statement` — income/balance/cashflow as structured JSON.
  - `get_filings` — recent SEC filings with metadata and document URLs.
  - `parse_filing_section` — extract a 10-K section (risk factors, MD&A) as clean text.
  - `get_insider_trades` — structured Form 3/4/5 insider transactions.
  - `get_macro_series` — FRED macro time series.
  - `get_quote` — real-time L1 quote via the Tradernet WebSocket feed.
  - `get_etf_holdings` — ETF/fund portfolio (NPORT-P) with AUM, NAV and asset/country mix.
  - `get_holdings_analysis` — look-through sector breakdown and weighted net-margin/ROE.
  - `get_index` — index snapshot (level via FRED, tracking ETF, holdings preview).
- Holding resolution by CUSIP/ISIN (OpenFIGI) with name-match fallback.
- Centralized HTTPS host-allowlist (SSRF defense), `defusedxml` XML parsing, secret redaction.

[0.1.1]: https://github.com/birthday-tools/edgarmcp/releases/tag/v0.1.1
[0.1.0]: https://github.com/birthday-tools/edgarmcp/releases/tag/v0.1.0
