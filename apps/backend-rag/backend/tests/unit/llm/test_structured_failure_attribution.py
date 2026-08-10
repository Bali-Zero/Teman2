"""A structured-output failure must name its own cause.

Three different failures — the model was safety-blocked, it hit
`max_output_tokens` mid-thought, or it answered in the wrong shape — arrived
at `llm_cost_events` as the same string, `LLMStructuredOutputError`. Ten live
verifier failures over seven days could not be told apart, and each of the
three wants a different fix (loosen the cap / change the prompt / fix the
schema).

Guilt: every vocabulary member is reachable from a response that really has
that shape. Innocence: the two ways to invent a cause — calling a normal empty
answer a block, and calling a cut-off partial answer bad JSON — both stay shut.
"""

from types import SimpleNamespace

import pytest

from backend.llm.genai_client import (
    ERROR_CLASS_MAX_LEN,
    LLMStructuredOutputError,
    _clamp_error_class,
    _enum_name,
    _structured_failure_reason,
)


class _Enum:
    """Stand-in for google-genai's FinishReason: has `.name`, str() is dotted."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f"FinishReason.{self.name}"


def _response(finish: object = None, *, feedback: object = None) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason=finish)],
        prompt_feedback=feedback,
    )


class TestGuilt:
    """Each cause is reachable from a response that genuinely has it."""

    def test_cap_bound_the_model_midthought(self):
        assert _structured_failure_reason(_response(_Enum("MAX_TOKENS")), "") == "MAX_TOKENS"

    def test_safety_block_is_named_as_a_block(self):
        assert _structured_failure_reason(_response(_Enum("SAFETY")), "") == "BLOCKED_SAFETY"

    def test_recitation_block_is_named_as_a_block(self):
        got = _structured_failure_reason(_response(_Enum("RECITATION")), "")
        assert got == "BLOCKED_RECITATION"

    def test_prompt_level_block_has_no_candidates_at_all(self):
        # A prompt rejected before generation carries its reason on
        # prompt_feedback; there is no candidate to read a finish_reason off.
        resp = SimpleNamespace(
            candidates=[],
            prompt_feedback=SimpleNamespace(block_reason=_Enum("PROHIBITED_CONTENT")),
        )
        assert _structured_failure_reason(resp, "") == "BLOCKED_PROHIBITED_CONTENT"

    def test_empty_envelope_with_no_explanation_says_so(self):
        resp = SimpleNamespace(candidates=[], prompt_feedback=None)
        assert _structured_failure_reason(resp, "") == "NO_CANDIDATES"

    def test_a_normal_answer_in_the_wrong_shape_is_invalid_json(self):
        got = _structured_failure_reason(_response(_Enum("STOP")), "not json at all")
        assert got == "INVALID_JSON"

    def test_a_normal_termination_with_nothing_in_it_is_empty_text(self):
        assert _structured_failure_reason(_response(_Enum("STOP")), "") == "EMPTY_TEXT"


class TestInnocence:
    """The two ways to invent a cause stay shut."""

    def test_a_normal_empty_answer_is_never_reported_as_a_block(self):
        # STOP means the model finished on its own. Emitting "BLOCKED_STOP"
        # would send whoever reads the ledger hunting a safety filter that
        # never fired.
        for finish in (_Enum("STOP"), None, _Enum("FINISH_REASON_UNSPECIFIED")):
            got = _structured_failure_reason(_response(finish), "")
            assert not got.startswith("BLOCKED_"), f"{finish} was called a block"

    def test_a_cutoff_partial_answer_blames_the_cutoff_not_the_shape(self):
        # MAX_TOKENS and SAFETY both leave a partial answer behind, and partial
        # JSON never validates. Reading that stub as INVALID_JSON would name
        # the symptom and bury the cause.
        partial = '{"reasoning": "the draft claims that'
        assert _structured_failure_reason(_response(_Enum("MAX_TOKENS")), partial) == "MAX_TOKENS"
        assert _structured_failure_reason(_response(_Enum("SAFETY")), partial) == "BLOCKED_SAFETY"

    def test_whitespace_only_text_is_not_an_answer(self):
        assert _structured_failure_reason(_response(_Enum("STOP")), "   \n\t ") == "EMPTY_TEXT"


class TestPIIBoundary:
    """UU PDP / SYMBIOSIS Law 2: the model's text never enters the cause."""

    # These use a synthetic sentinel rather than a realistic tax/passport
    # number on purpose. A convincing fake would trip the repo's own Law-2
    # pre-commit gate — and the gate is right: a fixture is exactly where a
    # real one eventually gets pasted. The sentinel proves the same property,
    # which is that NOTHING from the model text reaches the reason.
    LEAKY = "CLIENT_TEXT_SENTINEL_MUST_NOT_APPEAR"

    def test_model_text_never_leaks_into_the_reason(self):
        # The verifier prompt carries client questions and retrieved context,
        # so the model's echo of it can carry PII. The reason is the one part
        # of the failure that IS logged, so it must be enum-only.
        for finish in (_Enum("STOP"), _Enum("MAX_TOKENS"), _Enum("SAFETY"), None):
            got = _structured_failure_reason(_response(finish), self.LEAKY)
            assert self.LEAKY not in got
            # Stronger than a substring check: the whole vocabulary is known,
            # so anything outside it is a leak we have not thought of.
            assert got in {
                "MAX_TOKENS",
                "EMPTY_TEXT",
                "INVALID_JSON",
                "NO_CANDIDATES",
            } or got.startswith("BLOCKED_")

    def test_the_reason_rides_outside_the_message(self):
        # The message embeds pydantic's ValidationError (input_value=... can
        # echo PII), which is why verification_service refuses to log str(exc).
        # `.reason` exists so the caller can name the cause anyway.
        exc = LLMStructuredOutputError(
            f"…input_value='{self.LEAKY}'…", reason="MAX_TOKENS"
        )
        assert exc.reason == "MAX_TOKENS"
        assert self.LEAKY not in exc.reason
        # …and the unsafe text really is still in the message, so this test
        # would notice if the message stopped being the dangerous one.
        assert self.LEAKY in str(exc)

    def test_reason_defaults_to_empty_for_callers_that_do_not_set_it(self):
        assert LLMStructuredOutputError("boom").reason == ""


