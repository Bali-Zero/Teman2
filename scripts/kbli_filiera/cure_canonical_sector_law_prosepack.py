#!/usr/bin/env python3
"""One-shot: re-derive canonical editorial prose that still asserts the
PRE-adjudication figures on nine codes whose pma_status/pma_max_asing were
already corrected earlier in this PR.

WHAT WAS WRONG
--------------
This PR flipped six insurance codes to TERBATAS/80, cured 41011's gold PMA
line, and fixed 47221's pma_kondisi and 90200's canonical whatChanged — but
each of those cures touched only the RECORD FIELD it was named for. Sibling
prose fields on the SAME records kept asserting the OLD regime, verbatim:

  * `41011` — `l4_bali.reason`, five `intel_2026`/`editorial` fields, and
    `whoThisIsFor` all still said "max 67% WNA + partner locale" — a figure
    the adjudication itself withdrew (canonical stays TERBUKA/100; the real
    constraint is a segment reservation, not a whole-code cap).
  * `47221` — `intel_2026.whatChanged` still said "TERBATAS PMA restriction
    with 49% cap"; the record's own `pma_max_asing` is `"special"` (a
    distribution-network condition, not a percentage — Perpres 10/2021
    Lampiran III line 4202 #44).
  * `90200` — `intel_2026.zantaraOpener` still called the code "brand-new,"
    contradicting the record's own (already-cured) `whatChanged`, which
    correctly says it merged from four KBLI 2020 codes.
  * The six asuransi codes — `editorial.byTheNumbers[2]` (labelled "PMA
    source" or "National source") still read "Perpres 10/2021, 49/2021", the
    PRE-cure attribution, even though the record's own top-level
    `pma_source` field was corrected to the PP 14/2018 / Pasal 11(2)
    sector-law basis. Four `zantaraOpener` fields still opened with
    "Nationally this carries PMA status: Open." on a record now TERBATAS/80.
    Five of the six `editorial.body` fields carried an unqualified "the
    Perpres's annexes never governed this activity" claim (W113 — plausible,
    unverified as an absolute) instead of the narrower, verifiable claim the
    same paragraph is already built to support: Pasal 11(2) ROUTES
    financial/banking licensing to sector law, so the residual-open default
    cannot ground an ownership verdict here. Claims that the annexes never
    NAME these codes are a different, separately-true statement and are left
    untouched wherever the prose makes that narrower claim (65122).

EVERY REPLACEMENT IS DERIVED FROM THE RECORD'S OWN ALREADY-CURED FIELDS
-------------------------------------------------------------------------
No new fact is asserted here. `41011`'s replacement text mirrors the gold PMA
sentence this same PR already shipped for the same code
(`cure_gold_pma_line.py::AUTHORED_SENTENCES["41011"]`) and cites the same
locator (`data/kbli-filiera/perpres-umkm-reservation.json`, row `41011`,
`dialokasikan`, page 6, "madya: gedung tempat tinggal ..."). `47221`'s
replacement mirrors the record's own `pma_kondisi`/`pma_official_basis`
(distribution-network condition, no percentage). `90200`'s replacement
mirrors the record's own `bps_2020_ancestors.codes`. Every asuransi
`byTheNumbers` replacement is copied verbatim from the record's own
`pma_source` field. Every `zantaraOpener` replacement states only the
record's own `pma_status`/`pma_max_asing`. Every body softening keeps the
instrument citation (Pasal 11(2)) and drops only the absolute "never
governed"/"never actually governed/supplied" clause.

HARDENING (item 6 of the 2026-08-08 brief, item J of the DO-NOT-SHIP
fix-pack)
----------------------------------------------------------------------
Uses `_hardened_cure_io`: dotted+indexed paths (`H.read_field`/`write_field`
now support `editorial.byTheNumbers[2].value`), atomic write, and
`verify_untouched()` — built from `H.diff_leaf_for_patch_path()` so a
list-cell edit is declared at the leaf the untouched-fields diff can actually
see. Resume classification goes through `H.judge_patch()`: a live record
hashes to either the pinned `old_sha256` (apply the patch) or the pinned
`new_sha256` (already applied, noop) — never a per-key "already carries the
target values" guess, which is blind to drift on fields the patch never
named. `new_sha256` is backfilled after this compiler's own first
application (see `scripts/kbli_filiera/backfill_new_sha256.py` — a repo-wide
tool, not specific to this spec).

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
    / "canonical_sector_law_prosepack_2026_08_08.json"
)
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
CODE_FIELD = "kode_kbli_2025"

EXIT_OK = 0
EXIT_REFUSED = 2

CureError = H.CureError


def plan(spec: dict, records: list[dict]) -> dict[str, dict]:
    """Pure. {code: {"action": "patch"|"noop", "patch": {...}}} or raises
    CureError. Every code named in the spec is judged independently, via
    H.judge_patch (item J hardening — see module docstring)."""
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    verdicts: dict[str, dict] = {}
    for code, entry in spec["codes"].items():
        rec = by_code.get(code)
        if rec is None:
            raise CureError(f"{code}: not in canonical — nothing to cure")

        action = H.judge_patch(
            rec, entry["old_sha256"], entry.get("new_sha256"), code=code
        )
        if action == "noop":
            verdicts[code] = {"action": "noop", "reason": "already cured"}
            continue

        for path, want in spec["codes"][code].get("expect", {}).items():
            if not H.has_field(rec, path):
                raise CureError(f"{code}: expect[{path}] missing entirely — refusing")
            if H.read_field(rec, path) != want:
                raise CureError(
                    f"{code}: expect[{path}]={want!r} but hash matched old_sha256 "
                    "— internal inconsistency, refusing"
                )
        verdicts[code] = {"action": "patch", "patch": entry["patch"]}
    return verdicts


def verify_fleet(repair: bool) -> tuple[list[str], int]:
    """Same shape as every other canonical cure's fleet-sync step."""
    problems: list[str] = []
    repaired = 0

    check = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check"], capture_output=True, text=True
    )
    if check.returncode != 0:
        if not repair:
            problems.append(
                "consumer copies drifted from canonical (dry-run — rerun "
                f"with --apply to repair):\n{check.stdout.strip()[-800:]}"
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
            f"version sidecar stale ({sidecar.get('datasetSha256')!r} != "
            f"{digest!r}) — dry-run, rerun with --apply to repair"
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

    try:
        payload, records, original = H.load_dataset(path)
        verdicts = plan(spec, records)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    to_patch = {c: v for c, v in verdicts.items() if v["action"] == "patch"}
    noop = [c for c, v in verdicts.items() if v["action"] == "noop"]
    print(f"{len(to_patch)} code(s) to patch, {len(noop)} already cured")
    for code in sorted(to_patch):
        print(f"  {code}: {sorted(to_patch[code]['patch'])}")
    for code in noop:
        print(f"  {code}: already cured — no-op")

    if not to_patch:
        print("nothing to patch on canonical")
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

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    before_records = copy.deepcopy(records)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    for code, v in to_patch.items():
        for field_path, value in v["patch"].items():
            H.write_field(by_code[code], field_path, value)

    try:
        H.verify_untouched(
            before_records,
            records,
            CODE_FIELD,
            touched_codes=set(to_patch),
            touched_field_paths={
                code: {H.diff_leaf_for_patch_path(p) for p in v["patch"]}
                for code, v in to_patch.items()
            },
        )
    except CureError as exc:
        print(f"REFUSED (untouched_fields): {exc}")
        return EXIT_REFUSED

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(path, body + ("\n" if original.endswith("\n") else ""))

    # Read back and prove the write, rather than trusting that it happened.
    _, again, _ = H.load_dataset(path)
    fresh = {str(r.get(CODE_FIELD)): r for r in again}
    wrong = [
        f"{code}.{p}"
        for code, v in to_patch.items()
        for p, val in v["patch"].items()
        if H.read_field(fresh[code], p) != val
    ]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {len(to_patch)} code(s)")

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
