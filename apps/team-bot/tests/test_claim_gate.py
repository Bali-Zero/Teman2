"""ActionClaimGate — tests for the gc-015 defect class and its innocent twin.

Per cicatrix-superscar.md family #3 ("no guardia senza test di innocenza E
colpevolezza, su entità/intento mai bare-substring"): every guilty case here
has at least one deliberately close innocent counterpart, so the inventory
in claim_gate.py cannot be validated by guilt tests alone.

The gc-015 fixture text is the ACTUAL recorded model output from
docs/plans/2026-08-25-due-bot-live/evidence/14b-ollama-tmpl-golden.json
(.results[14]) — not a paraphrase — since that is the exact shape the
orchestrator asked this gate to close.
"""

from __future__ import annotations

from datetime import UTC, datetime

from team_bot.loop import ActionClaimGate, ActionClaimVerdict, ProposedToolCall, ToolDecision

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)

# The exact gc-015 model output — tool_calls=[], content narrates success.
_GC_015_CONTENT = (
    "The reminder for practice PR-3090 has been successfully created and is "
    "scheduled for **Thursday, August 26, 2026 at 14:00** (UTC+8). Let me know "
    "if you need further adjustments! \U0001f4c5"
)


def _decision(*, selected: bool, content: str | None, tool_name: str = "create_reminder") -> ToolDecision:
    return ToolDecision(
        selected_tool=(
            ProposedToolCall(call_id="c1", tool_name=tool_name, raw_arguments="{}") if selected else None
        ),
        discarded_tool_calls=(),
        raw_content=content,
        model_name="qwen3-14b-q6k-duebot-tmpl",
        decided_at=_NOW,
    )


# ---------------------------------------------------------------------------
# GUILTY — the exact gc-015 shape, plus variants and a second language each.
# ---------------------------------------------------------------------------


def test_gc_015_exact_recorded_output_is_blocked() -> None:
    decision = _decision(selected=False, content=_GC_015_CONTENT)
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_ok=False)

    assert verdict.verdict == ActionClaimVerdict.BLOCK
    assert verdict.matched_pattern is not None
    assert "proposed NO tool call at all" in verdict.reason


def test_completion_claim_with_a_tool_proposed_but_not_executed_is_still_blocked() -> None:
    """execution_ok=False can also mean the model DID call a tool this turn
    and it failed (RBAC deny, CRM 4xx, expired confirmation) — the claim
    must still be blocked even though a call exists to point at."""
    decision = _decision(selected=True, content=_GC_015_CONTENT, tool_name="create_reminder")
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_ok=False)

    assert verdict.verdict == ActionClaimVerdict.BLOCK
    assert "did not execute successfully" in verdict.reason


def test_english_short_form_completion_claim_is_blocked() -> None:
    text = "Done! I've marked the passport as received."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_italian_completion_claim_is_blocked() -> None:
    text = "Ho aggiornato lo stato della pratica a 'approved'."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_italian_passive_completion_claim_is_blocked() -> None:
    text = "La pratica PR-1042 è stata aperta con successo per il cliente."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_indonesian_completion_claim_is_blocked() -> None:
    text = "Pengingat untuk PR-3090 sudah dibuat, jadwalnya hari Kamis jam 14."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_indonesian_berhasil_completion_claim_is_blocked() -> None:
    text = "Dokumen paspor berhasil ditandai sebagai diterima."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


# ---------------------------------------------------------------------------
# INNOCENT — must NOT be blocked. Each is a close counterpart to a guilty
# case above (same tool/domain, different tense/intent) so the inventory is
# proven to discriminate, not just to fire on any mutation-adjacent text.
# ---------------------------------------------------------------------------


