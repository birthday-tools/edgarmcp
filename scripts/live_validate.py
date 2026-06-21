#!/usr/bin/env python3
"""Manual, network-gated end-to-end validation against live SEC EDGAR + FRED.

NOT a unit test — it makes real HTTP calls. Run manually before shipping:

    .venv/bin/python scripts/live_validate.py [TICKER] [FRED_SERIES]

Defaults: TICKER=AAPL, FRED_SERIES=FEDFUNDS.
Requires EDGAR_USER_AGENT (has a sane default) and, for the FRED tool,
FRED_API_KEY in the environment or in edgar-mcp/.env.
"""
import sys

from dotenv import load_dotenv

from edgarmcp.cache import FileCache
from edgarmcp.config import Settings
from edgarmcp.deps import build_context
from edgarmcp.http_client import EdgarClient
from edgarmcp.server import build_tools


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def show(label: str, ok: bool, detail: str) -> None:
    mark = "OK " if ok else "ERR"
    print(f"[{mark}] {label}: {detail}")


def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    series = sys.argv[2] if len(sys.argv) > 2 else "FEDFUNDS"

    load_dotenv()
    settings = Settings.from_env()
    client = EdgarClient(
        settings.user_agent,
        FileCache(settings.cache_dir),
        min_interval=1.0 / settings.rate_limit_per_sec if settings.rate_limit_per_sec else 0.0,
        allowed_hosts=settings.allowed_hosts,
    )
    ctx = build_context(settings, client)
    tools = build_tools(ctx)

    failures = 0

    section(f"SEC EDGAR tools — ticker {ticker}")

    # get_company_facts
    try:
        f = tools["get_company_facts"](ticker)
        metrics = f.get("metrics", {})
        rev = metrics.get("revenue", {})
        show("get_company_facts", bool(f.get("entity_name") and metrics),
             f"{f.get('entity_name')} | {len(metrics)} metrics | revenue={rev.get('value')} ({rev.get('period')})")
        if not metrics:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_company_facts", False, f"{type(e).__name__}: {e}")

    # get_financial_statement
    try:
        st = tools["get_financial_statement"](ticker, "income", "annual")
        li = st.get("line_items", {})
        show("get_financial_statement", bool(li),
             f"income/annual | {len(li)} line items | revenue={li.get('revenue', {}).get('value')}")
        if not li:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_financial_statement", False, f"{type(e).__name__}: {e}")

    # get_filings (10-K)
    filing_url = None
    try:
        fl = tools["get_filings"](ticker, "10-K", 2)
        if fl:
            filing_url = fl[0]["url"]
        show("get_filings", bool(fl),
             f"{len(fl)} 10-K filings | latest={fl[0]['filing_date'] if fl else None} | url={filing_url}")
        if not fl:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_filings", False, f"{type(e).__name__}: {e}")

    # parse_filing_section (uses the 10-K url from above)
    if filing_url:
        for sec_name in ("risk_factors", "mda"):
            try:
                text = tools["parse_filing_section"](filing_url, sec_name)
                ok = len(text) > 200
                preview = text[:160].replace("\n", " ")
                show(f"parse_filing_section[{sec_name}]", ok, f"{len(text)} chars | {preview!r}")
                if not ok:
                    failures += 1
            except Exception as e:
                failures += 1
                show(f"parse_filing_section[{sec_name}]", False, f"{type(e).__name__}: {e}")
    else:
        show("parse_filing_section", False, "skipped — no 10-K url")
        failures += 1

    # get_insider_trades
    try:
        it = tools["get_insider_trades"](ticker, 3)
        if it:
            e0 = it[0]
            rep = (e0.get("reporters") or [{}])[0]
            nd = e0.get("non_derivative") or []
            summ = e0.get("summary", {})
            detail = (f"{len(it)} filings | form={e0['form']} | reporter={rep.get('name')} "
                      f"({rep.get('relationship')}) | {len(nd)} non-deriv | "
                      f"summary={summ.get('action')} {summ.get('total_shares')}")
        else:
            detail = "0 insider filings returned"
        show("get_insider_trades", bool(it), detail)
        if not it:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_insider_trades", False, f"{type(e).__name__}: {e}")

    section(f"FRED tool — series {series}")
    try:
        ms = tools["get_macro_series"](series)
        obs = ms.get("observations", [])
        last = obs[-1] if obs else {}
        show("get_macro_series", bool(obs),
             f"{ms.get('title')} | {ms.get('units')} | {ms.get('frequency')} | "
             f"{ms.get('count')} obs | last={last.get('date')}={last.get('value')}")
        if not obs:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_macro_series", False, f"{type(e).__name__}: {e}")

    section(f"Tradernet tool — real-time quote {ticker}")
    try:
        q = tools["get_quote"](ticker)
        ok = q.get("price") is not None
        show("get_quote", ok,
             f"{q.get('ticker')} | last={q.get('price')} | bid={q.get('bid')} ask={q.get('ask')} | "
             f"vol={q.get('volume_day')} | t={q.get('last_trade_time')}")
        if not ok:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_quote", False, f"{type(e).__name__}: {e}")

    section("ETF tool — holdings SPY")
    try:
        h = tools["get_etf_holdings"]("SPY", 3)
        top = h.get("holdings", [])
        ok = bool(top) and h.get("total_net_assets") is not None
        names = ", ".join(x["name"] for x in top)
        show("get_etf_holdings", ok,
             f"{h.get('fund_name')} | {h.get('total_holdings')} holdings | "
             f"netAssets={h.get('total_net_assets')} | top: {names}")
        if not ok:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_etf_holdings", False, f"{type(e).__name__}: {e}")

    section("Look-through — get_holdings_analysis SP500")
    try:
        a = tools["get_holdings_analysis"]("SP500", 25)
        cov = a.get("coverage", {})
        secs = ", ".join(f"{b['sector']} {b['weight_pct']}%" for b in a.get("sector_breakdown", [])[:3])
        ok = cov.get("matched", 0) > 0
        res = cov.get("resolution", {})
        show("get_holdings_analysis", ok,
             f"{a.get('resolved_etf')} | matched {cov.get('matched')}/{cov.get('of')} "
             f"({cov.get('matched_weight_pct')}%) via cusip={res.get('by_cusip')}/isin={res.get('by_isin')}/name={res.get('by_name')} | "
             f"margin={a.get('weighted_net_margin')} roe={a.get('weighted_roe')} | top sectors: {secs}")
        if not ok:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_holdings_analysis", False, f"{type(e).__name__}: {e}")

    section("Index — get_index S&P 500")
    try:
        ix = tools["get_index"]("S&P 500")
        lvl = ix.get("level") or {}
        top = ", ".join(f"{x['name']}({x['ticker']})" for x in ix.get("top_holdings", [])[:3])
        ok = bool(ix.get("tracking_etf"))
        show("get_index", ok,
             f"{ix.get('index')} | level={lvl.get('value')} @ {lvl.get('date')} | etf={ix.get('tracking_etf')} | top: {top}")
        if not ok:
            failures += 1
    except Exception as e:
        failures += 1
        show("get_index", False, f"{type(e).__name__}: {e}")

    section("RESULT")
    print(f"{'ALL TOOLS OK' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
