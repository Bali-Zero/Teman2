#!/usr/bin/env python3
"""
Pure HTML parsing helpers for pajak_monitor.py — stdlib only, no agent_job/
browser_job imports so this module can be unit-tested in isolation.

pajak.go.id (DJP) now serves regulation/press hrefs as
`/index.php/id/peraturan/<slug>` (a `/index.php` prefix the older parser did
not anticipate) and each index row is a `views-row` block whose fields
(nomor, title, jenis, tanggal, status) must be read from WITHIN that block —
never from the whole page, or a link ends up paired with the next row's
title (or the pager).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

PAJAK_DOMAIN = "https://pajak.go.id"

_ROW_SPLIT_RE = re.compile(r'(?=<div class="peraturan-content views-row)')
_NOMOR_RE = re.compile(
    r'views-field-field-nomor-dokumen[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]*)</a>',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'views-field-title[^>]*>\s*<span[^>]*>([^<]*)</span>', re.DOTALL
)
_JENIS_RE = re.compile(
    r'views-field-field-jenis-dokumen[^>]*>\s*<strong[^>]*>([^<]*)</strong>',
    re.DOTALL,
)
_STATUS_RE = re.compile(
    r'views-field-field-status-peraturan[^>]*>\s*<strong[^>]*>([^<]*)</strong>',
    re.DOTALL,
)
_DATE_RE = re.compile(r'<time datetime="([^"]*)"')

_LINK_ITEM_RE = re.compile(
    r'<a[^>]+href="((?:/index\.php)?/id/(?:peraturan|siaran-pers|berita)/[^"?#]+)"'
    r'[^>]*>(.*?)</a>',
    re.DOTALL,
)


def canonical_pajak_url(href: str) -> str:
    """Absolute pajak.go.id URL, `/index.php` prefix stripped.

    This is the identity the Redis seen-set and `intel_items.canonical_url`
    dedup on — it must stay exactly `https://pajak.go.id/id/...`, whether
    the source href was relative, already absolute, on `www.`, or carried
    the new `/index.php` prefix.
    """
    href = href.strip()
    m = re.match(r"^https?://(?:www\.)?pajak\.go\.id(/.*)$", href, re.IGNORECASE)
    path = m.group(1) if m else href
    if not path.startswith("/"):
        path = "/" + path
    if path == "/index.php" or path.startswith("/index.php/"):
        path = path[len("/index.php"):] or "/"
    return PAJAK_DOMAIN + path


def source_host(url: str) -> str:
    """Lowercased hostname of *url*, leading `www.` stripped, port dropped.

    This is the label `_write_intel_feed` puts in `source_domain` — it must
    name the host an item actually came from, not the job that fetched it
    (Source 3, `_search_djp_updates`, is a Brave web_search that also
    returns press/tax-consulting sites, not just pajak.go.id). `www.` is
    stripped because both `intel_lake_router.py`'s `_RULES` (government
    entries like `pajak\\.go\\.id` are matched via `pattern.match`, i.e.
    anchored at the start of the string — `www.pajak.go.id` would not
    match) and `intel_source_whitelist.py`'s `INTEL_SOURCE_WHITELIST` key
    on the bare domain. Returns "" for an unparseable/hostless value; the
    caller must not fall back to a hardcoded domain on that empty result.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[len("www."):]
    return host


def parse_peraturan_index(html: str) -> list[dict]:
    """Parse a pajak.go.id `index-peraturan` Drupal views listing.

    One dict per `views-row` block; fields are read from within that block
    only. Blocks without an href are skipped. Deduped by canonical url,
    page order preserved.
    """
    items: list[dict] = []
    seen: set[str] = set()

    for block in _ROW_SPLIT_RE.split(html):
        if not block.startswith('<div class="peraturan-content views-row'):
            continue

        nomor_m = _NOMOR_RE.search(block)
        if not nomor_m:
            continue
        href, nomor = nomor_m.group(1), nomor_m.group(2).strip()
        url = canonical_pajak_url(href)
        if url in seen:
            continue
        seen.add(url)

        title_m = _TITLE_RE.search(block)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""

        jenis_m = _JENIS_RE.search(block)
        jenis = jenis_m.group(1).strip() if jenis_m else None

        status_m = _STATUS_RE.search(block)
        status = status_m.group(1).strip() if status_m else None

        date_m = _DATE_RE.search(block)
        regulation_date = date_m.group(1) if date_m else None

        items.append({
            "url": url,
            "nomor": nomor,
            "title": title,
            "jenis": jenis,
            "regulation_date": regulation_date,
            "status": status,
        })

    return items