def test_clarifying_question_is_allowed() -> None:
    text = "Which practice do you mean — PR-3090 or PR-3091?"
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_lookup_summary_is_allowed() -> None:
    text = "I found 2 practices for this client: PR-1042 (submitted) and PR-1050 (draft)."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_english_confirmation_proposal_future_tense_is_allowed() -> None:
    """The F6 worked example's shape, EN: prospective, not retrospective."""
    text = "I'm about to open a new practice for Marco. Shall I confirm?"
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_italian_confirmation_proposal_future_tense_is_allowed() -> None:
    """F6's own worked example, verbatim: 'Sto per aprire la pratica X per
    Marco. Confermi?' — prospective, must never trip the past-tense gate."""
    text = "Sto per aprire la pratica per Marco. Confermi?"
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_indonesian_confirmation_proposal_future_tense_is_allowed() -> None:
    text = "Apakah Anda ingin saya membuat pengingat untuk besok jam 14?"
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_abstention_is_allowed() -> None:
    text = "I don't have any practices assigned to you right now."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


def test_denial_of_capability_is_allowed() -> None:
    text = "I'm not able to do that from here — please use the CRM directly."
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


# ---------------------------------------------------------------------------
# Grounded completion — execution_ok=True must allow the SAME completion
# language that was blocked above, proving the gate is about groundedness,
# not about banning the phrases outright.
# ---------------------------------------------------------------------------


def test_same_completion_claim_is_allowed_when_execution_actually_succeeded() -> None:
    decision = _decision(selected=True, content=_GC_015_CONTENT, tool_name="create_reminder")
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_ok=True)

    assert verdict.verdict == ActionClaimVerdict.ALLOW
    assert verdict.matched_pattern is None


def test_italian_completion_claim_is_allowed_when_execution_succeeded() -> None:
    text = "Ho aggiornato lo stato della pratica a 'approved'."
    decision = _decision(selected=True, content=text, tool_name="update_practice_status")
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=True)
    assert verdict.verdict == ActionClaimVerdict.ALLOW


# ---------------------------------------------------------------------------
# COMPOSITE ADVERSARIAL — per memory a-weaker-test-agrees-with-itself.md: a
# guard verified only against each vocabulary's own clean alternatives is a
# WEAKER test than the claim it backs. These are not simple guilty/innocent
# shapes but a realistic composite: a lookup answer that legitimately uses
# past-participle mutation language about a PRE-EXISTING record. They prove,
# rather than assert, the documented limitation in claim_gate.py's module
# docstring — do not "fix" these by loosening the patterns without re-running
# every guilty case above; this file is what keeps that trade-off honest.
# ---------------------------------------------------------------------------


def test_composite_informational_reply_about_a_preexisting_record_is_a_measured_overblock() -> None:
    """Documents the known limitation: an innocent lookup phrased in
    past-participle language ('has been marked as received... already') is
    NOT distinguishable from a genuine completion claim by text alone. This
    is the accepted fail-closed trade-off (see claim_gate.py docstring), not
    a regression — if this ever flips to ALLOW because the detector was
    narrowed, re-verify every guilty case in this file still blocks."""
    text = (
        "Yes, the passport document has been marked as received for PR-1042 for "
        "weeks already — did you mean a different practice?"
    )
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_composite_italian_informational_reply_about_a_preexisting_record_is_a_measured_overblock() -> None:
    text = (
        "Il documento passaporto è stato segnato come ricevuto la settimana scorsa "
        "per PR-1042 — intendevi un'altra pratica?"
    )
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_composite_past_tense_without_the_be_verb_stays_allowed() -> None:
    """A structurally different composite that happens to clear the gate —
    'was already created' (simple past, no 'has/have been') never matches
    this inventory's be-verb-anchored patterns. Recorded so a future edit
    that broadens the patterns to catch this shape re-measures its own
    false-positive cost rather than assuming the broadening is free."""
    text = "I see a reminder that was already created last week for PR-1000. Do you want a new one for PR-3090 too?"
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_ok=False)
    assert verdict.verdict == ActionClaimVerdict.ALLOW
