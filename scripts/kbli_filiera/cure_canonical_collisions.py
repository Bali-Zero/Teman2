#!/usr/bin/env python3
"""cure_canonical_collisions.py — deterministic false-friend detach compiler.

GARUDA-FILIERA Fase 1 (research/operations/2026-07-17-kbli-pilot-a1-results.md):
7 KBLI-2025 codes carry a contaminated `per_skala` licensing block (wrong-vintage
or wrong-source, image-verified by the pilot D6 gate). This script mechanically
applies the SAME detach pattern already shipped for 68112 (PR #2508/#2527):

  1. per_skala -> []  (frontend guards licensing.length > 0, so this renders an
     honest "not yet defined" gap instead of wrong data)
  2. the CURRENT per_skala value is moved verbatim into a new disputed key
     (never silently deleted). If the record also carries per_skala_legacy,
     BOTH are folded into the disputed key as {"per_skala": ..., "per_skala_legacy": ...}
     and the top-level per_skala_legacy key is removed.
  3. _data_note = the spec's data_note string (provenance, never authored here).
  4. pp28_sources / intel_2026 / judul / uraian / pma_* / status_mapping / every
     other field is left untouched.

This script NEVER invents a licensing value — it is pure DETACH+PRESERVE, driven
entirely by scripts/kbli_filiera/cure_specs/fase1_collisions.json (or whatever
--spec points to). It is also the ONLY sanctioned writer of the canonical KBLI
dataset: infra/claude-hooks/data_plane_guard.py blocks direct Edit/Write/sed/tee
on data/source_documents/KBLI_2025_FINAL_CLEAN.json for every path except this
program's own compilers/ (infra/claude-hooks/data-plane-registry.json, id
"kbli-filiera") — opening the file inside this script is what is sanctioned;
hand-editing it via Edit/Write/Bash text tools is not.

Usage:
  # dry run (default) — prints a per-code diff summary, writes nothing
  python scripts/kbli_filiera/cure_canonical_collisions.py

  # apply — mutates canonical, propagates to the 4 consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the vitest sha256 sidecar
  python scripts/kbli_filiera/cure_canonical_collisions.py --apply

  # subset
  python scripts/kbli_filiera/cure_canonical_collisions.py --only 49213 51103 --apply
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

logger = logging.getLogger("kbli_filiera.cure_canonical_collisions")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "fase1_collisions.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"


class CureError(RuntimeError):
    """A spec/canonical mismatch severe enough to make the run's exit non-zero."""


def _detect_indent(raw_text: str) -> int:
    """Measure the JSON indent width from the file's own formatting rather than
    assuming 2 — the dataset has always used 2-space indent, but Karpathy
    discipline says measure, don't presume."""
    for line in raw_text.splitlines()[1:8]:
        stripped = line.lstrip(" ")
        leading = len(line) - len(stripped)
        if leading > 0:
            return leading
    return 2


def load_spec(spec_path: Path) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if "disputed_key" not in spec or "codes" not in spec:
        raise CureError(f"{spec_path}: spec missing required 'disputed_key' or 'codes' key")
    if not isinstance(spec["codes"], list) or not spec["codes"]:
        raise CureError(f"{spec_path}: 'codes' must be a non-empty list")
    return spec


def _index_by_code(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r[CODE_FIELD]: r for r in records if CODE_FIELD in r}


class CurePlan:
    """Outcome of evaluating one spec entry against the loaded canonical.

    status:
      "apply"          — record will be mutated (see `preview` for the diff facts)
      "already-cured"  — per_skala == [] AND disputed_key present: idempotent no-op
      "ambiguous-skip" — per_skala == [] but NO disputed_key: refuse to guess, skip
      "missing"        — code not found in canonical at all
    """

    def __init__(
        self,
        code: str,
        status: str,
        *,
        current_row_count: int = 0,
        folds_legacy: bool = False,
        disputed_key: str = "",
        data_note: str = "",
    ) -> None:
        self.code = code
        self.status = status
        self.current_row_count = current_row_count
        self.folds_legacy = folds_legacy
        self.disputed_key = disputed_key
        self.data_note = data_note

    def describe(self) -> str:
        note_preview = (self.data_note[:80] + "…") if len(self.data_note) > 80 else self.data_note
        if self.status == "missing":
            return f"{self.code}: NOT FOUND IN CANONICAL — cannot cure"
        if self.status == "already-cured":
            return f"{self.code}: ALREADY CURED (skip) — per_skala==[] and {self.disputed_key!r} present"
        if self.status == "ambiguous-skip":
            return (
                f"{self.code}: AMBIGUOUS (skip, no clobber) — per_skala==[] but no "
                f"{self.disputed_key!r} key; could be a different prior cure"
            )
        return (
            f"{self.code}: per_skala {self.current_row_count} row(s) -> 0 | "
            f"fold per_skala_legacy: {self.folds_legacy} | disputed_key: {self.disputed_key} | "
            f"_data_note: {note_preview!r}"
        )


