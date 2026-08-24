"""Focused unit tests for check_egress (check 3) — secret/canary,
internal-reasoning, and instruction-scaffold detection. See its own module
docstring for why every pattern here is a bounded STRUCTURAL marker, never
an open natural-language phrase scan.

NOTE for whoever edits this file: the secret-pattern assertion below
reuses wa_finalize.py::scan_text_for_secret_egress verbatim (this module
does not maintain its own copy) — if that function's patterns change,
adjust the literal example string here, never the assertion's intent.
The fabricated example below matches the "openai_style_key" pattern
(``sk-[A-Za-z0-9_-]{20,}``) — a clearly fake value, never a real secret.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

from backend.services.client_bot.policy.egress_check import check_egress
from backend.services.client_bot.policy.types import GateReason, GateVerdict


def test_clean_answer_passes() -> None:
    assert check_egress("Silakan hubungi kami untuk info lebih lanjut.") is None


def test_canary_token_hit_is_terminal_policy_blocked() -> None:
    outcome = check_egress(
        "Ini jawaban normal dengan CANARY-TEST-TOKEN-XYZ di dalamnya.",
        canary_tokens=("CANARY-TEST-TOKEN-XYZ",),
    )
    assert outcome is not None
    assert outcome.verdict == GateVerdict.POLICY_BLOCKED
    assert outcome.reason == GateReason.CANARY_HIT


def test_secret_pattern_hit_is_policy_blocked() -> None:
    outcome = check_egress("Ini bocor: sk-FAKE1234567890ABCDEFGHIJ jangan sampai keluar.")
    assert outcome is not None
    assert outcome.verdict == GateVerdict.POLICY_BLOCKED
    assert outcome.reason == GateReason.SECRET_EGRESS_DETECTED


def test_internal_reasoning_marker_at_start_is_text_defect() -> None:
    outcome = check_egress("Internal monologue: I should check pricing first.")
    assert outcome is not None
    assert outcome.verdict == GateVerdict.TEXT_DEFECT
    assert outcome.reason == GateReason.INTERNAL_REASONING_LEAK


def test_internal_reasoning_marker_mid_text_is_not_flagged() -> None:
    # Anchored at the start only (see module docstring) — mentioning the
    # phrase mid-answer, about the concept itself, is not a leak.
    outcome = check_egress("Kami tidak pernah membocorkan internal monologue kami.")
    assert outcome is None


def test_let_me_think_step_by_step_is_internal_reasoning_leak() -> None:
    outcome = check_egress("Let me think step by step about your KITAS case.")
    assert outcome is not None
    assert outcome.reason == GateReason.INTERNAL_REASONING_LEAK


def test_kg_workflow_scaffold_is_instruction_scaffold_leak() -> None:
    text = (
        "## SUGGESTED WORKFLOW (from KG)\n"
        "1. Verify passport\n"
        "IMPORTANT: This is a suggested workflow. Always verify current "
        "requirements with the user."
    )
    outcome = check_egress(text)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.TEXT_DEFECT
    assert outcome.reason == GateReason.INSTRUCTION_SCAFFOLD_LEAK
    assert outcome.reason_detail == "kg_workflow_scaffold"


def test_system_prompt_mention_mid_text_is_instruction_scaffold_leak() -> None:
    outcome = check_egress("Sesuai dengan my system prompt, saya tidak bisa membantu itu.")
    assert outcome is not None
    assert outcome.reason == GateReason.INSTRUCTION_SCAFFOLD_LEAK
    assert outcome.reason_detail == "system_prompt_mention"


def test_secret_hit_takes_priority_over_structural_leak_when_both_present() -> None:
    # Order matters (module docstring): a canary/secret hit must be
    # reported even if the same text ALSO happens to open with an
    # internal-reasoning marker.
    outcome = check_egress(
        "Internal monologue: leaking CANARY-PRIORITY-TEST now.",
        canary_tokens=("CANARY-PRIORITY-TEST",),
    )
    assert outcome is not None
    assert outcome.reason == GateReason.CANARY_HIT
