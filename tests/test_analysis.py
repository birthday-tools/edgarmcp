import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.config import Settings
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.analysis import get_holdings_analysis

TICKERS_JSON = {
    "0": {"cik_str": 884394, "ticker": "SPY", "title": "SPDR S&P 500 ETF TRUST"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
    "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
}

NPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo><regName>SPDR S&amp;P 500 ETF Trust</regName><repPdDate>2026-03-31</repPdDate></genInfo>
    <fundInfo><totAssets>1000</totAssets><totLiabs>0</totLiabs><netAssets>1000</netAssets></fundInfo>
    <invstOrSecs>
      <invstOrSec><name>Apple Inc</name><cusip>A</cusip><identifiers><isin value="US_A"/></identifiers>
        <balance>1</balance><valUSD>600</valUSD><pctVal>60.0</pctVal><payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry></invstOrSec>
      <invstOrSec><name>NVIDIA Corp</name><cusip>N</cusip><identifiers><isin value="US_N"/></identifiers>
        <balance>1</balance><valUSD>300</valUSD><pctVal>30.0</pctVal><payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry></invstOrSec>
      <invstOrSec><name>Mystery Trust Units</name><cusip>M</cusip><identifiers><isin value="US_M"/></identifiers>
        <balance>1</balance><valUSD>100</valUSD><pctVal>10.0</pctVal><payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry></invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""

SPY_SUBS = {"filings": {"recent": {
    "accessionNumber": ["0000000000-26-000001"], "filingDate": ["2026-05-01"],
    "reportDate": ["2026-03-31"], "acceptanceDateTime": [""], "form": ["NPORT-P"],
    "primaryDocument": ["xslFormNPORT-P_X01/primary_doc.xml"],
}}}

# AAPL: margin 0.25 (ni 250 / rev 1000), roe 0.50 (ni 250 / eq 500)
AAPL_FACTS = {"cik": 320193, "entityName": "APPLE INC", "facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [{"end": "2025-09-30", "val": 1000, "form": "10-K"}]}},
    "NetIncomeLoss": {"units": {"USD": [{"end": "2025-09-30", "val": 250, "form": "10-K"}]}},
    "StockholdersEquity": {"units": {"USD": [{"end": "2025-09-30", "val": 500, "form": "10-K"}]}},
}}}
AAPL_SUBS = {"sicDescription": "Electronic Computers", "filings": {"recent": {"form": ["10-K"]}}}

# NVDA: margin 0.50 (ni 500 / rev 1000), no equity tag -> roe None
NVDA_FACTS = {"cik": 1045810, "entityName": "NVIDIA CORP", "facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [{"end": "2026-01-31", "val": 1000, "form": "10-K"}]}},
    "NetIncomeLoss": {"units": {"USD": [{"end": "2026-01-31", "val": 500, "form": "10-K"}]}},
}}}
NVDA_SUBS = {"sicDescription": "Semiconductors & Related Devices", "filings": {"recent": {"form": ["10-K"]}}}


def make():
    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "submissions/CIK0000884394" in p:
            return httpx.Response(200, json=SPY_SUBS)
        if p.endswith("primary_doc.xml"):
            return httpx.Response(200, text=NPORT_XML)
        if "submissions/CIK0000320193" in p:
            return httpx.Response(200, json=AAPL_SUBS)
        if "submissions/CIK0001045810" in p:
            return httpx.Response(200, json=NVDA_SUBS)
        if "companyfacts/CIK0000320193" in p:
            return httpx.Response(200, json=AAPL_FACTS)
        if "companyfacts/CIK0001045810" in p:
            return httpx.Response(200, json=NVDA_FACTS)
        if p == "/v3/mapping":
            import json as _json
            figi = {"A": "AAPL", "N": "NVDA"}
            body = _json.loads(request.content)
            out = []
            for item in body:
                t = figi.get(item["idValue"])
                out.append({"data": [{"ticker": t, "exchCode": "US", "securityType": "Common Stock", "marketSector": "Equity", "name": t}]} if t else {"error": "x"})
            return httpx.Response(200, json=out)
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return settings, client, TickerResolver(client, settings.tickers_url)


