from defusedxml.ElementTree import fromstring

from .filings import get_insider_filings, raw_xml_url
from .http_client import EdgarClient, EdgarHTTPError
from .tickers import TickerResolver

# Form 3/4/5 transaction codes → English labels.
ACTION_LABELS: dict[str, str] = {
    "P": "Buy",
    "S": "Sell",
    "A": "Grant",
    "D": "Disposition to issuer",
    "F": "Tax withholding",
    "I": "Discretionary",
    "M": "Derivative conversion",
    "C": "Conversion",
    "X": "Option exercise",
    "G": "Gift",
    "L": "Small acquisition",
    "W": "Inheritance",
    "Z": "Voting trust",
    "J": "Other",
    "K": "Equity swap",
    "U": "Tender",
}


def _text(node, path: str) -> str | None:
    if node is None:
        return None
    el = node.find(path)
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


def _val(node, path: str) -> str | None:
    return _text(node, f"{path}/value")


def _float(node, path: str) -> float:
    v = _val(node, path)
    if v is None:
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def _flag(node, path: str) -> bool:
    return (_text(node, path) or "").lower() in ("1", "true")


def _relationship(is_dir: bool, is_off: bool, is_ten: bool, is_other: bool, title: str | None) -> str:
    parts: list[str] = []
    if is_off:
        parts.append(title or "officer")
    if is_dir:
        parts.append("director")
    if is_ten:
        parts.append("10% owner")
    if is_other:
        parts.append("other insider")
    return ", ".join(parts) or "insider"


def _summary(non_derivative: list[dict]) -> dict:
    by_code: dict[str, float] = {}
    for t in non_derivative:
        if t["code"]:
            by_code[t["code"]] = by_code.get(t["code"], 0.0) + t["shares"]
    primary = max(by_code, key=lambda c: by_code[c]) if by_code else None
    total_shares = 0.0
    total_value = 0.0
    if primary is not None:
        for t in non_derivative:
            if t["code"] == primary:
                total_shares += t["shares"]
                total_value += t["shares"] * t["price"]
    return {
        "primary_code": primary,
        "action": ACTION_LABELS.get(primary, "Other") if primary else None,
        "total_shares": total_shares,
        "total_value": total_value,
    }


def _empty() -> dict:
    return {
        "document_type": "",
        "period_of_report": None,
        "issuer": {"cik": None, "name": None, "symbol": None},
        "reporters": [],
        "non_derivative": [],
        "derivative": [],
        "summary": {"primary_code": None, "action": None, "total_shares": 0.0, "total_value": 0.0},
    }


def parse_ownership_xml(xml_content: str) -> dict:
    try:
        root = fromstring(xml_content)
    except Exception:
        # Malformed or unsafe (entity-bearing) XML — return an empty result.
        return _empty()

    issuer_node = root.find("issuer")
    issuer = {
        "cik": _text(issuer_node, "issuerCik"),
        "name": _text(issuer_node, "issuerName"),
        "symbol": _text(issuer_node, "issuerTradingSymbol"),
    }

    reporters: list[dict] = []
    for ro in root.findall("reportingOwner"):
        oid = ro.find("reportingOwnerId")
        rel = ro.find("reportingOwnerRelationship")
        is_dir = _flag(rel, "isDirector")
        is_off = _flag(rel, "isOfficer")
        is_ten = _flag(rel, "isTenPercentOwner")
        is_other = _flag(rel, "isOther")
        title = _text(rel, "officerTitle")
        reporters.append({
            "cik": _text(oid, "rptOwnerCik") or "",
            "name": _text(oid, "rptOwnerName") or "",
            "is_director": is_dir,
            "is_officer": is_off,
            "is_ten_percent": is_ten,
            "is_other": is_other,
            "officer_title": title,
            "relationship": _relationship(is_dir, is_off, is_ten, is_other, title),
        })

    non_derivative: list[dict] = []
    ndt = root.find("nonDerivativeTable")
    if ndt is not None:
        for t in ndt.findall("nonDerivativeTransaction"):
            code = _text(t, "transactionCoding/transactionCode") or ""
            non_derivative.append({
                "code": code,
                "action": ACTION_LABELS.get(code, "Other"),
                "security_title": _val(t, "securityTitle") or "",
                "date": _val(t, "transactionDate"),
                "shares": _float(t, "transactionAmounts/transactionShares"),
                "price": _float(t, "transactionAmounts/transactionPricePerShare"),
                "acquired_disposed": _val(t, "transactionAmounts/transactionAcquiredDisposedCode") or "",
                "post_holding": _float(t, "postTransactionAmounts/sharesOwnedFollowingTransaction"),
            })

    derivative: list[dict] = []
    dt = root.find("derivativeTable")
    if dt is not None:
        for t in dt.findall("derivativeTransaction"):
            code = _text(t, "transactionCoding/transactionCode") or ""
            derivative.append({
                "code": code,
                "action": ACTION_LABELS.get(code, "Other"),
                "security_title": _val(t, "securityTitle") or "",
                "shares": _float(t, "transactionAmounts/transactionShares"),
                "price": _float(t, "transactionAmounts/transactionPricePerShare"),
            })

    return {
        "document_type": _text(root, "documentType") or "",
        "period_of_report": _text(root, "periodOfReport"),
        "issuer": issuer,
        "reporters": reporters,
        "non_derivative": non_derivative,
        "derivative": derivative,
        "summary": _summary(non_derivative),
    }


def get_insider_trades(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    limit: int = 10,
) -> list[dict]:
    filings = get_insider_filings(client, base_data, base_www, resolver, ticker, limit)
    results: list[dict] = []
    for f in filings:
        # f["url"] is internally constructed from the hardcoded base_www + a
        # resolver-derived CIK + SEC-sourced accession — not user input, so no
        # host-allowlist check (unlike parse_filing_section's user-supplied url).
        xml_url = raw_xml_url(f["url"])
        try:
            xml = client.get_text(xml_url)
        except EdgarHTTPError:
            continue
        parsed = parse_ownership_xml(xml)
        results.append({
            "form": f["form"],
            "filing_date": f["filing_date"],
            "accession": f["accession"],
            "url": f["url"],
            "xml_url": xml_url,
            **parsed,
        })
    return results
