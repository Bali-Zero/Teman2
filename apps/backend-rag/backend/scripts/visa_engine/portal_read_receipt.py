"""portal_read_receipt.py — write the re-verification ledger WHILE reading.

The seq-17 attestation (``research/visa/2026-08-30-freshness-restamp-seq17-
attestation.md``) names the defect of every earlier re-stamp: the fold asserted a
``verified_at`` constant and nothing on disk proved anyone had looked. Its rule:
*write the ledger during the reading, not after it — one line per record at the
moment it is read: URL, HTTP status, the sentence checked, the clock.*

This script is the mechanical half of that rule. For every ``OFFICIAL_PORTAL``
source record it is pointed at, it

1. reads the wall clock BEFORE the request (``fetched_at``),
2. fetches ``canonical_url`` over HTTPS,
3. extracts the page's visible text (scripts, styles, tags and the per-request
   CSRF token stripped — Ditjen pages embed one, which is why two fetches of an
   unchanged page never share a raw-HTML hash and why ``content_sha256`` is a
   quotation fingerprint, never a fetch hash),
4. looks for the record's own key phrase in that text, and
5. appends ONE JSON line to the receipts file and writes the visible text to a
   per-fetch file (``text/<8id>-<fetched_at>.txt``, never overwritten) so a
   reader can quote from what was actually served.

The judgement — *does the page still say what the rules assume?* — is NOT made
here. A reader makes it, from the text file, and records it in a separate
judgement line that names the sentence it checked. Receipt and judgement are two
files on purpose: the receipt is reproducible by anyone with ``curl``; the
judgement is a human/LLM claim and is labelled as one.

Stdlib only, so it runs under any ``python3`` without the serving stack.

Usage::

    python3 portal_read_receipt.py \\
        --pack backend/services/visa_engine/contracts/packs/rulepack-prod-024.signed.json \\
        --out-dir research/visa/2026-10-07-freshness-restamp-seq25 \\
        --reader reader-a --ids 570f2bc4,950a9f63

``--ids`` takes source_record_id prefixes (8 hex chars are enough); ``--all``
selects every OFFICIAL_PORTAL record. Never writes anywhere but ``--out-dir``.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PORTAL_AUTHORITY = "OFFICIAL_PORTAL"
USER_AGENT = "Mozilla/5.0 (Macintosh) BaliZero-source-verifier/1.0 (+https://balizero.com)"
TIMEOUT_SECONDS = 45
MAX_BODY_BYTES = 4 * 1024 * 1024

_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")
# A bare 40-char Laravel CSRF token can survive outside a tag in odd markup;
# strip it from the fingerprint so the receipt hash describes content only.
_CSRF_TOKEN = re.compile(r"\b[A-Za-z0-9]{40}\b")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def visible_text(raw_html: str) -> str:
    text = _SCRIPT_STYLE.sub(" ", raw_html)
    text = _COMMENT.sub(" ", text)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", text, flags=re.IGNORECASE)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return _BLANK_LINES.sub("\n", text).strip()


#: The four portal records whose pack ``title`` is a catalogue label rather
#: than the page's own heading — pinned by ``source_key`` to the heading the
#: page actually carries (read 2026-10-07; a page that drops its heading is a
#: CHECK, which is the point).
KEY_PHRASE_BY_SOURCE_KEY = {
    "imigrasi-voa-country-list": "Daftar Subjek Visa on Arrival",
    "imigrasi-calling-visa-country-list": "Daftar Subjek Calling Visa",
    "imigrasi-press-2024-04-24-izin-tinggal-peralihan": "Izin Tinggal Peralihan",
    "imigrasi-alih-status-itk-itas-service-page": "Alih Status ITK - ITAS",
}


def key_phrase(record: dict[str, Any]) -> str:
    """The phrase whose presence shows the page is still the record's page.

    ``title`` is ``"<name> (<CODE>) — <publisher>"`` for the fifteen visa
    pages — the code is the sharpest key. The other four carry a catalogue
    label as ``title``; their key is the page heading pinned above.
    """
    pinned = KEY_PHRASE_BY_SOURCE_KEY.get(record["source_key"])
    if pinned:
        return pinned
    title = record["title"]
    code = re.search(r"\(([A-Z]\d{1,2}[A-Z]?)\)", title)
    if code:
        return code.group(1)
    return title.split(" — ")[0].strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(_CSRF_TOKEN.sub("", text).encode("utf-8")).hexdigest()


def fetch(url: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BODY_BYTES + 1)
            return response.status, body[:MAX_BODY_BYTES], response.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY_BYTES) if exc.fp else b""
        return exc.code, body, url


def portal_records(pack: dict[str, Any]) -> list[dict[str, Any]]:
    payload = pack.get("payload", pack)
    return [r for r in payload["source_records"] if r.get("authority_type") == PORTAL_AUTHORITY]


def select(records: list[dict[str, Any]], prefixes: list[str] | None) -> list[dict[str, Any]]:
    if prefixes is None:
        return records
    chosen: list[dict[str, Any]] = []
    for prefix in prefixes:
        hits = [r for r in records if r["source_record_id"].startswith(prefix)]
        if len(hits) != 1:
            sys.exit(f"--ids {prefix!r} matches {len(hits)} OFFICIAL_PORTAL records, need exactly 1")
        chosen.append(hits[0])
    return chosen


def _new_text_path(text_dir: Path, short_id: str, fetched_at: str) -> Path:
    """``<8id>-<fetched_at>.txt``: one saved text per fetch, never overwritten."""
    stamp = re.sub(r"[-:]", "", fetched_at)
    path = text_dir / f"{short_id}-{stamp}.txt"
    counter = 1
    while path.exists():
        counter += 1
        path = text_dir / f"{short_id}-{stamp}-{counter}.txt"
    return path


def read_one(record: dict[str, Any], *, reader: str, text_dir: Path) -> dict[str, Any]:
    fetched_at = _utc_now()
    phrase = key_phrase(record)
    receipt: dict[str, Any] = {
        "source_record_id": record["source_record_id"],
        "source_key": record["source_key"],
        "canonical_url": record["canonical_url"],
        "reader": reader,
        "fetched_at": fetched_at,
        "key_phrase": phrase,
    }
    try:
        status, body, final_url = fetch(record["canonical_url"])
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        receipt.update({"http_status": None, "error": f"{type(exc).__name__}: {exc}"})
        return receipt
    text = visible_text(body.decode("utf-8", errors="replace"))
    found_at = text.lower().find(phrase.lower())
    short_id = record["source_record_id"][:8]
    text_path = _new_text_path(text_dir, short_id, fetched_at)
    text_path.write_text(text + "\n", encoding="utf-8")
    receipt.update(
        {
            "http_status": status,
            "final_url": final_url,
            "body_bytes": len(body),
            "visible_text_chars": len(text),
            "visible_text_sha256": fingerprint(text),
            "key_phrase_found": found_at >= 0,
            "key_phrase_context": text[max(0, found_at - 80) : found_at + 160].replace("\n", " ")
            if found_at >= 0
            else None,
            "text_file": str(text_path),
        }
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch OFFICIAL_PORTAL sources and write read receipts.")
    parser.add_argument("--pack", required=True, type=Path, help="signed or source RulePack JSON")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--reader", required=True, help="who is reading (receipt + file name label)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ids", help="comma-separated source_record_id prefixes")
    group.add_argument("--all", action="store_true", help="every OFFICIAL_PORTAL record")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", args.reader):
        sys.exit("--reader must be a short lowercase slug")
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    records = select(portal_records(pack), None if args.all else args.ids.split(","))

    text_dir = args.out_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = args.out_dir / f"{args.reader}-receipts.jsonl"

    failures = 0
    with receipts_path.open("a", encoding="utf-8") as receipts:
        for record in records:
            receipt = read_one(record, reader=args.reader, text_dir=text_dir)
            receipts.write(json.dumps(receipt, ensure_ascii=False) + "\n")
            receipts.flush()
            ok = receipt.get("http_status") == 200 and receipt.get("key_phrase_found") is True
            failures += 0 if ok else 1
            print(
                f"{receipt['source_record_id'][:8]} http={receipt.get('http_status')} "
                f"phrase={receipt.get('key_phrase_found')} at={receipt['fetched_at']} "
                f"{'OK' if ok else 'CHECK'}"
            )
    print(f"receipts: {receipts_path} ({len(records)} read, {failures} to check)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
