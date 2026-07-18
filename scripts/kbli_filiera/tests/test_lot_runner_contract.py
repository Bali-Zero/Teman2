"""Contract tests for infra/workflows/kbli-batch-a-lot.js — the JS Workflow script itself has no
Python test runner, so these tests parse it as TEXT (regex over the source) and assert things that
are load-bearing per research/operations/2026-07-18-kbli-batch-a-plan.md §3/A4 + §5 and the
pilot-report criterion-#6 fix:

1. The pinned m1/m2/m4 calibration numeric literals in the .js match
   data/kbli-filiera/batch-reports/batchA-calibration.json byte-for-byte (drift guard — the .js
   comment explicitly says these are PINNED LITERALS, never re-derived at runtime, so nothing
   short of a text-level check catches them drifting apart from the calibration artifact).
2. The frozen verdict taxonomy (certified | quarantined | abstained) is the ONLY vocabulary the
   script ever emits as a verdict value — `boring_as_expected` (the pilot's 4th-token deviation,
   pilot-report criterion #6) may appear ONLY inside a comment explaining the normalization, never
   as a live enum/string literal a seat could emit.
3. The three plan §8 amendment A-1 out-of-scope facets (pma_status, l4_bali, TKA) are named in the
   seat prompts as out-of-scope this pass.
4. D5 is a TRULY BLIND refuter (plan §3/A4, red-team F5): d5Prompt takes ONLY `code` and its body
   never references D1's output — a conductor-verification finding (2026-07-18) caught the first
   draft embedding `JSON.stringify(d1Result)` directly in the refuter's prompt (anchoring theater,
   copied verbatim from kbli-pilot-a1.js, which has the identical unfixed defect). This test is
   the regression guard for that exact class of bug.
5. The membership in-scope gate exempts innocenceControl codes (they are BY DESIGN non-members —
   OSS-native clean codes), while still refusing a genuinely out-of-scope non-innocence code AND
   refusing a code that is BOTH an in-scope member AND flagged as an innocence control. A
   2026-07-18 over-match (requiring innocence controls to also be in-scope) blocked a real lot
   dispatch (run wf_3477eb84-e75, "REFUSED: 2 code(s) not in-scope: 65121, 85202" — both
   legitimate controls) — this is the regression guard for that exact class of bug.
6. A certified verdict whose D2 extraction FAILED self-confirmation (code_appears_in_row !== true)
   or came back with an empty per_skala_rows list MUST retro-demote to quarantined — the Lot A-L1
   close-out regression guard for code 38222 (D1/D5 agreed clean, but D2's evidence page only
   carried the parent code 38220; the runner still emitted certified).

The calibration artifact (data/kbli-filiera/batch-reports/batchA-calibration.json) ships on a
separate PR (agent/air-m5/kbli/batcha-calibration) — test 1 SKIPS (not fails) if that file is not
yet present on this branch, so this PR's CI stays green standalone; it becomes a real drift guard
the moment both PRs have landed on main.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOT_RUNNER_JS = REPO_ROOT / "infra/workflows/kbli-batch-a-lot.js"
CALIBRATION_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration.json"
CALIBRATION_V2_JSON = REPO_ROOT / "data/kbli-filiera/batch-reports/batchA-calibration-v2.json"


@pytest.fixture(scope="module")
def js_source() -> str:
    assert LOT_RUNNER_JS.exists(), f"lot runner not found at {LOT_RUNNER_JS}"
    return LOT_RUNNER_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. m1/m2/m4 numeric literals must match the calibration artifact (drift guard)
# ---------------------------------------------------------------------------

def _extract_js_number(source: str, key: str) -> float:
    m = re.search(rf"{re.escape(key)}\s*:\s*([0-9]+(?:\.[0-9]+)?)", source)
    assert m, f"could not find pinned literal {key!r} in {LOT_RUNNER_JS}"
    return float(m.group(1))


@pytest.mark.skipif(
    not CALIBRATION_JSON.exists(),
    reason=(
        "data/kbli-filiera/batch-reports/batchA-calibration.json not on this branch yet "
        "(ships on agent/air-m5/kbli/batcha-calibration) — drift guard activates once both "
        "PRs land on main"
    ),
)
def test_m1_m2_m4_literals_match_calibration_artifact(js_source: str) -> None:
    calibration = json.loads(CALIBRATION_JSON.read_text(encoding="utf-8"))
    limits = calibration["control_limits"]

    js_m1_floor = _extract_js_number(js_source, "m1_blind_concordance_floor")
    js_m2_floor = _extract_js_number(js_source, "m2_certification_rate_floor")
    js_m2_ceiling = _extract_js_number(js_source, "m2_certification_rate_ceiling")
    js_m4_ceiling = _extract_js_number(js_source, "m4_tokens_per_dossier_ceiling")

    assert js_m1_floor == limits["m1_blind_concordance"]["floor"]
    assert js_m2_floor == limits["m2_certification_rate"]["floor"]
    assert js_m2_ceiling == limits["m2_certification_rate"]["ceiling"]
    assert js_m4_ceiling == limits["m4_tokens_per_dossier"]["ceiling"]


def test_m3_closed_registry_matches_calibration_categories(js_source: str) -> None:
    """m3's closed registry (v2, 7 categories — Lot 1 close-out: +payload_cross_contamination,
    +mapping_metadata_false; phantom_source_pointer renamed unresolvable_source_pointer per plan
    A-5) is pinned in the .js as a JS array — assert it appears verbatim, and that it matches the
    v2 calibration artifact when present. The RETIRED v1 label must never reappear as a live
    emittable literal (only inside comments explaining the rename)."""
    expected = [
        "code_collision",
        "illegitimate_inheritance",
        "wrong_authority_level",
        "source_absent_in_vault",
        "payload_cross_contamination",
        "unresolvable_source_pointer",
        "mapping_metadata_false",
    ]
    for category in expected:
        assert f'"{category}"' in js_source, f"m3 category {category!r} missing from lot runner"

    assert '"phantom_source_pointer"' not in js_source, (
        "retired v1 label phantom_source_pointer still emittable in the lot runner — "
        "v2 renamed it unresolvable_source_pointer (plan A-5)"
    )

    if CALIBRATION_V2_JSON.exists():
        calibration = json.loads(CALIBRATION_V2_JSON.read_text(encoding="utf-8"))
        v2 = calibration["control_limits"]["m3_refutation_categories"]["categories"]
        assert sorted(v2) == sorted(expected)


# ---------------------------------------------------------------------------
# 2. frozen verdict taxonomy — boring_as_expected only in a comment, never emitted
# ---------------------------------------------------------------------------

FROZEN_TAXONOMY = ("certified", "quarantined", "abstained")


def test_frozen_taxonomy_tokens_present(js_source: str) -> None:
    for token in FROZEN_TAXONOMY:
        assert f'"{token}"' in js_source, f"frozen-taxonomy token {token!r} not found"


def test_boring_as_expected_never_emitted_as_a_verdict(js_source: str) -> None:
    """`boring_as_expected` (the pilot's 4th-token deviation) may only appear as prose inside a
    // comment explaining the normalization — never as a quoted string literal (enum value,
    schema default, or emitted verdict) that a seat could actually produce."""
    assert "boring_as_expected" in js_source, (
        "expected the normalization comment referencing the pilot's deviation to still be present"
    )
    for line in js_source.splitlines():
        if "boring_as_expected" not in line:
            continue
        stripped = line.strip()
        assert stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"), (
            f"boring_as_expected must appear only in a comment line, found: {line!r}"
        )
        # and never as a quoted literal even within the comment's own code-look-alike snippet
        assert '"boring_as_expected"' not in line and "'boring_as_expected'" not in line


def test_verdict_enums_use_only_frozen_taxonomy(js_source: str) -> None:
    """Every `enum: [...]` block that includes a verdict-shaped token set must be exactly the
    frozen three (order-independent) — catches a schema silently regaining a 4th state.

    UPDATE (2026-07-19, Lot 5 schema-neutralization v2): the ONLY schema that ever validated a
    seat-emitted `verdict` enum was INNOCENCE_SCHEMA, now retired (section 7 below) — D1_SCHEMA/
    D5_SCHEMA/D2_SCHEMA never had a verdict field; every result's verdict is 100% deterministic JS
    (diffD1D5() / d2SelfConfirmFailed ternary), never itself a seat-validated enum. Zero qualifying
    enum blocks is therefore the CORRECT, stronger post-fix state (no seat can emit a verdict at
    all, let alone a 4th token) — this test tolerates that explicitly rather than requiring one."""
    enum_blocks = re.findall(r"enum:\s*\[([^\]]*)\]", js_source)
    verdict_like = [
        blk for blk in enum_blocks
        if any(tok in blk for tok in FROZEN_TAXONOMY)
    ]
    for blk in verdict_like:
        tokens = {t.strip().strip('"').strip("'") for t in blk.split(",") if t.strip()}
        assert tokens == set(FROZEN_TAXONOMY), f"verdict enum block drifted from frozen taxonomy: {tokens}"


# ---------------------------------------------------------------------------
# 3. abstain-classes (pma_status, l4_bali, TKA) marked out-of-scope in the seat prompts
# ---------------------------------------------------------------------------

def test_abstain_classes_marked_out_of_scope(js_source: str) -> None:
    assert "OUT OF SCOPE" in js_source
    for facet in ("pma_status", "l4_bali", "TKA"):
        assert facet in js_source, f"abstain-class facet {facet!r} not named in the lot runner"
    # and it must be reachable from the shared out-of-scope notice actually interpolated into
    # every seat prompt function, not just mentioned in a header comment
    assert "OUT_OF_SCOPE_NOTICE" in js_source
    # innocencePrompt is deliberately NOT in this list (2026-07-19, Lot 5 schema-neutralization v2):
    # it no longer exists — a control now reads d1Prompt/d5Prompt/d2Prompt via adjudicateCode(),
    # already covered here.
    for fn in ("d1Prompt", "d5Prompt", "d2Prompt"):
        fn_match = re.search(rf"function {fn}\([^)]*\)\s*{{(.*?)\n}}", js_source, re.DOTALL)
        assert fn_match, f"could not locate {fn} in lot runner"
        assert "OUT_OF_SCOPE_NOTICE" in fn_match.group(1), f"{fn} does not interpolate the out-of-scope notice"


# ---------------------------------------------------------------------------
# 4. D5 is a TRULY BLIND refuter — guilt (leak absent) + innocence (extraction sound)
# ---------------------------------------------------------------------------

def _function_signature_and_body(source: str, fn: str) -> tuple[str, str]:
    sig_match = re.search(rf"function {fn}\(([^)]*)\)\s*{{", source)
    assert sig_match, f"could not locate {fn}'s signature in lot runner"
    body_match = re.search(rf"function {fn}\([^)]*\)\s*{{(.*?)\n}}", source, re.DOTALL)
    assert body_match, f"could not locate {fn}'s body in lot runner"
    return sig_match.group(1), body_match.group(1)


def test_guilt_d5_prompt_never_receives_or_references_d1(js_source: str) -> None:
    """GUILT: d5Prompt must take ONLY `code` — no second parameter that could carry D1's proposal
    — and its body must never reference a d1/proposal value. This is the direct regression guard
    for the 2026-07-18 conductor finding (anchoring theater: JSON.stringify(d1Result) embedded in
    the refuter's own prompt, copied verbatim from kbli-pilot-a1.js's identical unfixed defect)."""
    params, body = _function_signature_and_body(js_source, "d5Prompt")
    param_names = [p.strip() for p in params.split(",") if p.strip()]
    assert param_names == ["code"], (
        f"d5Prompt must take ONLY (code) — found params {param_names!r}; a second parameter is "
        "exactly how the D1 proposal leaked into the refuter's prompt before"
    )
    assert "d1Result" not in body, "d5Prompt body still references d1Result — blindness leak reintroduced"
    assert "JSON.stringify" not in body, "d5Prompt body stringifies something — a proposal leak by another name"
    assert not re.search(r"\bd1\b", body), (
        "d5Prompt body references a bare `d1` identifier — D5 must never see D1's output, directly "
        "or indirectly"
    )


def test_innocence_d1_prompt_may_reference_evidence(js_source: str) -> None:
    """INNOCENCE: d1Prompt (the EXTRACTOR, not the refuter) legitimately reads the evidence dir —
    proves the extraction/assertion machinery above is discriminating on the real leak (d1Result
    interpolated into ANOTHER seat's prompt), not just flagging any mention of evidence paths."""
    _params, body = _function_signature_and_body(js_source, "d1Prompt")
    assert "canonical.json" in body, "d1Prompt should legitimately reference the evidence dir"
    assert "crosswalk" in body and "pp28" in body


# ---------------------------------------------------------------------------
# 5. Membership gate exempts innocence controls from in-scope check (both directions)
# ---------------------------------------------------------------------------

def test_guilt_innocence_controls_exempt_from_in_scope_check(js_source: str) -> None:
    """GUILT: the outOfScope computation must filter OUT innocenceControl codes BEFORE checking
    membership — innocence controls are BY DESIGN non-members (OSS-native clean codes, same class
    as the pilot's 65121/85202/85579), and the workflow's own usage example (line ~92) shows an
    `{ code: "65121", innocenceControl: true }` entry. Requiring them to also be in-scope
    contradicted the script's own contract and blocked a real lot dispatch (run wf_3477eb84-e75,
    2026-07-18: REFUSED on 65121/85202, both legitimate innocence controls)."""
    assert re.search(
        r"outOfScope\s*=\s*CODES\.filter\(\s*\(c\)\s*=>\s*!c\.innocenceControl\s*\)",
        js_source,
    ), (
        "outOfScope computation does not exempt innocenceControl codes from the in-scope check — "
        "the 2026-07-18 over-match would block any lot containing a legitimate innocence control"
    )


def test_innocence_out_of_scope_non_innocence_code_still_refuses(js_source: str) -> None:
    """INNOCENCE: the guilt fix above must not be satisfiable by simply deleting the in-scope
    check outright — a genuinely out-of-scope NON-innocence code must still REFUSE the lot. Proves
    the exemption discriminates on innocenceControl, not on removing the gate entirely."""
    assert "not in-scope per the" in js_source
    assert re.search(r"if\s*\(outOfScope\.length\)\s*{", js_source), (
        "the out-of-scope refusal branch is missing — the membership gate would be a no-op"
    )


def test_guilt_in_scope_member_cannot_be_used_as_innocence_control(js_source: str) -> None:
    """GUILT (the OTHER direction): a code that IS an in-scope Batch A member cannot ALSO be
    flagged as an innocence control — a member has real obligations to adjudicate, so misusing it
    as a "nothing should change here" control would either mask a genuine miss or produce a
    spurious quarantine. Both directions of the exemption need their own guard (word-boundary /
    entity-level check per cicatrix family #3 — an exemption is a guardia a segno invertito)."""
    assert re.search(
        r"misusedAsInnocence\s*=\s*CODES\.filter\(\s*\(c\)\s*=>\s*c\.innocenceControl\s*&&\s*"
        r"inScopeCodes\.has\(c\.code\)",
        js_source,
    ), "no misusedAsInnocence guard found — an in-scope member could silently double as an innocence control"


def test_innocence_misused_as_innocence_refusal_branch_exists(js_source: str) -> None:
    """INNOCENCE: the misusedAsInnocence guilt check above must be wired to an actual REFUSE
    branch, not just a computed-and-ignored variable."""
    assert re.search(r"if\s*\(misusedAsInnocence\.length\)\s*{", js_source), (
        "misusedAsInnocence is computed but never gates the lot — the guard is dead code"
    )
    assert "cannot double as an innocence control" in js_source


# ---------------------------------------------------------------------------
# 6. D2 self-confirm failure retro-demotes a certified verdict (Lot A-L1 close-out, code 38222)
# ---------------------------------------------------------------------------

def test_guilt_d2_self_confirm_failure_retro_demotes_certified(js_source: str) -> None:
    """GUILT: a certified verdict whose D2 extraction failed self-confirmation
    (code_appears_in_row !== true) or came back with empty per_skala_rows MUST retro-demote to
    quarantined — the regression guard for code 38222 in Lot A-L1 (D1/D5 agreed clean, D2's
    evidence page only had the parent code 38220, but the runner still emitted certified)."""
    assert re.search(r"d2SelfConfirmFailed", js_source), (
        "no d2SelfConfirmFailed guard found — a failed D2 self-confirmation could still reach certified"
    )
    assert re.search(r"code_appears_in_row\s*!==\s*true", js_source), (
        "d2SelfConfirmFailed does not check self_confirmed.code_appears_in_row !== true"
    )
    assert re.search(r"per_skala_rows\.length\s*===\s*0", js_source), (
        "d2SelfConfirmFailed does not check for an empty per_skala_rows extraction"
    )
    assert re.search(
        r'verdict\s*=\s*d2SelfConfirmFailed\s*\?\s*"quarantined"\s*:\s*preD2Verdict',
        js_source,
    ), "the final verdict is not gated on d2SelfConfirmFailed — retro-demote is not wired"
    assert '"unresolvable_source_pointer"' in js_source


# NOTE (2026-07-19, Lot 5 conductor gate SECOND SIGNING, §1 BLOCKER): the two guilt/innocence tests
# that used to live here (test_guilt_innocence_prompt_never_announces_expected_verdict,
# test_innocence_neutral_symmetric_prompt_exists) guarded innocencePrompt()'s WORDING — but the red-
# team proved the Lot 4 prompt-only fix begat a twin bug on a DIFFERENT channel: INNOCENCE_SCHEMA's
# field descriptions leaked the control's nature and expected outcome even with a neutral prompt in
# place (both control seats' own notes self-identified as "innocence control"). The durable fix
# retires innocencePrompt()/INNOCENCE_SCHEMA entirely — a control now shares the EXACT D1/D5/D2
# schema+prompt a member code gets (see adjudicateInnocence() delegating to adjudicateCode() in the
# lot runner) — so there is no longer a standalone prompt to word-check; those two tests are
# SUPERSEDED by the schema-neutralization-v2 section below (section 7), which scans every seat-
# visible channel (prompt body AND schema property descriptions AND the label/phase/model literals
# passed to agent()) at once, per the gate report §6 lesson: a guilt test that only re-checks the
# channel that bit last time invites the next twin bug on yet another channel.


def test_innocence_successful_d2_keeps_certified_verdict(js_source: str) -> None:
    """INNOCENCE: a SUCCESSFUL D2 extraction (self-confirmed, non-empty rows) must NOT be
    downgraded, and a code that never triggers D2 at all must be unaffected — proves the
    retro-demote fires only on a genuine D2 failure, never on every D2 call or on codes where D2
    never ran (d2 stays null)."""
    assert re.search(
        r'const verdict = d2SelfConfirmFailed \? "quarantined" : preD2Verdict;',
        js_source,
    ), "verdict computation does not fall back to preD2Verdict when D2 self-confirms successfully"
    assert re.search(r"d2SelfConfirmFailed\s*=\s*\n?\s*d2\s*!==\s*null\s*&&", js_source), (
        "d2SelfConfirmFailed is not gated on d2 !== null — a code that never ran D2 could be "
        "wrongly demoted"
    )


# ---------------------------------------------------------------------------
# 7. INNOCENCE_SCHEMA neutralization v2 (Lot 5 conductor gate second signing, §1 BLOCKER /
#    §6 meta-pattern): the schema-shaped twin of the Lot-4 prompt fix. A control must now share the
#    EXACT D1/D5/D2 schema+prompt a member code gets — scanned across every seat-visible channel at
#    once (prompt body, schema property descriptions, and the label/phase/model literals passed to
#    agent()), not just the one channel ("boring"/"innocence control" prompt wording) that bit last
#    time (gate report §6: "the guard-fix-begets-twin-bug shape now has a THIRD instance").
# ---------------------------------------------------------------------------


def test_guilt_innocence_schema_and_prompt_are_retired(js_source: str) -> None:
    """GUILT: INNOCENCE_SCHEMA and innocencePrompt() must no longer be declared anywhere in the
    runner — their mere existence, even unused, is exactly the kind of residue that regrows a
    seat-visible surface later. Controls must have NO schema or prompt of their own left to leak
    from, under any name."""
    assert not re.search(r"\bconst\s+INNOCENCE_SCHEMA\b", js_source), (
        "INNOCENCE_SCHEMA is still declared — this is the exact schema-channel leak the Lot 5 "
        "gate's BLOCKER identified (field descriptions revealed control nature + expected outcome); "
        "controls must share D1_SCHEMA/D5_SCHEMA/D2_SCHEMA, never their own schema"
    )
    assert not re.search(r"\bfunction\s+innocencePrompt\b", js_source), (
        "innocencePrompt() is still declared — controls must share d1Prompt/d5Prompt/d2Prompt, "
        "never their own prompt, so there is nothing schema- or prompt-shaped left to leak from"
    )


def test_guilt_adjudicate_innocence_delegates_to_adjudicate_code(js_source: str) -> None:
    """GUILT: adjudicateInnocence must dispatch through adjudicateCode(code) — the EXACT function
    member codes use (same d1Prompt/D1_SCHEMA, d5Prompt/D5_SCHEMA, d2Prompt/D2_SCHEMA, same
    label/phase/model shape passed to agent(), same diffD1D5() compiler diff) — and must NOT call
    agent() directly itself. A direct agent() call here would mean a bespoke seat-visible surface
    still exists for controls, exactly the defect this fix eliminates."""
    _params, body = _function_signature_and_body(js_source, "adjudicateInnocence")
    assert re.search(r"\badjudicateCode\s*\(\s*code\s*\)", body), (
        "adjudicateInnocence does not call adjudicateCode(code) — it must delegate to the shared "
        "member pipeline rather than build any schema/prompt/label of its own"
    )
    assert "agent(" not in body, (
        "adjudicateInnocence still calls agent() directly — all seat dispatch for a control must "
        "happen exclusively inside adjudicateCode(), never in a separate call here"
    )


def test_innocence_shared_pipeline_body_carries_no_control_identifying_marker(js_source: str) -> None:
    """INNOCENCE (scans EVERY seat-visible channel at once — prompt bodies AND schema property
    descriptions — since adjudicateCode is now the SOLE dispatch path for both members and
    controls): d1Prompt/d5Prompt/d2Prompt bodies AND the D1_SCHEMA/D5_SCHEMA/D2_SCHEMA object
    literals must never mention 'innocence'/'control'/'boring' in any form — proves the actual text
    an agent() call sends to the model is genuinely agnostic to which kind of code invoked it.

    adjudicateCode's OWN runner-side bookkeeping (e.g. the `innocenceControl: false` field on its
    RETURN object) is intentionally OUT of scope here: that field is a value this JS computes AFTER
    the seat has already answered, never part of the prompt string or schema object handed to
    agent() — same distinction the gate report draws between 'seat-visible' and 'runner-side'.

    Word-boundary matching (scar-family #3 antidote, guard over-match): a bare substring check for
    'boring' false-positives inside 'NEIGHBORING'/'neighboring_codes' (both legitimate, in d2Prompt's
    body and D2_SCHEMA's own field name) — matched here with \\b so the marker can only fire on the
    real word (or a suffixed form, e.g. 'controls'/'controlled'), never a substring of an unrelated
    word."""
    marker_res = {
        "innocence": re.compile(r"\binnocence\w*\b"),
        "control": re.compile(r"\bcontrol\w*\b"),
        "boring": re.compile(r"\bboring\b"),
    }
    for fn in ("d1Prompt", "d5Prompt", "d2Prompt"):
        _params, body = _function_signature_and_body(js_source, fn)
        lowered = body.lower()
        for marker, pattern in marker_res.items():
            assert not pattern.search(lowered), (
                f"{fn} body contains {marker!r} — this prompt is sent VERBATIM to the seat for "
                "both members and controls; it must carry zero control-identifying text"
            )
    for schema_name in ("D1_SCHEMA", "D5_SCHEMA", "D2_SCHEMA"):
        m = re.search(rf"const {schema_name} = {{(.*?)\n}};", js_source, re.DOTALL)
        assert m, f"could not locate {schema_name} in lot runner"
        lowered = m.group(1).lower()
        for marker, pattern in marker_res.items():
            assert not pattern.search(lowered), (
                f"{schema_name} contains {marker!r} in a property description — this schema is "
                "handed VERBATIM to agent() for both members and controls; it must carry zero "
                "control-identifying text (this is exactly the channel the Lot 5 gate's BLOCKER "
                "found leaking on the retired INNOCENCE_SCHEMA)"
            )


def test_innocence_result_shape_still_reports_verdict_taxonomy(js_source: str) -> None:
    """INNOCENCE: the fix must not just delete the old defect — a runner-side (deterministic JS,
    executed AFTER the seat-blind adjudicateCode() call returns, never seen or executed by any seat)
    normalization must still tag the result innocenceControl/innocence, proving this is a delegate-
    then-relabel treatment swap, not a gutted no-op that silently drops the control marker."""
    _params, body = _function_signature_and_body(js_source, "adjudicateInnocence")
    assert "innocenceControl: true" in body
    assert "innocence: true" in body
    # the relabeling must happen strictly AFTER adjudicateCode's own (await-ed) result is in hand —
    # never interpolated into anything passed TO the seat call.
    assert re.search(r"await\s+adjudicateCode\s*\(\s*code\s*\)", body), (
        "adjudicateInnocence must await adjudicateCode(code) before doing any runner-side relabeling"
    )
