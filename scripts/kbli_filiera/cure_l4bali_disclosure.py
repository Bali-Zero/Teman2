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
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Sibling-module import (same pattern as cure_metadata_pp28_sources.py): the
# structural "what does this verdict rest on?" predicates are shared with the
# census emitter so the two can never drift apart.
_FILIERA_DIR = Path(__file__).resolve().parent
if str(_FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(_FILIERA_DIR))

import _l4bali_basis as basis  # noqa: E402

logger = logging.getLogger("kbli_filiera.cure_l4bali_disclosure")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l4bali_disclosure_2026_07_19.json"
DEFAULT_CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE_FIELD = "kode_kbli_2025"

DISCLOSURE_PREFIX = "[derivation under review] "

# WAVE 1's sentence, kept ONLY so the migration below can recognise what it
# wrote. It named the internal key (`per_skala_disputed_pp28_collision (see
# _data_note)`) inside prose that `apps/mouth/src/lib/kbli-faq.ts` splices
# verbatim into a published FAQ answer — two raw JSON field names in a sentence
# a client reads. That is the same debt the catalogue's 392 raw-key editorial
# narrations represent, and a cure for honesty must not add to it. The key is
# NOT lost: it stays on the record, in `_data_note`, and in the cure spec, which
# is where a maintainer looks — the reader does not need it.
LEGACY_DISCLOSURE_SUFFIX_FMT = (
    " — NOTE: the risk tier this verdict was derived from has been detached to "
    "{disputed_key} (see _data_note); verdict pending re-derivation from the "
    "true risk tier (GARUDA-FILIERA)."
)
LEGACY_SUFFIX_RE = re.compile(
    r" — NOTE: the risk tier this verdict was derived from has been detached to "
    r"per_skala_disputed_\w+ \(see _data_note\); verdict pending re-derivation "
    r"from the true risk tier \(GARUDA-FILIERA\)\.$"
)
DISCLOSURE_SUFFIX_DISPUTED_KEY = (
    " — NOTE: the licensing rows this verdict's risk tier was read from have "
    "since been set aside as unverifiable for KBLI 2025, so the verdict cannot "
    "currently be re-derived; verdict pending re-derivation from the true risk "
    "tier (GARUDA-FILIERA)."
)
# Wave 2 (2026-07-25): the same defect on codes that were never given a
# disputed marker — nothing was disowned INTO a key, the OSS scope simply never
# resolved. Naming a `per_skala_disputed_*` key here would be a fabricated
# citation, so the suffix states what is actually true of the record instead.
#
# Deliberately field-name-free. `l4_bali.reason` is READER-FACING — it is the
# Bali badge tooltip and `kbli-faq.ts` splices it verbatim into a published FAQ
# answer — and the catalogue already carries 392 codes whose editorial prose
# narrates raw keys ("l4_bali_blocked is false"). Writing `_l2_status` or
# `per_skala` into a client sentence would add to exactly the debt this
# programme is paying down. Wave 1's suffix names the disputed key because
# there the key IS the provenance pointer for the disowned rows; here nothing
# was disowned, so there is nothing to point at and plain language is both the
# only accurate option and the better one.
#
# WORDING (F12, and a near-miss worth recording): an earlier draft of this
# sentence told the reader "the scope endpoint returns 404". It does not say
# that — `_l2_status = "no_oss_risk"` is written by
# `scripts/build_kbli_l2_oss_risk.py:163` whenever the dump line is MISSING, or
# the status is any non-200, or the payload says success=false. Asserting a
# specific HTTP status we never verified, inside the very sentence whose job is
# honesty, is the disease this programme cures. It now says only what the record
# supports, and speaks about OUR retrieval, never about what the regulator has
# or has not published.
DISCLOSURE_SUFFIX_NO_OSS_SCOPE = (
    " — NOTE: no KBLI-2025 risk scope for this code could be retrieved from the "
    "OSS API when this dataset was built, and no licensing rows are served, so "
    "the risk tier this verdict was derived from is not verifiable; verdict "
    "pending re-derivation from the true risk tier (GARUDA-FILIERA)."
)
# Wave 2b: a PARTIAL detach (PR #2921's `partial_detach` primitive) leaves rows
# in place while removing the one the verdict was computed from — so the record
# looks intact and reads stale. Field-name-free for the same reason as above.
DISCLOSURE_SUFFIX_DETACHED_TIER = (
    " — NOTE: the risk tier this verdict cites is no longer among this code's "
    "licensing rows — it was set aside as unverifiable while other rows were "
    "kept — so the verdict cannot be re-derived from what the record now holds; "
    "verdict pending re-derivation from the true risk tier (GARUDA-FILIERA)."
)
GAP_BASIS_DISPUTED_KEY = "disputed_key"
GAP_BASIS_NO_OSS_SCOPE = "no_oss_scope"
GAP_BASIS_DETACHED_TIER = "detached_tier"
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


