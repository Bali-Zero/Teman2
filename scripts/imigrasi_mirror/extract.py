"""HTML -> clean readable text, for diffing CONTENT rather than markup.

The goal is to diff the same signal a human reading the page would see
(country list changed) — not whitespace/attribute/script churn a raw-HTML
diff would drown it in. Best-effort main-content selection: imigrasi.go.id
and the regional kanim mirrors run on different CMS themes (W... none yet,
but expect drift), so this tries a priority list of common content
selectors and falls back to <body> minus boilerplate tags.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

# Tags that are never content, regardless of which CMS rendered the page.
_STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe", "form", "button", "template")
# Structural boilerplate, stripped globally before content-candidate
# selection. `aside` covers the left-nav sidebar this site family renders as
# `<aside id="sidebar">` — measured live 2026-08-08: without it, the sidebar's
# ~35 menu items outweighed the real Calling Visa list (6 countries) and both
# ended up in the same "largest block" (the list survived, buried in noise).
_BOILERPLATE_TAGS = ("nav", "header", "footer", "aside")

# Tried in order; the first one whose extracted text exceeds the threshold
# wins. Covers WordPress-family themes (entry-content/post-content), generic
# semantic HTML5 (main/article), and common CMS content-div id/class names
# seen across imigrasi.go.id + the regional kanim mirrors.
_CONTENT_SELECTORS = (
    "main",
    "article",
    ".entry-content",
    ".post-content",
    "#content",
    ".content",
    "#main-content",
    ".main-content",
    ".container",
)
_MIN_CONTENT_CHARS = 200


def extract_text(html: str) -> str:
    """Return clean, newline-joined readable text from a page's HTML."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    # Boilerplate everywhere on this site family — strip BEFORE candidate
    # selection (not only in the body fallback), so a decorative notice bar
    # that happens to sit inside one of these never gets a chance to win.
    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()

    # Evaluate EVERY match of EVERY selector and keep the single LARGEST text
    # block — not "first selector, first match past the threshold". A
    # first-match rule is exactly the guard-over-match trap (cicatrix family
    # #3): imigrasi.go.id's real VOA/BVK/Calling list lives in
    # `div.container.my-5.px-4.content` (946 chars), but the page's generic
    # "secure .go.id website" notice banner is ALSO `div.container...` and
    # comes first in document order at 452 chars — a first-match rule landed
    # on the banner every time (measured live 2026-08-08, all 5 dry-run
    # snapshots were byte-identical 458-byte banner text, zero real content).
    best = None
    best_len = 0
    for selector in _CONTENT_SELECTORS:
        for candidate in soup.select(selector):
            length = len(candidate.get_text(strip=True))
            if length > best_len:
                best, best_len = candidate, length

    root = best if best is not None and best_len > _MIN_CONTENT_CHARS else (soup.body or soup)
    text = root.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def extract_produk_hukum(html: str) -> str:
    """Kemenimipas legal-document listing (Joomla category view).

    `extract_text` is WRONG for this page for two independent reasons, both
    verified live 2026-08-09:

    1. The regulation table lives inside `<form id="adminForm">` (Joomla's
       sort/filter form). `extract_text` strips every `<form>` as boilerplate,
       so the whole listing is destroyed and the "largest block" it keeps is
       the footer menu (386 chars of ministry address + category links) —
       stable, but the WRONG signal: a new Permen would never be detected
       (cicatrix family #3 UNDER-match / W99 — a guard that looks green while
       watching nothing).
    2. Every row carries a volatile `Dilihat: N` view counter that changes on
       every crawl — diffing the full rendered row would fire an alert every
       run (W116, an alarm nobody reads).

    So extract ONLY the regulation title links (`table.category td.list-title
    a`): "Permenimipas No 15 Tahun 2025 tentang ...", one per line, newest
    first (document order). A new regulation = a new line; view counters and
    footer never appear. If the Joomla theme ever changes, the selector stops
    matching and this returns "" — which diffs LOUDLY against the prior
    (all rows removed) rather than silently watching nothing.
    """
    soup = BeautifulSoup(html, "html.parser")
    titles = [a.get_text(strip=True) for a in soup.select("table.category td.list-title a")]
    return "\n".join(t for t in titles if t)


# Per-page extractor registry. `Page.extractor` selects one; unknown names
# (and the default) fall back to the generic `extract_text`.
_EXTRACTORS = {
    "default": extract_text,
    "produk_hukum": extract_produk_hukum,
}


def extract_for(name: str, html: str) -> str:
    """Dispatch to the page's declared extractor (default: generic)."""
    return _EXTRACTORS.get(name, extract_text)(html)
