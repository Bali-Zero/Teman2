#!/usr/bin/env python3
"""Restore 93114/43110's ingested-away licensing rows (SAETTA-20260915 W-H PR-2b).
Rows + reasons: cure_specs/pr2b_source_rows_93114_43110_2026_09_15.json. 93114
restores its golf row from `per_skala_disputed_pp28_collision`, drops `_data_note`;
43110 takes all three `per_skala_legacy` rows and flips l4_bali.blocked (Zero D5f).
Each code's spec pins `premises`: field -> {old_sha256, new_sha256}, judged by
`_hardened_cure_io.judge_patch`: "patch" (pre-cure), "noop" (post-cure, no write),
or a refusal (drift/disagreement between a code's own fields). Dry-run default.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import _hardened_cure_io as H  # noqa: E402
import _l4bali_basis as basis  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = Path(__file__).resolve().parent / "cure_specs" / "pr2b_source_rows_93114_43110_2026_09_15.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
CODE_FIELD = "kode_kbli_2025"
CureError = H.CureError

def _fixed(rows: list[dict], fixes: list[dict]) -> list[dict]:
    """Apply known extraction-artifact corrections (each fix names WHY in the spec)."""
    out = copy.deepcopy(rows)
    for fix in fixes:
        out[fix["index"]][fix["field"]] = fix["value"]
    return out

def classify(record: dict, code: str, premises: dict[str, dict]) -> str:
    """Verdict against pinned premises: "patch", "noop", or raise on drift/disagreement."""
    judged = {f: H.judge_patch(record.get(f), p["old_sha256"], p["new_sha256"], f"{code}.{f}") for f, p in premises.items()}
    distinct = {v for f, v in judged.items() if premises[f]["old_sha256"] != premises[f]["new_sha256"]}
    if len(distinct) != 1:
        raise CureError(f"{code}: premises disagree on state {judged} — partial application, refusing")
    return distinct.pop()

def plan(records: list[dict], spec: dict, verdicts: dict[str, str]) -> dict[str, Any]:
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    items: dict[str, Any] = {}
    if verdicts.get("93114") == "patch":
        r93114 = by_code.get("93114")
        if r93114 is None: raise CureError("93114: not in canonical")
        golf_rows = r93114.get(spec["93114"]["disputed_key"])
        if not isinstance(golf_rows, list) or not golf_rows:
            raise CureError("93114: disputed key missing or empty — nothing to restore")
        items["93114"] = {
            "per_skala": list(r93114.get("per_skala") or []) + copy.deepcopy(golf_rows),
            "drop_keys": list(spec["93114"]["drop_keys"]),
            "l4_patch": dict(spec["93114"]["l4_patch"]),
            "l4_drop": list(spec["93114"]["l4_drop"]),
        }
    if verdicts.get("43110") == "patch":
        r43110 = by_code.get("43110")
        if r43110 is None: raise CureError("43110: not in canonical")
        legacy = r43110.get(spec["43110"]["legacy_key"])
        if not isinstance(legacy, list) or len(legacy) != spec["43110"]["expected_legacy_count"]:
            raise CureError(f"43110: {spec['43110']['legacy_key']} does not have exactly {spec['43110']['expected_legacy_count']} rows")
        items["43110"] = {
            "per_skala": _fixed(legacy, spec["43110"].get("row_fixes") or []),
            "drop_keys": [],
            "l4_patch": dict(spec["43110"]["l4_patch"]),
            "l4_drop": list(spec["43110"]["l4_drop"]),
        }
    return items

def apply_item(record: dict, item: dict) -> None:
    record["per_skala"] = item["per_skala"]
    for key in item["drop_keys"]:
        record.pop(key, None)
    l4 = record.setdefault("l4_bali", {})
    for key in item["l4_drop"]:
        l4.pop(key, None)
    l4.update(item["l4_patch"])
    l4["verdict_state"] = basis.derive_verdict_state(record)

def touched_paths(item: dict) -> set[str]:
    paths = {"per_skala", "l4_bali.verdict_state"}
    paths.update(item["drop_keys"])
    paths.update(f"l4_bali.{k}" for k in item["l4_patch"])
    paths.update(f"l4_bali.{k}" for k in item["l4_drop"])
    return paths

def propagate() -> None:
    check = subprocess.run(["bash", str(SYNC_SCRIPT), "sync"], capture_output=True, text=True)
    if check.returncode != 0:
        raise CureError(f"sync_kbli_dataset.sh failed: {check.stderr[-800:]}")
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = "sha256:" + hashlib.sha256(CANONICAL.read_bytes()).hexdigest()
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("synced + sidecar updated")

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    payload, records, original = H.load_dataset(CANONICAL)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    try:
        verdicts = {code: classify(by_code.get(code, {}), code, entry["premises"]) for code, entry in spec.items()}
        items = plan(records, spec, verdicts)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return 2
    if not items:
        print(f"already cured ({verdicts}) — no-op")
        return 0
    if not args.apply:
        for code, item in items.items():
            print(f"{code}: per_skala -> {len(item['per_skala'])} row(s); l4_patch {item['l4_patch']}")
        print("\ndry-run — rerun with --apply to write")
        return 0
    before = copy.deepcopy(records)
    for code, item in items.items():
        apply_item(by_code[code], item)
    try:
        paths = {code: touched_paths(item) for code, item in items.items()}
        H.verify_untouched(before, records, CODE_FIELD, touched_codes=set(items), touched_field_paths=paths)
    except CureError as exc:
        print(f"REFUSED (untouched_fields): {exc}")
        return 2
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(CANONICAL, body + ("\n" if original.endswith("\n") else ""))
    _, fresh_records, _ = H.load_dataset(CANONICAL)
    fresh = {str(r.get(CODE_FIELD)): r for r in fresh_records}
    for code, item in items.items():
        if fresh[code]["per_skala"] != item["per_skala"]:
            print(f"WROTE BUT READ BACK WRONG on {code}")
            return 2
    print("applied and verified on re-read")
    propagate()
    return 0

if __name__ == "__main__":
    sys.exit(main())
