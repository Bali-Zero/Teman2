#!/usr/bin/env python3
"""cure_metadata_pp28_sources.py — deterministic metadata-only correction compiler.

GARUDA-FILIERA Batch A Lot 2 (2026-07-18, conductor-signed D6 verdict,
session f5892d39): the 56101 finding is an INNOCENCE-VIOLATION, not a
detach. 56101's per_skala substance (the actual licensing steps/authority/
jangka_waktu rows) was independently verified correct — the defect lives
only in the PROVENANCE POINTER LIST (pp28_sources) and the prose derived
from it (aggregation_note, intel_2026.whatChanged): the canonical claimed
56101 absorbed KBLI-2020 codes 56103+56104 (it does not — those map to
2025-56102) while never crediting the code it actually did absorb,
KBLI-2020 56102.

Neither existing compiler fits this shape:
  - cure_canonical_collisions.py detaches per_skala -> [] (wrong here: the
    licensing substance is NOT contaminated, only its provenance pointer).
  - cure_restore_per_ancestor.py restores per_skala FROM a prior detach
    (wrong here: there was never a detach to restore from).

This compiler is the third sanctioned shape: a pure METADATA correction.
It writes EXACTLY three fields — pp28_sources, aggregation_note,
intel_2026.whatChanged — plus _data_note (provenance, never authored by
this script, always copied verbatim from the spec). It NEVER reads or
writes per_skala or per_skala_legacy, and it refuses outright to run
against a record that already carries any `per_skala_disputed_*` key: a
metadata-only cure is only sound on an un-quarantined, innocence-confirmed
record — if the record has been detached, the fix belongs to
cure_canonical_collisions.py / cure_restore_per_ancestor.py, not here.

This script is a sanctioned writer of the canonical KBLI dataset alongside
cure_canonical_collisions.py and cure_restore_per_ancestor.py:
infra/claude-hooks/data_plane_guard.py blocks direct Edit/Write/sed/tee on
data/source_documents/KBLI_2025_FINAL_CLEAN.json for every path except this
program's own compilers/ (infra/claude-hooks/data-plane-registry.json, id
"kbli-filiera").

Usage:
  # dry run (default) — prints a diff summary, writes nothing
  python scripts/kbli_filiera/cure_metadata_pp28_sources.py

  # apply — mutates canonical, propagates to the 4 consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the sidecar sha256
  python scripts/kbli_filiera/cure_metadata_pp28_sources.py --apply
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Sibling-module import: works both when this file is executed directly
# (Python auto-adds its own directory to sys.path[0]) and when a test file
# has already inserted this directory (same pattern as
# cure_restore_per_ancestor.py).
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import cure_canonical_collisions as base  # noqa: E402

logger = logging.getLogger("kbli_filiera.cure_metadata_pp28_sources")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "metadata_56101.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = base.CODE_FIELD
CureError = base.CureError

REQUIRED_SPEC_KEYS = {"action", "code", "pp28_sources", "aggregation_note", "whatChanged", "data_note"}
SUPPORTED_ACTION = "correct_pp28_sources_metadata"


def load_spec(spec_path: Path) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    missing = REQUIRED_SPEC_KEYS - spec.keys()
    if missing:
        raise CureError(f"{spec_path}: spec missing required keys {sorted(missing)}")
    if spec["action"] != SUPPORTED_ACTION:
        raise CureError(
            f"{spec_path}: unsupported action {spec['action']!r} "
            f"(this compiler only handles {SUPPORTED_ACTION!r})"
        )
    if not isinstance(spec["pp28_sources"], list) or not spec["pp28_sources"]:
        raise CureError(f"{spec_path}: 'pp28_sources' must be a non-empty list")
    return spec


class MetadataPlan:
    """Outcome of evaluating the spec against the loaded canonical record.

    status:
      "apply"           — record will be mutated: pp28_sources /
                          aggregation_note / intel_2026.whatChanged /
                          _data_note set to the spec's corrected values.
      "already-cured"   — all four already match the spec: idempotent no-op.
      "missing"         — code not found in canonical at all.
      "detached-guard"  — record carries a per_skala_disputed_* key: refuses
                          to apply a metadata-only cure to an already-
                          quarantined record (no-clobber discipline — that
                          record's fix belongs to a different compiler).
      "no-intel"        — record has no intel_2026 dict to write whatChanged
                          into: refuses rather than fabricating the key.
    """

    def __init__(self, code: str, status: str) -> None:
        self.code = code
        self.status = status

    def describe(self) -> str:
        if self.status == "missing":
            return f"{self.code}: NOT FOUND IN CANONICAL — cannot cure"
        if self.status == "detached-guard":
            return (
                f"{self.code}: REFUSING — record carries a per_skala_disputed_* "
                "key (already quarantined); a metadata-only cure is only sound "
                "on an un-quarantined, innocence-confirmed record"
            )
        if self.status == "no-intel":
            return f"{self.code}: REFUSING — record has no intel_2026 dict to correct whatChanged in"
        if self.status == "already-cured":
            return f"{self.code}: ALREADY CURED (skip) — pp28_sources/aggregation_note/whatChanged/_data_note match the spec"
        return f"{self.code}: pp28_sources/aggregation_note/intel_2026.whatChanged/_data_note -> corrected"


def _has_disputed_key(record: dict[str, Any]) -> bool:
    return any(k.startswith("per_skala_disputed") for k in record)


def plan_metadata_cure(record: dict[str, Any], spec: dict[str, Any]) -> MetadataPlan:
    code = spec["code"]

    if _has_disputed_key(record):
        return MetadataPlan(code, "detached-guard")

    intel = record.get("intel_2026")
    if not isinstance(intel, dict):
        return MetadataPlan(code, "no-intel")

    already = (
        record.get("pp28_sources") == spec["pp28_sources"]
        and record.get("aggregation_note") == spec["aggregation_note"]
        and intel.get("whatChanged") == spec["whatChanged"]
        and record.get("_data_note") == spec["data_note"]
    )
    if already:
        return MetadataPlan(code, "already-cured")

    return MetadataPlan(code, "apply")


def apply_metadata_cure(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW record dict with the metadata cure applied. per_skala and
    per_skala_legacy are NEVER referenced here — they simply pass through
    unchanged as part of the dict(record) copy. Idempotent: setting the same
    four fields to the same values twice is a no-op on content."""
    new_record = dict(record)
    new_record["pp28_sources"] = copy.deepcopy(spec["pp28_sources"])
    new_record["aggregation_note"] = spec["aggregation_note"]

    intel = dict(new_record["intel_2026"])
    intel["whatChanged"] = spec["whatChanged"]
    new_record["intel_2026"] = intel

    new_record["_data_note"] = spec["data_note"]
    return new_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="metadata cure spec JSON (default: metadata_56101.json)")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL, help="canonical dataset to mutate")
    parser.add_argument("--apply", action="store_true", help="mutate the canonical (default: dry-run, writes nothing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    spec = load_spec(args.spec)
    code = spec["code"]

    if not args.canonical.exists():
        raise CureError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = base._detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = base._index_by_code(records)

    print(f"cure_metadata_pp28_sources.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"code = {code!r}, action = {spec['action']!r}, indent = {indent}")
    print("-" * 78)

    record = by_code.get(code)
    if record is None:
        plan = MetadataPlan(code, "missing")
        print(plan.describe())
        print("-" * 78)
        logger.error("spec code %r not found in canonical %s", code, args.canonical)
        return 1

    plan = plan_metadata_cure(record, spec)
    print(plan.describe())
    print("-" * 78)

    if plan.status in ("detached-guard", "no-intel"):
        logger.error(plan.describe())
        return 1

    if not args.apply:
        if plan.status == "already-cured":
            print("DRY RUN — nothing to apply (already cured). No files written.")
            return 0
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 0

    if plan.status == "already-cured":
        logger.info("nothing to apply — skipping sync + sidecar update")
        return 0

    records[next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)] = apply_metadata_cure(record, spec)

    tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=indent)
        tmp_path.replace(args.canonical)
        logger.info("wrote corrected metadata for %s to %s", code, args.canonical)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    base.run_sync_script()
    base.update_sidecar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