def build_new_reason(original_reason: str, gap_basis: str, disputed_key: str | None = None) -> str:
    """Wrap the original reason in the disclosure, naming the REAL basis.

    One suffix per basis, and each says only what that basis supports:
      disputed_key   -> every row was disowned into that key; cite it (there the
                        key IS the provenance pointer to the disowned rows).
      no_oss_scope   -> nothing was disowned; no scope ever resolved from OSS.
                        Citing a key that does not exist would be a fabrication.
      detached_tier  -> rows survive, but not the one this verdict cites.
    """
    if gap_basis == GAP_BASIS_DISPUTED_KEY:
        if not disputed_key:
            raise CureError("disputed_key basis with no key to cite — refusing to invent one")
        return DISCLOSURE_PREFIX + original_reason + DISCLOSURE_SUFFIX_DISPUTED_KEY
    if gap_basis == GAP_BASIS_NO_OSS_SCOPE:
        return DISCLOSURE_PREFIX + original_reason + DISCLOSURE_SUFFIX_NO_OSS_SCOPE
    if gap_basis == GAP_BASIS_DETACHED_TIER:
        return DISCLOSURE_PREFIX + original_reason + DISCLOSURE_SUFFIX_DETACHED_TIER
    raise CureError(f"unknown gap_basis {gap_basis!r} — no suffix defined for it")


def reword_legacy_reason(reason: str) -> str | None:
    """Swap wave 1's key-naming suffix for the plain-language one.

    Returns the new reason, or None when this reason is not a wave-1 disclosure.
    The tail must match `LEGACY_SUFFIX_RE` EXACTLY (anchored at end-of-string):
    a reason that was hand-touched, double-suffixed, or written by some other
    pass is left alone and reported, never re-shaped on a guess.
    """
    match = LEGACY_SUFFIX_RE.search(reason)
    if not match:
        return None
    return reason[: match.start()] + DISCLOSURE_SUFFIX_DISPUTED_KEY