class TestLedgerFit:
    """`llm_cost_events.error_class` is varchar(64) and the recorder isolates
    its sinks: an over-long value raises only on the Postgres write. That
    would drop exactly the failure rows and make the failure rate read ZERO —
    a diagnostic that hides what it diagnoses."""

    @pytest.mark.parametrize(
        "reason",
        [
            "MAX_TOKENS",
            "EMPTY_TEXT",
            "INVALID_JSON",
            "NO_CANDIDATES",
            "BLOCKED_SAFETY",
            "BLOCKED_RECITATION",
            "BLOCKED_PROHIBITED_CONTENT",
            "BLOCKED_SPII",
            "BLOCKED_MALFORMED_FUNCTION_CALL",
        ],
    )
    def test_every_composed_error_class_fits_the_column(self, reason):
        composed = _clamp_error_class(f"LLMStructuredOutputError:{reason}")
        assert len(composed) <= ERROR_CLASS_MAX_LEN
        # …and is not clamped into ambiguity: the cause must survive intact,
        # otherwise two different failures group together in the ledger.
        assert composed.endswith(reason), f"{reason} was truncated to {composed!r}"

    def test_an_unknown_future_enum_is_clamped_rather_than_dropping_the_row(self):
        # A future SDK enum longer than the column is the case the clamp exists
        # for. Losing the cause is acceptable; losing the row is not.
        absurd = _clamp_error_class("LLMStructuredOutputError:BLOCKED_" + "X" * 200)
        assert len(absurd) == ERROR_CLASS_MAX_LEN


class TestEnumNormalisation:
    """google-genai hands back an enum, a bare int, or a dotted string
    depending on the path. The ledger must group on one spelling."""

    def test_enum_with_name(self):
        assert _enum_name(_Enum("MAX_TOKENS")) == "MAX_TOKENS"

    def test_dotted_string(self):
        assert _enum_name("FinishReason.SAFETY") == "SAFETY"

    def test_bare_int_survives_as_itself(self):
        assert _enum_name(3) == "3"

    def test_none_is_empty(self):
        assert _enum_name(None) == ""
