"""Tests for freshest-candidate-wins tag selection in facts.py.

Both get_company_facts and get_financial_statement must evaluate ALL present
candidate tags and return the point with the LATEST end date — not the first
present candidate. This matters when a company migrates XBRL tags over time
(e.g. NVIDIA: RevenueFromContractWithCustomerExcludingAssessedTax → Revenues).
"""

import httpx
from edgarmcp.cache import MemoryCache
from edgarmcp.http_client import EdgarClient
from edgarmcp.tickers import TickerResolver
from edgarmcp.facts import get_company_facts, get_financial_statement

TICKERS_JSON = {"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA Corp"}}

# Companyfacts fixture:
# - First revenue candidate (RevenueFromContractWithCustomerExcludingAssessedTax):
#   stale, latest point end=2022-01-30, val=26_900_000_000
# - Second revenue candidate (Revenues):
#   fresh, latest point end=2026-01-25, val=215_938_000_000
COMPANYFACTS_STALE_FIRST = {
    "cik": 1045810,
    "entityName": "NVIDIA Corp",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [
                    {"end": "2021-01-31", "val": 16_675_000_000, "form": "10-K"},
                    {"end": "2022-01-30", "val": 26_900_000_000, "form": "10-K"},
                ]}
            },
            "Revenues": {
                "units": {"USD": [
                    {"end": "2023-01-29", "val": 26_974_000_000, "form": "10-K"},
                    {"end": "2024-01-28", "val": 60_922_000_000, "form": "10-K"},
                    {"end": "2026-01-25", "val": 215_938_000_000, "form": "10-K"},
                ]}
            },
        }
    },
}


def make_deps(companyfacts: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("company_tickers.json"):
            return httpx.Response(200, json=TICKERS_JSON)
        if "companyfacts" in request.url.path:
            return httpx.Response(200, json=companyfacts)
        return httpx.Response(404)

    client = EdgarClient("UA/1.0", MemoryCache(), transport=httpx.MockTransport(handler))
    resolver = TickerResolver(client, "https://www.sec.gov/files/company_tickers.json")
    return client, resolver


def test_get_company_facts_freshest_candidate_wins():
    """When the first candidate tag is stale and the second is fresh,
    get_company_facts must return the fresh value (latest end date wins)."""
    client, resolver = make_deps(COMPANYFACTS_STALE_FIRST)
    result = get_company_facts(client, "https://data.sec.gov", resolver, "NVDA")
    rev = result["metrics"]["revenue"]
    # Fresh Revenues tag has val=215_938_000_000 (end=2026-01-25)
    # Stale first tag has val=26_900_000_000 (end=2022-01-30)
    assert rev["value"] == 215_938_000_000, (
        f"Expected fresh revenue 215938000000 but got {rev['value']} — "
        f"first-present-wins returned stale data"
    )
    assert rev["period"] == "2026-01-25"


def test_get_financial_statement_freshest_candidate_wins():
    """When the first revenue candidate tag is stale and the second is fresh,
    get_financial_statement must return the fresh value (latest end date wins)."""
    client, resolver = make_deps(COMPANYFACTS_STALE_FIRST)
    result = get_financial_statement(
        client, "https://data.sec.gov", resolver, "NVDA", "income", "annual"
    )
    li = result["line_items"]["revenue"]
    # Fresh Revenues tag has val=215_938_000_000 (end=2026-01-25)
    assert li["value"] == 215_938_000_000, (
        f"Expected fresh revenue 215938000000 but got {li['value']} — "
        f"first-present-wins returned stale data"
    )
    assert li["end"] == "2026-01-25"