def test_holdings_analysis_resolves_index_and_aggregates():
    s, c, r = make()
    out = get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SP500", 25)
    assert out["symbol"] == "SP500"
    assert out["resolved_etf"] == "SPY"
    assert out["total_holdings"] == 3
    assert out["holdings_analyzed"] == 3
    assert out["coverage"]["matched"] == 2
    assert out["coverage"]["of"] == 3
    assert out["coverage"]["matched_weight_pct"] == 90.0
    assert out["unmatched"] == ["Mystery Trust Units"]
    sectors = {b["sector"]: b for b in out["sector_breakdown"]}
    assert sectors["Semiconductors & Related Devices"]["weight_pct"] == 30.0
    assert sectors["Electronic Computers"]["weight_pct"] == 60.0
    # net_margin: AAPL 0.25 @60, NVDA 0.50 @30 -> (15 + 15)/90 = 0.3333
    assert out["weighted_net_margin"] == 0.3333
    # roe: only AAPL 0.50 @60 (NVDA has no equity) -> 0.5
    assert out["weighted_roe"] == 0.5
    assert out["metric_coverage"] == {"net_margin": 2, "roe": 1, "of_matched": 2}
    assert out["coverage"]["resolution"] == {"by_cusip": 2, "by_isin": 0, "by_name": 0}


def test_limit_clamped_to_one():
    s, c, r = make()
    out = get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SPY", 0)
    assert out["holdings_analyzed"] == 1


def test_limit_clamped_to_fifty(monkeypatch):
    """Upper-bound clamp: limit > 50 must be clamped to 50; lower-bound (0 → 1) also checked."""
    import edgarmcp.analysis as analysis_mod

    recorded: list[int] = []

    def fake_get_etf_holdings(client, base_data, base_www, resolver, etf, limit):
        recorded.append(limit)
        return {"holdings": [], "fund_name": "X", "total_net_assets": 0, "total_holdings": 0, "report_date": "2026-03-31"}

    monkeypatch.setattr(analysis_mod, "get_etf_holdings", fake_get_etf_holdings)

    s, c, r = make()

    # upper clamp: 100 → 50
    get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SPY", 100)
    assert recorded[-1] == 50, f"expected 50 but got {recorded[-1]}"

    # lower clamp: 0 → 1
    get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SPY", 0)
    assert recorded[-1] == 1, f"expected 1 but got {recorded[-1]}"


def make_nvda_404():
    """Variant of make() where NVDA's companyfacts returns 404 but everything else is normal."""

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "submissions/CIK0000884394" in p:
            return httpx.Response(200, json=SPY_SUBS)
        if p.endswith("primary_doc.xml"):
            return httpx.Response(200, text=NPORT_XML)
        if "submissions/CIK0000320193" in p:
            return httpx.Response(200, json=AAPL_SUBS)
        if "submissions/CIK0001045810" in p:
            return httpx.Response(200, json=NVDA_SUBS)
        if "companyfacts/CIK0000320193" in p:
            return httpx.Response(200, json=AAPL_FACTS)
        if "companyfacts/CIK0001045810" in p:
            return httpx.Response(404)  # NVDA facts → 404
        if p == "/v3/mapping":
            import json as _json
            figi = {"A": "AAPL", "N": "NVDA"}
            body = _json.loads(request.content)
            out = []
            for item in body:
                t = figi.get(item["idValue"])
                out.append({"data": [{"ticker": t, "exchCode": "US", "securityType": "Common Stock", "marketSector": "Equity", "name": t}]} if t else {"error": "x"})
            return httpx.Response(200, json=out)
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return settings, client, TickerResolver(client, settings.tickers_url)


