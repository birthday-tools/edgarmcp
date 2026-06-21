import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient, DisallowedHost


def test_post_json_blocks_disallowed_host():
    c = EdgarClient("ua", MemoryCache(),
                    transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
                    allowed_hosts=frozenset({"api.openfigi.com"}))
    with pytest.raises(DisallowedHost):
        c.post_json("https://evil.example/x", [{"a": 1}])


def test_post_json_caches_by_body():
    calls = []
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"ok": True})
    c = EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))
    body = [{"idType": "ID_CUSIP", "idValue": "1"}]
    assert c.post_json("https://api.openfigi.com/v3/mapping", body)["ok"] is True
    c.post_json("https://api.openfigi.com/v3/mapping", body)   # identical body -> cache hit
    assert len(calls) == 1


def test_post_json_sends_apikey_header_when_given():
    seen = {}
    def handler(req):
        seen["key"] = req.headers.get("X-OPENFIGI-APIKEY")
        return httpx.Response(200, json={})
    c = EdgarClient("ua", MemoryCache(), transport=httpx.MockTransport(handler))
    c.post_json("https://api.openfigi.com/v3/mapping", [{"a": 1}], headers={"X-OPENFIGI-APIKEY": "KEY"})
    assert seen["key"] == "KEY"
