#!/usr/bin/env python3
"""emit_batch_calibration.py — GARUDA-FILIERA Batch A CALIBRATION compiler (plan §5).

Deterministic writer of the pre-registered calibration artifact required by
`research/operations/2026-07-18-kbli-batch-a-plan.md` §5: "BEFORE the first
lot, the conductor signs `data/kbli-filiera/batch-reports/batchA-calibration.md`
... No lot starts before this artifact exists." This compiler is the ONLY
writer of that artifact (plan §4, data-plane guard #2550 authorizes
`scripts/kbli_filiera/*.py` to write `data/kbli-filiera/**`).

Inputs (all pinned, no network):
  - canonical:   data/source_documents/KBLI_2025_FINAL_CLEAN.json
                 (fenced exactly like emit_batch_membership.py::_canonical_revision —
                 on-disk blob must equal HEAD's blob, else abort)
  - manifest:    data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json
                 (sha256 of the file AS COMMITTED = `manifest_digest`)
  - membership:  data/kbli-filiera/membership/batch-a-members.json
                 (its own canonical_sha256 must equal sha256 of the canonical
                 on disk — content-addressed, zero git; see
                 `_validate_membership_pin`. Legacy artifacts without that
                 field fall back to resolving canonical_revision via git,
                 which is environment-fragile under a shallow CI checkout.)
  - pilot A1 measurements: PINNED LITERAL below, source
    research/operations/2026-07-17-kbli-pilot-a1-results.md (conductor-set).

Control limits (plan §5, conductor-fixed from pilot A1 — written EXACTLY as
given, never re-derived). RECALIBRATED for remaining A-serving lots by plan §8
amendment A-3 (2026-07-18) after Lot A-L1 — the first truly-blind lot — breached
the original pilot-derived floors (m1=0.538, m2=0.077); root cause was that the
pilot's own D5 was anchored, not truly blind, so floors derived from it were
themselves miscalibrated. CURRENT values below; ORIGINAL values are preserved
in every emitted artifact under control_limits.*.revisions.original — never a
silent overwrite:
  m1 blind-concordance floor   >= 0.45   (was >= 0.75; pilot baseline: 0.917)
  m2 certification rate band   [0.05, 0.60] (was [0.20, 0.85]; pilot baseline:
                                 0.417 — a ceiling breach is drift, not excellence)
  m3 refutation-category registry (closed list) — any new category = pause — UNCHANGED
  m4 tokens/dossier ceiling    <= 400000 (pilot avg 225008, max 357453) — UNCHANGED
  m5 gold-set hit rate         == 1.00   — any miss halts the lot — UNCHANGED

Gold sets (digest-pinned, blind-to-lanes — plaintext NEVER printed, not to
the artifact, not to stdout):
  NEGATIVE = the 8 cured codes (honest-gap must survive).
  POSITIVE = the 8 lowest sha256(code + "|" + manifest_digest) among ELIGIBLE
             codes (canonical records with non-null _l2_source AND non-empty
             per_skala — the OSS-native Batch-C class). Deterministic: same
             canonical + same manifest_digest => same 8, always.
  Both lists are committed as sha256 hex digests ONLY; plaintext is revealed
  in the lot report AFTER the lot closes (plan §5).

Determinism (G16): same inputs => byte-identical files; sorted keys; trailing
newline. The date is a PINNED constant, never wall-clock, so re-running the
compiler on the same inputs on a different day still reproduces the artifact.

Usage:
    python scripts/kbli_filiera/emit_batch_calibration.py            # dry-run
    python scripts/kbli_filiera/emit_batch_calibration.py --apply    # write both files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
CANONICAL_REL = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
MANIFEST_PATH = REPO_ROOT / "data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json"
MEMBERSHIP_PATH = REPO_ROOT / "data/kbli-filiera/membership/batch-a-members.json"
OUT_MD = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration.md"
OUT_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration.json"
PLAN_PATH = "research/operations/2026-07-18-kbli-batch-a-plan.md"

# Pinned constant — never Date.now()/wall-clock (G16 determinism).
PINNED_DATE = "2026-07-18"

CONDUCTOR_SIGN_OFF = "SIGNED — Fable conductor session f5892d39, 2026-07-18"

# Pilot A1 measurements — PINNED LITERAL, source:
# research/operations/2026-07-17-kbli-pilot-a1-results.md (conductor-set, not
# re-derived by this compiler).
PILOT_A1: dict[str, Any] = {
    "codes": 15,
    "seats": 29,
    "total_sonnet_tokens": 3375127,
    "avg_tokens_per_code": 225008,
    "max_tokens_per_code": 357453,
    "max_tokens_code": "43216",
    "adjudicated": 12,
    "certified_clean": 5,
    "quarantined": 7,
    "innocence_untouched": 3,
    "d1_d5_dossier_concordance": "11/12",
}

# Recalibration — plan §8 amendment A-3 (2026-07-18): Lot A-L1 (the first
# TRULY blind lot — see agent/air-m5/kbli/batcha-lot-runner PR #2683's D5-blind
# fix) measured m1=0.538/m2=0.077, breaching the ORIGINAL pilot-derived floors
# below. Root cause: the pilot's own D5 was not truly blind (its
# d5Prompt(code, d1Result) embedded the extractor's own proposal in the
# refuter's prompt), so m1/m2 floors derived from that anchored baseline were
# themselves miscalibrated at the source — not a Lot A-L1 adjudication defect.
# Scope: REMAINING A-SERVING LOTS ONLY. m3/m4/m5 are UNCHANGED. Does NOT
# weaken blindness or relax any per-fact acceptance criterion (plan §3 A1-A6).
# The ORIGINAL values are kept alongside the revised ones in every emitted
# artifact (control_limits.*.revisions.original) — recalibration is auditable
# history, never a silent overwrite.
A3_AMENDMENT_REF = "plan §8 amendment A-3 (2026-07-18)"
A3_AMENDMENT_REASON = "floors re-derived from the first true-blind lot; original pilot baseline was anchored"
A3_AMENDMENT_SCOPE = "remaining A-serving lots only"
A3_REVISED_M1_FLOOR = 0.45
A3_REVISED_M2_FLOOR = 0.05
A3_REVISED_M2_CEILING = 0.60

# m3 — closed refutation-category registry (plan §5). Any category found
# outside this list during a lot is a NEW category => automatic lot pause.
REFUTATION_CATEGORIES: tuple[str, ...] = (
    "code_collision",
    "illegitimate_inheritance",
    "wrong_authority_level",
    "phantom_source_pointer",
    "source_absent_in_vault",
)

# Gold set — NEGATIVE controls: the 8 cured pilot/audit codes (honest-gap
# must survive re-run). Plaintext lives here (module constant, source input)
# but is NEVER written into the artifact or printed — only its digest is.
NEGATIVE_CONTROL_CODES: tuple[str, ...] = (
    "68112",
    "49213",
    "51103",
    "51203",
    "20111",
    "50115",
    "60312",
    "64310",
)

POSITIVE_ELIGIBILITY_PREDICATE = (
    "canonical record has kode_kbli_2025 set AND _l2_source is non-null "
    "AND per_skala is non-empty (the OSS-native Batch-C class)"
)
POSITIVE_SELECTION_RULE = (
    "among eligible codes, the 8 with the lowest sha256(code + \"|\" + manifest_digest) "
    "hex digest, sorted ascending — deterministic, never conductor-picked"
)


class CalibrationError(RuntimeError):
    """Raised on any precondition/fencing violation — fail-visible, never silent."""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _canonical_revision() -> str:
    """Fenced exactly like emit_batch_membership.py::_canonical_revision: the
    working canonical on disk MUST match HEAD's canonical blob, else abort."""
    head_blob = _git("rev-parse", f"HEAD:{CANONICAL_REL}")
    work_blob = hashlib.sha1(
        b"blob " + str(CANONICAL.stat().st_size).encode() + b"\x00" + CANONICAL.read_bytes()
    ).hexdigest()
    if head_blob != work_blob:
        raise CalibrationError(
            "canonical on disk differs from HEAD's canonical blob — commit or reset "
            f"before emitting calibration (HEAD={head_blob[:12]} work={work_blob[:12]})"
        )
    return _git("rev-parse", "HEAD")


