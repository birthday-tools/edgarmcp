import dataclasses

import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.config import Settings
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.indices import resolve_index, get_index, IndexNotFound

TICKERS_JSON = {
    "0": {"cik_str": 884394, "ticker": "SPY", "title": "SPDR S&P 500 ETF TRUST"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
}

NPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo><regName>SPDR S&amp;P 500 ETF Trust</regName><repPdDate>2026-03-31</repPdDate></genInfo>
    <fundInfo><totAssets>1000</totAssets><totLiabs>0</totLiabs><netAssets>1000</netAssets></fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>Apple Inc</name><cusip>AAA</cusip><identifiers><isin value="US_A"/></identifiers>
        <balance>10</balance><valUSD>1000</valUSD><pctVal>100.0</pctVal>
        <payoffProfile>Long</payoffProfile><assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""

SUBMISSIONS = {"filings": {"recent": {
    "accessionNumber": ["0000000000-26-000001"], "filingDate": ["2026-05-01"],
    "reportDate": ["2026-03-31"], "acceptanceDateTime": [""], "form": ["NPORT-P"],
    "primaryDocument": ["xslFormNPORT-P_X01/primary_doc.xml"],
}}}

FRED_OBS = {"observations": [{"date": "2026-06-18", "value": "6000.12"}]}


def make(with_key=True):
    def handler(request):
        p, host = request.url.path, request.url.host
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if host == "api.stlouisfed.org" and "observations" in p:
            return httpx.Response(200, json=FRED_OBS)
        if "submissions" in p:
            return httpx.Response(200, json=SUBMISSIONS)
        if p.endswith("primary_doc.xml"):
            return httpx.Response(200, text=NPORT_XML)
        return httpx.Response(404)

    settings = Settings.from_env()
    # force the key state so the test is hermetic regardless of the FRED_API_KEY env var
    settings = dataclasses.replace(settings, fred_api_key="DUMMY" if with_key else "")
    client = EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, settings.tickers_url)
    return settings, client, resolver


def test_resolve_index_aliases():
    assert resolve_index("SP500")["etf"] == "SPY"
    assert resolve_index("^GSPC")["etf"] == "SPY"
    assert resolve_index("s&p 500")["etf"] == "SPY"
    assert resolve_index("NDX")["etf"] == "QQQ"
    assert resolve_index("nonsense") is None


def test_get_index_level_and_preview():
    s, c, r = make(with_key=True)
    out = get_index(c, s.base_data, s.base_www, s.base_fred, s.fred_api_key, s.base_figi, s.openfigi_api_key, r, "S&P 500")
    assert out["tracking_etf"] == "SPY"
    assert out["level"] == {"value": 6000.12, "date": "2026-06-18", "source": "FRED:SP500"}
    assert out["total_holdings"] == 1
    assert out["top_holdings"][0]["name"] == "Apple Inc"
    assert out["top_holdings"][0]["ticker"] == "AAPL"


def test_get_index_degrades_without_fred_key():
    s, c, r = make(with_key=False)
    out = get_index(c, s.base_data, s.base_www, s.base_fred, s.fred_api_key, s.base_figi, s.openfigi_api_key, r, "SP500")
    assert out["level"] is None
    assert out["tracking_etf"] == "SPY"
    assert out["top_holdings"][0]["ticker"] == "AAPL"


def test_get_index_unknown_raises():
    s, c, r = make()
    with pytest.raises(IndexNotFound):
        get_index(c, s.base_data, s.base_www, s.base_fred, s.fred_api_key, s.base_figi, s.openfigi_api_key, r, "nonsense")