def test_graceful_skip_when_holding_facts_404():
    """A 404 on one holding's companyfacts must not abort the analysis."""
    s, c, r = make_nvda_404()
    out = get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SP500", 25)

    # Analysis completes without exception
    assert out is not None

    # NVDA is still matched (resolve_name + sector succeed)
    assert out["coverage"]["matched"] == 2

    # Only AAPL contributed metrics
    assert out["metric_coverage"]["net_margin"] == 1
    assert out["metric_coverage"]["roe"] == 1

    # weighted_net_margin is AAPL's margin alone: ni/rev = 250/1000 = 0.25
    assert out["weighted_net_margin"] == 0.25


# ---------------------------------------------------------------------------
# Period-consistency test: annual 10-K values must be used, NOT the
# later 10-Q quarterly point.
# ---------------------------------------------------------------------------

# Single holding ETF whose one holding is ACME (mapped to AAPL CIK for simplicity).
NPORT_XML_SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo><regName>Test ETF</regName><repPdDate>2026-03-31</repPdDate></genInfo>
    <fundInfo><totAssets>1000</totAssets><totLiabs>0</totLiabs><netAssets>1000</netAssets></fundInfo>
    <invstOrSecs>
      <invstOrSec><name>Apple Inc</name><cusip>A</cusip><identifiers><isin value="US_A"/></identifiers>
        <balance>1</balance><valUSD>1000</valUSD><pctVal>100.0</pctVal><payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry></invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""

# ACME facts: NetIncomeLoss has BOTH a 10-K annual point (250) AND a later 10-Q
# quarterly point (60).  The old code picks the latest (60), the new code must
# pick the 10-K annual point (250).
ACME_FACTS_MIXED = {"cik": 320193, "entityName": "APPLE INC", "facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        {"end": "2025-12-31", "val": 1000, "form": "10-K"},
    ]}},
    "NetIncomeLoss": {"units": {"USD": [
        {"end": "2025-12-31", "val": 250, "form": "10-K"},   # annual — correct
        {"end": "2026-03-31", "val": 60,  "form": "10-Q"},   # quarterly — must NOT be used
    ]}},
    "StockholdersEquity": {"units": {"USD": [
        {"end": "2025-12-31", "val": 500, "form": "10-K"},
    ]}},
}}}


def make_single_holding():
    """Variant of make() with a single-holding ETF and mixed-form net income data."""

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "submissions/CIK0000884394" in p:
            # Reuse SPY subs structure but point at our single-holding nport
            return httpx.Response(200, json=SPY_SUBS)
        if p.endswith("primary_doc.xml"):
            return httpx.Response(200, text=NPORT_XML_SINGLE)
        if "submissions/CIK0000320193" in p:
            return httpx.Response(200, json=AAPL_SUBS)
        if "companyfacts/CIK0000320193" in p:
            return httpx.Response(200, json=ACME_FACTS_MIXED)
        if p == "/v3/mapping":
            import json as _json
            figi = {"A": "AAPL"}
            body = _json.loads(request.content)
            out = []
            for item in body:
                t = figi.get(item["idValue"])
                out.append({"data": [{"ticker": t, "exchCode": "US", "securityType": "Common Stock", "marketSector": "Equity", "name": t}]} if t else {"error": "x"})
            return httpx.Response(200, json=out)
        return httpx.Response(404)

    settings = Settings.from_env()
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    return settings, client, TickerResolver(client, settings.tickers_url)


def test_metrics_use_annual_10k_not_quarterly():
    """_metrics_for must pick the annual 10-K net_income (250), not the later
    10-Q quarterly value (60), so that numerator and denominator are period-consistent."""
    s, c, r = make_single_holding()
    out = get_holdings_analysis(c, s.base_data, s.base_www, s.base_figi, s.openfigi_api_key, r, "SPY", 25)

    # With annual figures: net_margin = 250/1000 = 0.25, roe = 250/500 = 0.5
    assert out["weighted_net_margin"] == 0.25, (
        f"Expected 0.25 (annual 10-K net_income=250), got {out['weighted_net_margin']} "
        f"(likely picked quarterly 10-Q net_income=60 giving 0.06)"
    )
    assert out["weighted_roe"] == 0.5, (
        f"Expected 0.5 (annual 10-K ni=250/eq=500), got {out['weighted_roe']}"
    )
