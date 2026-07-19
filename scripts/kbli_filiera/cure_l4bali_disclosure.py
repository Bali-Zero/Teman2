#!/usr/bin/env python3
"""cure_l4bali_disclosure.py — deterministic l4_bali disclosure cure.

GARUDA-FILIERA program (Lot 6 gate report Appendix A §A.2 finding, 2026-07-19):
a program-wide census (`census_disputed.py`, read-only) found that 56 of the
73 `per_skala_disputed_*`-carrying KBLI-2025 codes on origin/main have a
STALE-CERTIFYING `l4_bali` block — it derives the Bali-moratorium verdict from
a `kategori_risiko` tier that now exists ONLY in the disowned
`per_skala_disputed_pp28_collision` block (per_skala itself is `[]`), while
STILL asserting `confidence` MEDIUM/HIGH and `needs_review:false` — several
even `blocked:true` at HIGH confidence (e.g. 52105, the seed finding). The
8 pilot codes cured earlier (`cure_l4_editorial.py`, fase1_l4_editorial.json)
show the CORRECT disclosed template: confidence LOW, needs_review true, and a
reason that says so in plain language. The Lots 1-5 cure compilers detached
`per_skala` but never touched `l4_bali` for the REST of the 73 — that gap is
what this script closes for the 57 codes in
`cure_specs/l4bali_disclosure_2026_07_19.json` (56 STALE-CERTIFYING on main +
1 guarded, 80190, pending PR #2800).

This cure is DELIBERATELY narrower than `cure_l4_editorial.py`'s wholesale
`l4_bali` replacement (that script re-derives a NEW verdict — NON_CLASSIFICABILE
for the 8 pilot codes). Here the true risk tier is still unknown for all 57
codes, so the ONLY honest move is to disclose the derivation defect without
re-deriving anything:

  1. l4_bali.confidence -> "LOW"
  2. l4_bali.needs_review -> true
  3. l4_bali.reason -> the ORIGINAL reason text, prefixed with
     "[derivation under review] " and suffixed with a disclosure sentence
     naming the detached disputed key (see DISCLOSURE_PREFIX/DISCLOSURE_SUFFIX_FMT
     below) — modeled on the 8 pilot DISCLOSED records' own vocabulary
     ("has been detached", "pending re-derivation", "(GARUDA-FILIERA)").
  4. l4_bali.status and l4_bali.blocked are NEVER modified — flipping either
     would be a re-derivation requiring true risk (F15: the conservative
     posture stays; a record that reads `blocked:true` keeps reading
     `blocked:true`, now correctly flagged low-confidence/needs-review instead
     of falsely certified).
  5. moratorium / from_2020 / review_basis (when present) / any other l4_bali
     key are copied through UNCHANGED.

Per-code preconditions are spec-authored (`expected_status`/`expected_reason`/
`expected_confidence`/`expected_needs_review`/`expected_blocked`) and verified
before mutation — a record that has drifted from the spec's recorded pristine
state (and is not already in the cured state) is a CureError, never a guess.

GUARD (80190 / any future code lacking its disputed key): before mutating a
record, the compiler checks that `entry["disputed_key"]` is actually present
as a top-level key on the record. If absent, the code is SKIPPED WITH A
WARNING (never silently, never a CureError) — this is how 80190 (PR #2800,
`origin/kbli/lot6-data-apply`, not yet merged as of spec authoring) degrades
safely: re-running `--apply` after the merge (or after rebasing this branch
onto main) activates the cure with no spec change.

`editorial_residue_flagged` and `excluded_clean_ambiguous` in the spec are
BOOKKEEPING ONLY — this script never mutates intel_2026 editorial prose or
touches the 8 DISCLOSED / 9 CLEAN records. They are printed for visibility.

This script is the ONLY sanctioned writer of the canonical KBLI dataset for
this cure, same data-plane registration as cure_canonical_collisions.py /
cure_l4_editorial.py (all live under scripts/kbli_filiera/, the registry's
`compilers` glob for entry "kbli-filiera").

Usage:
  # dry run (default) — prints a per-code diff summary, writes nothing
  python scripts/kbli_filiera/cure_l4bali_disclosure.py

  # apply — mutates canonical, propagates to the 4 consumer copies via
  # sync_kbli_dataset.sh, recomputes+writes the vitest sha256 sidecar
  python scripts/kbli_filiera/cure_l4bali_disclosure.py --apply

  # subset
  python scripts/kbli_filiera/cure_l4bali_disclosure.py --only 52105 01700 --apply
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

logger = logging.getLogger("kbli_filiera.cure_l4bali_disclosure")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l4bali_disclosure_2026_07_19.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"

DISCLOSURE_PREFIX = "[derivation under review] "
DISCLOSURE_SUFFIX_FMT = (
    " — NOTE: the risk tier this verdict was derived from has been detached to "
    "{disputed_key} (see _data_note); verdict pending re-derivation from the "
    "true risk tier (GARUDA-FILIERA)."
)
# Marker used to detect "already cured" idempotently without re-deriving the
# suffix per disputed_key (the prefix alone is a sufficient, stable anchor).
CURED_MARKER = DISCLOSURE_PREFIX


class CureError(RuntimeError):
    """A spec/canonical mismatch severe enough to make the run's exit non-zero."""


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


