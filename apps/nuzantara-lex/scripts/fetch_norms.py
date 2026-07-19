#!/usr/bin/env python3
"""fetch_norms.py — Phase-0 L1 fetch+verify step for NUZANTARA-LEX.

Reads data_sources/ketenagakerjaan_seed.json and, for each "unverified"
entry: searches peraturan.bpk.go.id by jenis+nomor+tahun (never free-text
keyword search — free-text on this portal ranks unrelated ministerial
regulations above the actual UU/PP, live-confirmed 2026-07-19), resolves
the /Details/<id>/<slug> page, resolves the /Download/<id>/<file> PDF
link on that page, downloads the PDF with a browser-standard User-Agent,
then verifies the regulation's IDENTITY by reading page 1 of the
downloaded PDF and requiring "NOMOR <nomor> TAHUN <anno>" to appear in
its text. Only then is the entry promoted to "verified" with pdf_url,
sha256, verified_at and a verify_note fragment. Any entry that can't be
found, resolved, downloaded, or content-verified stays "unverified" with
verify_note recording the concrete reason — this script never fabricates
a verified status, and it persists the seed file after every entry so a
mid-sweep crash never loses prior progress.

GROUNDED FACT (2026-07-19, live-probed before writing this script):
peraturan.bpk.go.id's Cloudflare rejects the default urllib/httpx User-
Agent with a bare 403; a real browser UA gets 200 on the same host, same
minute (first proven 2026-07-16 in scripts/kbli_filiera/vault_common.py
for direct /Download/<id> fetches — re-confirmed here for the
/Search + /Details flow this script also needs).

GOTCHA (guard-over-match, cicatrix-superscar.md family #3): matching a
bare `str(nomor) in type_line` on the BPK search-result text would trap
on substrings ("1" matches inside "13", "21", ...). Every nomor/anno
match against search-result text in this script is word-boundary regex,
never bare substring — and every claim of "verified" is anchored on the
PDF's own content, never on the filename, URL slug, or search-result
title (superscar family #6, "never trust a filename/slug").

GOTCHA #2 (broken-font digit confusables, empirically hit 2026-07-19 on
the very first live run): PP 35/2021's own BPK PDF extracts page 1 as
"NOMOR 35 TAHUN 2O2I" via pypdf — a broken embedded-font ToUnicode CMap,
not a wrong document (see _DIGIT_CONFUSABLES below for the full evidence
trail). verify_pdf_identity() tolerates this at the digit-position level
only; it does not broaden matching anywhere else.

Usage:
    python scripts/fetch_norms.py --limit 3
    python scripts/fetch_norms.py --all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent  # apps/nuzantara-lex
REPO_ROOT = APP_ROOT.parent.parent  # repo root
SEED_PATH = APP_ROOT / "data_sources" / "ketenagakerjaan_seed.json"
RAW_DIR = REPO_ROOT / "data" / "nuzantara-lex" / "raw"  # gitignored — see .gitignore

# ---------------------------------------------------------------------------
# Logging (logger, never print — CLAUDE.md golden rule #8)
# ---------------------------------------------------------------------------


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("nuzantara_lex.fetch_norms")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


LOG = _setup_logger()

# ---------------------------------------------------------------------------
# HTTP constants
# ---------------------------------------------------------------------------

BASE_URL = "https://peraturan.bpk.go.id"

# Browser UA required — see GROUNDED FACT in module docstring.
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}

# peraturan.bpk.go.id "Jenis Peraturan" filter codes (live-probed 2026-07-19
# from the <select name="jenis"> options on /Search). Only the two types
# used by the Phase-0 ketenagakerjaan seed are mapped; an entry whose
# `tipo` isn't in this dict fails cleanly with a descriptive verify_note
# rather than crashing.
JENIS_CODE: dict[str, int] = {
    "UU": 8,   # Undang-undang (UU)
    "PP": 10,  # Peraturan Pemerintah (PP)
}

# Substring expected in a matching search-result's type-line (e.g.
# "Undang-undang (UU) Nomor 13 Tahun 2003" or "... No. 13 Tahun 2003" —
# BPK's own display is inconsistent between "Nomor" and "No.", so we
# anchor on the type name, not that token).
TIPO_MARKER: dict[str, str] = {
    "UU": "undang-undang",
    "PP": "peraturan pemerintah",
}

# Pairs a search-result-card's type-line with its /Details/<id>/<slug>
# anchor. Live-verified 2026-07-19 against real /Search HTML: this only
# matches the actual result cards (class "fs-5 text-gray-600" title line
# immediately followed, within the same card, by the entry's own detail
# anchor) — "related regulations" links elsewhere on the page use a
# different markup and are never captured.
ENTRY_RE = re.compile(
    r'fs-5 text-gray-600">\s*(?P<type_line>[^<]+?)\s*</div>'
    r'.*?href="(?P<href>/Details/(?P<detail_id>\d+)/(?P<slug>[^"]+))"'
    r'\s*>\s*(?P<title>[^<]*?)\s*</a>',
    re.DOTALL,
)

# Matches only a real numeric-id download link, e.g. "/Download/31128/UU%20..."
# — the Details page also embeds a JS template literal
# "/Download/${id}/${filename}" that must NOT be picked up; requiring
# \d+ for the id excludes it structurally.
DOWNLOAD_RE = re.compile(r'/Download/(\d+)/([^"\'\s<>]+)')


@dataclass
class SearchOutcome:
    details_href: str | None
    note: str


@dataclass
class DownloadLinkOutcome:
    download_url: str | None
    note: str


@dataclass
class DownloadOutcome:
    body: bytes | None
    note: str


@dataclass
class VerifyOutcome:
    ok: bool
    note: str


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def http_get(
    client: httpx.Client,
    url: str,
    *,
    referer: str | None = None,
    retries: int = 3,
    backoff: float = 1.5,
) -> httpx.Response | None:
    """GET with browser headers + manual retry. Returns the httpx.Response
    (whatever its status code) on any attempt that completes without a
    transport-level error, so the caller inspects status_code/text itself.
    Returns None only if every attempt raised. A 200 or 404 returns
    immediately without retrying — a 404 is a real absence signal, not a
    transient failure to hammer (matches scripts/kbli_filiera/vault_common.py
    discipline)."""
    headers = dict(BROWSER_HEADERS)
    if referer:
        headers["Referer"] = referer
    last_error: Exception | None = None
    resp: httpx.Response | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            last_error = exc
            LOG.debug("GET %s attempt %s/%s raised: %s", url, attempt + 1, retries, exc)
            resp = None
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
            continue
        last_error = None
        if resp.status_code in (200, 404):
            return resp
        LOG.debug("GET %s attempt %s/%s -> HTTP %s", url, attempt + 1, retries, resp.status_code)
        if attempt < retries - 1:
            time.sleep(backoff * (attempt + 1))
    if last_error is not None:
        LOG.error("GET %s exhausted %s retries: %s", url, retries, last_error)
        return None
    return resp  # last non-2xx/404 response — caller reads its status_code


def _word_boundary_match(needle: str, haystack: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE) is not None


# ---------------------------------------------------------------------------
# Step 1 — search
# ---------------------------------------------------------------------------


def search_details_link(tipo: str, nomor: str, anno: str, client: httpx.Client) -> SearchOutcome:
    jenis = JENIS_CODE.get(tipo)
    if jenis is None:
        return SearchOutcome(None, f"unsupported tipo {tipo!r} — no jenis code mapping in JENIS_CODE")

    url = f"{BASE_URL}/Search?jenis={jenis}&nomor={nomor}&tahun={anno}"
    resp = http_get(client, url, referer=f"{BASE_URL}/")
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else "no-response"
        return SearchOutcome(None, f"search HTTP {status} for {url}")

    html = resp.text
    marker = TIPO_MARKER[tipo]
    candidates = 0
    for m in ENTRY_RE.finditer(html):
        candidates += 1
        type_line = m.group("type_line").strip()
        if marker not in type_line.lower():
            continue
        if not _word_boundary_match(nomor, type_line):
            continue
        if not _word_boundary_match(anno, type_line):
            continue
        return SearchOutcome(m.group("href"), f"matched search card type_line={type_line!r} title={m.group('title').strip()!r}")

    return SearchOutcome(
        None,
        f"no search-result card matched tipo={tipo} nomor={nomor} anno={anno} "
        f"({candidates} candidate card(s) scanned) at {url}",
    )


# ---------------------------------------------------------------------------
# Step 2 — resolve download link from the Details page
# ---------------------------------------------------------------------------


def resolve_download_link(details_href: str, client: httpx.Client) -> DownloadLinkOutcome:
    details_url = BASE_URL + details_href
    resp = http_get(client, details_url, referer=f"{BASE_URL}/")
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else "no-response"
        return DownloadLinkOutcome(None, f"details HTTP {status} for {details_url}")

    m = DOWNLOAD_RE.search(resp.text)
    if not m:
        return DownloadLinkOutcome(None, f"no /Download/<id>/<file> link found on {details_url}")

    download_id, filename = m.group(1), m.group(2)
    download_url = f"{BASE_URL}/Download/{download_id}/{filename}"
    return DownloadLinkOutcome(download_url, f"resolved from {details_url}")


# ---------------------------------------------------------------------------
# Step 3 — download the PDF
# ---------------------------------------------------------------------------


def download_pdf(download_url: str, referer: str, dest: Path, client: httpx.Client) -> DownloadOutcome:
    resp = http_get(client, download_url, referer=referer)
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else "no-response"
        return DownloadOutcome(None, f"download HTTP {status} for {download_url}")

    body = resp.content
    if not body.startswith(b"%PDF"):
        return DownloadOutcome(None, f"downloaded body is not a PDF (first bytes {body[:8]!r}) from {download_url}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return DownloadOutcome(body, f"saved {len(body)} bytes to {dest}")


# ---------------------------------------------------------------------------
# Step 4 — verify identity by content (never by filename/slug)
# ---------------------------------------------------------------------------

# EMPIRICALLY OBSERVED 2026-07-19 (live run against PP 35/2021's own BPK
# "SALINAN" PDF): a broken ToUnicode CMap in an embedded font subset makes
# pypdf extract some digit glyphs as visually-similar letters — the SAME
# page renders "NOMOR 35 TAHUN 2O2I" (2021), "Tahun 2OO3" (2003, correctly
# elsewhere as "2003"), and "Tahun l94S" (1945) — while "13" and "4279"
# on the same page extract as real digits. The corruption is per-glyph-
# instance (which embedded font subset drew that specific run of text),
# not a stable global remap, so a fixed find/replace would be wrong; only
# *tolerance* at match time is sound. This is narrowly scoped to digit
# positions inside the anchored "NOMOR ... TAHUN ..." pattern below — it
# does not loosen matching anywhere else, and it does not change how many
# digits must appear or their order, only which literal codepoint may
# stand in for a given digit at a given position.
_DIGIT_CONFUSABLES: dict[str, str] = {
    "0": "0Oo",
    "1": "1IlL",
    "5": "5Ss",
}


def _tolerant_digit_pattern(number_str: str) -> str:
    parts = []
    for ch in number_str:
        alts = _DIGIT_CONFUSABLES.get(ch, ch)
        parts.append(f"[{re.escape(alts)}]" if len(alts) > 1 else re.escape(alts))
    return "".join(parts)


def verify_pdf_identity(pdf_path: Path, nomor: str, anno: str) -> VerifyOutcome:
    """Reads page 1 only and requires "NOMOR <nomor> TAHUN <anno>" to
    appear (case-insensitive; digit positions additionally tolerate the
    empirically-observed confusable set above). On success `note` is the
    raw matched fragment as pypdf actually extracted it (<=100 chars,
    confusables included verbatim — never "cleaned" — so the record stays
    honest about what was really read); on failure it's the concrete
    reason."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 — pypdf can raise many exception types
        return VerifyOutcome(False, f"pypdf could not open file: {exc}")

    if len(reader.pages) == 0:
        return VerifyOutcome(False, "PDF has zero pages")

    try:
        text = reader.pages[0].extract_text() or ""
    except Exception as exc:  # noqa: BLE001
        return VerifyOutcome(False, f"pypdf could not extract page-1 text: {exc}")

    nomor_pat = _tolerant_digit_pattern(nomor)
    anno_pat = _tolerant_digit_pattern(anno)
    pattern = re.compile(rf"NOMOR\s+{nomor_pat}\s+TAHUN\s+{anno_pat}", re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        snippet = " ".join(text.split())[:100]
        return VerifyOutcome(False, f"'NOMOR {nomor} TAHUN {anno}' not found on page 1; page-1 starts: {snippet!r}")

    start = m.start()
    fragment = " ".join(text[max(0, start - 20) : start + 80].split())[:100]
    return VerifyOutcome(True, fragment)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _slugify(citation: str) -> str:
    """'UU 13/2003' -> 'uu-13-2003'."""
    s = citation.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_entry(entry: dict, client: httpx.Client) -> dict:
    citation = entry["citation"]
    tipo = entry["tipo"]
    nomor = str(entry["nomor"])
    anno = str(entry["anno"])

    LOG.info("=== %s: searching peraturan.bpk.go.id (jenis=%s nomor=%s tahun=%s) ===", citation, tipo, nomor, anno)

    search = search_details_link(tipo, nomor, anno, client)
    if search.details_href is None:
        LOG.warning("%s: search failed — %s", citation, search.note)
        entry["status"] = "unverified"
        entry["verify_note"] = search.note[:200]
        return entry
    LOG.info("%s: %s", citation, search.note)

    link = resolve_download_link(search.details_href, client)
    if link.download_url is None:
        LOG.warning("%s: details resolution failed — %s", citation, link.note)
        entry["status"] = "unverified"
        entry["verify_note"] = link.note[:200]
        return entry
    LOG.info("%s: download_url=%s", citation, link.download_url)

    dest = RAW_DIR / f"{_slugify(citation)}.pdf"
    dl = download_pdf(link.download_url, BASE_URL + search.details_href, dest, client)
    if dl.body is None:
        LOG.warning("%s: download failed — %s", citation, dl.note)
        entry["status"] = "unverified"
        entry["verify_note"] = dl.note[:200]
        return entry
    LOG.info("%s: %s", citation, dl.note)

    verify = verify_pdf_identity(dest, nomor, anno)
    if not verify.ok:
        LOG.warning("%s: content verification FAILED — %s", citation, verify.note)
        entry["status"] = "unverified"
        entry["verify_note"] = verify.note[:200]
        # pdf_url/sha256/verified_at intentionally left unset — an
        # unverified entry carries no provenance claim.
        return entry

    sha = hashlib.sha256(dl.body).hexdigest()
    LOG.info("%s: VERIFIED sha256=%s — %r", citation, sha[:12], verify.note)
    entry["status"] = "verified"
    entry["pdf_url"] = link.download_url
    entry["sha256"] = sha
    entry["verified_at"] = _now_iso()
    entry["verify_note"] = verify.note[:100]
    return entry


def load_seed() -> list[dict]:
    with SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_seed(entries: list[dict]) -> None:
    with SEED_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")


def run(*, limit: int, all_entries: bool, sleep_s: float) -> int:
    entries = load_seed()
    unverified_idx = [i for i, e in enumerate(entries) if e.get("status") == "unverified"]
    total_unverified = len(unverified_idx)
    if not all_entries:
        unverified_idx = unverified_idx[:limit]

    if not unverified_idx:
        LOG.info("nothing to do — 0 unverified entries selected (total unverified in seed: %s)", total_unverified)
        return 0

    LOG.info(
        "processing %s of %s unverified entries (limit=%s all=%s)",
        len(unverified_idx), total_unverified, limit, all_entries,
    )

    verified_count = 0
    failed_count = 0
    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
        for n, idx in enumerate(unverified_idx):
            entries[idx] = process_entry(entries[idx], client)
            if entries[idx]["status"] == "verified":
                verified_count += 1
            else:
                failed_count += 1
            save_seed(entries)  # persist after every entry — a crash mid-sweep never loses prior progress
            if n < len(unverified_idx) - 1:
                time.sleep(sleep_s)

    LOG.info("DONE — verified=%s failed=%s of %s attempted", verified_count, failed_count, len(unverified_idx))
    return 0 if failed_count == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=3, help="max unverified entries to process (default 3)")
    parser.add_argument("--all", action="store_true", help="process all unverified entries, ignoring --limit")
    parser.add_argument("--sleep-s", type=float, default=2.0, help="polite delay between norms in seconds (default 2.0)")
    args = parser.parse_args(argv)
    return run(limit=args.limit, all_entries=args.all, sleep_s=args.sleep_s)


if __name__ == "__main__":
    sys.exit(main())
