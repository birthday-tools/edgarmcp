from .figi import resolve_holdings
from .funds import get_etf_holdings
from .http_client import EdgarClient
from .macro import FredError, MissingApiKey, get_latest_observation
from .tickers import TickerResolver


class IndexNotFound(Exception):
    pass


INDEX_REGISTRY: dict[str, dict] = {
    "S&P 500": {"name": "S&P 500", "etf": "SPY", "fred": "SP500",
                "aliases": ["SP500", "SPX", "GSPC", "^GSPC", "S&P500"]},
    "NASDAQ-100": {"name": "NASDAQ-100", "etf": "QQQ", "fred": "NASDAQ100",
                   "aliases": ["NASDAQ100", "NDX", "^NDX"]},
    "Dow Jones Industrial Average": {"name": "Dow Jones Industrial Average", "etf": "DIA", "fred": "DJIA",
                                     "aliases": ["DJIA", "DJI", "^DJI", "DOW"]},
    "NASDAQ Composite": {"name": "NASDAQ Composite", "etf": "ONEQ", "fred": "NASDAQCOM",
                         "aliases": ["NASDAQCOM", "IXIC", "^IXIC", "COMP"]},
}

_ALIAS_INDEX: dict[str, dict] = {}
for _canon in INDEX_REGISTRY.values():
    _ALIAS_INDEX[_canon["name"].upper()] = _canon
    for _a in _canon["aliases"]:
        _ALIAS_INDEX[_a.upper()] = _canon


def resolve_index(alias: str) -> dict | None:
    return _ALIAS_INDEX.get(alias.strip().upper())


def get_index(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    base_fred: str,
    fred_api_key: str,
    base_figi: str,
    figi_api_key: str,
    resolver: TickerResolver,
    index: str,
) -> dict:
    canon = resolve_index(index)
    if canon is None:
        raise IndexNotFound(index)
    etf = canon["etf"]

    level = None
    try:
        obs = get_latest_observation(client, base_fred, fred_api_key, canon["fred"])
        if obs is not None and obs["value"] is not None:
            level = {"value": obs["value"], "date": obs["date"], "source": f"FRED:{canon['fred']}"}
    except (MissingApiKey, FredError):
        level = None

    data = get_etf_holdings(client, base_data, base_www, resolver, etf, 10)
    identities = resolve_holdings(client, base_figi, figi_api_key, resolver, data["holdings"])
    top = []
    for h, ident in zip(data["holdings"], identities):
        top.append({
            "name": h["name"],
            "ticker": ident["ticker"] if ident else None,
            "weight_pct": h["weight_pct"],
        })

    return {
        "index": canon["name"],
        "aliases": canon["aliases"],
        "tracking_etf": etf,
        "level": level,
        "fund_net_assets": data["total_net_assets"],
        "total_holdings": data["total_holdings"],
        "top_holdings": top,
    }
