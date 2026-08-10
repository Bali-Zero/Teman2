#!/usr/bin/env python3
"""One-shot (cure G): 47222's pma_nota/pma_kondisi contradict their own
pma_official_basis — copy-paste residue from a neighbouring annex row.

WHAT WAS WRONG
--------------
Canonical `47222` (Perdagangan Eceran Minuman Tidak Beralkohol — non-alcoholic
retail) carried:

* `pma_nota`: "Perdagangan eceran minuman beralkohol di bar" — the ALCOHOL-in-
  bar activity title. That is `47221`'s subject (Perdagangan Eceran Minuman
  Beralkohol), not 47222's — copy-paste residue from the neighbouring annex
  row 47222 sits next to in the source table.
* `pma_kondisi`: "Kemitraan dengan UMKM/Koperasi" — a PARTNERSHIP mechanism.
  47222's own `pma_official_basis` states verbatim: "...KEMITRAAN column
  EMPTY = pure reservation for domestic cooperatives/UMKM..." — a pure
  `dialokasikan` allocation has no kemitraan path. The condition string
  contradicts the basis it sits directly beside on the same record.

Both fields feed the WhatsApp/webchat channel's "Catatan PMA" line — verified
live (2026-08-07) serving the alcohol note on the non-alcoholic code.

THE FIX
-------
`pma_nota` -> a note naming the correct mechanism (Koperasi/UMKM allocation,
Lampiran II) instead of a different code's alcohol subject. `pma_kondisi` ->
`null`: the reservation is total; there is no condition under which a PMA
enters, so a condition string is not the right shape for this record at all
— the mechanism already lives in `pma_official_basis`/`pma_nota`. Team-lead
addendum, 2026-08-07 (cure G) — implemented verbatim from
`cure_specs/canonical_47222_nota_kondisi_2026_08_07.json`, this module does
not author prose.

`pma_status`/`pma_max_asing`/`pma_cap_verified`/`pma_official_basis` are all
in `untouched_fields` and never written by this compiler.

REFUSES, LOUDLY, RATHER THAN GUESSING
----------------------------------------
Aborts before writing anything if: the code is missing from canonical; the
spec's `expect` block (status/cap/cap_verified/official_basis substring)
does not match the live record — the premise the whole cure rests on; a
named field's LIVE value does not match the spec's pinned `old` (unless it
already reads as the pinned `new` — idempotent, not a failure).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = (
    Path(__file__).resolve().parent
    / "cure_specs"
    / "canonical_47222_nota_kondisi_2026_08_07.json"
)
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

EXIT_OK = 0
EXIT_REFUSED = 2


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def _has_field(rec: dict, path: str) -> bool:
    """Dotted-path presence check — `pma_nota` (top-level) and
    `intel_2026.whatChanged` (nested) both resolve through the same walk, so
    a spec can name either shape without the compiler special-casing one."""
    cur: object = rec
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def read_field(rec: dict, path: str) -> object:
    cur: object = rec
    for key in path.split("."):
        cur = cur[key]
    return cur


def write_field(rec: dict, path: str, value: object) -> None:
    keys = path.split(".")
    cur = rec
    for key in keys[:-1]:
        cur = cur[key]
    cur[keys[-1]] = value


def load(path: Path) -> tuple[dict, list[dict], str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise CureError(f"{path}: expected a non-empty record list")
    return payload, records, text


def check_expect(rec: dict, code: str, expect: dict) -> None:
    for key in ("pma_status", "pma_max_asing", "pma_cap_verified"):
        if key not in expect:
            continue
        want, got = expect[key], rec.get(key)
        if want != got:
            raise CureError(
                f"{code}: premise moved — expected {key}={want!r}, found "
                f"{got!r}. The card's premise changed — re-adjudicate, do "
                "not apply."
            )
    for key in sorted(k for k in expect if k.endswith("_contains")):
        field = key[: -len("_contains")]
        needle = expect[key]
        if needle and needle not in (rec.get(field) or ""):
            raise CureError(
                f"{code}: `{field}` no longer contains {needle!r} — the cure "
                "quotes that field as its basis; without it the premise no "
                "longer holds."
            )


def plan(spec: dict, records: list[dict]) -> dict:
    """Pure. Returns per-field verdicts or raises CureError on a bad
    precondition."""
    code = spec["code"]
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code.get(code)
    if rec is None:
        raise CureError(f"{code}: not in canonical — nothing to cure")

    check_expect(rec, code, spec["expect"])

    verdicts: dict[str, dict] = {}
    for field, pair in spec["fields"].items():
        if not _has_field(rec, field):
            raise CureError(f"{code}.{field}: the spec names a field this record does not carry")
        live = read_field(rec, field)
        if live == pair["new"]:
            verdicts[field] = {"action": "noop", "reason": "already cured"}
        elif live == pair["old"]:
            verdicts[field] = {"action": "patch", "new": pair["new"]}
        else:
            raise CureError(
                f"{code}.{field}: live value {live!r} matches neither the "
                f"pinned `old` nor the pinned `new` — it moved under the "
                "adjudication, re-derive before writing"
            )
    return verdicts


def verify_fleet(repair: bool) -> tuple[list[str], int]:
    """Check every consumer copy + the version sidecar against canonical,
    and optionally repair what is stale. Same shape as
    cure_canonical_47222_reservation.py::verify_fleet."""
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
            problems.append(f"sync_kbli_dataset.sh exited {result.returncode}: {result.stderr[-400:]}")
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
        payload, records, original = load(path)
        verdicts = plan(spec, records)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    code = spec["code"]
    to_patch = {f: v for f, v in verdicts.items() if v["action"] == "patch"}
    noop = [f for f, v in verdicts.items() if v["action"] == "noop"]
    print(f"{code}: {len(to_patch)} field(s) to patch, {len(noop)} already cured")
    for field, v in to_patch.items():
        print(f"  {field}: {spec['fields'][field]['old']!r} -> {v['new']!r}")
    for field in noop:
        print(f"  {field}: already cured — no-op")

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

    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code[code]
    for field, v in to_patch.items():
        write_field(rec, field, v["new"])

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    # Read back and prove the write, rather than trusting that it happened.
    _, again, _ = load(path)
    fresh = {str(r.get("kode_kbli_2025")): r for r in again}
    after = fresh[code]
    wrong = [f for f in to_patch if read_field(after, f) != spec["fields"][f]["new"]]
    if wrong:
        print(f"WROTE BUT READ BACK WRONG on: {wrong}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {code} ({len(to_patch)} field(s))")

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
