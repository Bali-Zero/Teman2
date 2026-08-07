#!/usr/bin/env python3
"""One-shot: canonical's own `intel_2026.whatChanged` for 90200 contradicted
canonical's own `bps_2020_ancestors` field on the SAME record.

WHAT WAS WRONG
--------------
`cure_gold_90200_whatchanged.py` (2026-08-07, #3749) corrected GOLD's
whatChanged for 90200 (Aktivitas Seni Pertunjukan) from "a completely new
code ... no equivalent in KBLI 2020" to "Merged in KBLI 2025 from four KBLI
2020 codes (90011, 90021, 90022, 90024 ...)" — the correct account, and it
matches canonical's own `bps_2020_ancestors.codes` field, which already
listed those same four predecessors. But that cure ONLY ever wrote gold
(`apps/mouth/data/kbli-gold-all.json`); canonical's `intel_2026.whatChanged`
was never touched and kept claiming "completely new ... no equivalent in
2020" — directly contradicted by canonical's own sibling field on the same
record. Gold wins at render, so the client-facing page has been correct
since #3749; this closes the SILENT self-contradiction inside canonical
itself, which is what any future reader of canonical (a report, a second
cure, a KG ingestion) would have inherited.

HARDENING (item 6, 2026-08-08 ledger): uses `_hardened_cure_io` — old_sha256
pin, atomic write, untouched_fields enforced (only `intel_2026.whatChanged`
may move; every other field on 90200, and every other record, is asserted
byte-identical before/after).

Dry-run is the default; nothing is written without --apply.
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import _hardened_cure_io as H  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = (
    Path(__file__).resolve().parent
    / "cure_specs"
    / "canonical_90200_whatchanged_2026_08_08.json"
)
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
CODE_FIELD = "kode_kbli_2025"

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError


def plan(spec: dict, records: list[dict]) -> dict:
    """Pure. {"action": "patch"|"noop", "patch": {...}} or raises CureError."""
    code = spec["code"]
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    rec = by_code.get(code)
    if rec is None:
        raise CureError(f"{code}: not in canonical — nothing to cure")

    patch = spec["patch"]
    already_patched = True
    for path, want in patch.items():
        if not H.has_field(rec, path) or H.read_field(rec, path) != want:
            already_patched = False
            break
    current_hash = H.sha256_of(rec)

    if current_hash == spec["old_sha256"]:
        if already_patched:
            raise CureError(
                f"{code}: hash matches the pre-image but already carries every "
                "patched value — spec authored against a no-op, re-check"
            )
        for path, want in spec.get("expect", {}).items():
            if not H.has_field(rec, path):
                raise CureError(f"{code}: expect[{path}] missing entirely — refusing")
            if H.read_field(rec, path) != want:
                raise CureError(
                    f"{code}: expect[{path}]={want!r} but hash matched — internal "
                    "inconsistency, refusing"
                )
        return {"action": "patch", "patch": patch}

    if already_patched:
        return {"action": "noop", "reason": "already cured"}

    raise CureError(
        f"{code}: live record hashes to {current_hash!r}, matching neither the "
        f"pinned old_sha256 {spec['old_sha256']!r} nor the already-patched state "
        "— the record drifted under this adjudication; re-derive before writing"
    )


def verify_fleet(repair: bool) -> tuple[list[str], int]:
    problems: list[str] = []
    repaired = 0

    check = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check"], capture_output=True, text=True
    )
    if check.returncode != 0:
        if not repair:
            problems.append(
                "consumer copies drifted from canonical (dry-run — rerun with "
                f"--apply to repair):\n{check.stdout.strip()[-800:]}"
            )
            return problems, repaired
        result = subprocess.run(
            ["bash", str(SYNC_SCRIPT), "sync"], capture_output=True, text=True
        )
        if result.returncode != 0:
            problems.append(
                f"sync_kbli_dataset.sh exited {result.returncode}: {result.stderr[-400:]}"
            )
            return problems, repaired
        repaired = result.stdout.count("synced:")
        recheck = subprocess.run(
            ["bash", str(SYNC_SCRIPT), "--check"], capture_output=True, text=True
        )
        if recheck.returncode != 0:
            problems.append(f"consumer copies still differ after repair: {recheck.stdout[-400:]}")
            return problems, repaired

    if not SIDECAR_DATASET.exists():
        problems.append(f"sidecar dataset copy missing: {SIDECAR_DATASET}")
        return problems, repaired

    import hashlib

    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_VERSION.read_text(encoding="utf-8"))
    if sidecar.get("datasetSha256") == digest:
        return problems, repaired

    if not repair:
        problems.append(
            f"version sidecar stale ({sidecar.get('datasetSha256')!r} != {digest!r}) "
            "— dry-run, rerun with --apply to repair"
        )
        return problems, repaired

    sidecar["datasetSha256"] = digest
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_VERSION.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    repaired += 1
    print(f"  sidecar version -> {digest}")
    return problems, repaired


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    ap.add_argument("--spec", default=str(SPEC_PATH))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    path = Path(args.dataset)
    code = spec["code"]

    try:
        payload, records, original = H.load_dataset(path)
        verdict = plan(spec, records)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    if verdict["action"] == "noop":
        print(f"{code}: already cured — no-op")
        if path.resolve() != CANONICAL.resolve():
            return EXIT_OK
        problems, repaired = verify_fleet(repair=args.apply)
        for p in problems:
            print(f"  FLEET PROBLEM: {p}")
        if problems:
            return EXIT_REFUSED
        if repaired:
            print(f"repaired {repaired} stale fleet artifact(s)")
        return EXIT_OK

    for path_key, val in verdict["patch"].items():
        print(f"{code}: {path_key} -> {val!r}")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    before_records = copy.deepcopy(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    for path_key, value in verdict["patch"].items():
        H.write_field(by_code[code], path_key, value)

    try:
        H.verify_untouched(
            before_records,
            records,
            CODE_FIELD,
            touched_codes={code},
            touched_field_paths={code: set(verdict["patch"])},
        )
    except CureError as exc:
        print(f"REFUSED (untouched_fields): {exc}")
        return EXIT_REFUSED

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(path, body + ("\n" if original.endswith("\n") else ""))

    _, again, _ = H.load_dataset(path)
    fresh = {str(r.get(CODE_FIELD)): r for r in again}
    wrong = [
        p for p, v in verdict["patch"].items() if H.read_field(fresh[code], p) != v
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED
    print("\napplied and verified on re-read")

    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK

    problems, repaired = verify_fleet(repair=True)
    for p in problems:
        print(f"  FLEET PROBLEM: {p}")
    if problems:
        return EXIT_REFUSED
    if repaired:
        print(f"repaired {repaired} stale fleet artifact(s)")
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
