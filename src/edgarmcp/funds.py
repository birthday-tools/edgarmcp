from defusedxml.ElementTree import fromstring

from .filings import get_fund_filings, raw_xml_url
from .http_client import EdgarClient
from .tickers import TickerResolver, cik_padded

# NPORT-P assetCat codes -> English labels (unknown codes pass through as-is).
ASSET_CAT_LABELS: dict[str, str] = {
    "EC": "Equity-common",
    "EP": "Equity-preferred",
    "DBT": "Debt",
    "ABS": "Asset-backed",
    "RA": "Repurchase agreement",
    "STIV": "Short-term investment vehicle",
    "COMM": "Commodity",
    "RE": "Real estate",
    "LON": "Loan",
    "SN": "Structured note",
    "DFE": "Derivative-future",
    "DIR": "Derivative-forward",
    "DO": "Derivative-option",
    "DSW": "Derivative-swap",
}


class FundError(Exception):
    pass


def _text(node, tag: str) -> str | None:
    if node is None:
        return None
    el = node.find(f"{{*}}{tag}")
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def _num(node, tag: str) -> float | None:
    v = _text(node, tag)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _round(v: float | None, digits: int) -> float | None:
    return round(v, digits) if v is not None else None


def parse_nport_xml(xml: str, limit: int = 25) -> dict:
    root = fromstring(xml)
    form_data = root.find("{*}formData")
    gen = form_data.find("{*}genInfo") if form_data is not None else None
    fund = form_data.find("{*}fundInfo") if form_data is not None else None

    holdings: list[dict] = []
    asset_mix: dict[str, float] = {}
    country_mix: dict[str, float] = {}

    for sec in root.findall(".//{*}invstOrSec"):
        ident = sec.find("{*}identifiers")
        isin_el = ident.find("{*}isin") if ident is not None else None
        pct = _num(sec, "pctVal")
        cat_code = _text(sec, "assetCat")
        cat = ASSET_CAT_LABELS.get(cat_code, cat_code) if cat_code else None
        country = _text(sec, "invCountry")
        holdings.append({
            "name": _text(sec, "name") or _text(sec, "title"),
            "cusip": _text(sec, "cusip"),
            "isin": isin_el.get("value") if isin_el is not None else None,
            "weight_pct": _round(pct, 4),
            "market_value": _num(sec, "valUSD"),
            "shares": _num(sec, "balance"),
            "asset_cat": cat,
            "issuer_cat": _text(sec, "issuerCat"),
            "country": country,
            "payoff": _text(sec, "payoffProfile"),
        })
        if pct is not None:
            if cat is not None:
                asset_mix[cat] = asset_mix.get(cat, 0.0) + pct
            if country is not None:
                country_mix[country] = country_mix.get(country, 0.0) + pct

    holdings.sort(key=lambda h: h["weight_pct"] if h["weight_pct"] is not None else -1.0, reverse=True)

    return {
        "fund_name": _text(gen, "regName"),
        "entity_type": "etf",
        "report_date": _text(gen, "repPdDate"),
        "total_net_assets": _num(fund, "netAssets"),
        "total_assets": _num(fund, "totAssets"),
        "total_liabilities": _num(fund, "totLiabs"),
        "total_holdings": len(holdings),
        "asset_mix": {k: round(v, 2) for k, v in asset_mix.items()},
        "country_mix": {k: round(v, 2) for k, v in country_mix.items()},
        "holdings": holdings[:limit],
    }


def classify_entity(client: EdgarClient, base_data: str, resolver: TickerResolver, ticker: str) -> str:
    cik = resolver.resolve(ticker)
    data = client.get_json(f"{base_data}/submissions/CIK{cik_padded(cik)}.json")
    forms = data.get("filings", {}).get("recent", {}).get("form", [])
    if any(isinstance(f, str) and f.upper() in {"NPORT-P", "NPORT-P/A"} for f in forms):
        return "etf"
    return "operating"


def get_etf_holdings(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    limit: int = 25,
) -> dict:
    rows = get_fund_filings(client, base_data, base_www, resolver, ticker, limit=12)
    if not rows:
        raise FundError(f"{ticker.upper()}: no NPORT-P filing found — not a fund or no portfolio data available")
    latest = max(rows, key=lambda r: r["filing_date"])
    xml = client.get_text(raw_xml_url(latest["url"]))
    result = parse_nport_xml(xml, limit)
    result["ticker"] = ticker.upper()
    return result
