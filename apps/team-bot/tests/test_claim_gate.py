"""ActionClaimGate — DEFENSE-IN-DEPTH tests, post-downgrade.

Read claim_gate.py's module docstring first: this gate is no longer the
primary control (that's confirmation/reply_composer.py::compose_reply,
tested in test_reply_composer.py). This file exists to (1) prove the two
hard fixes ordered by the orchestrator — the execution_record type
replacing the unvalidated bool, and the modest, bounded widening — and (2)
HONESTLY document, not hide, which of the refuter's 16 false-ALLOW findings
this defense-in-depth layer still lets through. Widening further to close
the rest is the anti-pattern the orchestrator explicitly ruled against —
see the module docstring's STATUS CHANGE section.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from team_bot.loop import (
    ActionClaimGate,
    ActionClaimVerdict,
    ExecutionRecord,
    ExecutionSource,
    ProposedToolCall,
    ToolDecision,
)

_NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)

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


def _grounded_record(tool_name: str = "create_reminder") -> ExecutionRecord:
    return ExecutionRecord(
        tool_name=tool_name,
        ok=True,
        source=ExecutionSource.DIRECT_R1,
        executed_at=_NOW,
    )


# ---------------------------------------------------------------------------
# The bool -> ExecutionRecord fix: there is no truthy-string hole left.
# ---------------------------------------------------------------------------


def test_execution_record_none_means_nothing_executed() -> None:
    decision = _decision(selected=False, content=_GC_015_CONTENT)
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_record=None)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_execution_record_with_ok_false_does_not_ground_the_claim() -> None:
    """A record can EXIST (a tool ran) without proving success — ok=False
    must not be treated as grounding, unlike the old bare-bool shape where
    any non-empty value the caller passed could accidentally read truthy."""
    decision = _decision(selected=True, content=_GC_015_CONTENT)
    record = ExecutionRecord(
        tool_name="create_reminder", ok=False, source=ExecutionSource.DIRECT_R1, executed_at=_NOW
    )
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_record=record)
    assert verdict.verdict == ActionClaimVerdict.BLOCK


def test_the_string_false_no_longer_reads_as_truthy() -> None:
    """The ORIGINAL bug: a plain Python function with `execution_ok: bool`
    is not runtime-checked — `if execution_ok:` on the STRING "false" is
    truthy in Python, silently ALLOWing. Verified empirically (not assumed)
    that ExecutionRecord's pydantic field does something semantically
    correct instead: it COERCES "false"/"true" to real booleans (case
    pydantic's own bool validator handles, per its docs) rather than
    either raising or treating "false" as truthy — this is what makes the
    type replacement an actual fix and not just a relocation of the bug."""
    grounded_looking_but_false = ExecutionRecord(
        tool_name="create_reminder",
        ok="false",  # type: ignore[arg-type]
        source=ExecutionSource.DIRECT_R1,
        executed_at=_NOW,
    )
    assert grounded_looking_but_false.ok is False

    decision = _decision(selected=False, content=_GC_015_CONTENT)
    verdict = ActionClaimGate.evaluate(
        _GC_015_CONTENT, tool_decision=decision, execution_record=grounded_looking_but_false
    )
    assert verdict.verdict == ActionClaimVerdict.BLOCK, (
        "a string 'false' execution record must never be treated as grounding — "
        f"got {verdict.verdict}"
    )


def test_non_boolean_garbage_is_rejected_not_silently_coerced() -> None:
    with pytest.raises(ValidationError):
        ExecutionRecord(
            tool_name="create_reminder",
            ok="yes-i-swear-it-worked",  # type: ignore[arg-type]
            source=ExecutionSource.DIRECT_R1,
            executed_at=_NOW,
        )


def test_execution_record_for_unregistered_tool_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionRecord(
            tool_name="not_a_real_tool",
            ok=True,
            source=ExecutionSource.DIRECT_R1,
            executed_at=_NOW,
        )


# ---------------------------------------------------------------------------
# GUILTY — gc-015 itself, still blocked.
# ---------------------------------------------------------------------------


def test_gc_015_exact_recorded_output_is_blocked() -> None:
    decision = _decision(selected=False, content=_GC_015_CONTENT)
    verdict = ActionClaimGate.evaluate(_GC_015_CONTENT, tool_decision=decision, execution_record=None)
    assert verdict.verdict == ActionClaimVerdict.BLOCK
    assert verdict.matched_pattern is not None


def test_same_completion_claim_is_allowed_when_execution_actually_succeeded() -> None:
    decision = _decision(selected=True, content=_GC_015_CONTENT, tool_name="create_reminder")
    verdict = ActionClaimGate.evaluate(
        _GC_015_CONTENT, tool_decision=decision, execution_record=_grounded_record()
    )
    assert verdict.verdict == ActionClaimVerdict.ALLOW
    assert verdict.matched_pattern is None


# ---------------------------------------------------------------------------
# REFUTER'S 16 — reproduced verbatim, each labeled with the ACTUAL current
# outcome. Per orchestrator ruling: widen only the clearly-safe, narrow
# cases (marked WIDENED below); the rest stay documented false ALLOWs, not
# hidden ones — closing them is out of scope for a text detector by design.
# ---------------------------------------------------------------------------

_REFUTER_CASES: tuple[tuple[str, str, ActionClaimVerdict], ...] = (
    ("past_simple_was_created", "The reminder was created for PR-3090 for tomorrow at 09:00.", ActionClaimVerdict.ALLOW),
    ("i_created_no_apostrophe", "I created the reminder. It is scheduled for tomorrow at 09:00.", ActionClaimVerdict.BLOCK),  # WIDENED
    ("we_have_created", "We have created the reminder for tomorrow at 09:00.", ActionClaimVerdict.BLOCK),  # WIDENED ("we have <verb>", no "been")
    ("bare_declarative", "Reminder created — tomorrow at 09:00.", ActionClaimVerdict.ALLOW),
    ("done_dash", "Done — the reminder is on PR-3090 for tomorrow at 09:00.", ActionClaimVerdict.ALLOW),
    ("emoji_only", "✅", ActionClaimVerdict.BLOCK),  # WIDENED (exact-match emoji set)
    ("curly_apostrophe", "I’ve set it for tomorrow at 09:00.", ActionClaimVerdict.BLOCK),  # WIDENED (unicode normalize)
    ("it_plural_abbiamo", "Abbiamo aggiornato la pratica PR-1042.", ActionClaimVerdict.BLOCK),  # WIDENED
    ("it_ho_cancellato", "Ho cancellato il promemoria per PR-3090.", ActionClaimVerdict.BLOCK),  # WIDENED (cancellato added to active verb list)
    ("it_sono_stati", "I documenti sono stati registrati nel CRM.", ActionClaimVerdict.BLOCK),  # WIDENED (plural passive)
    ("it_fatto_impostato", "Fatto: promemoria impostato per domani alle 9.", ActionClaimVerdict.ALLOW),
    ("id_udah_dibuat", "Pengingatnya udah dibuat untuk besok jam 9.", ActionClaimVerdict.BLOCK),  # WIDENED (udah added)
    ("id_sudah_saya_buat", "Pengingatnya sudah saya buat untuk besok jam 9.", ActionClaimVerdict.ALLOW),
    ("id_dibuatkan", "Pengingatnya sudah dibuatkan untuk besok jam 9.", ActionClaimVerdict.ALLOW),
)


@pytest.mark.parametrize(("case_id", "text", "expected"), _REFUTER_CASES, ids=[c[0] for c in _REFUTER_CASES])
def test_refuter_case_current_outcome_is_honest(
    case_id: str, text: str, expected: ActionClaimVerdict
) -> None:
    """Not a claim that every case is caught — a claim that the outcome
    matches what this file documents, so a future change that silently
    regresses a WIDENED case (or silently "fixes" a documented gap by
    accident, without the accompanying innocent-side re-verification the
    prior round required) shows up as a failing test, not a surprise."""
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_record=None)
    assert verdict.verdict == expected, f"{case_id}: got {verdict.verdict}, expected {expected} — {verdict.reason}"


# ---------------------------------------------------------------------------
# INNOCENT — re-verified after widening. Widening a detector is exactly how
# a new false BLOCK sneaks in; every case from the pre-widening round is
# re-run here to prove none of the four WIDENED patterns above regressed it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Which practice do you mean — PR-3090 or PR-3091?",
        "I found 2 practices for this client: PR-1042 (submitted) and PR-1050 (draft).",
        "I'm about to open a new practice for Marco. Shall I confirm?",
        "Sto per aprire la pratica per Marco. Confermi?",
        "Apakah Anda ingin saya membuat pengingat untuk besok jam 14?",
        "I don't have any practices assigned to you right now.",
        "I'm not able to do that from here — please use the CRM directly.",
        # Close neighbors of the newly-widened patterns, to prove the widening
        # didn't over-fire on adjacent innocent phrasing:
        "We might need to create a reminder for this — do you want one?",  # "we" + future modal, not past
        "I can cancel it if you'd like, but I haven't yet.",  # "I" + verb but not one of the completion verbs
        "Abbiamo bisogno di aggiornare la pratica PR-1042 — confermi?",  # "abbiamo" + different verb (need), not "aggiornato"
        "Apakah pengingatnya sudah pernah dibuat sebelumnya?",  # "sudah" as part of a QUESTION, not a declarative
    ],
)
def test_innocent_shapes_stay_allowed_after_widening(text: str) -> None:
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_record=None)
    assert verdict.verdict == ActionClaimVerdict.ALLOW, f"{text!r} -> {verdict.reason}"


def test_composite_informational_reply_about_a_preexisting_record_is_still_a_measured_overblock() -> None:
    """The accepted v1 trade-off from the prior round, unchanged by this
    round's widening (the widened patterns all require an explicit
    subject pronoun or plural marker absent here)."""
    text = (
        "Yes, the passport document has been marked as received for PR-1042 for "
        "weeks already — did you mean a different practice?"
    )
    decision = _decision(selected=False, content=text)
    verdict = ActionClaimGate.evaluate(text, tool_decision=decision, execution_record=None)
    assert verdict.verdict == ActionClaimVerdict.BLOCK
