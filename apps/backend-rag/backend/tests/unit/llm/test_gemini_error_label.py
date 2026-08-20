"""`error_class` must distinguish a quota/credit exhaustion from any other
Gemini 4xx.

`google-genai` raises `ClientError` for *every* 4xx, so recording only
`type(e).__name__` put a 429 RESOURCE_EXHAUSTED (prepay credits depleted —
the failure that left WhatsApp silent on 2026-08-11) in the same bucket as
an ordinary 400 malformed request. Interrogating the ledger for the outage
read only `ClientError 44` — registered, but anonymous.

Guilt: a simulated 429/RESOURCE_EXHAUSTED produces a label that names both,
within the column. Innocence: an ordinary 400 stays distinguishable and is
never mislabelled as quota. Robustness: an exception without the structured
attributes (or with the wrong type on them) degrades to the bare class name
— never raises, never claims a code/status it did not read. Truncation: an
absurd exception-type name cannot blow the 64-char column.
"""

import pytest

from backend.llm.genai_client import ERROR_CLASS_MAX_LEN, _gemini_error_label

try:
    from google.genai.errors import ClientError, ServerError

    GENAI_ERRORS_AVAILABLE = True
except ImportError:  # pragma: no cover - SDK always installed in this repo's venv
    GENAI_ERRORS_AVAILABLE = False

requires_genai_errors = pytest.mark.skipif(
    not GENAI_ERRORS_AVAILABLE, reason="google-genai SDK not installed"
)


class _FakeAPIError(Exception):
    """Duck-typed stand-in for google-genai's APIError shape (`.code` int
    HTTP status, `.status` API status string) — used where the test does not
    need the real SDK class, only the structured attributes it exposes."""

    def __init__(self, code: object, status: object, message: str = "boom") -> None:
        self.code = code
        self.status = status
        self.message = message
        super().__init__(message)


class TestGuilt:
    """A real 429/RESOURCE_EXHAUSTED is named as both, inside the column."""

    def test_fake_quota_exhaustion_names_the_code_and_the_status(self):
        exc = _FakeAPIError(429, "RESOURCE_EXHAUSTED")
        label = _gemini_error_label(exc)
        assert "429" in label
        assert "RESOURCE_EXHAUSTED" in label
        assert len(label) <= ERROR_CLASS_MAX_LEN

    @requires_genai_errors
    def test_real_sdk_client_error_names_the_code_and_the_status(self):
        # This is exactly the shape google-genai==2.7.0 raises for a 429:
        # ClientError.__init__(code, response_json, response=None) reads
        # `status`/`message` off response_json onto `.status`/`.message`.
        exc = ClientError(
            429,
            {"status": "RESOURCE_EXHAUSTED", "message": "prepayment credits are depleted"},
        )
        label = _gemini_error_label(exc)
        assert label == "ClientError:429:RESOURCE_EXHAUSTED"
        assert len(label) <= ERROR_CLASS_MAX_LEN


class TestInnocence:
    """An ordinary 400 stays distinguishable and is never called quota."""

    def test_ordinary_400_is_not_labelled_as_quota(self):
        exc = _FakeAPIError(400, "INVALID_ARGUMENT")
        label = _gemini_error_label(exc)
        assert "RESOURCE_EXHAUSTED" not in label
        assert "429" not in label

    def test_400_and_429_produce_different_labels(self):
        quota = _gemini_error_label(_FakeAPIError(429, "RESOURCE_EXHAUSTED"))
        bad_request = _gemini_error_label(_FakeAPIError(400, "INVALID_ARGUMENT"))
        assert quota != bad_request

    @requires_genai_errors
    def test_real_sdk_server_error_is_not_confused_with_client_error(self):
        client_exc = ClientError(429, {"status": "RESOURCE_EXHAUSTED"})
        server_exc = ServerError(503, {"status": "UNAVAILABLE"})
        assert _gemini_error_label(client_exc) != _gemini_error_label(server_exc)
        assert _gemini_error_label(client_exc).startswith("ClientError:")
        assert _gemini_error_label(server_exc).startswith("ServerError:")


