#!/usr/bin/env python3
"""One-shot: 47221's `pma_kondisi` was copy-paste residue from its neighbour.

WHAT WAS WRONG
--------------
47221 (Perdagangan Eceran Minuman Beralkohol — alcoholic beverage retail)
carried `pma_kondisi: "Kemitraan dengan UMKM/Koperasi"`, the UMKM/Koperosi
partnership-duty phrasing that belongs to its neighbour 47222 (non-alcoholic
beverage retail, genuinely allocated under Perpres 49/2021 Lampiran II p.13,
dialokasikan column).

Audited against 47221's OWN row in `data/kbli-filiera/perpres-umkm-reservation.json`
(item 4 of the 2026-08-08 sector-law brief): **47221 has zero rows there** —
grepped across every entry in the file for "47221", none found. Its own
`pma_official_basis` names a completely different instrument: Perpres
10/2021 Lampiran III (Bidang Usaha dengan Persyaratan Tertentu), line 4202
entry #44, persyaratan = "Jaringan distribusi dan tempatnya khusus" (special
distribution-network/location requirement) — Open-with-conditions per Pasal
3 huruf c, not a partnership duty and not a UMKM/Koperasi reservation at all.

The kondisi text is corrected to describe the condition the record's own
official_basis actually names, so the field stops contradicting its own
citation.

HARDENING (item 6, 2026-08-08 ledger; item J resume-noop hardening added
2026-08-08): uses `_hardened_cure_io` — old_sha256 pin, atomic write,
untouched_fields enforced (only `pma_kondisi` may move; every other field on
47221, and every other record, must be byte-identical). Resume goes through
`H.judge_patch()`, not a per-key value guess: 47221 is ALSO touched by this
fix-pack's `cure_canonical_sector_law_prosepack.py` (a different field,
`intel_2026.whatChanged`), so a check that only reads `pma_kondisi` would
call the record "already cured" without ever noticing that unrelated drift.
`new_sha256` is backfilled by `scripts/kbli_filiera/backfill_new_sha256.py`
after every cure touching this record has landed.

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
    Path(__file__).resolve().parent / "cure_specs" / "canonical_47221_kondisi_2026_08_08.json"
)
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
CODE_FIELD = "kode_kbli_2025"

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError


def plan(spec: dict, records: list[dict]) -> dict:
    """Pure. {"action": "patch"|"noop", "patch": {...}} or raises CureError.
    Resume classification is H.judge_patch (item J hardening — module
    docstring)."""
    code = spec["code"]
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    rec = by_code.get(code)
    if rec is None:
        raise CureError(f"{code}: not in canonical — nothing to cure")

    action = H.judge_patch(rec, spec["old_sha256"], spec.get("new_sha256"), code=code)
    if action == "noop":
        return {"action": "noop", "reason": "already cured"}

    for key, want in spec.get("expect", {}).items():
        if rec.get(key) != want:
            raise CureError(
                f"{code}: expect[{key}]={want!r} but hash matched old_sha256 "
                "— internal inconsistency, refusing"
            )
    return {"action": "patch", "patch": spec["patch"]}


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

    print(f"{code}: pma_kondisi -> {verdict['patch']['pma_kondisi']!r}")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    before_records = copy.deepcopy(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    for key, value in verdict["patch"].items():
        by_code[code][key] = value

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
    wrong = [k for k, v in verdict["patch"].items() if fresh[code].get(k) != v]
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
