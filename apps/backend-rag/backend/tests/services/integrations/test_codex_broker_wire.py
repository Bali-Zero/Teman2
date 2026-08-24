"""Tests for backend.services.integrations.codex_broker_wire.

Zero network, zero subprocess: `classify_codex_exec_failure`/
`describe_codex_exec_failure` are tested here against directly-constructed
exception instances, not by running `CodexExecClient.generate()` (that
path — the trigger patterns that decide WHICH exception gets raised in the
first place — is covered separately in `tests/llm/test_codex_exec_client.py`).

Two different kinds of claim are verified here, deliberately kept distinct
(see `codex_broker_wire.py`'s module docstring): the isinstance mapping in
`describe_codex_exec_failure` (and its thin wrapper
`classify_codex_exec_failure`) is PROVABLY EXHAUSTIVE and this file asserts
that plainly, with no hedging — every known codex_exec_client exception
type is enumerated below and an unrecognized type is proven to raise
loudly rather than silently defaulting to INTERNAL. This file makes no
claim at all about whether the stderr trigger patterns in
`codex_exec_client.py` fire on real Codex CLI output for quota/policy —
that remains an unverified hypothesis, out of scope for this file by
construction (it never runs `generate()`).
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.llm.codex_exec_client import (
    CodexExecAmbiguousError,
    CodexExecAuthError,
    CodexExecCommunicationError,
    CodexExecModelNotAllowedError,
    CodexExecOutputShapeError,
    CodexExecPolicyBlockedError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
    MatchConfidence,
    OutputShapeReason,
)
from backend.services.integrations.codex_broker_wire import (
    BrokerErrorClass,
    ClassifiedFailure,
    classify_codex_exec_failure,
    describe_codex_exec_failure,
)
from backend.tests.duebot.fake_codex_broker import BrokerErrorClass as FakeBrokerErrorClass
from backend.tests.duebot.fake_codex_broker import FakeCodexBroker


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (CodexExecAuthError("auth", confidence=MatchConfidence.LOW), BrokerErrorClass.AUTH_DEAD),
        (CodexExecQuotaError("quota", confidence=MatchConfidence.HIGH), BrokerErrorClass.QUOTA),
        (
            CodexExecPolicyBlockedError("policy", confidence=MatchConfidence.LOW),
            BrokerErrorClass.POLICY_BLOCKED,
        ),
        (CodexExecTimeoutError("timeout"), BrokerErrorClass.TIMEOUT),
        (CodexExecUnavailableError("unavailable"), BrokerErrorClass.HOST_OFFLINE),
        (
            CodexExecOutputShapeError("shape", reason=OutputShapeReason.EMPTY),
            BrokerErrorClass.OUTPUT_INVALID,
        ),
        (
            CodexExecOutputShapeError("shape", reason=OutputShapeReason.OVERSIZED),
            BrokerErrorClass.OUTPUT_INVALID,
        ),
        (
            CodexExecAmbiguousError("ambiguous", candidates=frozenset({"AUTH_DEATH", "QUOTA"})),
            BrokerErrorClass.INTERNAL,
        ),
        (CodexExecCommunicationError("comm"), BrokerErrorClass.INTERNAL),
        (CodexExecProcessError(1), BrokerErrorClass.INTERNAL),
        (CodexExecModelNotAllowedError("model"), BrokerErrorClass.INTERNAL),
    ],
)
def test_every_known_exception_type_maps_to_its_broker_error_class(
    exc: Exception, expected: BrokerErrorClass
) -> None:
    """PROVABLY EXHAUSTIVE by construction: every codex_exec_client
    exception type is listed here, table-driven, one row per type (ten
    types as of B2b — `CodexExecOutputShapeError` appears twice, once per
    `OutputShapeReason`, since both map to the SAME `BrokerErrorClass` but
    are meaningfully different inputs). No hedging — this is a plain
    isinstance mapping, not a hypothesis. `describe_codex_exec_failure` is
    checked too, since `classify_codex_exec_failure` is defined in terms
    of it and must never silently diverge."""
    assert classify_codex_exec_failure(exc) is expected
    assert describe_codex_exec_failure(exc).error_class is expected


def test_unrecognized_exception_type_raises_type_error() -> None:
    """Fail-loud contract: a plain, un-typed RuntimeError (not one of the
    ten known codex_exec_client exception types) must not be silently
    absorbed into INTERNAL — F3 exists precisely because a silent
    catch-all is how AUTH_DEAD and QUOTA collapsed into one bucket in the
    first place."""
    with pytest.raises(TypeError):
        classify_codex_exec_failure(RuntimeError("something codex_exec_client never raises"))
    with pytest.raises(TypeError):
        describe_codex_exec_failure(RuntimeError("something codex_exec_client never raises"))


# ---------------------------------------------------------------------------
# B2b additions — Rulings A/B: `describe_codex_exec_failure`'s REQUIRED
# detail field on OUTPUT_INVALID and INTERNAL.
# ---------------------------------------------------------------------------


class TestRequiredDetailRulingA:
    """Ruling A (orchestrator mandate 2026-08-25): `OUTPUT_INVALID` gets a
    REQUIRED, non-None sub-cause detail distinguishing the classic
    transient (`"empty"`, retry is likely to help) from the failure whose
    same-prompt retry is wasted (`"oversized"`, truncate/reprompt
    instead)."""

    def test_empty_reason_produces_empty_detail(self) -> None:
        cf = describe_codex_exec_failure(
            CodexExecOutputShapeError("x", reason=OutputShapeReason.EMPTY)
        )
        assert cf.error_class is BrokerErrorClass.OUTPUT_INVALID
        assert cf.detail == "empty"

    def test_oversized_reason_produces_oversized_detail(self) -> None:
        cf = describe_codex_exec_failure(
            CodexExecOutputShapeError("x", reason=OutputShapeReason.OVERSIZED)
        )
        assert cf.error_class is BrokerErrorClass.OUTPUT_INVALID
        assert cf.detail == "oversized"

    def test_reason_is_a_required_constructor_argument(self) -> None:
        """The two sub-causes must never be conflatable by omission — a
        raise site that forgets `reason=` fails LOUD at construction time,
        not silently defaulting to one of the two (which would repeat
        exactly the class of defect F3 exists to fix, one exception class
        lower)."""
        with pytest.raises(TypeError):
            CodexExecOutputShapeError("x")  # type: ignore[call-arg]


class TestRequiredDetailRulingB:
    """Ruling B (orchestrator mandate 2026-08-25): `INTERNAL` gets a
    REQUIRED, non-None detail naming WHICH internal fault this is, rather
    than one flat opaque bucket a tripwire can neither page correctly on
    nor safely ignore."""

    @pytest.mark.parametrize(
        ("exc", "expected_detail"),
        [
            (CodexExecCommunicationError("comm"), "communication_failure"),
            (CodexExecProcessError(7), "unclassified_exit:7"),
            (CodexExecModelNotAllowedError("model"), "model_not_allowed"),
        ],
    )
    def test_internal_sub_causes_are_distinguished(
        self, exc: Exception, expected_detail: str
    ) -> None:
        cf = describe_codex_exec_failure(exc)
        assert cf.error_class is BrokerErrorClass.INTERNAL
        assert cf.detail == expected_detail

    def test_ambiguous_candidates_survive_into_the_internal_detail(self) -> None:
        """SPEC P1: even after F3's frozen vocabulary forces an ambiguous
        multi-class match down into `INTERNAL` (no AMBIGUOUS slot exists),
        the original candidates are NOT silently dropped — they are named
        in the detail, sorted for a deterministic string."""
        exc = CodexExecAmbiguousError(
            "ambiguous", candidates=frozenset({"QUOTA", "AUTH_DEATH"})
        )
        cf = describe_codex_exec_failure(exc)
        assert cf.error_class is BrokerErrorClass.INTERNAL
        assert cf.detail == "ambiguous:AUTH_DEATH+QUOTA"

    @pytest.mark.parametrize(
        "exc",
        [
            CodexExecCommunicationError("comm"),
            CodexExecProcessError(1),
            CodexExecModelNotAllowedError("model"),
            CodexExecAmbiguousError("ambiguous", candidates=frozenset({"AUTH_DEATH", "QUOTA"})),
        ],
    )
    def test_every_internal_row_has_a_non_none_detail(self, exc: Exception) -> None:
        cf = describe_codex_exec_failure(exc)
        assert cf.error_class is BrokerErrorClass.INTERNAL
        assert cf.detail is not None


def test_classified_failure_is_a_frozen_dataclass_with_two_fields() -> None:
    cf = ClassifiedFailure(BrokerErrorClass.TIMEOUT)
    assert cf.error_class is BrokerErrorClass.TIMEOUT
    assert cf.detail is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        cf.detail = "mutated"  # type: ignore[misc]


def test_broker_error_class_matches_fake_broker_wire_vocabulary() -> None:
    """Drift guard: the production BrokerErrorClass (this module) and the
    test-only BrokerErrorClass (backend.tests.duebot.fake_codex_broker,
    lane B6's wire-protocol fake) must carry the exact same F3 value set —
    they are two independent Python classes by design (production code
    must never import from backend/tests/), so nothing else stops them
    silently diverging. Mirrors the B1a lane's
    test_pydantic_json_schema_matches_committed_file discipline for the
    same class of drift risk."""
    assert {e.value for e in BrokerErrorClass} == {e.value for e in FakeBrokerErrorClass}


def test_classified_error_is_accepted_by_fake_codex_broker_complete() -> None:
    """End-to-end interop smoke test against B6's zero-network wire fake.

    Relies deliberately on Python's str-enum cross-class value equality:
    BrokerErrorClass (this module, `enum.StrEnum`) and FakeBrokerErrorClass
    (`fake_codex_broker.py`, `(str, enum.Enum)`) are different Python
    classes, but both are str-mixin enums with matching string values, so a
    member of one compares `==` and hashes identically to the member of the
    other with the same value — `FakeCodexBroker.complete()`'s
    `error_class not in ALL_ERROR_CLASSES` check (a frozenset of the FAKE's
    own enum members) therefore accepts a classified value from THIS
    module directly, with no manual conversion. This is intentional and
    documented here, not an accidental reliance on an obscure language
    quirk.
    """
    broker = FakeCodexBroker()
    job_id = broker.offer({"prompt": "hello"})
    broker.claim()

    error_class = classify_codex_exec_failure(
        CodexExecAuthError("operator re-login needed", confidence=MatchConfidence.LOW)
    )
    job = broker.complete(job_id, error_class=error_class)

    assert job.error_class == FakeBrokerErrorClass.AUTH_DEAD


def test_auth_dead_and_quota_are_distinct_via_fake_broker() -> None:
    """The single test that most directly proves F3's "auth and quota MUST
    be distinct" requirement end-to-end, across BOTH new production pieces
    (the trigger-to-exception layer covered separately in
    test_codex_exec_client.py, and this module's classifier) all the way
    through B6's wire-protocol fake — mirrors that fake's own named test,
    `test_fake_codex_broker.py::test_auth_dead_and_quota_are_distinct_outcomes`,
    one layer up the stack."""
    broker = FakeCodexBroker()

    auth_job_id = broker.offer({"prompt": "hello"})
    broker.claim()
    auth_error_class = classify_codex_exec_failure(
        CodexExecAuthError("auth", confidence=MatchConfidence.LOW)
    )
    auth_job = broker.complete(auth_job_id, error_class=auth_error_class)
    assert auth_job.error_class == FakeBrokerErrorClass.AUTH_DEAD

    quota_job_id = broker.offer({"prompt": "hello again"})
    broker.claim()
    quota_error_class = classify_codex_exec_failure(
        CodexExecQuotaError("quota", confidence=MatchConfidence.HIGH)
    )
    quota_job = broker.complete(quota_job_id, error_class=quota_error_class)
    assert quota_job.error_class == FakeBrokerErrorClass.QUOTA

    assert auth_job.error_class != quota_job.error_class
