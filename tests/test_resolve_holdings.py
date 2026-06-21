import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.figi import resolve_holdings

CT = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "APPLE INC"},
    "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "2": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
}
# OpenFIGI maps: cusip CA->AAPL, isin IN->NVDA, cusip CF->FOREIGN (not in SEC tickers)
FIGI = {"CA": "AAPL", "IN": "NVDA", "CF": "FOREIGN"}


def make(fail_figi=False):
    def handler(req):
        p = req.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=CT)
        if p == "/v3/mapping":
            if fail_figi:
                return httpx.Response(503)
            import json
            body = json.loads(req.content)
            out = []
            for item in body:
                t = FIGI.get(item["idValue"])
                out.append({"data": [{"ticker": t, "exchCode": "US", "securityType": "Common Stock", "marketSector": "Equity", "name": t}]} if t else {"error": "x"})
            return httpx.Response(200, json=out)
        return httpx.Response(404)
    c = EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))
    return c, TickerResolver(c, "https://www.sec.gov/files/company_tickers.json")


def test_cusip_isin_and_name_fallback():
    c, r = make()
    holdings = [
        {"name": "Apple Inc", "cusip": "CA", "isin": "US_A"},          # cusip hit
        {"name": "NVIDIA Corp", "cusip": None, "isin": "IN"},          # isin hit (no cusip)
        {"name": "Microsoft Corp", "cusip": "CM", "isin": None},       # figi miss -> name fallback
        {"name": "Foreign Co", "cusip": "CF", "isin": None},           # figi ticker not in SEC -> name miss -> None
        {"name": "Totally Unknown XYZ", "cusip": "CU", "isin": None},  # full miss -> None
    ]
    out = resolve_holdings(c, "https://api.openfigi.com", "", r, holdings)
    assert out[0] == {"cik": 320193, "ticker": "AAPL", "via": "cusip"}
    assert out[1] == {"cik": 1045810, "ticker": "NVDA", "via": "isin"}
    assert out[2] == {"cik": 789019, "ticker": "MSFT", "via": "name"}
    assert out[3] is None
    assert out[4] is None


def test_figi_failure_falls_back_to_name_for_all():
    c, r = make(fail_figi=True)
    holdings = [{"name": "Apple Inc", "cusip": "CA", "isin": None}]
    out = resolve_holdings(c, "https://api.openfigi.com", "", r, holdings)
    assert out[0] == {"cik": 320193, "ticker": "AAPL", "via": "name"}
