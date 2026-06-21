from .http_client import DisallowedHost, EdgarClient, EdgarHTTPError
from .tickers import TickerResolver, UnknownTicker

_FIGI_PATH = "/v3/mapping"


class FigiError(Exception):
    pass


def _pick_ticker(data: list) -> dict | None:
    for d in data:
        if d.get("exchCode") == "US" and d.get("securityType") == "Common Stock" and d.get("ticker"):
            return {"ticker": d["ticker"], "name": d.get("name", "")}
    for d in data:
        if d.get("marketSector") == "Equity" and d.get("ticker"):
            return {"ticker": d["ticker"], "name": d.get("name", "")}
    return None


def resolve_identifiers(client: EdgarClient, base_figi: str, api_key: str, items: list[tuple[str, str]]) -> dict[str, dict]:
    if not items:
        return {}
    batch_size = 100 if api_key else 10
    headers = {"X-OPENFIGI-APIKEY": api_key} if api_key else None
    url = f"{base_figi}{_FIGI_PATH}"
    out: dict[str, dict] = {}
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        body = [{"idType": t, "idValue": v} for t, v in chunk]
        try:
            resp = client.post_json(url, body, headers=headers)
        except (EdgarHTTPError, DisallowedHost) as exc:
            raise FigiError(str(exc)) from None
        if not isinstance(resp, list):
            raise FigiError("unexpected OpenFIGI response (not a list)")
        for (_t, v), res in zip(chunk, resp):
            if not isinstance(res, dict):
                continue
            picked = _pick_ticker(res.get("data") or [])
            if picked is not None:
                out[v] = picked
    return out


def resolve_holdings(client: EdgarClient, base_figi: str, api_key: str, resolver: TickerResolver, holdings: list[dict]) -> list[dict | None]:
    items: list[tuple[str, str]] = []
    ids: list[tuple[str | None, str | None]] = []   # parallel to holdings: (id_value, via)
    for h in holdings:
        cusip = h.get("cusip")
        isin = h.get("isin")
        if cusip:
            items.append(("ID_CUSIP", cusip))
            ids.append((cusip, "cusip"))
        elif isin:
            items.append(("ID_ISIN", isin))
            ids.append((isin, "isin"))
        else:
            ids.append((None, None))

    try:
        figi_map = resolve_identifiers(client, base_figi, api_key, items)
    except FigiError:
        figi_map = {}

    out: list[dict | None] = []
    for h, (id_value, via) in zip(holdings, ids):
        resolved: dict | None = None
        if id_value is not None and id_value in figi_map:
            ticker = figi_map[id_value]["ticker"]
            try:
                resolved = {"cik": resolver.resolve(ticker), "ticker": ticker, "via": via}
            except UnknownTicker:
                resolved = None
        if resolved is None:
            entry = resolver.resolve_name(h["name"])
            if entry is not None:
                resolved = {"cik": entry["cik"], "ticker": entry["ticker"], "via": "name"}
        out.append(resolved)
    return out
