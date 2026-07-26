#!/usr/bin/env python3
"""emit_batch_calibration_v2.py — GARUDA-FILIERA Batch A CALIBRATION REGISTRY v2
compiler (plan §8 amendment A-6(c) — Lot-2 precondition).

`research/operations/2026-07-18-kbli-batch-a-plan.md` §8 A-6(c): "before ANY
Lot 2 work, the calibration registry (`data/kbli-filiera/batch-reports/
batchA-calibration.json` successor artifact) must be re-emitted to carry: the
m3 category extensions (A-5), the m1 measure formalized as cross-family
extractor-vs-extractor IAA, the m1/m2 declared-BREACH state + per-lot
explicit adjudication rule (A-4), and the m5 NEG wording ruling from (b)."

This compiler is that SUCCESSOR artifact writer. It does NOT touch the v1
artifact (`batchA-calibration.{json,md}`) — that artifact is SIGNED and is
NEVER rewritten (scar W88/#9: a signed artifact is historically accurate
forever; corrections land in a new artifact, never an edit to the old one).
v2 writes its OWN files:

  data/kbli-filiera/batch-reports/batchA-calibration-v2.json
  data/kbli-filiera/batch-reports/batchA-calibration-v2.md

Reuse (import, not copy — plan §4 "deterministic compilers are the ONLY
writers"; this compiler reuses v1's fencing/pin/eligibility primitives
verbatim so the two artifacts can never silently diverge on how they read
the canonical):
  - `_fenced_canonical_blob`, `_sha256_file`, `_load_membership`,
    `_validate_membership_pin`, `_canonical_revision`, `eligible_positive_codes`,
    `CalibrationError`, `PILOT_A1` (m4 baseline, invariant from v1),
    `NEGATIVE_CONTROL_CODES` (the 8 phase-1 cured codes),
    `POSITIVE_ELIGIBILITY_PREDICATE` — all imported from
    `emit_batch_calibration.py` (v1), never redefined.

Inputs (all pinned, no network — same as v1):
  - canonical:   data/source_documents/KBLI_2025_FINAL_CLEAN.json (fenced)
  - manifest:    data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json
  - membership:  data/kbli-filiera/membership/batch-a-members.json

Control limits v2 (plan §8 A-4/A-5/A-6, conductor-ruled 2026-07-18):
  m1 REDEFINED: cross-family extractor-vs-extractor IAA (lane D1 vs blind
      cross-family extractor with vision). floor >= 0.75 INVARIANT.
      Lot-1 reading 0.385 — declared-breach (same-family D1-vs-D5 agreement
      is NOT an m1 reading — scar W100).
  m2: certification-rate band [0.20, 0.85] INVARIANT. Lot-1 reading 0.000 —
      declared-breach. Per-lot explicit conductor adjudication required; no
      auto-resume; no floor re-registration (advisory-floor-0.0 WITHDRAWN).
  m3: refutation-category registry EXTENDED to 7 categories (closed list v2);
      `phantom_source_pointer` renamed to `unresolvable_source_pointer`
      (text-hunt evidence cannot establish nonexistence — plan A-5).
  m4: INVARIANT from v1 (ceiling 400000; pilot avg/max pinned as in v1).
  m5: == 1.00 any-miss-halts INVARIANT, plus a going-forward NEG-miss ruling:
      an evidenced completion path is adjudicated per-ancestor image-grade by
      the conductor (precedent: 49213, plan A-6(b)-RESOLVED).

Gold sets v2 (digest-pinned, blind-to-lanes, NEW salts so v1/v2 digests never
collide even for a code that appears in both generations):
  NEGATIVE (salt "v2") = the 21 codes cured as of Lot-1 close: the 8 phase-1
      cured codes (v1.NEGATIVE_CONTROL_CODES) + the 13 Lot-1 quarantined codes.
  POSITIVE (salt "v2-lot2") = the 8 lowest sha256(code|manifest_digest|salt)
      among codes eligible under v1's predicate, EXCLUDING the 8 Lot-1
      positive controls already revealed (plan §5 reveal rule — they are
      burned, never re-used as a gold control).
  Both lists are committed as sha256 hex digests ONLY; plaintext is never
  printed or written by this compiler.

Determinism (G16): same inputs => byte-identical files; sorted keys; trailing
newline. PINNED_DATE is a literal, never wall-clock.

Usage:
    python scripts/kbli_filiera/emit_batch_calibration_v2.py            # dry-run
    python scripts/kbli_filiera/emit_batch_calibration_v2.py --apply    # write both files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# --- reuse v1 (import, not copy) -------------------------------------------
FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))
import emit_batch_calibration as v1  # noqa: E402

REPO_ROOT = v1.REPO_ROOT
CANONICAL = v1.CANONICAL
CANONICAL_REL = v1.CANONICAL_REL
MANIFEST_PATH = v1.MANIFEST_PATH
MEMBERSHIP_PATH = v1.MEMBERSHIP_PATH
PLAN_PATH = v1.PLAN_PATH
CalibrationError = v1.CalibrationError

# Reused verbatim from v1 (plan §4 "deterministic compilers are the ONLY
# writers"; these primitives must never fork between v1/v2 or the two
# artifacts could silently disagree on fencing/pin/eligibility semantics).
_sha256_file = v1._sha256_file
_canonical_revision = v1._canonical_revision
_fenced_canonical_blob = v1._fenced_canonical_blob
_load_membership = v1._load_membership
_validate_membership_pin = v1._validate_membership_pin
eligible_positive_codes = v1.eligible_positive_codes

OUT_MD = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration-v2.md"
OUT_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration-v2.json"

# Pinned constant — never Date.now()/wall-clock (G16 determinism).
PINNED_DATE = "2026-07-18"

CONDUCTOR_SIGN_OFF = "SIGNED — Fable conductor session (MANDATO S2, post-GO), 2026-07-18"

PREDECESSOR_ARTIFACT_NOTE = (
    "data/kbli-filiera/batch-reports/batchA-calibration.json (v1) — SIGNED, "
    "NEVER rewritten (scar W88/#9). This v2 file is the successor artifact "
    "mandated by plan §8 A-6(c); it does not edit or supersede v1's historical "
    "record, only the registry going forward."
)

# --- m1 (REDEFINED, plan A-4) ----------------------------------------------
M1_FLOOR = 0.75
M1_LOT1_READING = 0.385
M1_NOTE = (
    "same-family D1-vs-D5 agreement is NOT an m1 reading (measures "
    "transcription fidelity, not truth — scar W100)"
)

# --- m2 (band invariant, plan A-4) -----------------------------------------
M2_FLOOR = 0.20
M2_CEILING = 0.85
M2_LOT1_READING = 0.000
M2_RULE = (
    "per-lot explicit conductor adjudication required; no auto-resume; no "
    "floor re-registration (the advisory-floor-0.0 proposal was withdrawn, "
    "plan A-4)"
)

# --- m3 (extended closed list, plan A-5) -----------------------------------
REFUTATION_CATEGORIES_V2: tuple[str, ...] = (
    "code_collision",
    "illegitimate_inheritance",
    "wrong_authority_level",
    "source_absent_in_vault",
    "payload_cross_contamination",
    "unresolvable_source_pointer",
    "mapping_metadata_false",
)
RENAMED_CATEGORIES: dict[str, str] = {"phantom_source_pointer": "unresolvable_source_pointer"}
RENAMED_NOTE = "text-hunt evidence cannot establish nonexistence (plan A-5 terminology note)"

# --- m4 — INVARIANT from v1 (reused, never redefined) ----------------------
M4_CEILING = 400000

# --- m5 (invariant + going-forward NEG-miss ruling, plan A-6(b)-RESOLVED) --
M5_REQUIRED = 1.00
M5_NEG_MISS_RULING = (
    "a NEG miss raising an evidenced completion path is adjudicated "
    "per-ancestor image-grade by the conductor: certified -> scheduled "
    "data-plane restore + halt lifts (precedent: 49213, plan "
    "A-6(b)-RESOLVED); refuted -> halt stands. An in-gate fill is never "
    "permitted."
)

# --- gold sets v2 -----------------------------------------------------------
# NEW salts so a v1 digest and a v2 digest for the SAME code never collide —
# lanes cannot cross-reference an earlier reveal to shortcut the blind check.
NEGATIVE_SALT = "v2"
POSITIVE_SALT = "v2-lot2"

# The 13 Lot-1 quarantined codes (conductor gate report, taxonomy order as
# adjudicated — plan A-4/A-5/A-6(a)); plaintext lives here (module constant,
# source input) but is NEVER written into the artifact or printed, only its
# digest is.
LOT1_QUARANTINED_CODES: tuple[str, ...] = (
    "01700",
    "02409",
    "05102",
    "38122",
    "39001",
    "02402",
    "38222",
    "05200",
    "01287",
    "02201",
    "08920",
    "36003",
    "19206",
)

# The 8 Lot-1 POSITIVE controls already revealed (plan §5 reveal rule, post
# lot-close) — burned: never re-registered as a gold control in v2 or later.
LOT1_POSITIVE_REVEALED: tuple[str, ...] = (
    "47401",
    "32902",
    "46737",
    "28262",
    "36002",
    "47732",
    "50121",
    "46204",
)

CONDUCTOR_GATE_REPORT_PATH = "research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md"
LOT1_PR_REFS = "PR #2721 (docs) + PR #2725 (data apply)"


def _digest_v2(code: str, manifest_digest: str, salt: str) -> str:
    return hashlib.sha256(f"{code}|{manifest_digest}|{salt}".encode()).hexdigest()


def eligible_positive_codes_v2(records: list[dict[str, Any]]) -> list[str]:
    """v1's predicate (_l2_source non-null AND per_skala non-empty), applied,
    EXCLUDING the 8 Lot-1 positive controls already revealed (burned)."""
    excluded = set(LOT1_POSITIVE_REVEALED)
    return [code for code in eligible_positive_codes(records) if code not in excluded]


def select_positive_digests_v2(
    records: list[dict[str, Any]], manifest_digest: str, n: int = 8
) -> list[str]:
    eligible = eligible_positive_codes_v2(records)
    if len(eligible) < n:
        raise CalibrationError(
            f"only {len(eligible)} eligible v2 positive-control codes "
            f"(post Lot-1-reveal exclusion), need >= {n}"
        )
    digests = sorted(_digest_v2(c, manifest_digest, POSITIVE_SALT) for c in eligible)
    return digests[:n]


def negative_digests_v2(manifest_digest: str) -> list[str]:
    codes = sorted(set(v1.NEGATIVE_CONTROL_CODES) | set(LOT1_QUARANTINED_CODES))
    return sorted(_digest_v2(c, manifest_digest, NEGATIVE_SALT) for c in codes)


def build_context(
    *,
    canonical_revision: str,
    manifest_digest: str,
    membership_sha256: str,
    eligible_population_before_exclusion: int,
    eligible_population_after_exclusion: int,
    positive_digests: list[str],
    neg_digests: list[str],
) -> dict[str, Any]:
    """Pure assembly of the artifact context — no I/O. Same inputs =>
    byte-identical render (G16)."""
    return {
        "batch": "A",
        "artifact_version": "v2",
        "plan": PLAN_PATH,
        "date": PINNED_DATE,
        "predecessor_artifact": PREDECESSOR_ARTIFACT_NOTE,
        "precondition": (
            "plan §8 A-6(c) — this re-emission is a precondition for ANY Lot "
            "2+ work; Zero's GO for the remainder is only actionable AFTER "
            "this registry re-emission is merged."
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
                "lot1_reading": M1_LOT1_READING,
                "lot1_reading_str": "0.385",
                "state": "declared-breach",
                "note": M1_NOTE,
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
                "state": "declared-breach",
                "rule": M2_RULE,
                "on_breach": "lane pauses (ceiling breach = drift suspicion), conductor-signed resume note",
            },
            "m3_refutation_categories": {
                "name": "refutation-category registry (closed list) v2",
                "categories": list(REFUTATION_CATEGORIES_V2),
                "renamed": {
                    "from": "phantom_source_pointer",
                    "to": "unresolvable_source_pointer",
                    "note": RENAMED_NOTE,
                },
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
            },
        },
        "gold_sets": {
            "negative_control": {
                "count": len(neg_digests),
                "salt": NEGATIVE_SALT,
                "eligibility": (
                    "the 21 codes cured as of Lot 1 close: the 8 phase-1 "
                    "cured codes + the 13 Lot-1 quarantined codes"
                ),
                "digest_formula": 'sha256(code + "|" + manifest_digest + "|v2")',
                "digests": neg_digests,
            },
            "positive_control": {
                "count": len(positive_digests),
                "salt": POSITIVE_SALT,
                "eligible_population_before_exclusion": eligible_population_before_exclusion,
                "excluded_lot1_revealed_positive_controls": len(LOT1_POSITIVE_REVEALED),
                "eligible_population_after_exclusion": eligible_population_after_exclusion,
                "eligibility_predicate": v1.POSITIVE_ELIGIBILITY_PREDICATE,
                "selection_rule": (
                    "among eligible codes EXCLUDING the 8 Lot-1 revealed "
                    'positive controls (burned), the 8 with the lowest '
                    'sha256(code + "|" + manifest_digest + "|v2-lot2") hex '
                    "digest, sorted ascending — deterministic, never "
                    "conductor-picked"
                ),
                "digest_formula": 'sha256(code + "|" + manifest_digest + "|v2-lot2")',
                "digests": positive_digests,
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
            "m1_state": "declared-breach",
            "m2_reading": M2_LOT1_READING,
            "m2_state": "declared-breach",
            "m3_state": "pause",
            "m3_new_categories": 2,
            "m5_neg_hit_rate": "7/8",
            "m5_halt_status": "halt lifted per A-6(b)-RESOLVED",
            "references": {
                "conductor_gate_report": CONDUCTOR_GATE_REPORT_PATH,
                "prs": LOT1_PR_REFS,
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
    lot1 = ctx["lot1_outcome"]

    lines: list[str] = []
    lines.append("# Batch A — calibration registry v2 (plan §8 A-6(c) successor artifact)")
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

    lines.append("## Control limits m1-m5 (v2 — registry closure per plan §8 A-6(c))")
    lines.append("")
    m1, m2, m3, m4, m5 = (
        cl["m1_blind_concordance"],
        cl["m2_certification_rate"],
        cl["m3_refutation_categories"],
        cl["m4_tokens_per_dossier"],
        cl["m5_gold_set_hit_rate"],
    )
    lines.append("| # | Metric | Limit | Lot-1 reading | State | On breach |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    lines.append(
        f"| m1 | {m1['name']} | floor {m1['floor_str']} | {m1['lot1_reading_str']} | "
        f"{m1['state']} | {m1['on_breach']} |"
    )
    lines.append(
        f"| m2 | {m2['name']} | floor {m2['floor_str']} / ceiling {m2['ceiling_str']} | "
        f"{m2['lot1_reading_str']} | {m2['state']} | {m2['on_breach']} |"
    )
    lines.append(
        f"| m3 | {m3['name']} | closed list: {', '.join('`' + c + '`' for c in m3['categories'])} "
        f"| n/a | pause (2 new categories) | {m3['on_breach']} |"
    )
    lines.append(
        f"| m4 | {m4['name']} | ceiling {m4['ceiling_str']} | n/a (invariant from v1) | ✅ | {m4['on_breach']} |"
    )
    lines.append(f"| m5 | {m5['name']} | {m5['required_str']} | NEG 7/8 (halt lifted) | resolved | {m5['on_breach']} |")
    lines.append("")
    lines.append("m1 note: " + m1["note"])
    lines.append("")
    lines.append("m2 rule: " + m2["rule"])
    lines.append("")
    lines.append("m5 NEG-miss ruling (going forward): " + m5["neg_miss_ruling"])
    lines.append("")

    lines.append("## m3 category rename")
    lines.append("")
    renamed = m3["renamed"]
    lines.append(f"`{renamed['from']}` renamed to `{renamed['to']}` — {renamed['note']}.")
    lines.append("")

    lines.append("## Gold sets v2 (digest-pinned, blind to lanes, new salts)")
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
        f"eligible after excluding the {pos['excluded_lot1_revealed_positive_controls']} "
        f"Lot-1 revealed controls; {pos['eligible_population_before_exclusion']} eligible "
        "before exclusion)"
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
    eligible_after = eligible_positive_codes_v2(records)
    positive_digests = select_positive_digests_v2(records, manifest_digest)
    neg_digests = negative_digests_v2(manifest_digest)

    ctx = build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population_before_exclusion=len(eligible_before),
        eligible_population_after_exclusion=len(eligible_after),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )

    md = render_markdown(ctx)
    payload_json = render_json(ctx)

    print(
        f"emit_batch_calibration_v2 — canonical revision {canonical_revision[:12]} — mode="
        f"{'APPLY' if args.apply else 'DRY-RUN'}"
    )
    print(f"  manifest_digest: {manifest_digest[:12]}...")
    print(f"  membership_sha256: {membership_sha256[:12]}...")
    print(f"  eligible positive-control population (before exclusion): {len(eligible_before)}")
    print(f"  eligible positive-control population (after Lot-1-reveal exclusion): {len(eligible_after)}")
    print(f"  negative controls (v2, salt={NEGATIVE_SALT}): {len(neg_digests)} digests")
    print(f"  positive controls (v2, salt={POSITIVE_SALT}): {len(positive_digests)} digests")
    print(
        "  control limits: m1>=0.75(declared-breach 0.385) m2=[0.20,0.85](declared-breach 0.000) "
        "m3=closed-7(renamed 1, added 2) m4<=400000 m5==1.00(NEG 7/8, halt lifted)"
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
