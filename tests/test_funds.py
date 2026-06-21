import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.config import Settings
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.funds import get_etf_holdings, classify_entity, FundError
import pytest

TICKERS_JSON = {"0": {"cik_str": 884394, "ticker": "SPY", "title": "SPDR S&P 500 ETF TRUST"}}

NPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo><regName>SPDR S&amp;P 500 ETF Trust</regName><repPdDate>2026-03-31</repPdDate></genInfo>
    <fundInfo><totAssets>1000</totAssets><totLiabs>0</totLiabs><netAssets>1000</netAssets></fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>Alpha Corp</name><cusip>AAA111</cusip>
        <identifiers><isin value="US_AAA"/></identifiers>
        <balance>10</balance><valUSD>1000</valUSD><pctVal>100.0</pctVal>
        <payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""

# submissions: an older NPORT-P plus a NEWER NPORT-P/A amendment (must win)
SUBMISSIONS = {"filings": {"recent": {
    "accessionNumber": ["0000000000-26-000002", "0000000000-26-000001"],
    "filingDate": ["2026-05-15", "2026-04-30"],
    "reportDate": ["2026-03-31", "2026-02-28"],
    "acceptanceDateTime": ["", ""],
    "form": ["NPORT-P/A", "NPORT-P"],
    "primaryDocument": ["xslFormNPORT-P_X01/primary_doc.xml", "xslFormNPORT-P_X01/primary_doc.xml"],
}}}

OPERATING_SUBMISSIONS = {"filings": {"recent": {
    "accessionNumber": ["0000000000-26-000009"], "filingDate": ["2026-05-01"],
    "reportDate": ["2026-03-31"], "acceptanceDateTime": [""], "form": ["10-K"],
    "primaryDocument": ["doc.htm"],
}}}


def make_client(submissions):
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "submissions" in p:
            return httpx.Response(200, json=submissions)
        if p.endswith("000000000026000002/primary_doc.xml"):   # the /A amendment doc
            return httpx.Response(200, text=NPORT_XML)
        if p.endswith("primary_doc.xml"):                       # the older original
            return httpx.Response(200, text="<edgarSubmission/>")
        return httpx.Response(404)

    settings = Settings.from_env()
    return settings, EdgarClient(settings.user_agent, MemoryCache(), transport=httpx.MockTransport(handler))


def _resolver(settings, client):
    return TickerResolver(client, settings.tickers_url)


def test_get_etf_holdings_uses_latest_amendment():
    s, c = make_client(SUBMISSIONS)
    out = get_etf_holdings(c, s.base_data, s.base_www, _resolver(s, c), "SPY")
    assert out["ticker"] == "SPY"
    assert out["fund_name"] == "SPDR S&P 500 ETF Trust"
    assert out["total_holdings"] == 1
    assert out["holdings"][0]["name"] == "Alpha Corp"


def test_get_etf_holdings_raises_when_no_nport():
    s, c = make_client(OPERATING_SUBMISSIONS)
    with pytest.raises(FundError):
        get_etf_holdings(c, s.base_data, s.base_www, _resolver(s, c), "SPY")


def test_classify_entity_detects_fund_and_operating():
    s1, c1 = make_client(SUBMISSIONS)
    assert classify_entity(c1, s1.base_data, _resolver(s1, c1), "SPY") == "etf"
    s2, c2 = make_client(OPERATING_SUBMISSIONS)
    assert classify_entity(c2, s2.base_data, _resolver(s2, c2), "SPY") == "operating"
