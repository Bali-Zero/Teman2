#!/usr/bin/env python3
"""cure_l4_editorial.py — deterministic L4-editorial detach compiler (Fase 1 cure #4).

GARUDA-FILIERA Fase 1, 4th layer (kbli-navigator corner, 2026-07-17): the first
three cures (per_skala detach #2508/#2589, whatYouNeed honest-gap #2608) fixed
the LICENSING surface for the 8 known false-friend collision codes. This
compiler fixes the fourth surface the same collision poisoned: the LOOP-2
magazine editorial (headline/standfirst/body/pullQuote/byTheNumbers) and the
l4_bali sovereign-local verdict itself still ASSERTED the collision-derived
Bali risk tier as fact (e.g. "Bali does not block this activity... its Bali
status is OK_or_HIGHER_RISK") — the prose never caught up with the licensing
fix. This script mechanically applies, per code, exactly what
scripts/kbli_filiera/cure_specs/fase1_l4_editorial.json specifies:

  1. editorial_patches — EXACT substring replace on intel_2026.editorial.<field>
     (headline/standfirst/body/pullQuote). Requires the old text to appear
     EXACTLY ONCE; if it is already absent and the new text is present, the
     patch is treated as already-applied (idempotent skip). Any other state
     (old missing+new missing, old repeated, both present) is a CureError —
     fail-visible, never a silent guess.
  2. byTheNumbers_patches — intel_2026.editorial.byTheNumbers[index].value is
     set to new_value, but only after verifying it currently equals old_value
     (or is already new_value, idempotent skip).
  3. l4_bali replacement — the record's l4_bali dict is replaced WHOLESALE by
     the spec's l4_bali_new object, EXCEPT the record's own CURRENT
     `moratorium` and `from_2020` values are preserved verbatim (never taken
     from the spec — those two are record-specific, not cure-specific).
     Every other l4_bali key (verdict/rule/review_basis — the old
     classification's own reasoning) is dropped: it explained a status this
     cure retracts.
  4. 68112-only — intel_2026.whatYouNeed is patched via the same exact-
     substring rule, driven by the spec's `_68112_intel_whatYouNeed` entry.
  5. 49213-only (gold layer) — apps/mouth/data/kbli-gold-all.json's 49213
     record gets its zantaraOpener/whatChanged/baliContext fields SET to the
     spec's `_gold_49213` full values (idempotent: no-op if already equal —
     gold has no "old" text to verify, since gold's prose diverged from
     intel_2026's prose long before this cure existed).

This script NEVER invents a value — every replacement text is spec-authored
(Codex cross-family adversarial gate, per the spec's own provenance). It is
the ONLY sanctioned writer of the canonical KBLI dataset for this cure, same
data-plane registration as cure_canonical_collisions.py (both live under
scripts/kbli_filiera/, the registry's `compilers` glob for entry "kbli-filiera").

Usage:
  # dry run (default) — prints a per-code diff summary, writes nothing
  python scripts/kbli_filiera/cure_l4_editorial.py

  # apply — mutates canonical + gold, propagates to the 4 consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the vitest sha256 sidecar
  python scripts/kbli_filiera/cure_l4_editorial.py --apply

  # subset
  python scripts/kbli_filiera/cure_l4_editorial.py --only 68112 49213 --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("kbli_filiera.cure_l4_editorial")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "fase1_l4_editorial.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
DEFAULT_GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"


class CureError(RuntimeError):
    """A spec/data mismatch severe enough to make the run's exit non-zero.

    Raised (never swallowed) whenever a patch's precondition is ambiguous —
    this is the "fail-visible" contract: a CureError propagates uncaught out
    of main(), same idiom as cure_canonical_collisions.py.
    """


def _detect_indent(raw_text: str) -> int:
    """Measure the JSON indent width from the file's own formatting rather
    than assuming 2 — Karpathy discipline says measure, don't presume."""
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def _index_by_code(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r[CODE_FIELD]: r for r in records if CODE_FIELD in r}