def _validate_membership_pin(membership: dict[str, Any], fenced_blob: str) -> None:
    """Content-aware pin check (scar W88 — verify by CONTENT, never by a
    commit-SHA/ancestor/git proxy). membership.json pins the canonical git
    REVISION it was emitted against; that commit and our fenced HEAD can
    legitimately differ (unrelated commits land between the two artifacts)
    while the canonical FILE content stays byte-identical.

    PRIMARY path — content-addressed, zero git: membership carries
    `canonical_sha256` (sha256 of the canonical file bytes, added
    2026-07-18). We compare that directly against sha256 of the canonical
    on disk. No git call at all, so this works in a SHALLOW CI checkout
    (depth=1), which does not have historical commit objects for arbitrary
    `canonical_revision` SHAs — resolving those via git 128'd in CI (see
    the fallback path below, which is what broke).

    FALLBACK path — legacy membership artifacts emitted before
    `canonical_sha256` existed: resolve `canonical_revision:<path>` via git
    and compare blob hashes. This still works locally (full clone) but is
    the environment-fragile path; any CalledProcessError here is wrapped
    with a clear "re-emit membership" pointer rather than a bare git 128."""
    pinned_sha256 = membership.get("canonical_sha256")
    if pinned_sha256:
        current_sha256 = _sha256_file(CANONICAL)
        if pinned_sha256 != current_sha256:
            raise CalibrationError(
                "membership artifact's canonical_sha256 does NOT match the canonical on disk "
                f"(membership={pinned_sha256[:12]} current={current_sha256[:12]}) "
                "— membership was built against different data; re-emit it before calibrating."
            )
        return

    pinned_rev = membership.get("canonical_revision")
    if not pinned_rev:
        raise CalibrationError("membership artifact missing canonical_revision")
    try:
        pinned_blob = _git("rev-parse", f"{pinned_rev}:{CANONICAL_REL}")
    except subprocess.CalledProcessError as e:
        raise CalibrationError(
            f"membership's pinned canonical_revision {pinned_rev!r} is not resolvable "
            "(shallow clone? historical commit objects are absent in a depth=1 checkout) "
            "— re-emit membership to get content-addressed pinning (canonical_sha256 field) "
            f"instead of relying on git history: {e}"
        ) from e
    if pinned_blob != fenced_blob:
        raise CalibrationError(
            "membership artifact's canonical_revision points at a DIFFERENT canonical blob "
            f"than the fenced HEAD (membership_blob={pinned_blob[:12]} fenced_blob={fenced_blob[:12]}) "
            "— membership was built against different data; re-emit it before calibrating."
        )


