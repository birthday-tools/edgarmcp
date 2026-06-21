from edgarmcp.insider import raw_xml_url, parse_ownership_xml

FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2023-09-28</periodOfReport>
  <issuer>
    <issuerCik>0000320193</issuerCik>
    <issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001214156</rptOwnerCik>
      <rptOwnerName>COOK TIMOTHY D</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <isOther>0</isOther>
      <officerTitle>Chief Executive Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2023-09-28</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>511000</value></transactionShares>
        <transactionPricePerShare><value>174.05</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>3280000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_raw_xml_url_strips_xsl_prefix():
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000200/xslF345X05/wk-form4.xml"
    assert raw_xml_url(url) == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000200/wk-form4.xml"


def test_raw_xml_url_noop_when_no_xsl():
    url = "https://www.sec.gov/Archives/edgar/data/320193/000.../wk-form4.xml"
    assert raw_xml_url(url) == url


def test_parse_form4_issuer_and_period():
    p = parse_ownership_xml(FORM4_XML)
    assert p["document_type"] == "4"
    assert p["period_of_report"] == "2023-09-28"
    assert p["issuer"] == {"cik": "0000320193", "name": "Apple Inc.", "symbol": "AAPL"}


def test_parse_form4_reporter_roles():
    p = parse_ownership_xml(FORM4_XML)
    assert len(p["reporters"]) == 1
    r = p["reporters"][0]
    assert r["name"] == "COOK TIMOTHY D"
    assert r["is_officer"] is True
    assert r["is_director"] is False
    assert r["officer_title"] == "Chief Executive Officer"
    assert r["relationship"] == "Chief Executive Officer"


def test_parse_form4_non_derivative_and_summary():
    p = parse_ownership_xml(FORM4_XML)
    assert len(p["non_derivative"]) == 1
    t = p["non_derivative"][0]
    assert t["code"] == "S"
    assert t["action"] == "Sell"
    assert t["security_title"] == "Common Stock"
    assert t["date"] == "2023-09-28"
    assert t["shares"] == 511000.0
    assert t["price"] == 174.05
    assert t["acquired_disposed"] == "D"
    assert t["post_holding"] == 3280000.0
    s = p["summary"]
    assert s["primary_code"] == "S"
    assert s["action"] == "Sell"
    assert s["total_shares"] == 511000.0
    assert s["total_value"] == 511000.0 * 174.05


def test_parse_malformed_xml_returns_empty():
    p = parse_ownership_xml("<not-valid><unclosed>")
    assert p["document_type"] == ""
    assert p["reporters"] == []
    assert p["non_derivative"] == []
    assert p["summary"]["primary_code"] is None


def test_parse_rejects_xxe_entity_xml():
    xxe = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<ownershipDocument><documentType>&xxe;</documentType></ownershipDocument>'
    )
    p = parse_ownership_xml(xxe)
    # defusedxml must reject the DTD/entity -> empty result, entity NOT expanded
    assert p["document_type"] == ""
    assert p["reporters"] == []
    assert p["summary"]["primary_code"] is None


def test_get_insider_trades_end_to_end():
    import httpx
    from edgarmcp.cache import MemoryCache
    from edgarmcp.http_client import EdgarClient
    from edgarmcp.tickers import TickerResolver
    from edgarmcp.insider import get_insider_trades

    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    recent = {"filings": {"recent": {
        "accessionNumber": ["0000320193-23-000106", "0000320193-23-000200"],
        "filingDate": ["2023-11-03", "2023-09-28"],
        "reportDate": ["2023-09-30", "2023-09-28"],
        "acceptanceDateTime": ["", ""],
        "form": ["10-K", "4"],
        "primaryDocument": ["aapl.htm", "xslF345X05/wk-form4.xml"],
    }}}

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if p.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=recent)
        # raw XML URL must have the xsl prefix stripped
        if p.endswith("/000032019323000200/wk-form4.xml"):
            return httpx.Response(200, text=FORM4_XML)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    out = get_insider_trades(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", limit=10)

    assert len(out) == 1  # only the Form 4, not the 10-K
    e = out[0]
    assert e["form"] == "4"
    assert e["accession"] == "0000320193-23-000200"
    assert e["xml_url"].endswith("/000032019323000200/wk-form4.xml")
    assert "xslF345" not in e["xml_url"]
    assert e["issuer"]["symbol"] == "AAPL"
    assert e["summary"]["action"] == "Sell"
    assert e["non_derivative"][0]["shares"] == 511000.0


def test_get_insider_trades_skips_filing_with_failed_xml_fetch():
    import httpx
    from edgarmcp.cache import MemoryCache
    from edgarmcp.http_client import EdgarClient
    from edgarmcp.tickers import TickerResolver
    from edgarmcp.insider import get_insider_trades

    tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    recent = {"filings": {"recent": {
        "accessionNumber": ["0000320193-23-000200", "0000320193-23-000201"],
        "filingDate": ["2023-09-28", "2023-09-27"],
        "reportDate": ["2023-09-28", "2023-09-27"],
        "acceptanceDateTime": ["", ""],
        "form": ["4", "4"],
        "primaryDocument": ["xslF345X05/wk-form4.xml", "xslF345X05/wk-missing.xml"],
    }}}

    def handler(request):
        p = request.url.path
        if p.endswith("company_tickers.json"):
            return httpx.Response(200, json=tickers)
        if p.endswith("CIK0000320193.json"):
            return httpx.Response(200, json=recent)
        if p.endswith("/000032019323000200/wk-form4.xml"):
            return httpx.Response(200, text=FORM4_XML)
        # /000032019323000201/wk-missing.xml is NOT registered -> 404 -> EdgarHTTPError
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    out = get_insider_trades(client, "https://data.sec.gov", "https://www.sec.gov", resolver, "AAPL", limit=10)

    # the second filing's XML 404s -> skipped; only the first survives
    assert len(out) == 1
    assert out[0]["accession"] == "0000320193-23-000200"


MIXED_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer><issuerCik>0000320193</issuerCik><issuerName>Apple Inc.</issuerName><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>10</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>500</value></transactionShares><transactionPricePerShare><value>20</value></transactionPricePerShare><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""


def test_summary_scopes_totals_to_primary_code():
    p = parse_ownership_xml(MIXED_FORM4_XML)
    s = p["summary"]
    # S has the larger volume (1000 > 500) -> primary
    assert s["primary_code"] == "S"
    assert s["action"] == "Sell"
    # totals reflect ONLY the S transactions, not the P
    assert s["total_shares"] == 1000.0
    assert s["total_value"] == 1000.0 * 10