def _apply_text_patch(
    container: dict[str, Any], field: str, old: str, new: str, label: str, changes: list[str]
) -> None:
    """In-place exact-substring cure of container[field]. Appends to `changes`
    only when a real mutation happens; a no-op (already applied) is silent."""
    current = container.get(field)
    if not isinstance(current, str):
        raise CureError(f"{label}.{field}: missing or not a string (got {type(current)})")
    has_old = old in current
    has_new = bool(new) and new in current
    if has_new and not has_old:
        return  # already cured — idempotent skip
    if has_old and not has_new and current.count(old) == 1:
        container[field] = current.replace(old, new, 1)
        changes.append(f"{label}.{field}: cured ({len(old)}->{len(new)} chars)")
        return
    if has_old and current.count(old) > 1:
        raise CureError(
            f"{label}.{field}: old text appears {current.count(old)} times "
            "(expected exactly 1) — refusing to guess which occurrence to replace"
        )
    if has_old and has_new:
        raise CureError(f"{label}.{field}: BOTH old and new text present — ambiguous state")
    raise CureError(
        f"{label}.{field}: neither old nor new text found — data has drifted from the "
        "spec, refusing to guess"
    )


def _apply_by_the_numbers(
    editorial: dict[str, Any], patches: list[dict[str, Any]], label: str, changes: list[str]
) -> None:
    btn = editorial.get("byTheNumbers")
    if not isinstance(btn, list):
        raise CureError(f"{label}: editorial.byTheNumbers missing or not a list")
    for p in patches:
        idx = p["index"]
        old_value = p["old_value"]
        new_value = p["new_value"]
        if idx >= len(btn):
            raise CureError(f"{label}: byTheNumbers index {idx} out of range (len={len(btn)})")
        row = btn[idx]
        current = row.get("value")
        if current == new_value:
            continue  # already cured — idempotent skip
        if current == old_value:
            row["value"] = new_value
            changes.append(f"{label}.byTheNumbers[{idx}]: {old_value!r} -> {new_value!r}")
            continue
        raise CureError(
            f"{label}.byTheNumbers[{idx}].value is {current!r}, expected {old_value!r} "
            f"(to cure) or {new_value!r} (already cured) — data drifted from spec"
        )


def _apply_l4_bali(
    record: dict[str, Any], l4_bali_new: dict[str, Any], label: str, changes: list[str]
) -> None:
    current_l4 = record.get("l4_bali")
    if not isinstance(current_l4, dict):
        raise CureError(f"{label}: l4_bali missing or not a dict — cannot cure")
    target = dict(l4_bali_new)
    target["moratorium"] = copy.deepcopy(current_l4.get("moratorium"))
    target["from_2020"] = current_l4.get("from_2020")
    if current_l4 == target:
        return  # already cured — idempotent skip
    record["l4_bali"] = target
    changes.append(
        f"{label}.l4_bali: status {current_l4.get('status')!r} -> {target['status']!r}"
    )


