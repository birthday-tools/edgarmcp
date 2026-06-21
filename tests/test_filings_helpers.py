from edgarmcp.filings import raw_xml_url


def test_raw_xml_url_strips_nport_xsl_folder():
    url = "https://www.sec.gov/Archives/edgar/data/884394/000141036826055357/xslFormNPORT-P_X01/primary_doc.xml"
    assert raw_xml_url(url) == "https://www.sec.gov/Archives/edgar/data/884394/000141036826055357/primary_doc.xml"


def test_raw_xml_url_strips_form345_xsl_folder():
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/xslF345X05/doc.xml"
    assert raw_xml_url(url) == "https://www.sec.gov/Archives/edgar/data/320193/000032019324000001/doc.xml"


def test_raw_xml_url_noop_without_xsl_folder():
    url = "https://www.sec.gov/Archives/edgar/data/1/2/primary_doc.xml"
    assert raw_xml_url(url) == url
