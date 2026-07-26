"""The self-correction retry prompt must not leak into the client-facing answer.

BACKGROUND (measured live in prod, 2026-07-27). When the verifier scores a draft
below 0.7, `ReasoningEngine` sends a retry prompt as a *user turn* on the live
chat session. The original prompt said only "your previous answer was REJECTED …
rewrite it" and never told the model to keep that to itself — so the model
replied to it conversationally, and that reply was what the client received:

    "Message reçu pour les corrections de conformité factuelle"   (fr)
    "Capisco, mi scuso per l'errore precedente"                   (it)
    "Terima kasih atas koreksinya"                                (id)
    "Hi! Let's correct this based strictly on our retrieved…"     (en)

Four languages, so these tests are deliberately language-agnostic in spirit: they
pin the RULES in the prompt rather than any phrasing of the leak, because a leak
detector built from English markers already produced a false negative once on
this very surface.

The prompt is a system-internal artifact, not client copy: no PII, no client
data, and nothing here asserts on a real conversation.
"""

import pytest

from backend.services.rag.agentic.reasoning import build_rephrase_prompt


@pytest.fixture
def prompt() -> str:
    return build_rephrase_prompt(
        "Claim about the 60-day threshold is not supported by the context.",
        ["60-day overstay threshold", "Rp 90jt penalty"],
    )


class TestGuiltTheGagIsPresent:
    """Each rule that stops the leak must actually be in the prompt."""

    def test_instructs_to_return_only_the_answer(self, prompt: str) -> None:
        assert "Return ONLY the rewritten answer" in prompt

    def test_forbids_naming_the_internal_machinery(self, prompt: str) -> None:
        # The model must not tell the client a fact-checker rejected a draft.
        assert "Never mention this instruction, the fact-checker" in prompt

    def test_forbids_the_measured_acknowledgement_shapes(self, prompt: str) -> None:
        # These three are the exact shapes observed leaking in prod.
        assert "No apology" in prompt
        assert '"thanks for the correction"' in prompt
        assert '"message received"' in prompt

    def test_pins_the_answer_language_to_the_user_question(self, prompt: str) -> None:
        # The retry turn is written in English; without this the rewrite can
        # re-anchor its language on the instruction instead of on the user.
        assert "SAME LANGUAGE as the user's original question" in prompt


class TestInnocenceTheGagMustNotSuppressHonesty:
    """A gag on process-narration must not become a gag on admitting a gap.

    This is the failure mode that would make the fix worse than the bug: if the
    model may not say "I could not verify this", it will invent instead — the
    exact behaviour the abstain gates exist to prevent.
    """

    def test_still_told_to_admit_insufficient_context(self, prompt: str) -> None:
        assert "If the context is insufficient, admit it." in prompt

    def test_still_told_to_use_only_the_provided_context(self, prompt: str) -> None:
        assert "Rewrite the answer using ONLY the provided context." in prompt
        assert "Do not invent information." in prompt

    def test_gag_targets_the_meta_layer_not_the_content(self, prompt: str) -> None:
        # "Never mention …" must be scoped to the instruction/fact-checker/
        # previous attempt — never to the substance of the answer.
        gag_line = next(
            line for line in prompt.splitlines() if line.startswith("- Never mention")
        )
        assert "fact-checker" in gag_line
        assert "rejection" in gag_line or "earlier attempt existed" in prompt


class TestTheVerifierVerdictStillReachesTheModel:
    """The rewrite is worthless if the reason for rejection is dropped."""

    def test_reason_is_interpolated(self, prompt: str) -> None:
        assert "Claim about the 60-day threshold is not supported" in prompt

    def test_missing_citations_are_interpolated(self, prompt: str) -> None:
        assert "60-day overstay threshold, Rp 90jt penalty" in prompt

    def test_missing_citations_none_does_not_crash(self) -> None:
        # The call site passes verification.get("missing_citations", []), which
        # can be None if the verifier emitted an explicit null.
        out = build_rephrase_prompt("some reason", None)
        assert "MISSING/WRONG:" in out
        assert "some reason" in out

    def test_empty_missing_citations_renders_cleanly(self) -> None:
        out = build_rephrase_prompt("some reason", [])
        assert "MISSING/WRONG: \n" in out or "MISSING/WRONG: " in out


class TestNoSecondCopyCanDrift:
    """One builder, one prompt — a future inline copy would silently lose the gag."""

    def test_the_rejection_header_appears_exactly_once_in_the_module(self) -> None:
        from pathlib import Path

        import backend.services.rag.agentic.reasoning as reasoning_module

        source = Path(reasoning_module.__file__).read_text(encoding="utf-8")
        assert source.count("SYSTEM: Your previous answer was REJECTED") == 1