def cure_record(
    record: dict[str, Any], code: str, entry: dict[str, Any], spec: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return (new_record, changes) — new_record is a deep copy of `record`
    with the cure applied (byte-identical to the input where already cured).
    `changes` empty means the whole record was already fully cured."""
    new_record = copy.deepcopy(record)
    changes: list[str] = []
    label = code

    intel = new_record.get("intel_2026")
    if not isinstance(intel, dict):
        raise CureError(f"{code}: intel_2026 missing or not a dict")
    editorial = intel.get("editorial")
    if not isinstance(editorial, dict):
        raise CureError(f"{code}: intel_2026.editorial missing or not a dict")

    for p in entry.get("editorial_patches", []):
        _apply_text_patch(editorial, p["field"], p["old"], p["new"], f"{label}.editorial", changes)

    _apply_by_the_numbers(editorial, entry.get("byTheNumbers_patches", []), f"{label}.editorial", changes)

    _apply_l4_bali(new_record, entry["l4_bali_new"], label, changes)

    # Per-code auxiliary patch: intel_2026.whatYouNeed (68112-only in this spec,
    # but keyed generically so a future code carrying the same aux key works too).
    wyn_key = f"_{code}_intel_whatYouNeed"
    wyn_patch = spec.get(wyn_key)
    if wyn_patch is not None:
        _apply_text_patch(intel, "whatYouNeed", wyn_patch["old"], wyn_patch["new"], f"{label}.intel_2026", changes)

    return new_record, changes


def cure_gold_record(
    gold_record: dict[str, Any], code: str, new_values: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    """Return (new_gold_record, changes). Full-value set per field — gold has
    no independent "old" text to verify (its prose diverged from intel_2026's
    long before this cure existed), so idempotency is a plain equality check."""
    new_gold = copy.deepcopy(gold_record)
    changes: list[str] = []
    for field, new_value in new_values.items():
        current = new_gold.get(field)
        if current == new_value:
            continue  # already cured — idempotent skip
        new_gold[field] = new_value
        changes.append(f"gold.{code}.{field}: updated ({len(str(current or ''))}->{len(new_value)} chars)")
    return new_gold, changes


def run_sync_script() -> None:
    logger.info("running %s sync", SYNC_SCRIPT)
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
        raise CureError(f"sync_kbli_dataset.sh sync failed with exit {result.returncode}")


def update_sidecar() -> None:
    if not SIDECAR_DATASET_PATH.exists():
        raise CureError(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = dict(sidecar)
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("sidecar updated: %s -> %s", before.get("datasetSha256"), sidecar["datasetSha256"])
    logger.info("sidecar lastModified: %s -> %s", before.get("lastModified"), sidecar["lastModified"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="cure spec JSON (default: fase1_l4_editorial.json)")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL, help="canonical dataset to mutate")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD, help="gold-tier dataset to mutate")
    parser.add_argument("--only", nargs="+", default=None, help="restrict to these KBLI codes")
    parser.add_argument("--apply", action="store_true", help="mutate the canonical+gold (default: dry-run, writes nothing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    spec: dict[str, Any] = json.loads(args.spec.read_text(encoding="utf-8"))
    codes = sorted(k for k in spec if not k.startswith("_"))
    if args.only:
        wanted = set(args.only)
        missing_requested = wanted - set(codes)
        if missing_requested:
            raise CureError(f"--only requested codes not present in spec: {sorted(missing_requested)}")
        codes = [c for c in codes if c in wanted]

    if not args.canonical.exists():
        raise CureError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = _detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = _index_by_code(records)

    gold_data: dict[str, Any] | None = None
    if args.gold.exists():
        gold_data = json.loads(args.gold.read_text(encoding="utf-8"))

    print(f"cure_l4_editorial.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 78)

    problems: list[str] = []
    new_canonical_records: dict[str, dict[str, Any]] = {}
    new_gold_records: dict[str, dict[str, Any]] = {}
    already_cured_count = 0
    missing_count = 0

    for code in codes:
        entry = spec[code]
        record = by_code.get(code)
        if record is None:
            missing_count += 1
            problems.append(f"spec code {code!r} not found in canonical {args.canonical}")
            print(f"{code}: NOT FOUND IN CANONICAL — cannot cure")
            continue

        new_record, changes = cure_record(record, code, entry, spec)
        canonical_cured = bool(changes)
        if canonical_cured:
            new_canonical_records[code] = new_record
            print(f"{code}: TO CURE — " + " | ".join(changes))
        else:
            print(f"{code}: ALREADY CURED (skip)")

        gold_key = f"_gold_{code}"
        gold_new_values = spec.get(gold_key)
        gold_cured = False
        if gold_new_values is not None:
            if gold_data is None:
                raise CureError(f"{code}: spec has {gold_key!r} but gold file not found: {args.gold}")
            gold_record = gold_data.get(code)
            if gold_record is None:
                raise CureError(f"{code}: gold record not found in {args.gold}")
            new_gold, gold_changes = cure_gold_record(gold_record, code, gold_new_values)
            gold_cured = bool(gold_changes)
            if gold_cured:
                new_gold_records[code] = new_gold
                print(f"{code}: TO CURE (gold) — " + " | ".join(gold_changes))
            else:
                print(f"{code}: ALREADY CURED (gold, skip)")

        if not canonical_cured and not gold_cured:
            already_cured_count += 1

    print("-" * 78)
    to_cure_count = len(set(new_canonical_records) | set(new_gold_records))
    print(f"summary: {to_cure_count} to cure, {already_cured_count} already cured, "
          f"{missing_count} missing, {len(problems)} problem(s)")

    if not args.apply:
        if problems:
            for p in problems:
                logger.error(p)
            return 1
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical+gold.")
        return 0

    # --apply path
    if new_canonical_records:
        for code, new_record in new_canonical_records.items():
            idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
            records[idx] = new_record
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d cured record(s) to %s", len(new_canonical_records), args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        run_sync_script()
        update_sidecar()
    else:
        logger.info("no canonical changes — skipping sync + sidecar update")

    if new_gold_records:
        assert gold_data is not None  # guaranteed by the loop above
        for code, new_gold in new_gold_records.items():
            gold_data[code] = new_gold
        tmp_gold = args.gold.with_suffix(args.gold.suffix + ".tmp")
        try:
            tmp_gold.write_text(
                json.dumps(gold_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            tmp_gold.replace(args.gold)
            logger.info("wrote %d cured gold record(s) to %s", len(new_gold_records), args.gold)
        except Exception:
            tmp_gold.unlink(missing_ok=True)
            raise
    else:
        logger.info("no gold changes — skipping gold write")

    if problems:
        for p in problems:
            logger.error(p)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