def parse_link_items(html: str) -> list[tuple[str, str]]:
    """Parse siaran-pers/berita link listings into `(canonical_url, title)`.

    Anchor text under 15 chars (whitespace-collapsed) is treated as pager/
    navigation chrome and skipped, unless the href's slug itself looks like
    a real article (falls back to a title derived from the slug).
    Deduped by canonical url in page order; when one url is linked several
    times ("Detail", "Selengkapnya", the headline), the longest text wins,
    so a short chrome link never shadows the headline that follows it.
    Only `/id/` pages: an `/en/` twin is a second url for the same item.
    """
    best: dict[str, str] = {}

    for m in _LINK_ITEM_RE.finditer(html):
        href, raw_text = m.group(1), m.group(2)
        text = re.sub(r"<[^>]+>", "", raw_text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < 15:
            slug = href.rstrip("/").split("/")[-1]
            if re.search(r"[a-z]{3,}-[a-z0-9]{3,}", slug):
                text = slug.replace("-", " ").title()
            else:
                continue

        url = canonical_pajak_url(href)
        if len(text) > len(best.get(url, "")):
            best[url] = text

    return list(best.items())


# ─── peraturan DETAIL page — citation + verbatim excerpt for admission ──────
#
# A pajak.go.id peraturan detail page is Drupal `node--type-peraturan`: the
# jenis/nomor/tanggal/body live in four `field--name-field-*` containers.
# The body field is a WYSIWYG table that nests further divs/spans — a plain
# regex on the whole page (like the index parser above) would either grab
# too little or bleed into a sibling field, so this walks tags with a depth
# counter per active field container instead.

_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

_DETAIL_FIELD_MARKERS = {
    "jenis": "field--name-field-jenis-dokumen",
    "nomor": "field--name-field-nomor-dokumen",
    "tanggal": "field--name-field-tanggal-peraturan",
    "body": "field--name-field-body-dalam-html",
}

_CUT_KEYWORD_RE = re.compile(r"\b(?:menimbang|mengingat)\b", re.IGNORECASE)
_EXCERPT_MAX_CHARS = 700


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _DetailFieldExtractor(HTMLParser):
    """Collects the text of each `_DETAIL_FIELD_MARKERS` container by class-substring match.

    Only ONE field is "active" at a time; its own nesting depth (void tags excluded — they
    never get a matching end tag, self-closed or not) decides when the container ends, so an
    inner `<div>`/`<span>` inside e.g. the body field never closes it early. The `tanggal`
    field's `<time datetime="...">` value is captured separately since that is the actual date,
    not display text like "12-05-2026".
    """

    def __init__(self) -> None:
        super().__init__()
        self.texts: dict[str, list[str]] = {name: [] for name in _DETAIL_FIELD_MARKERS}
        self.tanggal_datetime: str | None = None
        self._active: str | None = None
        self._depth = 0

    def _maybe_capture_time(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._active == "tanggal" and tag == "time" and self.tanggal_datetime is None:
            dt = dict(attrs).get("datetime")
            if dt:
                self.tanggal_datetime = dt

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._maybe_capture_time(tag, attrs)
        if self._active is None:
            cls = dict(attrs).get("class") or ""
            for name, marker in _DETAIL_FIELD_MARKERS.items():
                if marker in cls:
                    self._active = name
                    self._depth = 1
                    return
            return
        if tag not in _VOID_TAGS:
            self._depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Self-closed tag (`<br />`, `<img ... />`) — no separate end tag will arrive, so it
        # never changes depth, void or not.
        self._maybe_capture_time(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or tag in _VOID_TAGS:
            return
        self._depth -= 1
        if self._depth <= 0:
            self._active = None
            self._depth = 0

    def handle_data(self, data: str) -> None:
        if self._active:
            self.texts[self._active].append(data)


def extract_regulation(html: str) -> dict | None:
    """Citation + verbatim excerpt from a pajak.go.id peraturan DETAIL page.

    Returns `None` if the body field (`field--name-field-body-dalam-html`) is absent — there is
    nothing to quote. Otherwise returns `{"citation", "verbatim_excerpt", "regulation_date",
    "jenis", "nomor"}`; `citation` and `verbatim_excerpt` are `None` together when the heading
    cannot be found in the body — this never fabricates or paraphrases a citation, because the
    downstream admission rule (`_statement_is_from_source`) requires `citation` to occur as a
    literal, delimited token inside `verbatim_excerpt`, and a synthesized citation would either
    fail that check or, worse, pass it on text nobody actually wrote.
    """

    parser = _DetailFieldExtractor()
    parser.feed(html)

    body_text = _collapse_ws(" ".join(parser.texts["body"]))
    if not body_text:
        return None

    jenis = _collapse_ws(" ".join(parser.texts["jenis"])) or None
    nomor = _collapse_ws(" ".join(parser.texts["nomor"])) or None
    regulation_date = parser.tanggal_datetime

    citation = None
    if jenis and nomor:
        heading_re = re.compile(
            rf"{re.escape(jenis)}(?:\s+REPUBLIK\s+INDONESIA)?\s+NOMOR\s+{re.escape(nomor)}",
            re.IGNORECASE,
        )
        m = heading_re.search(body_text)
        if m:
            citation = m.group(0)
    if citation is None and nomor:
        m = re.search(rf"NOMOR\s+{re.escape(nomor)}", body_text, re.IGNORECASE)
        if m:
            citation = m.group(0)

    verbatim_excerpt = None
    if citation is not None:
        start = body_text.find(citation)
        hard_limit = min(start + _EXCERPT_MAX_CHARS, len(body_text))
        cut_m = _CUT_KEYWORD_RE.search(body_text, start)
        if cut_m and cut_m.start() <= hard_limit:
            end = cut_m.start()
        else:
            end = hard_limit
            if end < len(body_text):
                last_ws = body_text.rfind(" ", start, end)
                if last_ws > start:
                    end = last_ws
        verbatim_excerpt = body_text[start:end].rstrip()

    return {
        "citation": citation,
        "verbatim_excerpt": verbatim_excerpt,
        "regulation_date": regulation_date,
        "jenis": jenis,
        "nomor": nomor,
    }