def plan_cure(record: dict[str, Any], entry: dict[str, Any], disputed_key: str) -> CurePlan:
    code = entry["code"]
    current_per_skala = record.get("per_skala")
    has_disputed = disputed_key in record
    is_empty = current_per_skala == []

    if is_empty and has_disputed:
        return CurePlan(code, "already-cured", disputed_key=disputed_key)
    if is_empty and not has_disputed:
        return CurePlan(code, "ambiguous-skip", disputed_key=disputed_key)

    row_count = len(current_per_skala) if isinstance(current_per_skala, list) else 0
    return CurePlan(
        code,
        "apply",
        current_row_count=row_count,
        folds_legacy="per_skala_legacy" in record,
        disputed_key=disputed_key,
        data_note=entry["data_note"],
    )


def apply_cure(record: dict[str, Any], entry: dict[str, Any], disputed_key: str) -> dict[str, Any]:
    """Return a NEW record dict with the cure applied, preserving the original
    field order and inserting the disputed key immediately after `per_skala`
    (matching the 68112 template) and `_data_note` at the very end (also
    matching the 68112 template)."""
    current_per_skala = record.get("per_skala")
    disputed_value: Any
    if "per_skala_legacy" in record:
        disputed_value = {
            "per_skala": current_per_skala,
            "per_skala_legacy": record["per_skala_legacy"],
        }
    else:
        disputed_value = current_per_skala

    new_record: dict[str, Any] = {}
    for key, value in record.items():
        if key == "per_skala_legacy":
            continue  # folded into disputed_value above; dropped from top level
        if key == "per_skala":
            new_record["per_skala"] = []
            new_record[disputed_key] = copy.deepcopy(disputed_value)
            continue
        new_record[key] = value
    new_record["_data_note"] = entry["data_note"]
    return new_record


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
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="cure spec JSON (default: fase1_collisions.json)")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL, help="canonical dataset to mutate")
    parser.add_argument("--only", nargs="+", default=None, help="restrict to these KBLI codes")
    parser.add_argument("--apply", action="store_true", help="mutate the canonical (default: dry-run, writes nothing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    spec = load_spec(args.spec)
    disputed_key: str = spec["disputed_key"]
    entries: list[dict[str, Any]] = spec["codes"]
    if args.only:
        wanted = set(args.only)
        entries = [e for e in entries if e["code"] in wanted]
        missing_requested = wanted - {e["code"] for e in entries}
        if missing_requested:
            raise CureError(f"--only requested codes not present in spec: {sorted(missing_requested)}")

    if not args.canonical.exists():
        raise CureError(f"canonical dataset not found: {args.canonical}")
    raw_text = args.canonical.read_text(encoding="utf-8")
    indent = _detect_indent(raw_text)
    dataset = json.loads(raw_text)
    records: list[dict[str, Any]] = dataset["data"]
    by_code = _index_by_code(records)

    plans: list[CurePlan] = []
    problems: list[str] = []
    for entry in entries:
        code = entry["code"]
        record = by_code.get(code)
        if record is None:
            plan = CurePlan(code, "missing")
            problems.append(f"spec code {code!r} not found in canonical {args.canonical}")
        else:
            plan = plan_cure(record, entry, disputed_key)
            if plan.status == "ambiguous-skip":
                problems.append(
                    f"code {code!r}: per_skala==[] with no {disputed_key!r} key — ambiguous prior "
                    "state, skipped to avoid clobbering an unrelated cure"
                )
        plans.append(plan)

    print(f"cure_canonical_collisions.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"disputed_key = {disputed_key!r}, indent = {indent}")
    print("-" * 78)
    for plan in plans:
        print(plan.describe())
    print("-" * 78)

    applied = [p for p in plans if p.status == "apply"]
    skipped = len(plans) - len(applied)
    print(f"summary: {len(applied)} to cure, {skipped} skipped/missing, {len(problems)} problem(s)")

    if not args.apply:
        if problems:
            for p in problems:
                logger.error(p)
            return 1
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 0

    # --apply path
    for entry, plan in zip(entries, plans):
        if plan.status != "apply":
            continue
        code = entry["code"]
        record = by_code[code]
        idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
        records[idx] = apply_cure(record, entry, disputed_key)

    if applied:
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d cured record(s) to %s", len(applied), args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        run_sync_script()
        update_sidecar()
    else:
        logger.info("nothing to apply — skipping sync + sidecar update")

    if problems:
        for p in problems:
            logger.error(p)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