def plan_legacy_rewording(records: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    """(code -> new reason) for every record still carrying wave 1's wording.

    Scans ALL records, not just this spec's codes: the debt was created by an
    earlier wave and a cure applied to one lot only is how this catalogue keeps
    growing half-fixed classes.
    """
    rewordings: dict[str, str] = {}
    suspicious: list[str] = []
    for record in records:
        l4 = record.get("l4_bali")
        if not isinstance(l4, dict):
            continue
        reason = str(l4.get("reason") or "")
        if "has been detached to per_skala_disputed" not in reason:
            continue
        new_reason = reword_legacy_reason(reason)
        if new_reason is None:
            suspicious.append(str(record.get(CODE_FIELD)))
            continue
        rewordings[str(record.get(CODE_FIELD))] = new_reason
    return rewordings, suspicious


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

    # Wave-1 specs predate `gap_basis` and are all disputed-key based.
    gap_basis = entry.get("gap_basis", GAP_BASIS_DISPUTED_KEY)

    if gap_basis == GAP_BASIS_DISPUTED_KEY:
        disputed_key = entry["disputed_key"]
        if disputed_key not in record:
            return CurePlan(
                code,
                "skip_guard",
                f"disputed key {disputed_key!r} absent from record — code not yet detached "
                f"on this canonical (e.g. pending an unmerged PR); SKIPPED, not cured",
            )
    elif gap_basis == GAP_BASIS_NO_OSS_SCOPE:
        # Nothing was disowned into a key here; the claim this cure makes is
        # that no OSS scope resolved. Verify BOTH halves on the live record —
        # a gap healed since the spec was emitted must be skipped, never
        # disclosed with a statement that is no longer true.
        disputed_key = None
        if record.get("per_skala"):
            return CurePlan(
                code,
                "skip_guard",
                "per_skala is non-empty on this canonical — the risk layer has been "
                "restored or re-adjudicated since the spec was emitted, so the verdict "
                "no longer rests on a gap; SKIPPED, not cured",
            )
        if record.get("_l2_status") != "no_oss_risk":
            return CurePlan(
                code,
                "skip_guard",
                f"_l2_status is {record.get('_l2_status')!r}, not 'no_oss_risk' — the "
                "no-OSS-scope basis is not corroborated on this record; SKIPPED, not cured",
            )
    elif gap_basis == GAP_BASIS_DETACHED_TIER:
        # A partial detach: rows survive, but not the one this verdict cites.
        # Re-check that on the live record with the SAME rule that wrote the
        # verdict — if the tier came back (or the verdict was re-derived to
        # match what remains), disclosing would be a false statement.
        disputed_key = None
        if not basis.disputed_keys(record):
            return CurePlan(
                code,
                "skip_guard",
                "no per_skala_disputed_* key on this record — nothing was detached, so "
                "the partial-detach basis does not hold; SKIPPED, not cured",
            )
        if not record.get("per_skala"):
            return CurePlan(
                code,
                "skip_guard",
                "per_skala is empty — this is a FULL detach, not the partial-detach "
                "basis the spec recorded; SKIPPED, not cured (re-emit the spec)",
            )
        if basis.status_matches_surviving_rows(record.get("l4_bali", {}).get("status"), record) is not False:
            return CurePlan(
                code,
                "skip_guard",
                "the stored verdict is consistent with the rows this record still "
                "carries — its basis survived the detach; SKIPPED, not cured",
            )
    else:
        raise CureError(
            f"{code}: unknown gap_basis {gap_basis!r} — expected one of "
            f"{GAP_BASIS_DISPUTED_KEY!r}, {GAP_BASIS_NO_OSS_SCOPE!r}, "
            f"{GAP_BASIS_DETACHED_TIER!r}"
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
    new_l4["reason"] = build_new_reason(entry["expected_reason"], gap_basis, disputed_key)
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
    parser.add_argument(
        "--reword-legacy",
        action="store_true",
        help="also migrate every EXISTING wave-1 disclosure off the key-naming sentence "
        "(catalogue-wide, not spec-scoped) — reader-facing prose must not narrate JSON keys",
    )
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

    rewordings: dict[str, str] = {}
    if args.reword_legacy:
        rewordings, suspicious = plan_legacy_rewording(records)
        # A record already scheduled for cure gets the new wording from
        # build_new_reason, so it must not be rewritten twice.
        rewordings = {c: r for c, r in rewordings.items() if c not in to_apply}
        print("-" * 78)
        print(f"legacy rewording: {len(rewordings)} record(s) still carry wave 1's key-naming sentence")
        if suspicious:
            problems.append(
                f"{len(suspicious)} record(s) mention a detached disputed key in a shape this "
                f"migration does not recognise — inspect by hand, NOT rewritten: {sorted(suspicious)}"
            )
            print(f"  UNRECOGNISED SHAPE (left untouched): {sorted(suspicious)}")

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
    if to_apply or rewordings:
        for code, new_l4 in to_apply.items():
            idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
            records[idx]["l4_bali"] = new_l4
        for code, new_reason in rewordings.items():
            idx = next(i for i, r in enumerate(records) if r.get(CODE_FIELD) == code)
            records[idx]["l4_bali"]["reason"] = new_reason
        tmp_path = args.canonical.with_suffix(args.canonical.suffix + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=indent)
            tmp_path.replace(args.canonical)
            logger.info(
                "wrote %d cured + %d reworded record(s) to %s",
                len(to_apply), len(rewordings), args.canonical,
            )
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
