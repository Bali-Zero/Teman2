#!/usr/bin/env python3
"""vault_fetch_perpres.py — Batch-0 vault compiler: the Daftar Positif Investasi.

WHY THIS EXISTS
---------------
Every `pma_status` / `pma_max_asing` value in this catalogue cites
"Perpres 10/2021, 49/2021" — 1,559 records out of 1,559. Two modules in this
package hold transcriptions of those annexes as DATA
(`perpres_foreign_cap_relation.py` = Lampiran III, foreign-ownership caps;
`perpres_umkm_reservation_relation.py` = Lampiran II, Koperasi/UMKM
reservation). Until this fetcher existed, **neither transcription was
re-derivable**: measured 2026-08-02, the vault held 22 PDFs — 21 PP-28/2025
lampiran plus one BPS conversion table — and **zero** files naming either
Perpres; `perpres-foreign-caps.json` records `transcribed_from: "page images
rendered at 200dpi"` with no path, no URL and no sha256, and no fetch-log line
in any vault subdir mentions the instrument. So the module whose docstring says
it makes "the PMA axis stop being the one axis with no checkable source" named a
source nobody could reach. A transcription whose artifact is unpinned is not
evidence; it is a claim. This pins the artifact.

THE OPERATIVE ANNEXES BELONG TO 49/2021, NOT 10/2021
-----------------------------------------------------
Perpres 49/2021 articles 3, 4 and 5 read `Lampiran I diubah` / `Lampiran II
diubah` / `Lampiran III diubah`: all three annexes of 10/2021 were REPLACED.
BPK publishes them as three separate downloads under 49/2021 (161563/161564/
161565), while 10/2021's own annexes survive only as a single `Lampiran.zip`
(154475). That zip is fetched as ARCHAEOLOGY and marked `superseded: True` —
a locator that names it points at replaced text. Anything deciding a live
foreign-ownership question must read a `superseded: False` row.

ROLE IS VERIFIED, NEVER ASSUMED
--------------------------------
`vault_fetch_pp28` learned the hard way that one lampiran letter can span
several ids, so it parses the server's own filename rather than trusting the
id order. Same discipline here, inverted: each id carries a DECLARED role, and
the fetcher cross-checks that role against the `Content-Disposition` filename
BPK actually returns. A mismatch is a hard failure with both strings in the
message — never a silent re-label. If BPK renumbers a download, this fetcher
stops instead of quietly vaulting Lampiran I under the name of Lampiran III,
which is precisely the substitution the two relation modules could not survive.

Fail-visible (superscar #2, "esiste != armato"): the sweep always runs to
completion; only at the end does a non-empty failure list cause a non-zero exit,
so one bad id never hides the rest of the report.

Usage:
    python scripts/kbli_filiera/vault_fetch_perpres.py [--vault-root PATH] [--sleep-s N]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover — allow `python vault_fetch_perpres.py` from this dir
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

BASE_URL = "https://peraturan.bpk.go.id/Download/"

# Live-probed 2026-08-02 from peraturan.bpk.go.id/Details/168534 (Perpres 49/2021)
# and /Details/161806 (Perpres 10/2021). `match` is the substring the server's own
# Content-Disposition filename MUST contain for the row to be accepted.
DOWNLOADS: tuple[dict, ...] = (
    {"id": 161562, "instrument": "Perpres 49/2021", "role": "body",
     "match": "49 Tahun 2021.pdf", "superseded": False},
    {"id": 161563, "instrument": "Perpres 49/2021", "role": "lampiran-I",
     "match": "Lampiran I.pdf", "superseded": False},
    {"id": 161564, "instrument": "Perpres 49/2021", "role": "lampiran-II",
     "match": "Lampiran II.pdf", "superseded": False},
    {"id": 161565, "instrument": "Perpres 49/2021", "role": "lampiran-III",
     "match": "Lampiran III.pdf", "superseded": False},
    {"id": 154474, "instrument": "Perpres 10/2021", "role": "body",
     "match": "10 Tahun 2021.pdf", "superseded": False},
    # 10/2021's annexes were REPLACED by 49/2021 arts. 3-5 — archaeology only.
    {"id": 154475, "instrument": "Perpres 10/2021", "role": "lampiran-zip",
     "match": "Lampiran.zip", "superseded": True},
)

LOG = common.setup_logger("vault_fetch_perpres")


def fetch_log_path(vault_root: Path) -> Path:
    return vault_root / "perpres" / "fetch-log.jsonl"


def load_latest_by_id(vault_root: Path) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for rec in common.read_jsonl(fetch_log_path(vault_root)):
        rid = rec.get("id")
        if rid is not None:
            latest[rid] = rec
    return latest


def target_path(vault_root: Path, download_id: int, filename: str) -> Path:
    return vault_root / "perpres" / f"{download_id}__{common.sanitize_filename(filename)}"


def role_mismatch(spec: dict, filename: str) -> str | None:
    """None when the server's filename confirms the declared role.

    `Lampiran I.pdf` is a PREFIX of nothing here, but `Lampiran II.pdf` would be
    matched by a naive `"Lampiran I" in filename` test — so the expected
    substrings carry their extension and are compared whole. Anything else is a
    mismatch, reported with both strings so the reader never has to guess which
    side moved.
    """
    if spec["match"] in filename:
        return None
    return f"role {spec['role']}: expected a filename containing {spec['match']!r}, server sent {filename!r}"


def fetch_one(vault_root: Path, spec: dict, prior: dict | None, *, sleep_s: float = 2.0) -> dict:
    """Fetch (or verify-and-skip) one download id.

    Returns the record to append to the fetch-log, or the untouched `prior`
    record itself on a verified skip (callers use `is` identity to decide
    whether the log needs a new line).
    """
    download_id = spec["id"]
    if prior is not None and not prior.get("error"):
        candidate = target_path(vault_root, download_id, prior.get("filename") or "")
        if common.decide_resume(prior, candidate) == "skip":
            LOG.info("id=%s SKIP (verified on disk) -> %s", download_id, candidate.name)
            return prior

    url = BASE_URL + str(download_id)
    result = common.http_get(url, headers={"Accept": "application/octet-stream"})
    fetched_at = common.now_iso()
    base = {
        "id": download_id,
        "url": url,
        "instrument": spec["instrument"],
        "role": spec["role"],
        "superseded": spec["superseded"],
        "fetched_at": fetched_at,
        "http_status": result.status,
    }

    if result.status != 200:
        LOG.error("id=%s FETCH FAILED status=%s error=%s", download_id, result.status, result.error)
        return {**base, "filename": None, "bytes": 0, "sha256": None, "rel_path": None,
                "error": result.error or f"HTTP {result.status}"}

    filename = common.parse_content_disposition_filename(
        result.headers.get("Content-Disposition")
    ) or f"{download_id}.pdf"

    # Verify the declared role BEFORE writing: a renumbered download must never
    # land in the vault wearing the name of the annex it is not.
    mismatch = role_mismatch(spec, filename)
    if mismatch:
        LOG.error("id=%s ROLE MISMATCH %s", download_id, mismatch)
        return {**base, "filename": filename, "bytes": len(result.body),
                "sha256": common.sha256_bytes(result.body), "rel_path": None, "error": mismatch}

    content_length = result.headers.get("Content-Length")
    if content_length is not None and str(content_length).isdigit() and int(content_length) != len(result.body):
        LOG.error("id=%s SIZE MISMATCH content-length=%s downloaded=%s",
                  download_id, content_length, len(result.body))
        return {**base, "filename": filename, "bytes": len(result.body),
                "sha256": common.sha256_bytes(result.body), "rel_path": None,
                "error": f"size mismatch: content-length={content_length} downloaded={len(result.body)}"}

    target = target_path(vault_root, download_id, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.body)
    rec = {**base, "filename": filename, "bytes": len(result.body),
           "sha256": common.sha256_bytes(result.body),
           "rel_path": target.relative_to(vault_root).as_posix()}
    LOG.info("id=%s OK role=%s bytes=%s sha256=%s -> %s",
             download_id, spec["role"], rec["bytes"], rec["sha256"][:12], rec["rel_path"])
    time.sleep(sleep_s)  # polite: 1 request at a time
    return rec


def run(vault_root: Path, downloads: tuple[dict, ...] = DOWNLOADS, *, sleep_s: float = 2.0) -> int:
    latest = load_latest_by_id(vault_root)
    log_path = fetch_log_path(vault_root)
    failures: list[int] = []

    for spec in downloads:
        prior = latest.get(spec["id"])
        rec = fetch_one(vault_root, spec, prior, sleep_s=sleep_s)
        if rec is not prior:
            common.append_jsonl(log_path, rec)
        if rec.get("error") or rec.get("http_status") != 200:
            failures.append(spec["id"])

    if failures:
        LOG.error("SWEEP COMPLETE with %s of %s failures: %s", len(failures), len(downloads), failures)
        return 1
    LOG.info("SWEEP COMPLETE %s of %s ok", len(downloads), len(downloads))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument("--sleep-s", type=float, default=2.0, help="polite delay between requests")
    args = ap.parse_args(argv)
    return run(args.vault_root.expanduser(), sleep_s=args.sleep_s)


if __name__ == "__main__":
    sys.exit(main())
