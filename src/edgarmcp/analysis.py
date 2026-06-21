from .facts import EntityTypeError, UnknownStatement, get_financial_statement
from .funds import get_etf_holdings
from .http_client import EdgarClient, EdgarHTTPError
from .figi import resolve_holdings
from .indices import resolve_index
from .tickers import TickerResolver, cik_padded


def weighted_average(pairs: list[tuple[float, float]]) -> float | None:
    total_w = sum(w for _, w in pairs)
    if not pairs or total_w == 0:
        return None
    return round(sum(v * w for v, w in pairs) / total_w, 4)


def build_analysis(
    symbol: str,
    resolved_etf: str,
    fund_name: str | None,
    as_of: str | None,
    total_holdings: int,
    holdings_analyzed: int,
    enriched: list[dict],
) -> dict:
    matched = [h for h in enriched if h["matched"]]

    resolution = {"by_cusip": 0, "by_isin": 0, "by_name": 0}
    _via_key = {"cusip": "by_cusip", "isin": "by_isin", "name": "by_name"}
    for h in matched:
        key = _via_key.get(h.get("via"))
        if key is not None:
            resolution[key] += 1

    sectors: dict[str, dict] = {}
    for h in matched:
        sec = h["sector"] or "Unknown"
        bucket = sectors.setdefault(sec, {"sector": sec, "weight_pct": 0.0, "holdings": 0})
        bucket["weight_pct"] += h["weight_pct"]
        bucket["holdings"] += 1
    sector_breakdown = sorted(sectors.values(), key=lambda b: b["weight_pct"], reverse=True)
    for b in sector_breakdown:
        b["weight_pct"] = round(b["weight_pct"], 2)

    margin_pairs = [(h["net_margin"], h["weight_pct"]) for h in matched if h["net_margin"] is not None]
    roe_pairs = [(h["roe"], h["weight_pct"]) for h in matched if h["roe"] is not None]

    return {
        "symbol": symbol,
        "resolved_etf": resolved_etf,
        "fund_name": fund_name,
        "as_of": as_of,
        "holdings_analyzed": holdings_analyzed,
        "total_holdings": total_holdings,
        "coverage": {
            "matched": len(matched),
            "of": holdings_analyzed,
            "matched_weight_pct": round(sum(h["weight_pct"] for h in matched), 2),
            "resolution": resolution,
        },
        "sector_breakdown": sector_breakdown,
        "weighted_net_margin": weighted_average(margin_pairs),
        "weighted_roe": weighted_average(roe_pairs),
        "metric_coverage": {
            "net_margin": len(margin_pairs),
            "roe": len(roe_pairs),
            "of_matched": len(matched),
        },
        "unmatched": [h["name"] for h in enriched if not h["matched"]],
    }


def _sector_for(client: EdgarClient, base_data: str, cik: int) -> str | None:
    try:
        data = client.get_json(f"{base_data}/submissions/CIK{cik_padded(cik)}.json")
    except EdgarHTTPError:
        return None
    desc = data.get("sicDescription")
    return desc or None


def _metrics_for(client: EdgarClient, base_data: str, resolver: TickerResolver, ticker: str) -> tuple[float | None, float | None]:
    try:
        income = get_financial_statement(client, base_data, resolver, ticker, "income", "annual")
        balance = get_financial_statement(client, base_data, resolver, ticker, "balance", "annual")
        li = income["line_items"]
        rev = li.get("revenue", {}).get("value")
        ni = li.get("net_income", {}).get("value")
        eq = balance["line_items"].get("stockholders_equity", {}).get("value")
        net_margin = ni / rev if (ni is not None and rev) else None
        roe = ni / eq if (ni is not None and eq) else None
        return net_margin, roe
    except (EdgarHTTPError, EntityTypeError, UnknownStatement, KeyError, TypeError):
        return None, None


def get_holdings_analysis(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    base_figi: str,
    figi_api_key: str,
    resolver: TickerResolver,
    symbol: str,
    limit: int = 25,
) -> dict:
    canon = resolve_index(symbol)
    etf = canon["etf"] if canon else symbol
    limit = max(1, min(50, limit))

    data = get_etf_holdings(client, base_data, base_www, resolver, etf, limit)
    identities = resolve_holdings(client, base_figi, figi_api_key, resolver, data["holdings"])

    enriched: list[dict] = []
    for h, ident in zip(data["holdings"], identities):
        if ident is None:
            enriched.append({"name": h["name"], "weight_pct": h["weight_pct"], "matched": False,
                             "sector": None, "net_margin": None, "roe": None, "via": None})
            continue
        sector = _sector_for(client, base_data, ident["cik"])
        net_margin, roe = _metrics_for(client, base_data, resolver, ident["ticker"])
        enriched.append({"name": h["name"], "weight_pct": h["weight_pct"], "matched": True,
                         "sector": sector, "net_margin": net_margin, "roe": roe, "via": ident["via"]})

    return build_analysis(symbol, etf, data["fund_name"], data["report_date"],
                          data["total_holdings"], len(data["holdings"]), enriched)
