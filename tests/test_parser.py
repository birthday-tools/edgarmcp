import httpx
import pytest
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.parser import parse_filing_section, UnknownSection, DisallowedURL

FILING_HTML = """
<html><body>
<p>Item 1. Business</p>
<p>We design and sell smartphones and computers.</p>
<p>Item 1A. Risk Factors</p>
<div>Our business is subject to competition.</div>
<div>Supply chain disruptions may harm results.</div>
<p>Item 1B. Unresolved Staff Comments</p>
<p>None.</p>
<p>Item 7. Management&rsquo;s Discussion and Analysis</p>
<p>Revenue increased year over year.</p>
<p>Item 7A. Quantitative Disclosures</p>
<p>Interest rate risk.</p>
</body></html>
"""

URL = "https://www.sec.gov/Archives/edgar/data/320193/000.../aapl.htm"


def make_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FILING_HTML)

    return EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))


def test_parse_risk_factors():
    text = parse_filing_section(make_client(), URL, "risk_factors")
    assert "subject to competition" in text
    assert "Supply chain disruptions" in text
    # must stop before the next item
    assert "Unresolved Staff Comments" not in text
    assert "smartphones" not in text


def test_parse_mda():
    text = parse_filing_section(make_client(), URL, "mda")
    assert "Revenue increased year over year" in text
    assert "Interest rate risk" not in text


def test_unknown_section_raises():
    with pytest.raises(UnknownSection):
        parse_filing_section(make_client(), URL, "footnotes")


def test_parse_business():
    text = parse_filing_section(make_client(), URL, "business")
    assert "smartphones and computers" in text
    assert "subject to competition" not in text


def test_rejects_non_sec_host():
    with pytest.raises(DisallowedURL):
        parse_filing_section(make_client(), "https://evil.example.com/x.htm", "risk_factors")


def test_rejects_non_https_scheme():
    with pytest.raises(DisallowedURL):
        parse_filing_section(make_client(), "http://www.sec.gov/x.htm", "risk_factors")


def test_rejects_metadata_ip():
    with pytest.raises(DisallowedURL):
        parse_filing_section(make_client(), "http://169.254.169.254/latest/meta-data/", "risk_factors")


def _client_returning(body: str):
    def handler(request):
        return httpx.Response(200, text=body)

    return EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))


SGML_FILING = """<SEC-DOCUMENT>0000320193-23-000106.txt : 20231103
<SEC-HEADER>ACCESSION NUMBER: 0000320193-23-000106
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<TEXT>
<html><body>
<p>Item 1. Business</p>
<p>We sell devices. Refer to Item 1A for related risks.</p>
<p>Item 1A. Risk Factors</p>
<p>Competition is intense.</p>
<p>Item 1B. Unresolved Staff Comments</p>
<p>None.</p>
</body></html>
</TEXT>
</DOCUMENT>
"""

SEC_URL = "https://www.sec.gov/Archives/edgar/data/320193/000.../aapl.htm"


def test_business_survives_sgml_wrapper_and_cross_reference():
    text = parse_filing_section(_client_returning(SGML_FILING), SEC_URL, "business")
    # SGML header content must not leak in
    assert "ACCESSION NUMBER" not in text
    # full business paragraph kept, NOT truncated at the "Item 1A" cross-reference
    assert "We sell devices" in text
    assert "Refer to Item 1A for related risks" in text
    # stops at the real heading line
    assert "Competition is intense" not in text


def test_risk_factors_from_sgml_wrapped_filing():
    text = parse_filing_section(_client_returning(SGML_FILING), SEC_URL, "risk_factors")
    assert "Competition is intense" in text
    assert "Unresolved Staff Comments" not in text
    assert "We sell devices" not in text


def test_rejects_non_html_document():
    from edgarmcp.parser import UnsupportedDocument
    with pytest.raises(UnsupportedDocument):
        parse_filing_section(make_client(), "https://www.sec.gov/Archives/edgar/data/1/2/form4.xml", "risk_factors")


def test_rejects_xsl_insider_document():
    from edgarmcp.parser import UnsupportedDocument
    with pytest.raises(UnsupportedDocument):
        parse_filing_section(make_client(), "https://www.sec.gov/Archives/edgar/data/1/2/xslF345X05/doc.htm", "risk_factors")


def test_strip_sgml_wrapper_is_noop_without_html_region():
    from edgarmcp.parser import _strip_sgml_wrapper
    raw = "Plain text with no markup at all."
    assert _strip_sgml_wrapper(raw) == raw


# --- Regression: real-filing heading variance (found via live validation on MSFT) ---

TOC_FILING = """<html><body>
<p>Item 1A.</p><p>Risk Factors</p><p>15</p>
<p>Item 1B.</p><p>Unresolved Staff Comments</p><p>20</p>
<p>Item 1. Business</p><p>We make software for enterprises and consumers.</p>
<p>Item 1A. Risk Factors</p>
<p>Our results may be affected by intense competition in cloud services.</p>
<p>Cybersecurity incidents could harm our reputation and finances.</p>
<p>Item 1B. Unresolved Staff Comments</p><p>None.</p>
</body></html>"""


def test_risk_factors_skips_table_of_contents():
    # The TOC repeats "Item 1A." / "Item 1B." with a tiny body; the real section
    # is large. We must return the real section, not the TOC stub.
    text = parse_filing_section(_client_returning(TOC_FILING), SEC_URL, "risk_factors")
    assert "intense competition in cloud services" in text
    assert "Cybersecurity incidents" in text
    assert "Unresolved Staff Comments" not in text


SPLIT_TITLE_FILING = """<html><body>
<p>Item 1. Business</p><p>We build rockets.</p>
<p>ITEM 1A. RIS</p><p>K FACTORS</p>
<p>Launch failures could materially harm operations.</p>
<p>ITEM 1B. UNRESOLVED STAFF COMMENTS</p><p>None.</p>
</body></html>"""


def test_risk_factors_handles_split_title_heading():
    # Markup can split the title mid-word ("RIS" + "K FACTORS"); anchoring on the
    # item number still locates the section.
    text = parse_filing_section(_client_returning(SPLIT_TITLE_FILING), SEC_URL, "risk_factors")
    assert "Launch failures could materially harm operations" in text
    assert "We build rockets" not in text
