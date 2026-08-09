#!/usr/bin/env python3
"""One-shot: the asuransi/reasuransi family is a SECTOR-LAW cap the Perpres
never governed — canonical carried the Perpres residual-open default instead.

WHAT WAS WRONG
--------------
`65111`/`65112`/`65121`/`65122`/`65201`/`65202` (Asuransi Jiwa, Asuransi
Umum, Reasuransi — Konvensional + Syariah) all carried `pma_status: TERBUKA`,
`pma_max_asing: 100`, `pma_source: "Perpres 10/2021, 49/2021"` — the blanket
residual-open attribution every un-adjudicated code in this catalogue
carries. But insurance/reinsurance is a `Perusahaan Perasuransian` under
UU 40/2014, and **Perpres 10/2021 Pasal 11 ayat (2) carves the financial and
banking bidang usaha OUT to sector law**: "Perizinan berusaha dan
pelaksanaan kegiatan dalam rangka Penanaman Modal untuk Bidang Usaha
keuangan dan Bidang Usaha perbankan dilaksanakan sesuai dengan ketentuan
peraturan perundang-undangan di bidangnya masing-masing." The Perpres
annexes and its residual-open default (Pasal 3(1)(d)) never applied here —
the 100%-open figure was never a verdict on this sector at all.

The sector law is `PP 14/2018 tentang Kepemilikan Asing pada Perusahaan
Perasuransian`, Pasal 5 ayat (1): "Kepemilikan Asing pada Perusahaan
Perasuransian dilarang melebihi 80% (delapan puluh persen) dari modal
disetor Perusahaan Perasuransian" — an 80% cap, general (not
acquisition-only), with listed insurers (perseroan terbuka) exempt (Pasal 5
ayat 2) and pre-2018 foreign holdings above 80% grandfathered without
increase (Pasal 6, as amended by PP 3/2020 — the amendment restructured the
grandfather mechanics but the 80%-cap-and-grandfather shape survives).

WHY REASURANSI IS CERTAIN, NOT CONDITIONAL
-------------------------------------------
UU 40/2014 Pasal 1 angka 14 defines `Perusahaan Perasuransian` as
"perusahaan asuransi, perusahaan asuransi syariah, PERUSAHAAN REASURANSI,
PERUSAHAAN REASURANSI SYARIAH, perusahaan pialang asuransi, perusahaan
pialang reasuransi, dan perusahaan penilai kerugian asuransi" — reasuransi
companies are named BY NUMBER in the definition, not inferred. Primary
sources for both instruments are pinned verbatim in the spec.

WHAT THIS EXCLUDES, AND WHY (all named in the spec's `excluded` block)
------------------------------------------------------------------------
`65123` (Penjaminan Simpanan) is LPS, a statutory deposit-insurance body
under UU 24/2004 — absent from the Pasal 1 angka 14 list. `65131`/`65132`/
`65203`/`65204` (the Penjaminan/guarantee family) are regulated under UU
1/2016, a DIFFERENT sector law — also absent from that same list, so PP
14/2018 does not reach them; their cap is not primary-verified here. The
`66xxx` broker/agent codes are intermediaries under a separate UU 40/2014
chapter (Pasal 1 angka 11-12), never mapped to a specific PP 14/2018
provision — left to the Task-#10 financial-family lane.

HARDENING (item 6, 2026-08-08 ledger; item J resume-noop hardening added
2026-08-08)
--------------------------------------------------------------------------
Uses `_hardened_cure_io`: each code's spec entry pins `old_sha256` — the
sha256 of the WHOLE record as observed when this cure was authored — so a
record that drifted under it (re-adjudicated elsewhere, hand-edited) is
refused rather than silently overwritten. The write is atomic (tmp+rename).
`verify_untouched()` asserts, after patching in memory and BEFORE writing to
disk, that no field outside each code's declared `patch` keys moved, and
that none of the other 1,553 records changed at all.

Resume classification goes through `H.judge_patch()`, not the earlier
per-key `already_patched = all(rec.get(k) == v for k, v in patch.items())`
guess: that guess only reads the keys the PATCH names, so a record whose
patched fields already carry the target values but whose UNRELATED fields
have since moved (this fix-pack's own `cure_canonical_sector_law_prosepack.py`
touches these same six records' `editorial.byTheNumbers`/`zantaraOpener`/
`body` fields) would still read as "already cured" with the drift never
reported. `judge_patch` requires the live record to hash to the pinned
`old_sha256` (apply) or the pinned `new_sha256` (noop) — nothing in between.
`new_sha256` is backfilled by `scripts/kbli_filiera/backfill_new_sha256.py`
after every cure touching the same record has landed, never by this
compiler itself (see that script's docstring for why the ordering matters).

REFUSES, LOUDLY
----------------
Aborts before writing anything if: a code is missing from canonical; its
`expect` block (status/cap) no longer matches the live record; its live hash
matches neither `old_sha256` nor the pinned `new_sha256` (i.e. the world
moved under a THIRD state); or the untouched-fields fingerprint fails.
Already-patched (hash matches the pinned `new_sha256`) is success, not
failure — idempotent, not a re-adjudication.

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
    / "canonical_asuransi_pp14_cap_2026_08_08.json"
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
    H.judge_patch (item J hardening — see the module docstring)."""
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    verdicts: dict[str, dict] = {}
    for code, entry in spec["codes"].items():
        rec = by_code.get(code)
        if rec is None:
            raise CureError(f"{code}: not in canonical — nothing to cure")

        action = H.judge_patch(rec, entry["old_sha256"], entry.get("new_sha256"), code=code)
        if action == "noop":
            verdicts[code] = {"action": "noop", "reason": "already cured"}
            continue

        for key, want in entry.get("expect", {}).items():
            if rec.get(key) != want:
                raise CureError(
                    f"{code}: expect[{key}]={want!r} but hash matched old_sha256 "
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
        print(f"  {code}: TERBUKA/100 -> TERBATAS/80 (PP 14/2018 Pasal 5(1))")
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
        for key, value in v["patch"].items():
            by_code[code][key] = value

    try:
        H.verify_untouched(
            before_records,
            records,
            CODE_FIELD,
            touched_codes=set(to_patch),
            touched_field_paths={code: set(v["patch"]) for code, v in to_patch.items()},
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
        code
        for code, v in to_patch.items()
        if any(fresh[code].get(k) != val for k, val in v["patch"].items())
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