def build_new_reason(original_reason: str, disputed_key: str) -> str:
    return DISCLOSURE_PREFIX + original_reason + DISCLOSURE_SUFFIX_FMT.format(disputed_key=disputed_key)


class CurePlan:
    """Outcome of evaluating one spec entry against the loaded canonical.

    status:
      "apply"           — record is in the spec's recorded pristine state;
                          l4_bali will be mutated (confidence/needs_review/reason).
      "already_cured"   — l4_bali already carries the disclosure marker,
                          confidence LOW, needs_review true — no-op.
      "skip_guard"      — entry["disputed_key"] is absent from the record
                          (e.g. 80190 pending PR #2800 merge) — SKIPPED WITH
                          A WARNING, never a CureError.
      "missing"         — code not found in canonical at all.
    """

    def __init__(self, code: str, status: str, detail: str, new_l4: dict[str, Any] | None = None):
        self.code = code
        self.status = status
        self.detail = detail
        self.new_l4 = new_l4


def evaluate_code(code: str, entry: dict[str, Any], by_code: dict[str, dict[str, Any]]) -> CurePlan:
    record = by_code.get(code)
    if record is None:
        return CurePlan(code, "missing", f"code {code!r} not found in canonical")

    disputed_key = entry["disputed_key"]
    if disputed_key not in record:
        return CurePlan(
            code,
            "skip_guard",
            f"disputed key {disputed_key!r} absent from record — code not yet detached "
            f"on this canonical (e.g. pending an unmerged PR); SKIPPED, not cured",
        )

    l4 = record.get("l4_bali")
    if not isinstance(l4, dict):
        raise CureError(f"{code}: l4_bali missing or not a dict — cannot cure")

    current_reason = l4.get("reason")
    current_confidence = l4.get("confidence")
    current_needs_review = l4.get("needs_review")
    current_blocked = l4.get("blocked")
    current_status = l4.get("status")

    expected_blocked = entry["expected_blocked"]
    expected_status = entry["expected_status"]
    if current_blocked != expected_blocked or current_status != expected_status:
        raise CureError(
            f"{code}: l4_bali.status/blocked drifted from spec expectation "
            f"(status={current_status!r} vs {expected_status!r}, "
            f"blocked={current_blocked!r} vs {expected_blocked!r}) — this cure "
            "NEVER modifies status/blocked, refusing to proceed on unexpected drift"
        )

    already_cured = (
        current_confidence == "LOW"
        and current_needs_review is True
        and isinstance(current_reason, str)
        and current_reason.startswith(CURED_MARKER)
    )
    if already_cured:
        return CurePlan(code, "already_cured", "l4_bali already disclosed — no-op")

    is_pristine = (
        current_reason == entry["expected_reason"]
        and current_confidence == entry["expected_confidence"]
        and current_needs_review == entry["expected_needs_review"]
    )
    if not is_pristine:
        raise CureError(
            f"{code}: l4_bali is neither in the spec's pristine state nor already "
            f"cured — data has drifted (reason={current_reason!r}, "
            f"confidence={current_confidence!r}, needs_review={current_needs_review!r}); "
            "refusing to guess"
        )

    new_l4 = copy.deepcopy(l4)
    new_l4["confidence"] = "LOW"
    new_l4["needs_review"] = True
    new_l4["reason"] = build_new_reason(entry["expected_reason"], disputed_key)
    return CurePlan(
        code,
        "apply",
        f"confidence {current_confidence!r}->LOW, needs_review {current_needs_review!r}->true, "
        f"reason disclosed ({len(current_reason)}->{len(new_l4['reason'])} chars)",
        new_l4=new_l4,
    )


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
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="cure spec JSON (default: l4bali_disclosure_2026_07_19.json)")
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

    spec: dict[str, Any] = json.loads(args.spec.read_text(encoding="utf-8"))
    all_codes: dict[str, Any] = spec["codes"]
    codes = sorted(all_codes.keys())
    if args.only:
        wanted = set(args.only)
        missing_requested = wanted - set(all_codes)
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

    print(f"cure_l4bali_disclosure.py — spec={args.spec} canonical={args.canonical} "
          f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print("-" * 78)

    problems: list[str] = []
    to_apply: dict[str, dict[str, Any]] = {}
    already_cured_count = 0
    skip_guard_count = 0
    missing_count = 0

    for code in codes:
        entry = all_codes[code]
        try:
            plan = evaluate_code(code, entry, by_code)
        except CureError as exc:
            problems.append(str(exc))
            print(f"{code}: CURE ERROR — {exc}")
            continue

        if plan.status == "missing":
            missing_count += 1
            problems.append(f"spec code {code!r} not found in canonical {args.canonical}")
            print(f"{code}: NOT FOUND IN CANONICAL — cannot cure")
        elif plan.status == "skip_guard":
            skip_guard_count += 1
            note = entry.get("pending_pr_note", "")
            print(f"{code}: SKIPPED (guard) — {plan.detail}" + (f" | {note}" if note else ""))
        elif plan.status == "already_cured":
            already_cured_count += 1
            print(f"{code}: ALREADY CURED (skip)")
        elif plan.status == "apply":
            to_apply[code] = plan.new_l4  # type: ignore[assignment]
            print(f"{code}: TO CURE — {plan.detail}")
        else:  # pragma: no cover - defensive
            raise CureError(f"{code}: unknown plan status {plan.status!r}")

    print("-" * 78)
    editorial_flagged = spec.get("editorial_residue_flagged", [])
    excluded_clean = spec.get("excluded_clean_ambiguous", {})
    print(
        f"summary: {len(to_apply)} to cure, {already_cured_count} already cured, "
        f"{skip_guard_count} skipped (guard), {missing_count} missing, "
        f"{len(problems)} problem(s)"
    )
    print(
        f"housekeeping (bookkeeping only, not mutated by this script): "
        f"{len(editorial_flagged)} editorial-residue-flagged, "
        f"{len(excluded_clean)} excluded-clean-ambiguous"
    )
    if editorial_flagged:
        print(f"  editorial_residue_flagged: {editorial_flagged}")
    if excluded_clean:
        print(f"  excluded_clean_ambiguous: {sorted(excluded_clean.keys())}")

    if not args.apply:
        if problems:
            for p in problems:
                logger.error(p)
            return 1
        print("DRY RUN — no files written. Re-run with --apply to mutate the canonical.")
        return 0

    # --apply path
    if to_apply:
        for code, new_l4 in to_apply.items():
            idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
            records[idx]["l4_bali"] = new_l4
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info("wrote %d cured record(s) to %s", len(to_apply), args.canonical)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        run_sync_script()
        update_sidecar()
    else:
        logger.info("no canonical changes — skipping sync + sidecar update")

    if problems:
        for p in problems:
            logger.error(p)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
