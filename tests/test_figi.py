import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.figi import resolve_identifiers, FigiError


def _data(ticker, name, exch="US", st="Common Stock", sector="Equity"):
    return {"ticker": ticker, "name": name, "exchCode": exch, "securityType": st, "marketSector": sector}


def make(calls, response_for):
    def handler(req):
        calls.append(req)
        import json
        body = json.loads(req.content)
        return httpx.Response(200, json=[response_for(item["idValue"]) for item in body])
    return EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))


def test_resolves_and_picks_us_common_stock():
    def resp(v):
        if v == "67066G104":
            return {"data": [_data("NVDA-OLD", "x", exch="LN"), _data("NVDA", "NVIDIA CORP")]}
        if v == "037833100":
            return {"data": [_data("AAPL", "APPLE INC")]}
        return {"error": "No identifier found."}
    c = make([], resp)
    out = resolve_identifiers(c, "https://api.openfigi.com", "", [("ID_CUSIP", "67066G104"), ("ID_CUSIP", "037833100"), ("ID_CUSIP", "ZZZ")])
    assert out["67066G104"]["ticker"] == "NVDA"
    assert out["037833100"]["ticker"] == "AAPL"
    assert "ZZZ" not in out


def test_batches_over_ten_without_key():
    calls = []
    c = make(calls, lambda v: {"data": [_data(f"T{v}", "n")]})
    items = [("ID_CUSIP", str(i)) for i in range(25)]
    out = resolve_identifiers(c, "https://api.openfigi.com", "", items)
    assert len(out) == 25
    assert len(calls) == 3   # 10 + 10 + 5


def test_empty_items_makes_no_call():
    calls = []
    c = make(calls, lambda v: {"data": []})
    assert resolve_identifiers(c, "https://api.openfigi.com", "", []) == {}
    assert calls == []


def test_http_error_becomes_figi_error():
    def handler(req):
        return httpx.Response(429)
    c = EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))
    with pytest.raises(FigiError):
        resolve_identifiers(c, "https://api.openfigi.com", "", [("ID_CUSIP", "1")])
