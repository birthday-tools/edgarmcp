import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient, EdgarHTTPError


def make_transport(handler):
    return httpx.MockTransport(handler)


def test_get_json_sends_user_agent_and_parses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, json={"ok": True})

    client = EdgarClient("UA/1.0 (a@b.com)", MemoryCache(), transport=make_transport(handler))
    assert client.get_json("https://data.sec.gov/x") == {"ok": True}
    assert seen["ua"] == "UA/1.0 (a@b.com)"


def test_get_json_uses_cache_on_second_call():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"v": calls["n"]})

    client = EdgarClient("UA/1.0", MemoryCache(), transport=make_transport(handler))
    first = client.get_json("https://data.sec.gov/x")
    second = client.get_json("https://data.sec.gov/x")
    assert first == second == {"v": 1}
    assert calls["n"] == 1


def test_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    client = EdgarClient("UA/1.0", MemoryCache(), transport=make_transport(handler))
    with pytest.raises(EdgarHTTPError):
        client.get_json("https://data.sec.gov/missing")


def test_rate_limit_sleeps_between_calls():
    now = {"t": 0.0}
    slept = []

    def clock():
        return now["t"]

    def sleep(seconds):
        slept.append(seconds)
        now["t"] += seconds

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    client = EdgarClient(
        "UA/1.0", MemoryCache(), transport=make_transport(handler),
        min_interval=0.1, sleep=sleep, clock=clock,
    )
    client.get_json("https://data.sec.gov/a", use_cache=False)
    client.get_json("https://data.sec.gov/b", use_cache=False)
    assert slept and slept[0] == pytest.approx(0.1, abs=1e-9)


def test_allowed_hosts_rejects_disallowed_host():
    from edgarmcp.http_client import DisallowedHost

    def handler(request):
        return httpx.Response(200, json={})

    client = EdgarClient(
        "UA/1.0", MemoryCache(), transport=make_transport(handler),
        allowed_hosts=frozenset({"data.sec.gov"}),
    )
    with pytest.raises(DisallowedHost):
        client.get_json("https://evil.example.com/x")


def test_allowed_hosts_rejects_non_https():
    from edgarmcp.http_client import DisallowedHost

    def handler(request):
        return httpx.Response(200, json={})

    client = EdgarClient(
        "UA/1.0", MemoryCache(), transport=make_transport(handler),
        allowed_hosts=frozenset({"data.sec.gov"}),
    )
    with pytest.raises(DisallowedHost):
        client.get_json("http://data.sec.gov/x")


def test_allowed_hosts_allows_listed_host():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    client = EdgarClient(
        "UA/1.0", MemoryCache(), transport=make_transport(handler),
        allowed_hosts=frozenset({"data.sec.gov"}),
    )
    assert client.get_json("https://data.sec.gov/x") == {"ok": True}


def test_no_allowlist_means_no_host_check():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    client = EdgarClient("UA/1.0", MemoryCache(), transport=make_transport(handler))
    assert client.get_json("https://anything.example.com/x") == {"ok": True}


def test_disallowed_host_message_redacts_api_key():
    from edgarmcp.http_client import DisallowedHost

    def handler(request):
        return httpx.Response(200, json={})

    client = EdgarClient(
        "UA/1.0", MemoryCache(), transport=make_transport(handler),
        allowed_hosts=frozenset({"data.sec.gov"}),
    )
    with pytest.raises(DisallowedHost) as ei:
        client.get_json("https://evil.example.com/x?api_key=SUPERSECRET123")
    assert "SUPERSECRET123" not in str(ei.value)
    assert "REDACTED" in str(ei.value)
