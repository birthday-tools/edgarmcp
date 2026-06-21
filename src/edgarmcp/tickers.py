import re
import threading

from .http_client import EdgarClient


_NOISE = re.compile(
    r"\b(INCORPORATED|INC|CORPORATION|CORP|COMPANIES|COMPANY|HOLDINGS|HLDGS|"
    r"LIMITED|LTD|GROUP|PLC|CLASS\s+[A-C]|COM|CO|THE)\b"
)


def normalize_company_name(name: str) -> str:
    s = name.upper()
    s = re.sub(r"[.,&/]", " ", s)
    s = _NOISE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class UnknownTicker(Exception):
    pass


def cik_padded(cik: int) -> str:
    return str(cik).zfill(10)


class TickerResolver:
    def __init__(self, client: EdgarClient, tickers_url: str) -> None:
        self._client = client
        self._url = tickers_url
        self._map: dict[str, int] | None = None
        self._by_name: dict[str, dict] | None = None
        self._lock = threading.Lock()

    def _load(self) -> dict[str, int]:
        if self._map is None:
            with self._lock:
                if self._map is None:
                    raw = self._client.get_json(self._url)
                    self._map = {
                        entry["ticker"].upper(): int(entry["cik_str"])
                        for entry in raw.values()
                    }
        return self._map

    def resolve(self, ticker: str) -> int:
        mapping = self._load()
        key = ticker.strip().upper()
        if key not in mapping:
            raise UnknownTicker(ticker)
        return mapping[key]

    def resolve_name(self, name: str) -> dict | None:
        if self._by_name is None:
            with self._lock:
                if self._by_name is None:
                    raw = self._client.get_json(self._url)
                    index: dict[str, dict] = {}
                    for entry in raw.values():
                        key = normalize_company_name(entry["title"])
                        if key and key not in index:
                            index[key] = {
                                "cik": int(entry["cik_str"]),
                                "ticker": entry["ticker"],
                                "title": entry["title"],
                            }
                    self._by_name = index
        return self._by_name.get(normalize_company_name(name))