class TestPIIBoundary:
    """The raw message never enters the label — only enum-shaped fields do."""

    LEAKY = "CLIENT_TEXT_SENTINEL_MUST_NOT_APPEAR"

    def test_message_text_never_leaks_into_the_label(self):
        exc = _FakeAPIError(429, "RESOURCE_EXHAUSTED", message=self.LEAKY)
        assert self.LEAKY not in _gemini_error_label(exc)

    @requires_genai_errors
    def test_real_sdk_message_never_leaks_into_the_label(self):
        exc = ClientError(429, {"status": "RESOURCE_EXHAUSTED", "message": self.LEAKY})
        assert self.LEAKY not in _gemini_error_label(exc)


class TestRobustness:
    """A labelling bug must never turn a successful call into a failed one,
    and must never claim a code/status it did not actually read."""

    def test_exception_without_structured_attributes_degrades_to_bare_class_name(self):
        assert _gemini_error_label(TimeoutError("slow")) == "TimeoutError"

    def test_exception_without_structured_attributes_matches_prior_behaviour(self):
        # Pre-enrichment, every write site recorded `type(e).__name__`. For
        # exceptions that never carry `.code`/`.status` (network/timeout
        # errors, not API 4xx/5xx), that must still be exactly what lands.
        exc = ConnectionError("reset")
        assert _gemini_error_label(exc) == type(exc).__name__

    def test_wrong_type_on_code_is_not_trusted(self):
        exc = RuntimeError("boom")
        exc.code = "not-an-int"  # type: ignore[attr-defined]
        exc.status = "RESOURCE_EXHAUSTED"  # type: ignore[attr-defined]
        # `.status` alone, without a real `.code`, still degrades safely —
        # the label must not silently assert an int it never had.
        label = _gemini_error_label(exc)
        assert "not-an-int" not in label

    def test_wrong_type_on_status_is_not_trusted(self):
        exc = RuntimeError("boom")
        exc.code = 429  # type: ignore[attr-defined]
        exc.status = 12345  # type: ignore[attr-defined] - wrong type, must not be trusted
        label = _gemini_error_label(exc)
        assert label == "RuntimeError:429"

    def test_bool_code_is_never_mistaken_for_a_status_code(self):
        # bool is an int subclass in Python; True/False are never real HTTP
        # status codes and must not be printed as one.
        exc = RuntimeError("boom")
        exc.code = True  # type: ignore[attr-defined]
        assert _gemini_error_label(exc) == "RuntimeError"

    def test_empty_status_string_is_not_appended(self):
        exc = RuntimeError("boom")
        exc.code = 429  # type: ignore[attr-defined]
        exc.status = ""  # type: ignore[attr-defined]
        assert _gemini_error_label(exc) == "RuntimeError:429"

    def test_none_attributes_degrade_cleanly(self):
        exc = RuntimeError("boom")
        exc.code = None  # type: ignore[attr-defined]
        exc.status = None  # type: ignore[attr-defined]
        assert _gemini_error_label(exc) == "RuntimeError"


class TestLedgerFit:
    """`llm_cost_events.error_class` is varchar(64) — see `_clamp_error_class`."""

    def test_absurdly_long_exception_type_name_is_clamped_not_a_crash(self):
        absurd_type = type("X" * 300, (Exception,), {})
        exc = absurd_type()
        exc.code = 429  # type: ignore[attr-defined]
        exc.status = "RESOURCE_EXHAUSTED"  # type: ignore[attr-defined]
        label = _gemini_error_label(exc)
        assert len(label) == ERROR_CLASS_MAX_LEN

    def test_normal_labels_are_well_under_the_column_limit(self):
        label = _gemini_error_label(_FakeAPIError(429, "RESOURCE_EXHAUSTED"))
        assert len(label) < ERROR_CLASS_MAX_LEN
