#!/usr/bin/env python3
"""cure_restore_per_ancestor.py — deterministic per-ancestor PP28 restore compiler.

GARUDA-FILIERA per-code restore (2026-07-18, research/operations/2026-07-18-
kbli-batch-a-plan.md §A-6(b)-RESOLVED; conductor gate PR #2721/#2740):

KBLI 2025 code 49213 "Angkutan Perkotaan" was DETACHED by the Fase-1 cure
(cure_canonical_collisions.py, #2589) after a code-number collision was found
(the served per_skala carried the WRONG KBLI-2020 AKDP/inter-city licensing).
That detach was pure quarantine — an honest gap, never a fabricated fix. This
script applies the FOLLOW-UP: the signed adjudication determined the correct
regulatory basis is the MERGE of 3 image-verified PP28/2025 Lampiran rows from
3 KBLI-2020 ancestors whose regimes are substantially identical for the urban
scope. This compiler mechanically RESTORES per_skala from that merge:

  1. per_skala <- the spec's per-ancestor rows (verbatim, image-verified —
     this script NEVER derives/invents a licensing value; every row traces to
     a sha256-pinned render in the spec's adjudication.renders).
  2. pp28_sources <- the spec's ancestor list (replaces the old, partly-wrong
     pointer set).
  3. _data_note <- the spec's data_note string (provenance, never authored
     here).
  4. per_skala_disputed_pp28_collision (the OLD wrong-vintage AKDP-collision
     block) is left COMPLETELY UNTOUCHED — it stays as the historical audit
     trail, never re-derived, never reused, never re-detached. This is the
     opposite operation from cure_canonical_collisions.py's detach, which is
     why 49213 was REMOVED from that compiler's own spec (fase1_collisions.json)
     in the same PR that ships this file — leaving it there would let a future
     --apply of the detach compiler treat the restored data as a fresh
     contamination and clobber it back into the disputed key.
  5. Every other field (judul, uraian, pma_*, status_mapping, intel_2026,
     l4_bali, aggregation_note, ...) is left untouched by THIS compiler —
     editorial/gold realignment and l4_bali re-derivation are explicitly
     scoped OUT and gated separately (see the spec's own _doc + the PR body).

This script is a sanctioned writer of the canonical KBLI dataset alongside
cure_canonical_collisions.py: infra/claude-hooks/data_plane_guard.py blocks
direct Edit/Write/sed/tee on data/source_documents/KBLI_2025_FINAL_CLEAN.json
for every path except this program's own compilers/ (id "kbli-filiera").

Usage:
  # dry run (default) — prints a diff summary, writes nothing
  python scripts/kbli_filiera/cure_restore_per_ancestor.py

  # apply — mutates canonical, propagates to the 4 consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the sidecar sha256
  python scripts/kbli_filiera/cure_restore_per_ancestor.py --apply
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path
from typing import Any

# Sibling-module import: works both when this file is executed directly
# (Python auto-adds its own directory to sys.path[0]) and when a test file
# has already inserted this directory (matches the pattern already used by
# scripts/kbli_filiera/tests/test_cure_canonical_collisions.py).
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import cure_canonical_collisions as base  # noqa: E402

logger = logging.getLogger("kbli_filiera.cure_restore_per_ancestor")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "restore_49213.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = base.CODE_FIELD
CureError = base.CureError

REQUIRED_SPEC_KEYS = {"action", "code", "disputed_key", "per_skala", "pp28_sources", "data_note"}
SUPPORTED_ACTION = "restore_per_skala_per_ancestor"


def load_spec(spec_path: Path) -> dict[str, Any]:
    import json

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    missing = REQUIRED_SPEC_KEYS - spec.keys()
    if missing:
        raise CureError(f"{spec_path}: spec missing required keys {sorted(missing)}")
    if spec["action"] != SUPPORTED_ACTION:
        raise CureError(
            f"{spec_path}: unsupported action {spec['action']!r} "
            f"(this compiler only handles {SUPPORTED_ACTION!r})"
        )
    if not isinstance(spec["per_skala"], list) or not spec["per_skala"]:
        raise CureError(f"{spec_path}: 'per_skala' must be a non-empty list")
    if not isinstance(spec["pp28_sources"], list) or not spec["pp28_sources"]:
        raise CureError(f"{spec_path}: 'pp28_sources' must be a non-empty list")
    return spec


class RestorePlan:
    """Outcome of evaluating the spec against the loaded canonical record.

    status:
      "apply"          — record will be mutated: per_skala / pp28_sources /
                         _data_note set to the spec's restored values.
      "already-cured"  — all three already match the spec: idempotent no-op.
      "missing"        — code not found in canonical at all.
      "no-disputed"    — refuses to restore a code with no
                         per_skala_disputed_* key: a restore is only sound as
                         a follow-up to an existing detach/quarantine (rule:
                         detach>plausible-remap implies the reverse move only
                         ever happens FROM a documented quarantine).
      "unexpected-state" — per_skala is neither [] (the expected pre-restore
                         state) nor already equal to the spec's target rows:
                         refuse to clobber an unrecognised prior state.
    """

    def __init__(self, code: str, status: str, *, needs_apply: bool = False) -> None:
        self.code = code
        self.status = status
        self.needs_apply = needs_apply

    def describe(self) -> str:
        if self.status == "missing":
            return f"{self.code}: NOT FOUND IN CANONICAL — cannot restore"
        if self.status == "no-disputed":
            return (
                f"{self.code}: NO per_skala_disputed_* key found — refusing an "
                "ungated restore (a restore is only sound as a follow-up to an "
                "existing detach/quarantine)"
            )
        if self.status == "unexpected-state":
            return (
                f"{self.code}: per_skala is neither [] nor already the spec's "
                "restored rows — refusing to clobber an unrecognised prior state "
                "(no-clobber discipline)"
            )
        if self.status == "already-cured":
            return f"{self.code}: ALREADY CURED (skip) — per_skala/pp28_sources/_data_note match the spec"
        return (
            f"{self.code}: per_skala -> {len(_current_target_rows(self))} restored row(s), "
            "pp28_sources updated, _data_note set"
        )


def _current_target_rows(plan: RestorePlan) -> list:
    # helper only used for the describe() row-count message when applying;
    # kept trivial and side-effect-free.
    return getattr(plan, "_rows", [])


def plan_restore(record: dict[str, Any], spec: dict[str, Any]) -> RestorePlan:
    code = spec["code"]
    disputed_key = spec["disputed_key"]
    current_per_skala = record.get("per_skala")

    has_disputed = disputed_key in record and bool(record.get(disputed_key))
    if not has_disputed:
        return RestorePlan(code, "no-disputed")

    target_per_skala = spec["per_skala"]
    target_pp28 = spec["pp28_sources"]
    target_note = spec["data_note"]

    already = (
        current_per_skala == target_per_skala
        and record.get("pp28_sources") == target_pp28
        and record.get("_data_note") == target_note
    )
    if already:
        return RestorePlan(code, "already-cured")

    is_empty = current_per_skala == []
    is_target_already = current_per_skala == target_per_skala
    if not is_empty and not is_target_already:
        return RestorePlan(code, "unexpected-state")

    plan = RestorePlan(code, "apply", needs_apply=True)
    plan._rows = target_per_skala  # type: ignore[attr-defined]
    return plan


def apply_restore(record: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Return a NEW record dict with the restore applied. Idempotent: setting
    the same three fields to the same values twice is a no-op on content.
    per_skala_disputed_* is NEVER touched — it is simply absent from the set
    of keys this function writes."""
    new_record = dict(record)
    new_record["per_skala"] = copy.deepcopy(spec["per_skala"])
    new_record["pp28_sources"] = copy.deepcopy(spec["pp28_sources"])
    new_record["_data_note"] = spec["data_note"]
    return new_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="restore spec JSON (default: restore_49213.json)")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL, help="canonical dataset to mutate")
    parser.add_argument("--apply", action="store_true", help="mutate the canonical (default: dry-run, writes nothing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    import json

    spec = load_spec(args.spec)
    code = spec["code"]

    if not args.canonical.exists():
        raise CureError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = base._detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = base._index_by_code(records)

    print(f"cure_restore_per_ancestor.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"code = {code!r}, action = {spec['action']!r}, indent = {indent}")
    print("-" * 78)

    record = by_code.get(code)
    if record is None:
        plan = RestorePlan(code, "missing")
        print(plan.describe())
        print("-" * 78)
        logger.error("spec code %r not found in canonical %s", code, args.canonical)
        return 1

    plan = plan_restore(record, spec)
    print(plan.describe())
    print("-" * 78)

    if plan.status in ("no-disputed", "unexpected-state"):
        logger.error(plan.describe())
        return 1

    if not args.apply:
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 0

    if plan.status != "apply":
        logger.info("nothing to apply — skipping sync + sidecar update")
        return 0

    idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
    records[idx] = apply_restore(record, spec)

    tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=indent)
        tmp_path.replace(args.canonical)
        logger.info("wrote restored record %r to %s", code, args.canonical)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    base.run_sync_script()
    base.update_sidecar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
