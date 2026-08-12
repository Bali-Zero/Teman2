#!/usr/bin/env python3
"""Compile the state-derived ``l4_bali.verdict_state`` spec.

This compiler is additive by contract.  It writes only ``verdict_state`` and
never changes the legacy Boolean ``blocked`` consumed by existing renderers.
Before any mutation it re-derives every entry's facts basis from the live
record and refuses the whole run on drift.  A non-empty apply to the canonical
dataset also runs ``scripts/sync_kbli_dataset.sh`` and updates the dataset SHA
sidecar; a zero-patch apply is a pure no-op.

Usage:
  python scripts/kbli_filiera/cure_l4bali_verdict_state.py
  python scripts/kbli_filiera/cure_l4bali_verdict_state.py --apply
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
from _l4bali_basis import (  # noqa: E402
    CODE_FIELD,
    VERDICT_STATES,
    derive_verdict_state,
    verdict_state_facts,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
# The tracked root ``source_documents`` symlink points here, so this path is
# the sync source of truth itself.  The sync's ``cmp -s`` therefore sees the
# data-path consumer as the same file and short-circuits any self-copy.
DEFAULT_CANONICAL = (
    REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
)
DEFAULT_SPEC = (
    FILIERA_DIR / "cure_specs" / "l4bali_verdict_state_2026_08_12.json"
)
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = (
    REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
)

EXIT_OK = 0
EXIT_REFUSED = 2
ALLOWED_PATCH_KEYS = frozenset({"verdict_state"})

CureError = H.CureError


def load_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    codes = spec.get("codes") if isinstance(spec, dict) else None
    if not isinstance(codes, dict) or not codes:
        raise CureError(f"{path}: expected a non-empty codes object")
    return spec


def _validate_patch(code: str, entry: dict[str, Any]) -> str:
    patch = entry.get("patch")
    if not isinstance(patch, dict):
        raise CureError(f"{code}: patch missing or not an object")
    extra = set(patch) - ALLOWED_PATCH_KEYS
    if extra:
        if "blocked" in extra:
            raise CureError(
                f"{code}: dangerous direction refused — this compiler never writes "
                "l4_bali.blocked (including true->false)"
            )
        raise CureError(f"{code}: forbidden patch key(s) {sorted(extra)}")
    if set(patch) != ALLOWED_PATCH_KEYS:
        raise CureError(f"{code}: patch must contain exactly verdict_state")
    target = patch["verdict_state"]
    if target not in VERDICT_STATES:
        raise CureError(f"{code}: invalid verdict_state {target!r}")
    return str(target)


def plan(
    spec: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, dict[str, str]]:
    """Return per-code patch/noop plans, or refuse the complete run on drift."""
    by_code: dict[str, dict[str, Any]] = {}
    for record in records:
        code = str(record.get(CODE_FIELD) or "")
        if not code:
            raise CureError("canonical record without kode_kbli_2025")
        if code in by_code:
            raise CureError(f"duplicate canonical code {code!r}")
        by_code[code] = record

    entries = spec["codes"]
    missing = set(by_code) - set(entries)
    extra = set(entries) - set(by_code)
    if missing or extra:
        raise CureError(
            "spec/canonical population drift — "
            f"missing_from_spec={sorted(missing)[:10]} ({len(missing)}), "
            f"not_in_canonical={sorted(extra)[:10]} ({len(extra)})"
        )

    plans: dict[str, dict[str, str]] = {}
    for code in sorted(entries):
        entry = entries[code]
        if not isinstance(entry, dict):
            raise CureError(f"{code}: spec entry is not an object")
        target = _validate_patch(code, entry)
        record = by_code[code]
        try:
            live_facts = verdict_state_facts(record)
            derived = derive_verdict_state(record)
        except ValueError as exc:
            raise CureError(f"{code}: cannot re-derive facts basis: {exc}") from exc
        expected_facts = entry.get("facts_basis")
        if live_facts != expected_facts:
            raise CureError(
                f"{code}: facts-basis drift — expected {expected_facts!r}, "
                f"re-derived {live_facts!r}"
            )
        if target != derived:
            raise CureError(
                f"{code}: spec target {target!r} disagrees with live-state "
                f"derivation {derived!r}"
            )

        current = (record.get("l4_bali") or {}).get("verdict_state")
        if live_facts["blocked"] is True and target == "open":
            raise CureError(
                f"{code}: dangerous direction refused — blocked=true cannot compile to open"
            )
        if current == "blocked" and target == "open":
            raise CureError(
                f"{code}: dangerous direction refused — verdict_state blocked->open"
            )
        if current is not None and current not in VERDICT_STATES:
            raise CureError(f"{code}: invalid live verdict_state {current!r}")
        plans[code] = {
            "action": "noop" if current == target else "patch",
            "target": target,
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
        raise CureError(
            f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)"
        )
    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = digest
    sidecar["lastModified"] = date.today().isoformat()
    H.atomic_write_text(
        SIDECAR_PATH, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"sidecar datasetSha256 -> {digest}")


def _report(plans: dict[str, dict[str, str]], records: list[dict[str, Any]]) -> None:
    targets = Counter(plan["target"] for plan in plans.values())
    actions = Counter(plan["action"] for plan in plans.values())
    by_code = {str(record.get(CODE_FIELD)): record for record in records}
    preserved = sum(
        1
        for code, item in plans.items()
        if item["target"] == "unknown"
        and (by_code[code].get("l4_bali") or {}).get("blocked") is True
    )
    print(
        f"summary: {actions['patch']} to patch, {actions['noop']} already correct, "
        f"{len(plans)} facts bases verified"
    )
    for state in ("blocked", "open", "unknown", "provisional"):
        print(f"  {state:12} {targets[state]}")
    print(f"  unknown with blocked=true preserved: {preserved}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write; default is dry-run")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    args = parser.parse_args(argv)

    try:
        spec = load_spec(args.spec)
        payload, records, original = H.load_dataset(args.canonical)
        plans = plan(spec, records)
    except (OSError, json.JSONDecodeError, CureError) as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    print(
        "cure_l4bali_verdict_state.py — "
        f"mode={'APPLY' if args.apply else 'DRY-RUN'}"
    )
    _report(plans, records)
    to_patch = {code: item for code, item in plans.items() if item["action"] == "patch"}
    if not args.apply:
        print("dry-run — no files written; rerun with --apply to write")
        return EXIT_OK
    if not to_patch:
        print("nothing to patch")
        return EXIT_OK

    before_records = copy.deepcopy(records)
    by_code = {str(record.get(CODE_FIELD)): record for record in records}
    for code, item in to_patch.items():
        by_code[code]["l4_bali"]["verdict_state"] = item["target"]

    try:
        H.verify_untouched(
            before_records,
            records,
            CODE_FIELD,
            touched_codes=set(to_patch),
            touched_field_paths={
                code: {"l4_bali.verdict_state"} for code in to_patch
            },
        )
    except CureError as exc:
        print(f"REFUSED (untouched fields): {exc}")
        return EXIT_REFUSED

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(
        args.canonical, body + ("\n" if original.endswith("\n") else "")
    )

    try:
        _, reread, _ = H.load_dataset(args.canonical)
        reread_by_code = {str(record.get(CODE_FIELD)): record for record in reread}
        wrong = [
            code
            for code, item in to_patch.items()
            if reread_by_code[code]["l4_bali"].get("verdict_state") != item["target"]
        ]
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
