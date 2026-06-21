from .funds import classify_entity
from .http_client import EdgarClient, EdgarHTTPError
from .tickers import TickerResolver, cik_padded

# Normalized metric -> candidate us-gaap tags, first present wins.
FACT_MAP: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "eps_basic": ["EarningsPerShareBasic"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity"],
}


def load_company_facts(client: EdgarClient, base_data: str, resolver: TickerResolver, ticker: str) -> dict:
    cik = resolver.resolve(ticker)
    url = f"{base_data}/api/xbrl/companyfacts/CIK{cik_padded(cik)}.json"
    return client.get_json(url)


class EntityTypeError(Exception):
    pass


def _load_facts_or_route(client: EdgarClient, base_data: str, resolver: TickerResolver, ticker: str) -> dict:
    try:
        return load_company_facts(client, base_data, resolver, ticker)
    except EdgarHTTPError as exc:
        if "-> 404" in str(exc):
            try:
                is_fund = classify_entity(client, base_data, resolver, ticker) == "etf"
            except EdgarHTTPError:
                is_fund = False
            if is_fund:
                raise EntityTypeError(
                    f"{ticker.upper()} is an ETF/fund: no XBRL fundamentals — use get_etf_holdings"
                ) from exc
        raise


def _latest_point(tag_obj: dict) -> dict | None:
    units = tag_obj.get("units", {})
    best: dict | None = None
    best_unit = ""
    for unit, points in units.items():
        for p in points:
            if "end" not in p or "val" not in p:
                continue
            if best is None or p["end"] > best["end"]:
                best = p
                best_unit = unit
    if best is None:
        return None
    return {
        "value": best["val"],
        "period": best["end"],
        "form": best.get("form", ""),
        "unit": best_unit,
    }


def get_company_facts(client: EdgarClient, base_data: str, resolver: TickerResolver, ticker: str) -> dict:
    raw = _load_facts_or_route(client, base_data, resolver, ticker)
    us_gaap = raw.get("facts", {}).get("us-gaap", {})
    metrics: dict[str, dict] = {}
    for name, candidates in FACT_MAP.items():
        best = None
        for tag in candidates:
            if tag in us_gaap:
                point = _latest_point(us_gaap[tag])
                if point is not None and (best is None or point["period"] > best["period"]):
                    best = point
        if best is not None:
            metrics[name] = best
    return {
        "ticker": ticker.upper(),
        "cik": raw.get("cik"),
        "entity_name": raw.get("entityName", ""),
        "metrics": metrics,
    }


class UnknownStatement(Exception):
    pass


# statement -> {normalized line item: [candidate us-gaap tags]}
STATEMENT_MAP: dict[str, dict[str, list[str]]] = {
    "income": {
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
        "operating_income": ["OperatingIncomeLoss"],
        "net_income": ["NetIncomeLoss"],
    },
    "balance": {
        "total_assets": ["Assets"],
        "total_liabilities": ["Liabilities"],
        "stockholders_equity": ["StockholdersEquity"],
        "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    },
    "cashflow": {
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "investing_cash_flow": ["NetCashProvidedByUsedInInvestingActivities"],
        "financing_cash_flow": ["NetCashProvidedByUsedInFinancingActivities"],
    },
}

_FORM_FOR_PERIOD: dict[str, str] = {"annual": "10-K", "quarterly": "10-Q"}


def _latest_point_for_form(tag_obj: dict, form: str) -> dict | None:
    best: dict | None = None
    for points in tag_obj.get("units", {}).values():
        for p in points:
            if p.get("form") != form or "end" not in p or "val" not in p:
                continue
            if best is None or p["end"] > best["end"]:
                best = p
    if best is None:
        return None
    return {"value": best["val"], "end": best["end"], "form": best["form"]}


def get_financial_statement(
    client: EdgarClient,
    base_data: str,
    resolver: TickerResolver,
    ticker: str,
    statement: str,
    period: str = "annual",
) -> dict:
    if statement not in STATEMENT_MAP:
        raise UnknownStatement(statement)
    if period not in _FORM_FOR_PERIOD:
        raise UnknownStatement(period)
    form = _FORM_FOR_PERIOD[period]
    raw = _load_facts_or_route(client, base_data, resolver, ticker)
    us_gaap = raw.get("facts", {}).get("us-gaap", {})
    line_items: dict[str, dict] = {}
    for name, candidates in STATEMENT_MAP[statement].items():
        best = None
        for tag in candidates:
            if tag in us_gaap:
                point = _latest_point_for_form(us_gaap[tag], form)
                if point is not None and (best is None or point["end"] > best["end"]):
                    best = point
        if best is not None:
            line_items[name] = best
    return {
        "ticker": ticker.upper(),
        "statement": statement,
        "period": period,
        "line_items": line_items,
    }
