import re
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser

from .http_client import EdgarClient

_ALLOWED_HOSTS = {"www.sec.gov", "data.sec.gov"}

_NON_HTML_SUFFIX = re.compile(r"\.(xml|pdf|jpg|jpeg|png|gif)$", re.IGNORECASE)
_XSL_INSIDER = re.compile(r"xslF345", re.IGNORECASE)


class UnknownSection(Exception):
    pass


class DisallowedURL(Exception):
    pass


class UnsupportedDocument(Exception):
    pass


# section -> (start item-number regex, end item-number regex).
#
# Anchored on the Item NUMBER only, at the start of a line. Real filings often
# split or mangle the section TITLE across markup (e.g. MSFT renders
# "Item 1A. Risk Factors" as "ITEM 1A. RIS" + "K FACTORS" on separate lines, and
# repeats "Item 1A." in the table of contents), but the item number itself is
# stable. `\b` keeps "item 1" from matching "item 1a"/"item 1b" and "item 7" from
# matching "item 7a". (A `\b` after a digit is not a boundary before another
# digit, so "item 1" also won't match "item 10"/"item 11".)
_SECTION_BOUNDS: dict[str, tuple[str, str]] = {
    "business": (r"item\s*1\b", r"item\s*1a\b"),
    "risk_factors": (r"item\s*1a\b", r"item\s*1b\b"),
    "mda": (r"item\s*7\b", r"item\s*7a\b"),
}


def _strip_sgml_wrapper(html: str) -> str:
    # EDGAR wraps documents in <SEC-HEADER>...<DOCUMENT><TEXT>...</TEXT></DOCUMENT>
    # SGML headers. Isolate the <html>...</html> region so parsing starts at real
    # markup. If a complete region is not present, return the input unchanged.
    m = re.search(r"<html.*?</html>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(0)
    return html


def _to_lines(html: str) -> list[str]:
    html = _strip_sgml_wrapper(html)
    tree = HTMLParser(html)
    text = tree.body.text(separator="\n") if tree.body else tree.text(separator="\n")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def parse_filing_section(client: EdgarClient, url: str, section: str) -> str:
    if section not in _SECTION_BOUNDS:
        raise UnknownSection(section)
    if _NON_HTML_SUFFIX.search(url) or _XSL_INSIDER.search(url):
        raise UnsupportedDocument(url)
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in _ALLOWED_HOSTS:
        raise DisallowedURL(url)
    start_pat, end_pat = _SECTION_BOUNDS[section]
    start_re = re.compile(start_pat, re.IGNORECASE)
    end_re = re.compile(end_pat, re.IGNORECASE)

    lines = _to_lines(client.get_text(url))
    return _largest_span(lines, start_re, end_re)


def _largest_span(lines: list[str], start_re: "re.Pattern[str]", end_re: "re.Pattern[str]") -> str:
    """Return the body between a start-item heading and the next end-item heading.

    A 10-K names each section heading more than once (table of contents, the real
    section, cross-references), so we collect every start->next-end span and return
    the one with the most content. The table-of-contents entry is tiny and the
    real section is large, so this reliably skips the TOC and stray references
    without depending on the (often mangled) section title text.
    """
    starts = [i for i, ln in enumerate(lines) if start_re.match(ln)]
    best = ""
    for si in starts:
        end = next((j for j in range(si + 1, len(lines)) if end_re.match(lines[j])), None)
        if end is None:
            continue  # require a real closing heading
        content = "\n\n".join(lines[si + 1:end]).strip()
        if len(content) > len(best):
            best = content
    return best
