#!/usr/bin/env python3
"""vault_fetch_pp28.py — Batch-0 vault compiler: PP 28/2025 lampiran corpus.

Downloads all 21 BPK-hosted lampiran PDFs (peraturan.bpk.go.id/Download/<id>,
ids 394930..394950 — all HTTP 200, content-type application/octet-stream,
real filename in Content-Disposition; live-probed 2026-07-16) into
<vault-root>/pp28/<id>__<filename>.

GROUNDED FACT (2026-07-16): one lampiran LETTER can span MULTIPLE
sequential ids — e.g. id 394941 is
"2.6g Lampiran I.F ... (I.F.4501-5248).pdf". This script never assumes
1 id = 1 letter: it structurally parses each downloaded Content-Disposition
filename (vault_common.parse_pp28_lampiran_filename) and records
{fragment, letter, range} alongside every fetch-log entry, so the
id->lampiran map is the fetch-log itself — no separate map file to drift.

Idempotent resume: an id already recorded with http_status==200 is
verified on disk (size + re-hashed sha256, vault_common.decide_resume)
before being skipped — a stale/corrupted local copy is always refetched,
never trusted from the log alone.

Fail-visible (superscar #2, "esiste != armato"): the full 21-id sweep
always runs to completion; only at the end does a non-empty failure list
cause a non-zero exit, so one bad id never hides the rest of the report.

Usage:
    python scripts/kbli_filiera/vault_fetch_pp28.py [--vault-root PATH] [--sleep-s N]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover — allow `python vault_fetch_pp28.py` from this dir
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

BASE_URL = "https://peraturan.bpk.go.id/Download/"
# Verified live 2026-07-16 (kbli-navigator SKILL.md §3): 21 files, all HTTP 200.
LAMPIRAN_IDS: tuple[int, ...] = tuple(range(394930, 394951))

LOG = common.setup_logger("vault_fetch_pp28")


def fetch_log_path(vault_root: Path) -> Path:
    return vault_root / "pp28" / "fetch-log.jsonl"


def load_latest_by_id(vault_root: Path) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for rec in common.read_jsonl(fetch_log_path(vault_root)):
        rid = rec.get("id")
        if rid is not None:
            latest[rid] = rec
    return latest


def target_path(vault_root: Path, lampiran_id: int, filename: str) -> Path:
    safe = common.sanitize_filename(filename)
    return vault_root / "pp28" / f"{lampiran_id}__{safe}"


def fetch_one(vault_root: Path, lampiran_id: int, prior: dict | None, *, sleep_s: float = 2.0) -> dict:
    """Fetch (or verify-and-skip) one lampiran id. Returns the record that
    should be appended to the fetch-log, or the untouched `prior` record
    itself on a verified skip (callers use `is` identity to decide whether
    the log actually needs a new line — see run())."""
    if prior is not None:
        candidate_target = target_path(vault_root, lampiran_id, prior.get("filename") or "")
        if common.decide_resume(prior, candidate_target) == "skip":
            LOG.info("id=%s SKIP (verified on disk) -> %s", lampiran_id, candidate_target.name)
            return prior

    url = BASE_URL + str(lampiran_id)
    result = common.http_get(url, headers={"Accept": "application/octet-stream"})
    fetched_at = common.now_iso()

    if result.status != 200:
        LOG.error("id=%s FETCH FAILED status=%s error=%s", lampiran_id, result.status, result.error)
        return {
            "id": lampiran_id,
            "url": url,
            "filename": None,
            "bytes": 0,
            "sha256": None,
            "fetched_at": fetched_at,
            "http_status": result.status,
            "rel_path": None,
            "error": result.error or f"HTTP {result.status}",
        }

    filename = common.parse_content_disposition_filename(
        result.headers.get("Content-Disposition")
    ) or f"{lampiran_id}.pdf"
    target = target_path(vault_root, lampiran_id, filename)

    content_length = result.headers.get("Content-Length")
    if content_length is not None and str(content_length).isdigit() and int(content_length) != len(result.body):
        LOG.error(
            "id=%s SIZE MISMATCH content-length=%s downloaded=%s",
            lampiran_id, content_length, len(result.body),
        )
        return {
            "id": lampiran_id,
            "url": url,
            "filename": filename,
            "bytes": len(result.body),
            "sha256": common.sha256_bytes(result.body),
            "fetched_at": fetched_at,
            "http_status": result.status,
            "rel_path": None,
            "error": f"size mismatch: content-length={content_length} downloaded={len(result.body)}",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.body)
    rec = {
        "id": lampiran_id,
        "url": url,
        "filename": filename,
        "bytes": len(result.body),
        "sha256": common.sha256_bytes(result.body),
        "fetched_at": fetched_at,
        "http_status": result.status,
        "rel_path": target.relative_to(vault_root).as_posix(),
        **common.parse_pp28_lampiran_filename(filename),
    }
    LOG.info("id=%s OK bytes=%s sha256=%s -> %s", lampiran_id, rec["bytes"], rec["sha256"][:12], rec["rel_path"])
    time.sleep(sleep_s)  # polite: 1 request at a time
    return rec


def run(vault_root: Path, ids: tuple[int, ...] = LAMPIRAN_IDS, *, sleep_s: float = 2.0) -> int:
    latest = load_latest_by_id(vault_root)
    log_path = fetch_log_path(vault_root)
    failures: list[int] = []

    for lampiran_id in ids:
        prior = latest.get(lampiran_id)
        rec = fetch_one(vault_root, lampiran_id, prior, sleep_s=sleep_s)
        if rec is not prior:
            common.append_jsonl(log_path, rec)
        if rec.get("error") or rec.get("http_status") != 200:
            failures.append(lampiran_id)

    if failures:
        LOG.error("SWEEP COMPLETE with %s of %s failures: %s", len(failures), len(ids), failures)
        return 1
    LOG.info("SWEEP COMPLETE %s of %s ok", len(ids), len(ids))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument("--sleep-s", type=float, default=2.0, help="polite delay between requests")
    args = ap.parse_args(argv)
    return run(args.vault_root.expanduser(), sleep_s=args.sleep_s)


if __name__ == "__main__":
    sys.exit(main())