def _fenced_canonical_blob() -> str:
    return _git("rev-parse", f"HEAD:{CANONICAL_REL}")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_membership() -> dict[str, Any]:
    if not MEMBERSHIP_PATH.exists():
        raise CalibrationError(f"membership artifact not found: {MEMBERSHIP_PATH} (run P0 first)")
    return json.loads(MEMBERSHIP_PATH.read_text(encoding="utf-8"))


def _digest(code: str, manifest_digest: str) -> str:
    return hashlib.sha256(f"{code}|{manifest_digest}".encode()).hexdigest()


def eligible_positive_codes(records: list[dict[str, Any]]) -> list[str]:
    """POSITIVE_ELIGIBILITY_PREDICATE, applied. Guilt: _l2_source set AND
    per_skala non-empty. Innocence: either condition alone is NOT enough."""
    out: list[str] = []
    for r in records:
        code = r.get("kode_kbli_2025")
        if not code:
            continue
        if r.get("_l2_source") is not None and bool(r.get("per_skala")):
            out.append(code)
    return out


def select_positive_digests(
    records: list[dict[str, Any]], manifest_digest: str, n: int = 8
) -> list[str]:
    eligible = eligible_positive_codes(records)
    if len(eligible) < n:
        raise CalibrationError(
            f"only {len(eligible)} eligible positive-control codes on canonical, need >= {n}"
        )
    digests = sorted(_digest(c, manifest_digest) for c in eligible)
    return digests[:n]


def negative_digests(manifest_digest: str) -> list[str]:
    return sorted(_digest(c, manifest_digest) for c in NEGATIVE_CONTROL_CODES)


