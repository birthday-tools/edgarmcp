import json

import pytest
from edgarmcp.quotes import TradernetClient, get_quote, TradernetError

WELCOME = json.dumps(["userData", {"mode": "demo"}])


def tick(c, ltp, bbp=None, bap=None, vol=None, ltt=None):
    q = {"c": c, "ltp": ltp}
    if bbp is not None:
        q["bbp"] = bbp
    if bap is not None:
        q["bap"] = bap
    if vol is not None:
        q["vol"] = vol
    if ltt is not None:
        q["ltt"] = ltt
    return json.dumps(["q", q])


class FakeWS:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.closed = False

    def send(self, m):
        self.sent.append(m)

    def settimeout(self, t):
        pass

    def recv(self):
        if not self._messages:
            raise TimeoutError("no more messages")
        return self._messages.pop(0)

    def close(self):
        self.closed = True


def fake_connect(messages, captured=None):
    def _connect(url, timeout):
        ws = FakeWS(messages)
        if captured is not None:
            captured["ws"] = ws
            captured["url"] = url
        return ws
    return _connect


def test_quote_parses_tick():
    msgs = [WELCOME, tick("AAPL.US", 295.63, bbp=295.63, bap=295.65, vol=9895577, ltt="2026-06-19T10:51:06")]
    out = get_quote(TradernetClient(connect=fake_connect(msgs)), "AAPL")
    assert out["symbol"] == "AAPL"
    assert out["ticker"] == "AAPL.US"
    assert out["price"] == 295.63
    assert out["bid"] == 295.63
    assert out["ask"] == 295.65
    assert out["volume_day"] == 9895577
    assert out["last_trade_time"] == "2026-06-19T10:51:06"
    assert out["source"] == "tradernet"


def test_subscribe_frame_and_symbol_qualification():
    captured = {}
    out = get_quote(TradernetClient(connect=fake_connect([tick("AAPL.US", 100.0)], captured)), "aapl")
    assert captured["ws"].sent[0] == json.dumps(["quotes", ["AAPL.US"]])
    assert captured["url"] == "wss://wss.tradernet.com/"
    assert out["price"] == 100.0


def test_skips_other_symbol_ticks():
    msgs = [tick("MSFT.US", 382.0), tick("AAPL.US", 295.0)]
    out = get_quote(TradernetClient(connect=fake_connect(msgs)), "AAPL")
    assert out["symbol"] == "AAPL"
    assert out["price"] == 295.0


def test_missing_optional_fields_are_none():
    out = get_quote(TradernetClient(connect=fake_connect([tick("AAPL.US", 295.0)])), "AAPL")
    assert out["bid"] is None
    assert out["ask"] is None
    assert out["volume_day"] is None
    assert out["last_trade_time"] is None


def test_timeout_raises_when_no_matching_tick():
    msgs = [WELCOME, tick("MSFT.US", 382.0)]  # never AAPL, then recv runs dry
    with pytest.raises(TradernetError):
        get_quote(TradernetClient(connect=fake_connect(msgs)), "AAPL", timeout=1.0)


def test_explicit_symbol_with_suffix_preserved():
    captured = {}
    out = get_quote(TradernetClient(connect=fake_connect([tick("SBER.MISX", 250.0)], captured)), "SBER.MISX")
    assert captured["ws"].sent[0] == json.dumps(["quotes", ["SBER.MISX"]])
    assert out["symbol"] == "SBER"
    assert out["ticker"] == "SBER.MISX"


def test_connection_is_closed():
    captured = {}
    get_quote(TradernetClient(connect=fake_connect([tick("AAPL.US", 1.0)], captured)), "AAPL")
    assert captured["ws"].closed is True
