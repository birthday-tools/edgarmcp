from edgarmcp.funds import parse_nport_xml

NPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo>
      <regName>Test S&amp;P 500 ETF</regName>
      <repPdDate>2026-03-31</repPdDate>
    </genInfo>
    <fundInfo>
      <totAssets>1000.00</totAssets>
      <totLiabs>50.00</totLiabs>
      <netAssets>950.00</netAssets>
    </fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>Alpha Corp</name><cusip>AAA111</cusip>
        <identifiers><isin value="US_AAA"/></identifiers>
        <balance>100.0</balance><valUSD>500.0</valUSD><pctVal>52.63</pctVal>
        <payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>Beta Inc</name><cusip>BBB222</cusip>
        <identifiers><isin value="US_BBB"/></identifiers>
        <balance>50.0</balance><valUSD>300.0</valUSD><pctVal>31.58</pctVal>
        <payoffProfile>Long</payoffProfile>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>Gamma SA</name><cusip>CCC333</cusip>
        <identifiers><isin value="FR_CCC"/></identifiers>
        <balance>20.0</balance><valUSD>150.0</valUSD><pctVal>15.79</pctVal>
        <payoffProfile>Long</payoffProfile>
        <assetCat>XYZ</assetCat><issuerCat>CORP</issuerCat><invCountry>FR</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""


def test_parses_header_and_totals():
    out = parse_nport_xml(NPORT_XML)
    assert out["fund_name"] == "Test S&P 500 ETF"
    assert out["entity_type"] == "etf"
    assert out["report_date"] == "2026-03-31"
    assert out["total_net_assets"] == 950.0
    assert out["total_assets"] == 1000.0
    assert out["total_liabilities"] == 50.0
    assert out["total_holdings"] == 3


def test_holding_fields_and_weight_is_pctval_directly():
    out = parse_nport_xml(NPORT_XML)
    top = out["holdings"][0]
    assert top["name"] == "Alpha Corp"
    assert top["cusip"] == "AAA111"
    assert top["isin"] == "US_AAA"
    assert top["weight_pct"] == 52.63       # == pctVal, NOT pctVal*100
    assert top["market_value"] == 500.0
    assert top["shares"] == 100.0
    assert top["asset_cat"] == "Equity-common"   # EC label
    assert top["issuer_cat"] == "CORP"
    assert top["country"] == "US"
    assert top["payoff"] == "Long"


def test_holdings_sorted_by_weight_desc():
    out = parse_nport_xml(NPORT_XML)
    weights = [h["weight_pct"] for h in out["holdings"]]
    assert weights == sorted(weights, reverse=True)
    assert [h["name"] for h in out["holdings"]] == ["Alpha Corp", "Beta Inc", "Gamma SA"]


def test_limit_truncates_holdings_but_not_aggregates():
    out = parse_nport_xml(NPORT_XML, limit=2)
    assert len(out["holdings"]) == 2
    assert out["total_holdings"] == 3                      # counted over ALL
    assert out["asset_mix"]["Equity-common"] == 84.21      # 52.63 + 31.58, over ALL
    assert out["asset_mix"]["XYZ"] == 15.79                # unknown code passes through
    assert out["country_mix"]["US"] == 84.21
    assert out["country_mix"]["FR"] == 15.79


NPORT_XML_TITLE_FALLBACK = """<?xml version="1.0" encoding="UTF-8"?>
<edgarSubmission xmlns="http://www.sec.gov/edgar/nport">
  <formData>
    <genInfo>
      <regName>Bond ETF</regName>
      <repPdDate>2026-03-31</repPdDate>
    </genInfo>
    <fundInfo>
      <totAssets>2000.00</totAssets>
      <totLiabs>100.00</totLiabs>
      <netAssets>1900.00</netAssets>
    </fundInfo>
    <invstOrSecs>
      <invstOrSec>
        <title>US Treasury Bond 2.5% 2030</title>
        <cusip>DDD444</cusip>
        <identifiers><isin value="US_DDD"/></identifiers>
        <balance>1000.0</balance><valUSD>1000.0</valUSD><pctVal>55.0</pctVal>
        <assetCat>DBT</assetCat><issuerCat>UST</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>Regular Equity</name>
        <title>Should Be Ignored</title>
        <cusip>EEE555</cusip>
        <identifiers><isin value="US_EEE"/></identifiers>
        <balance>500.0</balance><valUSD>500.0</valUSD><pctVal>45.0</pctVal>
        <assetCat>EC</assetCat><issuerCat>CORP</issuerCat><invCountry>US</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>"""


def test_holding_name_falls_back_to_title_when_name_missing():
    """Debt/derivative holdings may have <title> but no <name>; name should fall back."""
    out = parse_nport_xml(NPORT_XML_TITLE_FALLBACK)
    # sorted by weight desc: 55.0 first, 45.0 second
    bond = out["holdings"][0]
    assert bond["name"] == "US Treasury Bond 2.5% 2030", (
        f"Expected title fallback but got: {bond['name']!r}"
    )


def test_holding_name_wins_over_title_when_both_present():
    """When both <name> and <title> are present, <name> must be used."""
    out = parse_nport_xml(NPORT_XML_TITLE_FALLBACK)
    equity = out["holdings"][1]
    assert equity["name"] == "Regular Equity"


def test_existing_holdings_name_unchanged():
    """Existing fixtures with <name> must not be affected by the fallback."""
    out = parse_nport_xml(NPORT_XML)
    assert out["holdings"][0]["name"] == "Alpha Corp"