def build_context(
    *,
    canonical_revision: str,
    manifest_digest: str,
    membership_sha256: str,
    eligible_population: int,
    positive_digests: list[str],
    neg_digests: list[str],
) -> dict[str, Any]:
    """Pure assembly of the artifact context — no I/O. Same inputs =>
    byte-identical render (G16)."""
    return {
        "batch": "A",
        "plan": PLAN_PATH,
        "date": PINNED_DATE,
        "pinned_revisions": {
            "canonical_git_revision": canonical_revision,
            "canonical_path": CANONICAL_REL,
            "manifest_path": "data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json",
            "manifest_sha256": manifest_digest,
            "membership_path": "data/kbli-filiera/membership/batch-a-members.json",
            "membership_sha256": membership_sha256,
        },
        "pilot_a1": PILOT_A1,
        "control_limits": {
            "m1_blind_concordance": {
                "name": "extractor/refuter blind-concordance floor per lot",
                "floor": A3_REVISED_M1_FLOOR,
                "floor_str": f"{A3_REVISED_M1_FLOOR:.2f}",
                "pilot_baseline": 0.917,
                "pilot_baseline_str": "0.917",
                "definition": (
                    "per-lot fraction of adjudicated dossiers where the D5 blind verdict "
                    "matches the D1 proposal"
                ),
                "on_breach": "lane pauses at lot boundary, conductor-signed resume note in plan §8",
                "revisions": {
                    "original": {
                        "floor": 0.75,
                        "floor_str": "0.75",
                        "source": "pilot A1 baseline — D5 was NOT truly blind (anchored), see A-3 root cause",
                    },
                    "current": {
                        "floor": A3_REVISED_M1_FLOOR,
                        "floor_str": f"{A3_REVISED_M1_FLOOR:.2f}",
                        "amendment": A3_AMENDMENT_REF,
                        "reason": A3_AMENDMENT_REASON,
                        "scope": A3_AMENDMENT_SCOPE,
                    },
                },
            },
            "m2_certification_rate": {
                "name": "certification rate per lot",
                "floor": A3_REVISED_M2_FLOOR,
                "floor_str": f"{A3_REVISED_M2_FLOOR:.2f}",
                "ceiling": A3_REVISED_M2_CEILING,
                "ceiling_str": f"{A3_REVISED_M2_CEILING:.2f}",
                "pilot_baseline": 0.417,
                "pilot_baseline_str": "0.417",
                "definition": "certified_clean / adjudicated, per lot — a too-high rate is drift, not excellence",
                "on_breach": "lane pauses (ceiling breach = drift suspicion), conductor-signed resume note",
                "revisions": {
                    "original": {
                        "floor": 0.20,
                        "floor_str": "0.20",
                        "ceiling": 0.85,
                        "ceiling_str": "0.85",
                        "source": "pilot A1 baseline — D5 was NOT truly blind (anchored), see A-3 root cause",
                    },
                    "current": {
                        "floor": A3_REVISED_M2_FLOOR,
                        "floor_str": f"{A3_REVISED_M2_FLOOR:.2f}",
                        "ceiling": A3_REVISED_M2_CEILING,
                        "ceiling_str": f"{A3_REVISED_M2_CEILING:.2f}",
                        "amendment": A3_AMENDMENT_REF,
                        "reason": A3_AMENDMENT_REASON,
                        "scope": A3_AMENDMENT_SCOPE,
                    },
                },
            },
            "m3_refutation_categories": {
                "name": "refutation-category registry (closed list)",
                "categories": list(REFUTATION_CATEGORIES),
                "on_breach": "any category outside the registry = automatic lot pause + conductor triage",
            },
            "m4_tokens_per_dossier": {
                "name": "tokens/dossier ceiling",
                "ceiling": 400000,
                "ceiling_str": "400000",
                "pilot_avg": PILOT_A1["avg_tokens_per_code"],
                "pilot_max": PILOT_A1["max_tokens_per_code"],
                "pilot_max_code_digest_only": True,
                "on_breach": "lane pauses, investigate runaway",
            },
            "m5_gold_set_hit_rate": {
                "name": "gold-set hit rate",
                "required": 1.00,
                "required_str": "1.00",
                "on_breach": "any miss halts the lot immediately",
            },
        },
        "gold_sets": {
            "negative_control": {
                "count": len(neg_digests),
                "eligibility": "the 8 cured codes from the pilot/audit runs (honest-gap must survive)",
                "digests": neg_digests,
            },
            "positive_control": {
                "count": len(positive_digests),
                "eligible_population": eligible_population,
                "eligibility_predicate": POSITIVE_ELIGIBILITY_PREDICATE,
                "selection_rule": POSITIVE_SELECTION_RULE,
                "digests": positive_digests,
            },
            "reveal_rule": (
                "Plaintext code lists for both control classes are revealed in the lot "
                "report AFTER the lot closes (plan §5). Never before."
            ),
        },
        "mutation_testing": (
            "Per plan §5 (workflow §5 binding): the conductor periodically injects corrupted "
            "intermediates (a wrong code string in a render locator, an altered row value) "
            "into the pipeline. The refuter/compiler MUST catch every injection. An uncaught "
            "mutation is a program-level defect: the lot halts and a root-cause pass runs "
            "before any resume."
        ),
        "pause_resume_protocol": (
            "Any control-limit breach (m1-m5) pauses the affected lane at the lot boundary. "
            f"Resume requires a conductor-signed note appended to {PLAN_PATH} §8, citing the "
            "specific breached metric and the root cause. No silent resume."
        ),
        "conductor_sign_off": CONDUCTOR_SIGN_OFF,
    }


