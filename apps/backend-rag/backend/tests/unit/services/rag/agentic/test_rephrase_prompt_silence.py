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
        assert "Return ONLY the answer itself" in prompt

    def test_forbids_naming_the_internal_machinery(self, prompt: str) -> None:
        # The model must not tell the client a fact-checker rejected a draft.
        assert "anything that came before" in prompt

    def test_forbids_the_measured_acknowledgement_shapes(self, prompt: str) -> None:
        # These three are the exact shapes observed leaking in prod.
        # The gag no longer enumerates "thanks for the correction" as a quoted
        # example, for the same reason it no longer names the fact-checker: an
        # example of the leak is a template for the leak. It bans the CLASS.
        assert "no apology" in prompt.lower()
        assert "no thanks" in prompt.lower()
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
        assert "Write the answer using ONLY the provided context." in prompt
        assert "Do not invent information." in prompt

    def test_gag_targets_the_meta_layer_not_the_content(self, prompt: str) -> None:
        """The gag still bans meta-commentary — it just no longer NAMES what it bans.

        Rewritten 2026-08-11. The previous version required the literal words
        "fact-checker" and "rejection" to appear in the gag line, which is what
        the gag used to say: it enumerated the three concepts it forbade, and so
        introduced them into the model's context in order to forbid them. The
        leak this whole file exists for reappeared through exactly that surface —
        a client-facing answer narrating "The previous answer was rejected
        because…" from inside the monologue. A prohibition is a weak instrument
        against a concept the model is now holding; not supplying the concept is
        the stronger one.

        So this now asserts the ban is still there and still scoped to the meta
        layer, without demanding the vocabulary that was the problem.
        """
        assert "No preamble, no apology" in prompt
        assert "anything that came before" in prompt
        # and the substance of the answer is NOT gagged
        assert "Do not invent information." in prompt


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
        assert "must not appear unless" in out
        assert "some reason" in out

    def test_empty_missing_citations_renders_cleanly(self) -> None:
        out = build_rephrase_prompt("some reason", [])
        assert "must not appear unless" in out


class TestNoSecondCopyCanDrift:
    """One builder, one prompt — a future inline copy would silently lose the gag."""

    def test_the_rejection_header_exists_nowhere_in_the_module(self) -> None:
        """Zero, not one — INCLUDING in comments.

        This test caught its own author: after rewriting the prompt I kept the
        old header quoted verbatim in an explanatory comment, so a future
        `grep` for the phrase would still have found it in this file and read as
        if the code still said it. A record of a removed string is a copy of it.
        """
        from pathlib import Path

        import backend.services.rag.agentic.reasoning as reasoning_module

        source = Path(reasoning_module.__file__).read_text(encoding="utf-8")
        assert source.count("SYSTEM: Your previous answer was REJECTED") == 0


def test_rephrase_prompt_never_narrates_a_rejection() -> None:
    """The retry prompt must not contain a story about a failed attempt.

    The gag added 2026-07-27 stopped the model APOLOGISING to the client. On
    2026-08-11 the leak reappeared one layer down: probing 16 cold questions in 8
    languages caught an Indonesian answer opening "internal_monologue The user is
    asking for the requirements to open a PT PMA in Bali. The previous answer was
    rejected because it included detailed inf…". The model obeys "never mention
    the rejection" in its reply and narrates it in the monologue, which ships
    (python-genai #2121: thought text arrives with `part.thought` false, so the
    structured filter misses it, and the response cleaner can strip the marker
    token but not the sentences after it).

    A gag can only ask the model not to repeat what is in its context. This
    asserts the stronger property: the rejection is not in its context at all.
    The verifier's information survives as forward constraints — asserted below,
    so this cannot be satisfied by simply dropping the feedback.
    """
    prompt = build_rephrase_prompt(
        reasoning="claim about capital requirement is unsupported",
        missing_citations=["minimum paid-up capital IDR 10 billion"],
    )
    lowered = prompt.lower()

    narrating = [
        "rejected",
        "rejection",
        "fact-checker",
        "factchecker",
        "previous answer",
        "previous attempt",
        "your last answer",
        "you were wrong",
        "failed",
        "error",
    ]
    found = [w for w in narrating if w in lowered]
    assert not found, f"the retry prompt narrates a rejection: {found}"

    # …and the information the verifier produced still reaches the model, so this
    # test cannot be satisfied by deleting the feedback instead of rephrasing it.
    assert "minimum paid-up capital IDR 10 billion" in prompt
    assert "claim about capital requirement is unsupported" in prompt


def test_rephrase_prompt_keeps_the_gag_as_a_second_layer() -> None:
    """Removing the thing to narrate is the mechanism; the gag is belt-and-braces.

    Both must be present — the model can still be told about a rejection by some
    other future caller, and the gag is what covers that.
    """
    prompt = build_rephrase_prompt(reasoning="r", missing_citations=["c"])
    assert "This is the user's first sight of it." in prompt
    assert "Answer in the SAME LANGUAGE" in prompt
