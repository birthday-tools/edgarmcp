from edgarmcp.analysis import weighted_average, build_analysis


def test_weighted_average_renormalizes_and_handles_empty():
    assert weighted_average([(0.20, 50.0), (0.10, 30.0)]) == 0.1625
    assert weighted_average([]) is None
    assert weighted_average([(0.5, 0.0)]) is None   # zero total weight -> None


ENRICHED = [
    {"name": "A", "weight_pct": 50.0, "matched": True, "sector": "Tech", "net_margin": 0.20, "roe": 0.30, "via": "cusip"},
    {"name": "B", "weight_pct": 30.0, "matched": True, "sector": "Tech", "net_margin": 0.10, "roe": None, "via": "cusip"},
    {"name": "C", "weight_pct": 10.0, "matched": True, "sector": "Auto", "net_margin": None, "roe": 0.15, "via": "name"},
    {"name": "D Unmatched", "weight_pct": 5.0, "matched": False, "sector": None, "net_margin": None, "roe": None},
]


def test_build_analysis_aggregates():
    out = build_analysis("SP500", "SPY", "Fund", "2026-03-31", 503, 4, ENRICHED)
    assert out["symbol"] == "SP500"
    assert out["resolved_etf"] == "SPY"
    assert out["holdings_analyzed"] == 4
    assert out["total_holdings"] == 503
    assert out["coverage"] == {
        "matched": 3, "of": 4, "matched_weight_pct": 90.0,
        "resolution": {"by_cusip": 2, "by_isin": 0, "by_name": 1},
    }
    assert out["sector_breakdown"][0] == {"sector": "Tech", "weight_pct": 80.0, "holdings": 2}
    assert out["sector_breakdown"][1] == {"sector": "Auto", "weight_pct": 10.0, "holdings": 1}
    assert out["weighted_net_margin"] == 0.1625   # (0.20*50 + 0.10*30)/80
    assert out["weighted_roe"] == 0.275           # (0.30*50 + 0.15*10)/60
    assert out["metric_coverage"] == {"net_margin": 2, "roe": 2, "of_matched": 3}
    assert out["unmatched"] == ["D Unmatched"]
