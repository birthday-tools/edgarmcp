import json
import time
from typing import Callable


class TradernetError(Exception):
    pass


_WS_URL = "wss://wss.tradernet.com/"


def _to_float(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _parse_tick(data, want_symbol: str) -> dict | None:
    if not isinstance(data, list) or len(data) < 2 or data[0] != "q":
        return None
    q = data[1]
    if not isinstance(q, dict):
        return None
    c = q.get("c")
    price = _to_float(q.get("ltp"))
    if not isinstance(c, str) or price is None:
        return None
    sym = c.split(".")[0].upper()
    if sym != want_symbol:
        return None
    vol = _to_float(q.get("vol"))
    ltt = q.get("ltt")
    return {
        "symbol": sym,
        "ticker": c,
        "price": price,
        "bid": _to_float(q.get("bbp")),
        "ask": _to_float(q.get("bap")),
        "volume_day": int(vol) if vol is not None else None,
        "last_trade_time": ltt if isinstance(ltt, str) and ltt else None,
        "source": "tradernet",
    }


class TradernetClient:
    def __init__(self, connect: Callable[[str, float], object] | None = None) -> None:
        self._connect = connect

    def _open(self, timeout: float):
        if self._connect is not None:
            return self._connect(_WS_URL, timeout)
        from websocket import create_connection  # lazy: only needed for real use
        return create_connection(_WS_URL, timeout=timeout)

    def quote(self, ticker: str, timeout: float = 8.0) -> dict:
        symbol = ticker if "." in ticker else f"{ticker.upper()}.US"
        want = symbol.split(".")[0].upper()
        ws = self._open(timeout)
        try:
            ws.send(json.dumps(["quotes", [symbol]]))
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    ws.settimeout(max(0.1, deadline - time.monotonic()))
                except Exception:
                    pass
                try:
                    raw = ws.recv()
                except Exception:
                    break
                try:
                    data = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                tick = _parse_tick(data, want)
                if tick is not None:
                    return tick
            raise TradernetError(f"no quote for {symbol} within {timeout}s")
        finally:
            try:
                ws.close()
            except Exception:
                pass


def get_quote(client: TradernetClient, ticker: str, timeout: float = 8.0) -> dict:
    return client.quote(ticker, timeout)
