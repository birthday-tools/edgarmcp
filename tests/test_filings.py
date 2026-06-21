import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.filings import get_filings

TICKERS_JSON = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}

SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {"recent": {
        "accessionNumber": ["0000320193-23-000106", "0000320193-23-000077", "0000320193-23-000064"],
        "filingDate": ["2023-11-03", "2023-08-04", "2023-05-05"],
        "reportDate": ["2023-09-30", "2023-07-01", "2023-04-01"],
        "form": ["10-K", "10-Q", "10-Q"],
        "primaryDocument": ["aapl-20230930.htm", "aapl-20230701.htm", "aapl-20230401.htm"],
    }},
}


def make_deps():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "submissions" in request.url.path:
            return httpx.Response(200, json=SUBMISSIONS)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    return client, resolver


def test_get_filings_returns_all_with_urls():
    client, resolver = make_deps()
    out = get_filings(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL")
    assert len(out) == 3
    first = out[0]
    assert first["form"] == "10-K"
    assert first["filing_date"] == "2023-11-03"
    assert first["accession"] == "0000320193-23-000106"
    assert first["url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019323000106/aapl-20230930.htm"
    )


def test_get_filings_filters_by_form_and_limit():
    client, resolver = make_deps()
    out = get_filings(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", form_type="10-q", limit=1)
    assert len(out) == 1
    assert out[0]["form"] == "10-Q"
    assert out[0]["report_date"] == "2023-07-01"


def test_get_filings_skips_empty_form_rows():
    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    subs = {"filings": {"recent": {
        "accessionNumber": ["0000320193-23-000106", "0000320193-23-000077"],
        "filingDate": ["2023-11-03", "2023-08-04"],
        "reportDate": ["2023-09-30", "2023-07-01"],
        "form": ["", "10-Q"],
        "primaryDocument": ["x.htm", "y.htm"],
    }}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if "submissions" in request.url.path:
            return httpx.Response(200, json=subs)
        return httpx.Response(404)

    from edgarmcp.cache import MemoryCache
    c = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    r = TickerResolver(c, "https://www.sec.gov/files/company_tickers.json")
    out = get_filings(c, "https://data.sec.gov", "https://www.sec.gov", r, "AAPL")
    assert [f["form"] for f in out] == ["10-Q"]


def test_get_filings_default_limit_caps_at_10():
    n = 12
    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    subs = {"filings": {"recent": {
        "accessionNumber": [f"0000320193-23-{i:06d}" for i in range(n)],
        "filingDate": ["2023-01-01"] * n,
        "reportDate": ["2022-12-31"] * n,
        "form": ["8-K"] * n,
        "primaryDocument": [f"doc{i}.htm" for i in range(n)],
    }}}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if "submissions" in request.url.path:
            return httpx.Response(200, json=subs)
        return httpx.Response(404)

    from edgarmcp.cache import MemoryCache
    c = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    r = TickerResolver(c, "https://www.sec.gov/files/company_tickers.json")
    out = get_filings(c, "https://data.sec.gov", "https://www.sec.gov", r, "AAPL")
    assert len(out) == 10


def test_paginates_to_older_file_when_recent_lacks_form():
    import httpx
    from edgarmcp.cache import MemoryCache
    from edgarmcp.http_client import EdgarClient
    from edgarmcp.tickers import TickerResolver

    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    # recent has only 8-Ks, no 10-K
    recent = {"filings": {
        "recent": {
            "accessionNumber": ["0000320193-24-000010"],
            "filingDate": ["2024-02-01"], "reportDate": ["2024-01-31"],
            "acceptanceDateTime": ["2024-02-01T16:30:00.000Z"],
            "form": ["8-K"], "primaryDocument": ["a.htm"],
        },
        "files": [{"name": "CIK0000320193-submissions-001.json",
                   "filingFrom": "2018-01-01", "filingTo": "2020-12-31"}],
    }}
    older = {
        "accessionNumber": ["0000320193-19-000119"],
        "filingDate": ["2019-10-31"], "reportDate": ["2019-09-28"],
        "acceptanceDateTime": ["2019-10-31T16:30:00.000Z"],
        "form": ["10-K"], "primaryDocument": ["aapl-2019.htm"],
    }
    calls = {"older": 0}

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if p.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=recent)
        if "submissions-001" in p:
            calls["older"] += 1
            return httpx.Response(200, json=older)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    out = get_filings(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", form_type="10-K", limit=5)
    assert calls["older"] == 1
    assert len(out) == 1
    assert out[0]["form"] == "10-K"
    assert out[0]["accession"] == "0000320193-19-000119"
    assert out[0]["acceptance_datetime"] == "2019-10-31T16:30:00.000Z"
    assert out[0]["url"] == "https://www.sec.gov/Archives/edgar/data/320193/000032019319000119/aapl-2019.htm"


def test_no_older_fetch_when_recent_satisfies_limit():
    import httpx
    from edgarmcp.cache import MemoryCache
    from edgarmcp.http_client import EdgarClient
    from edgarmcp.tickers import TickerResolver

    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    recent = {"filings": {
        "recent": {
            "accessionNumber": ["0000320193-23-000106"],
            "filingDate": ["2023-11-03"], "reportDate": ["2023-09-30"],
            "acceptanceDateTime": ["2023-11-03T18:01:00.000Z"],
            "form": ["10-K"], "primaryDocument": ["aapl.htm"],
        },
        "files": [{"name": "CIK0000320193-submissions-001.json",
                   "filingFrom": "2018-01-01", "filingTo": "2020-12-31"}],
    }}
    calls = {"older": 0}

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if p.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=recent)
        if "submissions-001" in p:
            calls["older"] += 1
            return httpx.Response(200, json={})
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    out = get_filings(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", form_type="10-K", limit=1)
    assert calls["older"] == 0
    assert len(out) == 1
    assert out[0]["acceptance_datetime"] == "2023-11-03T18:01:00.000Z"


def test_get_insider_filings_returns_only_insider_forms():
    import httpx
    from edgarmcp.cache import MemoryCache
    from edgarmcp.http_client import EdgarClient
    from edgarmcp.tickers import TickerResolver
    from edgarmcp.filings import get_insider_filings

    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    recent = {"filings": {"recent": {
        "accessionNumber": ["0000320193-23-000106", "0000320193-23-000200", "0000320193-23-000201"],
        "filingDate": ["2023-11-03", "2023-11-04", "2023-11-05"],
        "reportDate": ["2023-09-30", "2023-11-02", "2023-11-03"],
        "acceptanceDateTime": ["", "", ""],
        "form": ["10-K", "4", "3/A"],
        "primaryDocument": ["aapl.htm", "xslF345X05/wk-form4.xml", "xslF345X05/wk-form3a.xml"],
    }}}

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if p.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=recent)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    out = get_insider_filings(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", limit=10)
    forms = [f["form"] for f in out]
    assert forms == ["4", "3/A"]  # 10-K excluded, order preserved
    assert out[0]["url"].endswith("xslF345X05/wk-form4.xml")
