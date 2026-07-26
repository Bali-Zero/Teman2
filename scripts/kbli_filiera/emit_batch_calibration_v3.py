#!/usr/bin/env python3
"""emit_batch_calibration_v3.py — GARUDA-FILIERA Batch A CALIBRATION REGISTRY v3
compiler (Lot 3 conductor gate sign-off condition (3) — Lot 4 precondition).

`research/operations/2026-07-19-kbli-batch-a-lot3-conductor-gate.md` sign-off:
"Lot 4 is authorized ONLY after: (1) cross-family m1/m5 adjudicated in an
appendix to this report, (2) the Lot 3 cure shipped, (3) the v3 registry
re-salt shipped." Condition (1) is MET in that report's own Appendix A
(m1 5/5=1.00, m5-NEG 3/3=1.00). This compiler ships condition (3).

This compiler is the SUCCESSOR artifact writer to v2. It does NOT touch the
v2 artifact (`batchA-calibration-v2.{json,md}`) — that artifact is SIGNED and
is NEVER rewritten (scar W88/#9: a signed artifact is historically accurate
forever; corrections land in a new artifact, never an edit to the old one).
v3 writes its OWN files:

  data/kbli-filiera/batch-reports/batchA-calibration-v3.json
  data/kbli-filiera/batch-reports/batchA-calibration-v3.md

Reuse (import, not copy — plan §4 "deterministic compilers are the ONLY
writers"; this compiler reuses v2's fencing/pin/eligibility primitives
verbatim, and v2 in turn reused v1's, so the three artifacts can never
silently diverge on how they read the canonical):
  - `_fenced_canonical_blob`, `_sha256_file`, `_load_membership`,
    `_validate_membership_pin`, `_canonical_revision`, `eligible_positive_codes`,
    `CalibrationError`, `PILOT_A1` (m4 baseline, invariant from v1) — imported
    from v2, which itself re-exports them verbatim from v1 (emit_batch_calibration.py),
    never redefined at any generation.
  - `LOT1_QUARANTINED_CODES`, `LOT1_POSITIVE_REVEALED`, `eligible_positive_codes_v2`
    — imported from v2 directly (the Lot-1 exclusion is a precondition v3 layers
    on top of, never re-derived).

Inputs (all pinned, no network — same as v1/v2):
  - canonical:   data/source_documents/KBLI_2025_FINAL_CLEAN.json (fenced)
  - manifest:    data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json
  - membership:  data/kbli-filiera/membership/batch-a-members.json

Control limits v3 (conductor-ruled across the Lot 2 + Lot 3 conductor gate
reports, PRs #2753 and #2768):
  m1: floor >= 0.75 INVARIANT. cross-family extractor-vs-extractor IAA IS the
      measure (scar W100) — same-family (D1-vs-D5) agreement is NEVER an m1
      reading, however high it reads. Three lot readings on file: Lot 1 0.385
      (TRUE cross-family, BREACH — Lot 1 gate report §7), Lot 2 1.00 (TRUE
      cross-family, Appendix A — supersedes the same-family 0.538 the first
      signing mislabeled as m1), Lot 3 1.00 (TRUE cross-family, Appendix A).
  m2: certification-rate band [0.20, 0.85] INVARIANT. Lot 1/2/3 all read
      0.000 — a DECLARED-BREACH regime that has now held for three
      consecutive lots (same disease band, not instrument drift; per-lot
      explicit conductor adjudication required each time, no auto-resume,
      no floor re-registration).
  m3: refutation-category registry INVARIANT from v2 (closed list of 7,
      `phantom_source_pointer` already renamed at v2). Zero new categories
      surfaced in Lot 2 or Lot 3 — both gate reports confirm every seen
      category is in the v2 closed registry.
  m4: INVARIANT from v1 (ceiling 400000; pilot avg/max pinned as in v1/v2).
  m5: == 1.00 any-miss-halts INVARIANT, PLUS two going-forward rulings now on
      file: (a) the NEG-miss per-ancestor image-grade ruling (precedent:
      49213, plan A-6(b)-RESOLVED, carried from v2 unchanged); (b) a NEW
      POS-disqualification ruling — a POS control later found contaminated
      with a TRUE finding is DISQUALIFIED as a control (never scored as a
      miss on the extracting seat) and folds into the standalone
      metadata-fix cure list (precedent: 10433, Lot 2 conductor gate
      Appendix A — the THIRD contaminated "clean" control found that day,
      after 52101 and 46100).

POS pre-verification rule (NEW, Lot 3 Appendix A / plan A-6 successor rule):
  the v3 registry's `gold_sets.positive_control.pos_preverification_required`
  flag documents that POS controls must be pre-verified on BOTH crosswalk
  directions (forward Lampiran 5 AND reverse Lampiran 10) BEFORE enrollment
  as a gold control — not merely digest-selected by lowest sha256. Lot 3's
  2/2 clean controls (vs 0/2 in Lot 2) is the validation: pre-verified
  controls behave. Pre-verification is executed by the CONDUCTOR at REVEAL
  time (post-lot-close), per the Lot 3 gate report's own control protocol
  note (§4: "Control protocol validated: pre-verify on BOTH directions").

Gold sets v3 (digest-pinned, blind-to-lanes, re-salted "v3" — NEW salt so a
v2 digest and a v3 digest for the SAME code never collide even for a code
appearing in both generations):
  NEGATIVE (salt "v3") = the 47 codes cured as of Lot-3 close: the 21 v2
      NEGATIVE codes (8 phase-1 cured + 13 Lot-1 quarantined) + the 13 Lot-2
      quarantined codes + the 13 Lot-3 quarantined codes.
  POSITIVE (salt "v3") = the 8 lowest sha256(code|manifest_digest|salt) among
      codes eligible under v1's predicate, EXCLUDING BOTH the 8 Lot-1
      positive controls (v2's exclusion, unchanged) AND the 8 Lot-2 positive
      controls revealed at Lot 2's cross-family Appendix A (plan §5 reveal
      rule — all 8 are burned, never re-used as a gold control, regardless
      of whether any individual code was itself later found contaminated;
      10433 — one of the 8 — was ADDITIONALLY found to be a true finding
      (Lot 2 Appendix A) and joins the standalone metadata-fix cure list,
      but its exclusion here is unconditional the same as the other 7).
  Both lists are committed as sha256 hex digests ONLY; plaintext is never
  printed or written by this compiler.

Determinism (G16): same inputs => byte-identical files; sorted keys; trailing
newline. PINNED_DATE is a literal, never wall-clock.

Usage:
    python scripts/kbli_filiera/emit_batch_calibration_v3.py            # dry-run
    python scripts/kbli_filiera/emit_batch_calibration_v3.py --apply    # write both files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# --- reuse v2 (import, not copy — v2 itself reused v1 verbatim) ------------
FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))
import emit_batch_calibration as v1  # noqa: E402
import emit_batch_calibration_v2 as v2  # noqa: E402

REPO_ROOT = v2.REPO_ROOT
CANONICAL = v2.CANONICAL
CANONICAL_REL = v2.CANONICAL_REL
MANIFEST_PATH = v2.MANIFEST_PATH
MEMBERSHIP_PATH = v2.MEMBERSHIP_PATH
PLAN_PATH = v2.PLAN_PATH
CalibrationError = v2.CalibrationError

# Reused verbatim from v2 (which itself reuses v1) — plan §4 "deterministic
# compilers are the ONLY writers"; these primitives must never fork between
# generations or the artifacts could silently disagree on fencing/pin/
# eligibility semantics.
_sha256_file = v2._sha256_file
_canonical_revision = v2._canonical_revision
_fenced_canonical_blob = v2._fenced_canonical_blob
_load_membership = v2._load_membership
_validate_membership_pin = v2._validate_membership_pin
eligible_positive_codes = v2.eligible_positive_codes  # v1's raw base predicate

OUT_MD = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration-v3.md"
OUT_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration-v3.json"

# Pinned constant — never Date.now()/wall-clock (G16 determinism).
PINNED_DATE = "2026-07-19"

CONDUCTOR_SIGN_OFF = "SIGNED — Fable conductor session (MANDATO S2, post-Lot-3-GO), 2026-07-19"

PREDECESSOR_ARTIFACT_NOTE = (
    "data/kbli-filiera/batch-reports/batchA-calibration-v2.json (v2) — SIGNED, "
    "NEVER rewritten (scar W88/#9). This v3 file is the successor artifact "
    "mandated by the Lot 3 conductor gate report's sign-off condition (3) "
    "(research/operations/2026-07-19-kbli-batch-a-lot3-conductor-gate.md); it "
    "does not edit or supersede v2's historical record, only the registry "
    "going forward."
)

# --- m1 (invariant floor; three lot readings on file, all TRUE cross-family) -
M1_FLOOR = 0.75
M1_PRINCIPLE = (
    "cross-family extractor-vs-extractor IAA IS the measure (scar W100); "
    "same-family (D1-vs-D5) agreement is NEVER an m1 reading, however high "
    "it reads — it measures transcription fidelity, not truth. Every m1 "
    "reading recorded in this registry is the TRUE cross-family figure, "
    "never a same-family proxy."
)
M1_LOT1_READING = 0.385
M1_LOT1_STATE = "declared-breach"
M1_LOT1_NOTE = "TRUE cross-family (GLM-blind vs lane D1), Lot 1 gate report §7 — a real floor breach, not a proxy mislabel."
M1_LOT2_READING = 1.00
M1_LOT2_STATE = "measured, no breach"
M1_LOT2_NOTE = (
    "TRUE cross-family (Lot 2 gate report Appendix A, 5/5 lot codes blind-concur) — "
    "supersedes the first signing's same-family 0.538 figure, which was a mislabel "
    "(a red-team MAJOR), never a valid m1 reading."
)
M1_LOT3_READING = 1.00
M1_LOT3_STATE = "measured, no breach"
M1_LOT3_NOTE = (
    "TRUE cross-family (Lot 3 gate report Appendix A, 5/5 lot codes blind-concur, "
    "including an independent re-derivation of 64940's true ancestor 64992)."
)

# --- m2 (band invariant; declared-breach regime now held for 3 lots) --------
M2_FLOOR = 0.20
M2_CEILING = 0.85
M2_LOT1_READING = 0.000
M2_LOT2_READING = 0.000
M2_LOT3_READING = 0.000
M2_STATE = "declared-breach"
M2_RULE = (
    "per-lot explicit conductor adjudication required; no auto-resume; no "
    "floor re-registration (the advisory-floor-0.0 proposal was withdrawn, "
    "plan A-4). Three consecutive 0.000 readings (Lot 1/2/3) are read as the "
    "true state of the disease band, not instrument drift — pausing the "
    "program on this metric alone would reward the disease."
)

# --- m3 (closed list, INVARIANT from v2 — zero new categories Lot 2/Lot 3) --
REFUTATION_CATEGORIES_V3: tuple[str, ...] = v2.REFUTATION_CATEGORIES_V2
RENAMED_CATEGORIES: dict[str, str] = dict(v2.RENAMED_CATEGORIES)
RENAMED_NOTE = v2.RENAMED_NOTE
M3_NOTE = (
    "closed-7 registry INVARIANT from v2 — zero new categories surfaced in "
    "either Lot 2 (3 seen: payload_cross_contamination, source_absent_in_vault, "
    "mapping_metadata_false) or Lot 3 (5 seen, adding illegitimate_inheritance "
    "and unresolvable_source_pointer to the seen set) — every category in both "
    "lots was already in the v2 closed list."
)

# --- m4 — INVARIANT from v1 (reused, never redefined) -----------------------
M4_CEILING = 400000

# --- m5 (invariant + two going-forward rulings on file) ---------------------
M5_REQUIRED = 1.00
M5_NEG_MISS_RULING = v2.M5_NEG_MISS_RULING  # carried verbatim (49213 precedent)
M5_POS_DISQUALIFIED_RULING = (
    "a POS control later found contaminated with a TRUE finding is "
    "DISQUALIFIED as a control (never scored as a miss on the extracting "
    "seat — the seat found a real defect, it just found it on a code the "
    "conductor had mis-enrolled as 'clean') and folds into the standalone "
    "metadata-fix cure list. Precedent: 10433 (Lot 2 conductor gate "
    "Appendix A) — the THIRD contaminated 'clean' control found that "
    "session (after 52101 and 46100), all on the crosswalk-metadata layer. "
    "Going forward, this class of miss is prevented at the source by the "
    "pos_preverification_required rule (see gold_sets.positive_control), "
    "not merely adjudicated after the fact."
)

# --- gold sets v3 -------------------------------------------------------------
# NEW salt so a v2 digest and a v3 digest for the SAME code never collide —
# lanes cannot cross-reference an earlier reveal to shortcut the blind check.
NEGATIVE_SALT = "v3"
POSITIVE_SALT = "v3"

# The 13 Lot-2 quarantined codes (conductor gate report PR #2753, second
# signing + Appendix A); plaintext lives here (module constant, source
# input) but is NEVER written into the artifact or printed, only its digest.
LOT2_QUARANTINED_CODES: tuple[str, ...] = (
    "42999",
    "47771",
    "49233",
    "49296",
    "50113",
    "52103",
    "52105",
    "52211",
    "52219",
    "52232",
    "52239",
    "52299",
    "59131",
)

# The 13 Lot-3 quarantined codes (conductor gate report PR #2768, second
# signing + Appendix A); plaintext lives here (module constant, source
# input) but is NEVER written into the artifact or printed, only its digest.
LOT3_QUARANTINED_CODES: tuple[str, ...] = (
    "60101",
    "60103",
    "60201",
    "60203",
    "60311",
    "61905",
    "61909",
    "64110",
    "64220",
    "64320",
    "64330",
    "64920",
    "64940",
)

# The 8 Lot-2 POSITIVE controls revealed at Lot 2's cross-family Appendix A
# (plan §5 reveal rule, post lot-close) — burned: never re-registered as a
# gold control in v3 or later, regardless of individual disposition. One of
# these (10433) was ADDITIONALLY disqualified as a TRUE finding (see
# M5_POS_DISQUALIFIED_RULING); its exclusion here is unconditional, the same
# as the other 7 which remain valid (46329 HIT clean) or simply un-sampled.
LOT2_POSITIVE_REVEALED: tuple[str, ...] = (
    "10433",
    "46329",
    "46631",
    "42204",
    "06202",
    "23129",
    "01285",
    "47711",
)
LOT2_POS_BURN_NOTE = (
    "8 codes revealed at the Lot 2 cross-family Appendix A (2026-07-18) — the "
    "committed v2-lot2 digests, derivation independently replicated, matched "
    "byte-for-byte. 10433 is ADDITIONALLY a disqualified control (a TRUE "
    "finding, see m5_gold_set_hit_rate.pos_disqualified_ruling and the "
    "standalone metadata-fix cure metadata_fixes_2026_07_19.json) — it is "
    "excluded here for the SAME reveal-burn reason as the other 7, not "
    "specially; all 8 are permanently ineligible as v3+ gold controls."
)

CONDUCTOR_GATE_REPORT_PATH = "research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md"
LOT1_PR_REFS = "PR #2721 (docs) + PR #2725 (data apply)"
LOT2_GATE_REPORT_PATH = "research/operations/2026-07-18-kbli-batch-a-lot2-conductor-gate.md"
LOT2_PR_REFS = "PR #2753 (docs, second signing + Appendix A) + PR #2761 (data apply)"
LOT3_GATE_REPORT_PATH = "research/operations/2026-07-19-kbli-batch-a-lot3-conductor-gate.md"
LOT3_PR_REFS = "PR #2768 (docs, second signing + Appendix A) + PR #2769 (data apply)"


def _digest_v3(code: str, manifest_digest: str, salt: str) -> str:
    return hashlib.sha256(f"{code}|{manifest_digest}|{salt}".encode()).hexdigest()


def eligible_positive_codes_v3(records: list[dict[str, Any]]) -> list[str]:
    """v2's already-filtered pool (v1 predicate, minus the 8 Lot-1 revealed
    positive controls), further EXCLUDING the 8 Lot-2 revealed positive
    controls (burned at Lot 2's cross-family Appendix A)."""
    excluded = set(LOT2_POSITIVE_REVEALED)
    return [code for code in v2.eligible_positive_codes_v2(records) if code not in excluded]


def select_positive_digests_v3(
    records: list[dict[str, Any]], manifest_digest: str, n: int = 8
) -> list[str]:
    eligible = eligible_positive_codes_v3(records)
    if len(eligible) < n:
        raise CalibrationError(
            f"only {len(eligible)} eligible v3 positive-control codes "
            f"(post Lot-1+Lot-2-reveal exclusion), need >= {n}"
        )
    digests = sorted(_digest_v3(c, manifest_digest, POSITIVE_SALT) for c in eligible)
    return digests[:n]


def negative_digests_v3(manifest_digest: str) -> list[str]:
    codes = (
        set(v1.NEGATIVE_CONTROL_CODES)
        | set(v2.LOT1_QUARANTINED_CODES)
        | set(LOT2_QUARANTINED_CODES)
        | set(LOT3_QUARANTINED_CODES)
    )
    return sorted(_digest_v3(c, manifest_digest, NEGATIVE_SALT) for c in codes)


def build_context(
    *,
    canonical_revision: str,
    manifest_digest: str,
    membership_sha256: str,
    eligible_population_before_exclusion: int,
    eligible_population_after_lot1_exclusion: int,
    eligible_population_after_exclusion: int,
    positive_digests: list[str],
    neg_digests: list[str],
) -> dict[str, Any]:
    """Pure assembly of the artifact context — no I/O. Same inputs =>
    byte-identical render (G16)."""
    return {
        "batch": "A",
        "artifact_version": "v3",
        "plan": PLAN_PATH,
        "date": PINNED_DATE,
        "predecessor_artifact": PREDECESSOR_ARTIFACT_NOTE,
        "precondition": (
            "Lot 3 conductor gate report sign-off condition (3) "
            f"({LOT3_GATE_REPORT_PATH}): 'Lot 4 is authorized ONLY after: "
            "(1) cross-family m1/m5 adjudicated in an appendix to this "
            "report, (2) the Lot 3 cure shipped, (3) the v3 registry "
            "re-salt shipped.' This re-emission ships condition (3)."
        ),
        "pinned_revisions": {
            "canonical_git_revision": canonical_revision,
            "canonical_path": CANONICAL_REL,
            "manifest_path": "data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json",
            "manifest_sha256": manifest_digest,
            "membership_path": "data/kbli-filiera/membership/batch-a-members.json",
            "membership_sha256": membership_sha256,
        },
        "pilot_a1_m4_baseline": {
            "avg_tokens_per_code": v1.PILOT_A1["avg_tokens_per_code"],
            "max_tokens_per_code": v1.PILOT_A1["max_tokens_per_code"],
            "max_tokens_code_digest_only": True,
        },
        "control_limits": {
            "m1_blind_concordance": {
                "name": (
                    "cross-family extractor-vs-extractor IAA (lane D1 vs "
                    "blind cross-family extractor with vision)"
                ),
                "floor": M1_FLOOR,
                "floor_str": "0.75",
                "principle": M1_PRINCIPLE,
                "lot1_reading": M1_LOT1_READING,
                "lot1_reading_str": "0.385",
                "lot1_state": M1_LOT1_STATE,
                "lot1_note": M1_LOT1_NOTE,
                "lot2_reading": M1_LOT2_READING,
                "lot2_reading_str": "1.00",
                "lot2_state": M1_LOT2_STATE,
                "lot2_note": M1_LOT2_NOTE,
                "lot3_reading": M1_LOT3_READING,
                "lot3_reading_str": "1.00",
                "lot3_state": M1_LOT3_STATE,
                "lot3_note": M1_LOT3_NOTE,
                "on_breach": "lane pauses at lot boundary, conductor-signed resume note in plan §8",
            },
            "m2_certification_rate": {
                "name": "certification rate per lot",
                "floor": M2_FLOOR,
                "floor_str": "0.20",
                "ceiling": M2_CEILING,
                "ceiling_str": "0.85",
                "lot1_reading": M2_LOT1_READING,
                "lot1_reading_str": "0.000",
                "lot2_reading": M2_LOT2_READING,
                "lot2_reading_str": "0.000",
                "lot3_reading": M2_LOT3_READING,
                "lot3_reading_str": "0.000",
                "state": M2_STATE,
                "rule": M2_RULE,
                "on_breach": "lane pauses (ceiling breach = drift suspicion), conductor-signed resume note",
            },
            "m3_refutation_categories": {
                "name": "refutation-category registry (closed list) v3 (invariant from v2)",
                "categories": list(REFUTATION_CATEGORIES_V3),
                "renamed": {
                    "from": "phantom_source_pointer",
                    "to": "unresolvable_source_pointer",
                    "note": RENAMED_NOTE,
                },
                "note": M3_NOTE,
                "on_breach": "any category outside the registry = automatic lot pause + conductor triage",
            },
            "m4_tokens_per_dossier": {
                "name": "tokens/dossier ceiling",
                "ceiling": M4_CEILING,
                "ceiling_str": "400000",
                "pilot_avg": v1.PILOT_A1["avg_tokens_per_code"],
                "pilot_max": v1.PILOT_A1["max_tokens_per_code"],
                "on_breach": "lane pauses, investigate runaway",
            },
            "m5_gold_set_hit_rate": {
                "name": "gold-set hit rate",
                "required": M5_REQUIRED,
                "required_str": "1.00",
                "on_breach": "any miss halts the lot immediately",
                "neg_miss_ruling": M5_NEG_MISS_RULING,
                "pos_disqualified_ruling": M5_POS_DISQUALIFIED_RULING,
            },
        },
        "gold_sets": {
            "negative_control": {
                "count": len(neg_digests),
                "salt": NEGATIVE_SALT,
                "eligibility": (
                    "the 47 codes cured as of Lot 3 close: the 21 v2 NEGATIVE "
                    "codes (8 phase-1 cured + 13 Lot-1 quarantined) + the 13 "
                    "Lot-2 quarantined codes + the 13 Lot-3 quarantined codes"
                ),
                "digest_formula": 'sha256(code + "|" + manifest_digest + "|v3")',
                "digests": neg_digests,
            },
            "positive_control": {
                "count": len(positive_digests),
                "salt": POSITIVE_SALT,
                "eligible_population_before_exclusion": eligible_population_before_exclusion,
                "eligible_population_after_lot1_exclusion": eligible_population_after_lot1_exclusion,
                "excluded_lot1_revealed_positive_controls": len(v2.LOT1_POSITIVE_REVEALED),
                "excluded_lot2_revealed_positive_controls": len(LOT2_POSITIVE_REVEALED),
                "eligible_population_after_exclusion": eligible_population_after_exclusion,
                "eligibility_predicate": v1.POSITIVE_ELIGIBILITY_PREDICATE,
                "selection_rule": (
                    "among eligible codes EXCLUDING both the 8 Lot-1 AND the "
                    '8 Lot-2 revealed positive controls (16 burned total), '
                    'the 8 with the lowest sha256(code + "|" + manifest_digest '
                    '+ "|v3") hex digest, sorted ascending — deterministic, '
                    "never conductor-picked"
                ),
                "digest_formula": 'sha256(code + "|" + manifest_digest + "|v3")',
                "digests": positive_digests,
                "lot2_burn_note": LOT2_POS_BURN_NOTE,
                "pos_preverification_required": True,
                "pos_preverification_rule": (
                    "POS controls are pre-verified on BOTH crosswalk directions "
                    "(forward BPS Lampiran 5 AND reverse Lampiran 10) BEFORE "
                    "enrollment as a gold control — not merely digest-selected "
                    "by lowest sha256. Pre-verification is executed by the "
                    "CONDUCTOR at REVEAL time (post-lot-close), per the Lot 3 "
                    "gate report's control protocol note (§4): 'pre-verify on "
                    "BOTH directions -> 2/2 clean controls (vs 0/2 in Lot 2)' "
                    "— this is now the standing protocol for every lot from "
                    "v3 forward."
                ),
            },
            "reveal_rule": (
                "Plaintext code lists for both control classes are revealed "
                "in the lot report AFTER the lot closes (plan §5). Never before."
            ),
        },
        "lot1_outcome": {
            "quarantined": 13,
            "certified": 0,
            "m1_reading": M1_LOT1_READING,
            "m1_state": M1_LOT1_STATE,
            "m2_reading": M2_LOT1_READING,
            "m2_state": M2_STATE,
            "m3_state": "pause",
            "m3_new_categories": 2,
            "m5_neg_hit_rate": "7/8",
            "m5_halt_status": "halt lifted per A-6(b)-RESOLVED",
            "references": {
                "conductor_gate_report": CONDUCTOR_GATE_REPORT_PATH,
                "prs": LOT1_PR_REFS,
            },
        },
        "lot2_outcome": {
            "quarantined": 13,
            "certified": 0,
            "innocence_controls": "0/2 true-clean (BOTH contaminated on the crosswalk-metadata layer: 52101 lane-quarantined true finding, 46100 retro-quarantined post-red-team)",
            "m1_reading": M1_LOT2_READING,
            "m1_state": M1_LOT2_STATE,
            "m2_reading": M2_LOT2_READING,
            "m2_state": M2_STATE,
            "m3_state": "pass (3 seen, all in v2 closed registry)",
            "m5_neg_hit_rate": "3/3",
            "m5_pos_hit_rate": "1 valid HIT (46329) + 1 DISQUALIFIED (10433, true finding)",
            "references": {
                "conductor_gate_report": LOT2_GATE_REPORT_PATH,
                "prs": LOT2_PR_REFS,
            },
        },
        "lot3_outcome": {
            "quarantined": 13,
            "certified": 0,
            "innocence_controls": "2/2 true-clean (59140, 59201 — first lot to validate the pre-verify-both-directions control protocol)",
            "m1_reading": M1_LOT3_READING,
            "m1_state": M1_LOT3_STATE,
            "m2_reading": M2_LOT3_READING,
            "m2_state": M2_STATE,
            "m3_state": "pass (5 seen, all in v2 closed registry)",
            "m5_neg_hit_rate": "3/3",
            "m5_pos_hit_rate": "not run (POS leg deliberately skipped — v2-lot2 plaintexts burned, v3 re-salt ships in this PR)",
            "references": {
                "conductor_gate_report": LOT3_GATE_REPORT_PATH,
                "prs": LOT3_PR_REFS,
            },
        },
        "pause_resume_protocol": (
            "Any control-limit breach (m1-m5) pauses the affected lane at the lot boundary. "
            f"Resume requires a conductor-signed note appended to {PLAN_PATH} §8, citing the "
            "specific breached metric and the root cause. No silent resume."
        ),
        "conductor_sign_off": CONDUCTOR_SIGN_OFF,
    }


def render_markdown(ctx: dict[str, Any]) -> str:
    rev = ctx["pinned_revisions"]
    cl = ctx["control_limits"]
    gs = ctx["gold_sets"]
    lot1, lot2, lot3 = ctx["lot1_outcome"], ctx["lot2_outcome"], ctx["lot3_outcome"]

    lines: list[str] = []
    lines.append("# Batch A — calibration registry v3 (Lot 3 gate sign-off condition (3))")
    lines.append("")
    lines.append(f"- **Batch:** {ctx['batch']}")
    lines.append(f"- **Artifact version:** {ctx['artifact_version']}")
    lines.append(f"- **Date:** {ctx['date']}")
    lines.append(f"- **Plan:** `{ctx['plan']}`")
    lines.append("")
    lines.append(f"> **Predecessor:** {ctx['predecessor_artifact']}")
    lines.append("")
    lines.append(f"> **Precondition:** {ctx['precondition']}")
    lines.append("")

    lines.append("## Pinned revisions")
    lines.append("")
    lines.append("| Artifact | Pin |")
    lines.append("| --- | --- |")
    lines.append(f"| canonical (`{rev['canonical_path']}`) | git revision `{rev['canonical_git_revision']}` |")
    lines.append(f"| vault manifest (`{rev['manifest_path']}`) | sha256 `{rev['manifest_sha256']}` |")
    lines.append(f"| membership (`{rev['membership_path']}`) | sha256 `{rev['membership_sha256']}` |")
    lines.append("")

    lines.append("## Control limits m1-m5 (v3 — three-lot registry)")
    lines.append("")
    m1, m2, m3, m4, m5 = (
        cl["m1_blind_concordance"],
        cl["m2_certification_rate"],
        cl["m3_refutation_categories"],
        cl["m4_tokens_per_dossier"],
        cl["m5_gold_set_hit_rate"],
    )
    lines.append("| # | Metric | Limit | Lot-1 | Lot-2 | Lot-3 | On breach |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    lines.append(
        f"| m1 | {m1['name']} | floor {m1['floor_str']} | "
        f"{m1['lot1_reading_str']} ({m1['lot1_state']}) | "
        f"{m1['lot2_reading_str']} ({m1['lot2_state']}) | "
        f"{m1['lot3_reading_str']} ({m1['lot3_state']}) | {m1['on_breach']} |"
    )
    lines.append(
        f"| m2 | {m2['name']} | floor {m2['floor_str']} / ceiling {m2['ceiling_str']} | "
        f"{m2['lot1_reading_str']} | {m2['lot2_reading_str']} | {m2['lot3_reading_str']} | "
        f"{m2['on_breach']} |"
    )
    lines.append(
        f"| m3 | {m3['name']} | closed list: {', '.join('`' + c + '`' for c in m3['categories'])} "
        f"| pass | pass | pass | {m3['on_breach']} |"
    )
    lines.append(
        f"| m4 | {m4['name']} | ceiling {m4['ceiling_str']} | n/a (invariant) | n/a | n/a | {m4['on_breach']} |"
    )
    lines.append(
        f"| m5 | {m5['name']} | {m5['required_str']} | NEG 7/8 | NEG 3/3, POS 1 HIT + 1 DQ | NEG 3/3, POS n/a | {m5['on_breach']} |"
    )
    lines.append("")
    lines.append("m1 principle: " + m1["principle"])
    lines.append("")
    lines.append("m1 Lot-1 note: " + m1["lot1_note"])
    lines.append("")
    lines.append("m1 Lot-2 note: " + m1["lot2_note"])
    lines.append("")
    lines.append("m1 Lot-3 note: " + m1["lot3_note"])
    lines.append("")
    lines.append("m2 rule: " + m2["rule"])
    lines.append("")
    lines.append("m3 note: " + m3["note"])
    lines.append("")
    lines.append("m5 NEG-miss ruling: " + m5["neg_miss_ruling"])
    lines.append("")
    lines.append("m5 POS-disqualified ruling (NEW at v3): " + m5["pos_disqualified_ruling"])
    lines.append("")

    lines.append("## m3 category rename (carried from v2)")
    lines.append("")
    renamed = m3["renamed"]
    lines.append(f"`{renamed['from']}` renamed to `{renamed['to']}` — {renamed['note']}.")
    lines.append("")

    lines.append("## Gold sets v3 (digest-pinned, blind to lanes, re-salted)")
    lines.append("")
    neg, pos = gs["negative_control"], gs["positive_control"]
    lines.append(f"### NEGATIVE controls ({neg['count']})")
    lines.append("")
    lines.append(f"Eligibility: {neg['eligibility']}. Digest formula: `{neg['digest_formula']}`, sorted:")
    lines.append("")
    for d in neg["digests"]:
        lines.append(f"- `{d}`")
    lines.append("")
    lines.append(
        f"### POSITIVE controls ({pos['count']} of {pos['eligible_population_after_exclusion']} "
        f"eligible after excluding {pos['excluded_lot1_revealed_positive_controls']} Lot-1 + "
        f"{pos['excluded_lot2_revealed_positive_controls']} Lot-2 revealed controls; "
        f"{pos['eligible_population_after_lot1_exclusion']} eligible after Lot-1 exclusion only; "
        f"{pos['eligible_population_before_exclusion']} eligible before any exclusion)"
    )
    lines.append("")
    lines.append(f"Eligibility predicate: {pos['eligibility_predicate']}.")
    lines.append("")
    lines.append(f"Selection rule: {pos['selection_rule']}.")
    lines.append("")
    lines.append(f"Digest formula: `{pos['digest_formula']}`.")
    lines.append("")
    for d in pos["digests"]:
        lines.append(f"- `{d}`")
    lines.append("")
    lines.append("**Lot-2 burn note:** " + pos["lot2_burn_note"])
    lines.append("")
    lines.append(
        f"**POS pre-verification required (NEW, v3):** `pos_preverification_required` = "
        f"{pos['pos_preverification_required']}. {pos['pos_preverification_rule']}"
    )
    lines.append("")
    lines.append(f"**Reveal rule:** {gs['reveal_rule']}")
    lines.append("")

    lines.append("## Lot 1 outcome (pinned literal, reference)")
    lines.append("")
    lines.append(f"- Quarantined: {lot1['quarantined']} · Certified: {lot1['certified']}")
    lines.append(f"- m1: {lot1['m1_reading']:.3f} — {lot1['m1_state']}")
    lines.append(f"- m2: {lot1['m2_reading']:.3f} — {lot1['m2_state']}")
    lines.append(f"- m3: {lot1['m3_state']} ({lot1['m3_new_categories']} new categories)")
    lines.append(f"- m5 NEG hit rate: {lot1['m5_neg_hit_rate']} — {lot1['m5_halt_status']}")
    lines.append(
        f"- References: `{lot1['references']['conductor_gate_report']}` — {lot1['references']['prs']}"
    )
    lines.append("")

    lines.append("## Lot 2 outcome (pinned literal, reference)")
    lines.append("")
    lines.append(f"- Quarantined: {lot2['quarantined']} · Certified: {lot2['certified']}")
    lines.append(f"- Innocence controls: {lot2['innocence_controls']}")
    lines.append(f"- m1: {lot2['m1_reading']:.3f} — {lot2['m1_state']}")
    lines.append(f"- m2: {lot2['m2_reading']:.3f} — {lot2['m2_state']}")
    lines.append(f"- m3: {lot2['m3_state']}")
    lines.append(f"- m5 NEG hit rate: {lot2['m5_neg_hit_rate']} · POS: {lot2['m5_pos_hit_rate']}")
    lines.append(
        f"- References: `{lot2['references']['conductor_gate_report']}` — {lot2['references']['prs']}"
    )
    lines.append("")

    lines.append("## Lot 3 outcome (pinned literal, reference)")
    lines.append("")
    lines.append(f"- Quarantined: {lot3['quarantined']} · Certified: {lot3['certified']}")
    lines.append(f"- Innocence controls: {lot3['innocence_controls']}")
    lines.append(f"- m1: {lot3['m1_reading']:.3f} — {lot3['m1_state']}")
    lines.append(f"- m2: {lot3['m2_reading']:.3f} — {lot3['m2_state']}")
    lines.append(f"- m3: {lot3['m3_state']}")
    lines.append(f"- m5 NEG hit rate: {lot3['m5_neg_hit_rate']} · POS: {lot3['m5_pos_hit_rate']}")
    lines.append(
        f"- References: `{lot3['references']['conductor_gate_report']}` — {lot3['references']['prs']}"
    )
    lines.append("")

    lines.append("## Pause/resume protocol")
    lines.append("")
    lines.append(ctx["pause_resume_protocol"])
    lines.append("")

    lines.append("## Sign-off")
    lines.append("")
    lines.append(f"Conductor sign-off: {ctx['conductor_sign_off']}")

    return "\n".join(lines).rstrip("\n") + "\n"


def render_json(ctx: dict[str, Any]) -> str:
    return json.dumps(ctx, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write both artifacts (default: dry-run)")
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    args = ap.parse_args(argv)

    if not CANONICAL.exists():
        raise CalibrationError(f"canonical not found: {CANONICAL}")
    if not MANIFEST_PATH.exists():
        raise CalibrationError(f"vault manifest not found: {MANIFEST_PATH} (P1 precondition)")

    canonical_revision = _canonical_revision()
    fenced_blob = _fenced_canonical_blob()

    membership = _load_membership()
    _validate_membership_pin(membership, fenced_blob)

    manifest_digest = _sha256_file(MANIFEST_PATH)
    membership_sha256 = _sha256_file(MEMBERSHIP_PATH)

    records = json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]
    eligible_before = eligible_positive_codes(records)
    eligible_after_lot1 = v2.eligible_positive_codes_v2(records)
    eligible_after = eligible_positive_codes_v3(records)
    positive_digests = select_positive_digests_v3(records, manifest_digest)
    neg_digests = negative_digests_v3(manifest_digest)

    ctx = build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(eligible_before),
        eligible_population_after_lot1_exclusion=len(eligible_after_lot1),
        eligible_population_after_exclusion=len(eligible_after),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )

    md = render_markdown(ctx)
    payload_json = render_json(ctx)

    print(
        f"emit_batch_calibration_v3 — canonical revision {canonical_revision[:12]} — mode="
        f"{'APPLY' if args.apply else 'DRY-RUN'}"
    )
    print(f"  manifest_digest: {manifest_digest[:12]}...")
    print(f"  membership_sha256: {membership_sha256[:12]}...")
    print(f"  eligible positive-control population (before exclusion): {len(eligible_before)}")
    print(f"  eligible positive-control population (after Lot-1 exclusion): {len(eligible_after_lot1)}")
    print(f"  eligible positive-control population (after Lot-1+Lot-2 exclusion): {len(eligible_after)}")
    print(f"  negative controls (v3, salt={NEGATIVE_SALT}): {len(neg_digests)} digests")
    print(f"  positive controls (v3, salt={POSITIVE_SALT}): {len(positive_digests)} digests")
    print(
        "  control limits: m1>=0.75(Lot1 0.385 BREACH / Lot2 1.00 / Lot3 1.00, all TRUE cross-family) "
        "m2=[0.20,0.85](0.000 x3, declared-breach regime) m3=closed-7(invariant, 0 new) m4<=400000 "
        "m5==1.00(NEG 7/8+3/3+3/3; POS 1 HIT + 1 DISQUALIFIED)"
    )

    if not args.apply:
        print("DRY RUN — no file written. Re-run with --apply.")
        return 0

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(md, encoding="utf-8")
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(payload_json, encoding="utf-8")
    print(f"wrote {_display_path(args.out_md)} (sha256 {hashlib.sha256(md.encode()).hexdigest()[:12]})")
    print(f"wrote {_display_path(args.out_json)} (sha256 {hashlib.sha256(payload_json.encode()).hexdigest()[:12]})")
    return 0


def _display_path(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CalibrationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
