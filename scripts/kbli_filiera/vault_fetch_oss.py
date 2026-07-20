#!/usr/bin/env python3
"""vault_fetch_oss.py — Batch-0 vault compiler: full OSS RBA re-snapshot.

For every 5-digit KBLI-2025 code in the code->uuid ground-truth map
(data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json, 1,559 codes),
fetches detail + ruang-lingkup + relasi + umku from gw.oss.go.id and writes
each into <vault-root>/oss/<code>/{detail,ruang_lingkup,relasi,umku}.json
(raw response bytes — this IS the L0 raw-evidence vault, never reformatted).

A 404 on ruang-lingkup/relasi/umku is a LEGIT no-scope signal (P3,
research/operations/2026-07-16-kbli-filiera-methodology.md) — recorded in
<vault-root>/oss/absences.jsonl as {"status": 404, "recorded_as": "absent",
...}, NEVER as an empty file pretending to be data. `vault_common.http_get`
already refuses to retry a 404 (no retry-storm on a single probe); this
compiler does not itself cache/skip a previously-recorded absence across
runs — corroboration-over-time (>=3 attempts over >=72h, the methodology's
D0 discipline) is a later compiler's job, not batch-0's "full re-snapshot".

Auth: OSS_RBA_USER_KEY env var (static public app credential — never
hardcoded, fail-visible if unset). TRAP: urllib honors the system proxy by
default; vault_common.http_get already bypasses it (ProxyHandler({})).

Idempotent resume (data records only — see docstring above re: absences):
an already-recorded 200 is verified on disk before being skipped.

Usage:
    OSS_RBA_USER_KEY=... python scripts/kbli_filiera/vault_fetch_oss.py \\
        [--vault-root PATH] [--ground-truth PATH] [--only 47111,68112]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

BASE = "https://gw.oss.go.id/v2/portal/kbli/"
# Path segments appended to BASE before the uuid, per kbli-navigator SKILL.md §3.
ENDPOINT_PREFIX = {
    "detail": "",
    "ruang_lingkup": "ruang-lingkup/",
    "relasi": "relasi/",
    "umku": "umku/",
}
RATE_S = 1.0 / 3.0  # ~3 req/s max
PROGRESS_EVERY = 50

USER_KEY = os.environ.get("OSS_RBA_USER_KEY", "")
LOG = common.setup_logger("vault_fetch_oss")


def endpoint_url(endpoint: str, uuid: str) -> str:
    return f"{BASE}{ENDPOINT_PREFIX[endpoint]}{uuid}"


def load_code_uuid_map(ground_truth_path: Path) -> list[tuple[str, str]]:
    data = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    return [(str(x["kode"]), x["uuid"]) for x in data["data"] if x.get("digits") == 5]


def build_absence_record(code: str, endpoint: str, url: str, uuid: str, status: int, fetched_at: str) -> dict:
    """The exact recorded shape for a corroborated-by-a-single-probe
    absence — {"status": 404, "recorded_as": "absent", ...} — pure, no I/O,
    directly unit-testable."""
    return {
        "code": code,
        "endpoint": endpoint,
        "url": url,
        "uuid": uuid,
        "status": status,
        "recorded_as": "absent",
        "fetched_at": fetched_at,
    }


def data_path(vault_root: Path, code: str, endpoint: str) -> Path:
    return vault_root / "oss" / code / f"{endpoint}.json"


def fetch_log_path(vault_root: Path) -> Path:
    return vault_root / "oss" / "fetch-log.jsonl"


def absences_path(vault_root: Path) -> Path:
    return vault_root / "oss" / "absences.jsonl"


def load_latest(vault_root: Path) -> dict[tuple[str, str], dict]:
    latest: dict[tuple[str, str], dict] = {}
    for rec in common.read_jsonl(fetch_log_path(vault_root)):
        key = (rec.get("code"), rec.get("endpoint"))
        latest[key] = rec
    return latest


def fetch_endpoint(vault_root: Path, code: str, uuid: str, endpoint: str, prior: dict | None) -> dict | None:
    """Returns {"_kind": "data"|"absence", ...record} to be appended to the
    matching log, or None on a verified-on-disk skip (no log growth)."""
    target = data_path(vault_root, code, endpoint)

    if prior is not None and common.decide_resume(prior, target) == "skip":
        return None

    url = endpoint_url(endpoint, uuid)
    result = common.http_get(url, headers={"user_key": USER_KEY, "accept": "application/json"})
    fetched_at = common.now_iso()

    if result.status == 404:
        LOG.info("code=%s endpoint=%s ABSENT (404)", code, endpoint)
        return {"_kind": "absence", **build_absence_record(code, endpoint, url, uuid, 404, fetched_at)}

    if result.status != 200:
        LOG.error("code=%s endpoint=%s FETCH FAILED status=%s error=%s", code, endpoint, result.status, result.error)
        return {
            "_kind": "data",
            "code": code,
            "endpoint": endpoint,
            "url": url,
            "uuid": uuid,
            "bytes": 0,
            "sha256": None,
            "fetched_at": fetched_at,
            "http_status": result.status,
            "rel_path": None,
            "error": result.error or f"HTTP {result.status}",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.body)
    return {
        "_kind": "data",
        "code": code,
        "endpoint": endpoint,
        "url": url,
        "uuid": uuid,
        "bytes": len(result.body),
        "sha256": common.sha256_bytes(result.body),
        "fetched_at": fetched_at,
        "http_status": 200,
        "rel_path": target.relative_to(vault_root).as_posix(),
    }


def run(vault_root: Path, ground_truth_path: Path, *, only: set[str] | None = None, rate_s: float = RATE_S) -> int:
    codes = load_code_uuid_map(ground_truth_path)
    if only:
        codes = [(c, u) for c, u in codes if c in only]
    latest = load_latest(vault_root)
    log_path = fetch_log_path(vault_root)
    abs_path = absences_path(vault_root)

    total = len(codes)
    failures = 0
    for i, (code, uuid) in enumerate(codes, start=1):
        for endpoint in ENDPOINT_PREFIX:
            prior = latest.get((code, endpoint))
            rec = fetch_endpoint(vault_root, code, uuid, endpoint, prior)
            if rec is None:
                continue
            kind = rec.pop("_kind")
            if kind == "absence":
                common.append_jsonl(abs_path, rec)
            else:
                common.append_jsonl(log_path, rec)
                if rec.get("http_status") == 200:
                    latest[(code, endpoint)] = rec
                else:
                    failures += 1
            time.sleep(rate_s)
        if i % PROGRESS_EVERY == 0 or i == total:
            LOG.info("%s of %s codes processed (failures=%s)", i, total, failures)

    if failures:
        LOG.error("SWEEP COMPLETE with %s endpoint failures across %s codes", failures, total)
        return 1
    LOG.info("SWEEP COMPLETE %s codes ok", total)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=common.DEFAULT_VAULT_ROOT)
    ap.add_argument(
        "--ground-truth", type=Path,
        default=Path("data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"),
    )
    ap.add_argument("--only", type=str, default="", help="comma-separated 5-digit codes for a partial run")
    args = ap.parse_args(argv)

    if not USER_KEY:
        LOG.error("OSS_RBA_USER_KEY not set — see kbli-navigator SKILL.md §3 (public app credential)")
        return 2
    if not args.ground_truth.exists():
        LOG.error("ground-truth map not found: %s (pass --ground-truth explicitly)", args.ground_truth)
        return 2

    only = {c.strip() for c in args.only.split(",") if c.strip()} or None
    return run(args.vault_root.expanduser(), args.ground_truth, only=only)


if __name__ == "__main__":
    sys.exit(main())