def render_markdown(ctx: dict[str, Any]) -> str:
    rev = ctx["pinned_revisions"]
    pilot = ctx["pilot_a1"]
    cl = ctx["control_limits"]
    gs = ctx["gold_sets"]

    lines: list[str] = []
    lines.append("# Batch A — calibration artifact (plan §5 gate)")
    lines.append("")
    lines.append(f"- **Batch:** {ctx['batch']}")
    lines.append(f"- **Date:** {ctx['date']}")
    lines.append(f"- **Plan:** `{ctx['plan']}`")
    lines.append("")
    lines.append(
        "> No lot starts before this artifact exists (plan §5). It is compiler-emitted "
        "from pilot A1 measurements and conductor-signed below; changing a control limit "
        "mid-batch requires a logged amendment in the plan's §8, never a silent edit here."
    )
    lines.append("")

    lines.append("## Pinned revisions")
    lines.append("")
    lines.append("| Artifact | Pin |")
    lines.append("| --- | --- |")
    lines.append(f"| canonical (`{rev['canonical_path']}`) | git revision `{rev['canonical_git_revision']}` |")
    lines.append(f"| vault manifest (`{rev['manifest_path']}`) | sha256 `{rev['manifest_sha256']}` |")
    lines.append(f"| membership (`{rev['membership_path']}`) | sha256 `{rev['membership_sha256']}` |")
    lines.append("")

    lines.append("## Pilot A1 measurements (conductor-set baseline)")
    lines.append("")
    lines.append(
        "Source: `research/operations/2026-07-17-kbli-pilot-a1-results.md`. Pinned literal, "
        "not re-derived by this compiler."
    )
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| codes / seats | {pilot['codes']} / {pilot['seats']} |")
    lines.append(f"| total Sonnet tokens | {pilot['total_sonnet_tokens']} |")
    lines.append(f"| avg tokens/code | {pilot['avg_tokens_per_code']} |")
    lines.append(f"| max tokens/code | {pilot['max_tokens_per_code']} (code {pilot['max_tokens_code']}) |")
    lines.append(f"| adjudicated | {pilot['adjudicated']} |")
    lines.append(f"| certified-clean | {pilot['certified_clean']} |")
    lines.append(f"| quarantined | {pilot['quarantined']} |")
    lines.append(f"| innocence untouched | {pilot['innocence_untouched']} |")
    lines.append(f"| D1/D5 dossier concordance | {pilot['d1_d5_dossier_concordance']} |")
    lines.append("")

    lines.append("## Control limits m1-m5 (falsifiable, pre-registered)")
    lines.append("")
    m1, m2, m3, m4, m5 = cl["m1_blind_concordance"], cl["m2_certification_rate"], \
        cl["m3_refutation_categories"], cl["m4_tokens_per_dossier"], cl["m5_gold_set_hit_rate"]
    lines.append("| # | Metric | Limit | Pilot baseline | On breach |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(
        f"| m1 | {m1['name']} | floor {m1['floor_str']} | {m1['pilot_baseline_str']} | {m1['on_breach']} |"
    )
    lines.append(
        f"| m2 | {m2['name']} | floor {m2['floor_str']} / ceiling {m2['ceiling_str']} | "
        f"{m2['pilot_baseline_str']} | {m2['on_breach']} |"
    )
    lines.append(
        f"| m3 | {m3['name']} | closed list: {', '.join('`' + c + '`' for c in m3['categories'])} | n/a | {m3['on_breach']} |"
    )
    lines.append(
        f"| m4 | {m4['name']} | ceiling {m4['ceiling_str']} | avg {m4['pilot_avg']} / max {m4['pilot_max']} | {m4['on_breach']} |"
    )
    lines.append(f"| m5 | {m5['name']} | {m5['required_str']} | n/a | {m5['on_breach']} |")
    lines.append("")
    lines.append(
        "m1 definition: " + m1["definition"] + ". m2 definition: " + m2["definition"] + "."
    )
    lines.append("")

    lines.append("## Recalibration history — m1/m2 (plan §8 A-3)")
    lines.append("")
    lines.append(
        "The m1/m2 limits in the table above are the CURRENT ones (post-A-3, in force for "
        "remaining A-serving lots). The original pilot-derived values are kept here — "
        "recalibration is auditable history, never a silent overwrite."
    )
    lines.append("")
    lines.append("| Metric | Original (pilot-derived) | Current (A-3) | Amendment | Reason |")
    lines.append("| --- | --- | --- | --- | --- |")
    m1r, m2r = m1["revisions"], m2["revisions"]
    lines.append(
        f"| m1 floor | {m1r['original']['floor_str']} | {m1r['current']['floor_str']} | "
        f"{m1r['current']['amendment']} | {m1r['current']['reason']} |"
    )
    lines.append(
        f"| m2 floor / ceiling | {m2r['original']['floor_str']} / {m2r['original']['ceiling_str']} | "
        f"{m2r['current']['floor_str']} / {m2r['current']['ceiling_str']} | "
        f"{m2r['current']['amendment']} | {m2r['current']['reason']} |"
    )
    lines.append("")
    lines.append(f"Scope: {m1r['current']['scope']}. m3/m4/m5 are unchanged by this amendment.")
    lines.append("")

    lines.append("## Gold sets (digest-pinned, blind to lanes)")
    lines.append("")
    neg, pos = gs["negative_control"], gs["positive_control"]
    lines.append(f"### NEGATIVE controls ({neg['count']})")
    lines.append("")
    lines.append(f"Eligibility: {neg['eligibility']}. sha256(code + \"|\" + manifest_digest), sorted:")
    lines.append("")
    for d in neg["digests"]:
        lines.append(f"- `{d}`")
    lines.append("")
    lines.append(f"### POSITIVE controls ({pos['count']} of {pos['eligible_population']} eligible)")
    lines.append("")
    lines.append(f"Eligibility predicate: {pos['eligibility_predicate']}.")
    lines.append("")
    lines.append(f"Selection rule: {pos['selection_rule']}.")
    lines.append("")
    for d in pos["digests"]:
        lines.append(f"- `{d}`")
    lines.append("")
    lines.append(f"**Reveal rule:** {gs['reveal_rule']}")
    lines.append("")

    lines.append("## Mutation testing")
    lines.append("")
    lines.append(ctx["mutation_testing"])
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
    eligible = eligible_positive_codes(records)
    positive_digests = select_positive_digests(records, manifest_digest)
    neg_digests = negative_digests(manifest_digest)

    ctx = build_context(
        canonical_revision=canonical_revision,
        manifest_digest=manifest_digest,
        membership_sha256=membership_sha256,
        eligible_population=len(eligible),
        positive_digests=positive_digests,
        neg_digests=neg_digests,
    )

    md = render_markdown(ctx)
    payload_json = render_json(ctx)

    print(f"emit_batch_calibration — canonical revision {canonical_revision[:12]} — mode="
          f"{'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"  manifest_digest: {manifest_digest[:12]}...")
    print(f"  membership_sha256: {membership_sha256[:12]}...")
    print(f"  eligible positive-control population: {len(eligible)}")
    print(f"  negative controls: {len(neg_digests)} digests")
    print(f"  positive controls: {len(positive_digests)} digests")
    print(
        f"  control limits (current, plan §8 A-3): m1>={A3_REVISED_M1_FLOOR:.2f} "
        f"m2=[{A3_REVISED_M2_FLOOR:.2f},{A3_REVISED_M2_CEILING:.2f}] m3=closed-5 "
        "m4<=400000 m5==1.00 (original pre-A-3: m1>=0.75 m2=[0.20,0.85])"
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
