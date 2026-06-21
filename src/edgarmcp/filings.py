import re
from typing import Callable

from .http_client import EdgarClient
from .tickers import TickerResolver, cik_padded

INSIDER_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A"}
NPORT_FORMS = {"NPORT-P", "NPORT-P/A"}

_XSL_PREFIX = re.compile(r"/xsl[^/]+/")


def raw_xml_url(url: str) -> str:
    # primaryDocument URLs point at an xsl-rendered view (/.../xsl<Form>/doc.xml);
    # the raw XML lives at the parent path. Covers Form 3/4/5 (xslF345X05) and
    # NPORT-P (xslFormNPORT-P_X01).
    return _XSL_PREFIX.sub("/", url)


def _collect_rows(
    cols: dict,
    cik: int,
    base_www: str,
    form_match: Callable[[str], bool],
    limit: int,
    out: list[dict],
) -> None:
    accessions = cols.get("accessionNumber", [])
    forms = cols.get("form", [])
    filing_dates = cols.get("filingDate", [])
    report_dates = cols.get("reportDate", [])
    acceptances = cols.get("acceptanceDateTime", [])
    docs = cols.get("primaryDocument", [])
    for i in range(len(accessions)):
        if len(out) >= limit:
            return
        form = forms[i] if i < len(forms) else ""
        if not form:
            continue
        if not form_match(form):
            continue
        accession = accessions[i]
        doc = docs[i] if i < len(docs) else ""
        acc_nodash = accession.replace("-", "")
        out.append({
            "form": form,
            "filing_date": filing_dates[i] if i < len(filing_dates) else "",
            "report_date": report_dates[i] if i < len(report_dates) else "",
            "acceptance_datetime": acceptances[i] if i < len(acceptances) else "",
            "accession": accession,
            "primary_document": doc,
            "url": f"{base_www}/Archives/edgar/data/{cik}/{acc_nodash}/{doc}",
        })


def _fetch_filings(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    form_match: Callable[[str], bool],
    limit: int,
) -> list[dict]:
    cik = resolver.resolve(ticker)
    data = client.get_json(f"{base_data}/submissions/CIK{cik_padded(cik)}.json")
    filings = data.get("filings", {})

    out: list[dict] = []
    _collect_rows(filings.get("recent", {}), cik, base_www, form_match, limit, out)

    # Opt-in: reach into older paginated files only if `recent` did not satisfy `limit`.
    if len(out) < limit:
        for file_meta in filings.get("files", []):
            if len(out) >= limit:
                break
            name = file_meta.get("name")
            if not name:
                continue
            older = client.get_json(f"{base_data}/submissions/{name}")
            _collect_rows(older, cik, base_www, form_match, limit, out)

    return out[:limit]


def get_filings(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    form_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    if form_type is None:
        def form_match(_form: str) -> bool:
            return True
    else:
        wanted = form_type.upper()

        def form_match(form: str) -> bool:
            return form.upper() == wanted

    return _fetch_filings(client, base_data, base_www, resolver, ticker, form_match, limit)


def get_insider_filings(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    limit: int = 10,
) -> list[dict]:
    def form_match(form: str) -> bool:
        return form.upper() in INSIDER_FORMS

    return _fetch_filings(client, base_data, base_www, resolver, ticker, form_match, limit)


def get_fund_filings(
    client: EdgarClient,
    base_data: str,
    base_www: str,
    resolver: TickerResolver,
    ticker: str,
    limit: int = 12,
) -> list[dict]:
    def form_match(form: str) -> bool:
        return form.upper() in NPORT_FORMS

    return _fetch_filings(client, base_data, base_www, resolver, ticker, form_match, limit)
