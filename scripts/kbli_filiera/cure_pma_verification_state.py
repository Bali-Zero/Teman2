#!/usr/bin/env python3
"""Add the explicit verification state for every canonical PMA verdict.

The catalogue renders a foreign-ownership answer for every code.  Until this
compiler existed, absence of ``pma_official_basis`` was merely an absent field:
the page still rendered the answer, while the coverage scoreboard correctly
classified it as a bare assertion.  This additive compiler turns that absence
into an explicit, machine-readable declaration:

* ``located`` requires both a non-blank per-code official basis and a source
  vintage;
* ``declared_gap`` means the current value is retained for continuity but has
  no adjudicated per-code basis and must be presented as unverified.

It never invents a basis and never changes the PMA value.  For the 19 already
adjudicated records whose basis predates this field, it fills only the missing
instrument vintage from the instrument named by that same basis.  Unknown
instruments are a refusal, never guessed.

Usage:
  python scripts/kbli_filiera/cure_pma_verification_state.py
  python scripts/kbli_filiera/cure_pma_verification_state.py --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))

import _hardened_cure_io as H  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts/sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps/mouth/data/kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"
STATUS_FIELD = "pma_verification_status"
VINTAGE_FIELD = "pma_source_vintage"
VALID_STATES = frozenset({"located", "declared_gap"})

# The operative amendment dates, verified against the BPK regulation metadata.
# These are the source-instrument vintages, not KBLI classification vintages.
PERPRES_VINTAGE = "2021-05-25"
INSURANCE_VINTAGE = "2020-01-20"

EXIT_OK = 0
EXIT_REFUSED = 2
CureError = H.CureError


def _nonblank(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def infer_vintage(basis: str) -> str:
    """Infer only from an already-adjudicated basis naming a known instrument."""
    if "PP 14/2018" in basis and "PP 3/2020" in basis:
        return INSURANCE_VINTAGE
    if "Perpres 10/2021" in basis or "Perpres 49/2021" in basis:
        return PERPRES_VINTAGE
    raise CureError(
        "cannot infer source vintage from an unrecognised official basis; "
        "adjudicate the instrument instead of guessing"
    )


def expected_fields(record: dict[str, Any]) -> dict[str, str | None]:
    basis = _nonblank(record.get("pma_official_basis"))
    current_vintage = _nonblank(record.get(VINTAGE_FIELD))
    if not basis:
        if current_vintage:
            raise CureError(
                "source vintage exists without a non-blank pma_official_basis"
            )
        return {STATUS_FIELD: "declared_gap", VINTAGE_FIELD: None}
    return {
        STATUS_FIELD: "located",
        VINTAGE_FIELD: current_vintage or infer_vintage(basis),
    }


def plan(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    plans: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for record in records:
        code = str(record.get(CODE_FIELD) or "")
        if not code:
            raise CureError("canonical record without kode_kbli_2025")
        if code in seen:
            raise CureError(f"duplicate canonical code {code!r}")
        seen.add(code)

        current_status = record.get(STATUS_FIELD)
        if current_status is not None and current_status not in VALID_STATES:
            raise CureError(f"{code}: invalid {STATUS_FIELD} {current_status!r}")
        try:
            expected = expected_fields(record)
        except CureError as exc:
            raise CureError(f"{code}: {exc}") from exc

        patch = {
            key: value
            for key, value in expected.items()
            if value is not None and record.get(key) != value
        }
        # A declared gap must not carry a stale vintage.  Refuse above rather
        # than silently deleting it, so this compiler remains additive.
        plans[code] = {
            "action": "patch" if patch else "noop",
            "patch": patch,
            "target": expected[STATUS_FIELD],
        }
    return plans


def run_sync_script() -> None:
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise CureError(
            f"sync_kbli_dataset.sh sync failed with exit {result.returncode}"
        )


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH}")
    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = digest
    sidecar["lastModified"] = date.today().isoformat()
    H.atomic_write_text(
        SIDECAR_PATH, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"sidecar datasetSha256 -> {digest}")


def _report(plans: dict[str, dict[str, Any]]) -> None:
    actions = Counter(item["action"] for item in plans.values())
    targets = Counter(item["target"] for item in plans.values())
    vintages = sum(VINTAGE_FIELD in item["patch"] for item in plans.values())
    print(
        f"summary: {actions['patch']} to patch, {actions['noop']} already correct, "
        f"{len(plans)} records partitioned"
    )
    print(f"  located       {targets['located']}")
    print(f"  declared_gap  {targets['declared_gap']}")
    print(f"  vintages to fill {vintages}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write; default is dry-run")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    args = parser.parse_args(argv)

    try:
        payload, records, original = H.load_dataset(args.canonical)
        plans = plan(records)
    except (OSError, json.JSONDecodeError, CureError) as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    print(
        "cure_pma_verification_state.py — "
        f"mode={'APPLY' if args.apply else 'DRY-RUN'}"
    )
    _report(plans)
    to_patch = {code: item for code, item in plans.items() if item["action"] == "patch"}
    if not args.apply:
        print("dry-run — no files written; rerun with --apply to write")
        return EXIT_OK
    if not to_patch:
        print("nothing to patch")
        return EXIT_OK

    before = copy.deepcopy(records)
    by_code = {str(record[CODE_FIELD]): record for record in records}
    touched_paths: dict[str, set[str]] = {}
    for code, item in to_patch.items():
        touched_paths[code] = set(item["patch"])
        by_code[code].update(item["patch"])

    try:
        H.verify_untouched(
            before,
            records,
            CODE_FIELD,
            touched_codes=set(to_patch),
            touched_field_paths=touched_paths,
        )
    except CureError as exc:
        print(f"REFUSED (untouched fields): {exc}")
        return EXIT_REFUSED

    H.atomic_write_text(
        args.canonical,
        json.dumps(payload, ensure_ascii=False, indent=2)
        + ("\n" if original.endswith("\n") else ""),
    )

    try:
        _, reread, _ = H.load_dataset(args.canonical)
        reread_plan = plan(reread)
        wrong = [code for code, item in reread_plan.items() if item["action"] != "noop"]
        if wrong:
            raise CureError(f"write read-back mismatch on {wrong[:10]}")
        print(f"applied and verified on re-read: {len(to_patch)} code(s)")
        if args.canonical.resolve() == DEFAULT_CANONICAL.resolve():
            run_sync_script()
            update_sidecar()
            print("consumer copies synced; sidecar SHA updated")
        else:
            print("custom canonical fixture — consumer sync and sidecar update skipped")
    except (OSError, json.JSONDecodeError, CureError) as exc:
        print(f"REFUSED after canonical write: {exc}")
        return EXIT_REFUSED
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
