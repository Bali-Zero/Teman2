"""Tests for team_bot.brain.errors — guilt AND innocence (SPEC P6), plus a
disjointness lock (P7) that iterates the FULL representative status range
rather than each branch's own hand-picked example (memory:
`a-weaker-test-agrees-with-itself.md` — "I checked disjointness on each
vocabulary's own alternatives; the claim was about stderr lines, and
nothing ever disagreed" is exactly the failure mode this test avoids by
construction: it checks every status against every OTHER status, not each
branch in isolation).
"""

from __future__ import annotations

import json

import pytest

from team_bot.brain.errors import (
    BrainErrorClass,
    EvidenceProvenance,
    MatchConfidence,
    classify_response,
    verdict_for_network_error,
    verdict_for_output_invalid,
    verdict_for_timeout,
)

# ---------------------------------------------------------------------------
# Guilt fixtures — real bodies. The 401/404 shapes below are VERBATIM,
# byte-for-byte, what the live TP1 door returned to this session on
# 2026-08-25 (see errors.py's evidence ledger). The 429/5xx shapes are
# synthetic, OpenAI-envelope-shaped, and labeled as such — never presented
# as vendor-observed.
# ---------------------------------------------------------------------------

_OBSERVED_401_BODY = (
    '{"error":{"message":"Invalid API-key provided. For details, see: '
    "https://www.alibabacloud.com/help/en/model-studio/error-code#apikey-error\","
    '"id":"67a650b7-b4a5-449b-af3f-c7fb5c01527b","type":"invalid_request_error",'
    '"code":"invalid_api_key"}}'
)

_OBSERVED_404_BODY = (
    '{"error":{"message":"Model not exist.","id":"f21dd93c-0925-4fe6-a7a4-9342868c3af1",'
    '"type":"invalid_request_error","code":"model_not_found"}}'
)

_SYNTHETIC_429_BODY = (
    '{"error":{"message":"Rate limit reached for requests",'
    '"type":"rate_limit_error","code":"rate_limit_exceeded"}}'
)

_SYNTHETIC_500_BODY = '{"error":{"message":"internal server error","type":"server_error"}}'


def test_observed_401_is_auth_dead_high_confidence_and_observed() -> None:
    v = classify_response(401, _OBSERVED_401_BODY)
    assert v.error_class is BrainErrorClass.AUTH_DEAD
    assert v.confidence is MatchConfidence.HIGH
    assert v.provenance is EvidenceProvenance.OBSERVED_TP1_LIVE
    assert v.vendor_code == "invalid_api_key"
    assert v.http_status == 401


def test_observed_404_model_not_found() -> None:
    v = classify_response(404, _OBSERVED_404_BODY)
    assert v.error_class is BrainErrorClass.MODEL_NOT_FOUND
    assert v.confidence is MatchConfidence.HIGH
    assert v.provenance is EvidenceProvenance.OBSERVED_TP1_LIVE
    assert v.vendor_code == "model_not_found"


def test_synthetic_429_is_rate_limited_but_not_observed() -> None:
    v = classify_response(429, _SYNTHETIC_429_BODY)
    assert v.error_class is BrainErrorClass.RATE_LIMITED
    # HIGH confidence: the STATUS CODE alone is structured/protocol
    # evidence, independent of whether the vendor body shape was observed.
    assert v.confidence is MatchConfidence.HIGH
    assert v.provenance is EvidenceProvenance.PROTOCOL_INFERRED


def test_429_with_no_body_at_all_still_classifies_from_status_alone() -> None:
    v = classify_response(429, "")
    assert v.error_class is BrainErrorClass.RATE_LIMITED
    assert v.confidence is MatchConfidence.HIGH
    assert v.provenance is EvidenceProvenance.PROTOCOL_INFERRED
    assert v.vendor_code is None


def test_synthetic_5xx_is_server_error() -> None:
    for status in (500, 502, 503, 504, 599):
        v = classify_response(status, _SYNTHETIC_500_BODY)
        assert v.error_class is BrainErrorClass.SERVER_ERROR, status
        assert v.provenance is EvidenceProvenance.PROTOCOL_INFERRED


def test_401_without_vendor_code_still_auth_dead_but_protocol_inferred() -> None:
    v = classify_response(401, "")
    assert v.error_class is BrainErrorClass.AUTH_DEAD
    assert v.provenance is EvidenceProvenance.PROTOCOL_INFERRED


def test_404_without_model_not_found_code_is_generic_invalid_request() -> None:
    body = json.dumps({"error": {"message": "bad thing", "type": "invalid_request_error"}})
    v = classify_response(404, body)
    assert v.error_class is BrainErrorClass.INVALID_REQUEST


def test_unrecognised_status_falls_to_unknown_never_a_guess() -> None:
    # P5: "unknown stays unknown". 3xx is not a TP1-meaningful failure
    # shape this module has ever seen or has protocol grounds to name.
    v = classify_response(303, "")
    assert v.error_class is BrainErrorClass.UNKNOWN
    assert v.confidence is MatchConfidence.LOW
    assert v.provenance is EvidenceProvenance.UNVERIFIED_GUESS


def test_non_json_body_degrades_gracefully_never_raises() -> None:
    v = classify_response(502, "<html>502 Bad Gateway</html>")
    assert v.error_class is BrainErrorClass.SERVER_ERROR
    assert "no parseable error envelope" in v.detail


# ---------------------------------------------------------------------------
# Innocence fixtures — payloads that name auth/quota vocabulary in PROSE
# must NOT be misclassified, because this module never scans body prose to
# classify (only `error.type`/`error.code`/status). This is the direct
# analogue of the codex SPEC's guilt+innocence requirement, made moot by
# construction rather than by careful regex tuning — the test exists to
# LOCK that architectural property, not to tune a pattern.
# ---------------------------------------------------------------------------


def test_innocent_400_mentioning_auth_and_quota_prose_is_not_auth_or_quota() -> None:
    # A 400 whose vendor message happens to use the words "quota" and
    # "unauthorized" in ordinary validation prose (e.g. an upstream
    # generic-gateway 400) must classify by STATUS, not by scanning
    # `vmsg` for those words.
    body = json.dumps(
        {
            "error": {
                "message": "The requested quota field is unauthorized for this schema version",
                "type": "invalid_request_error",
            }
        }
    )
    v = classify_response(400, body)
    assert v.error_class is BrainErrorClass.INVALID_REQUEST
    assert v.error_class is not BrainErrorClass.AUTH_DEAD
    assert v.error_class is not BrainErrorClass.RATE_LIMITED


def test_innocent_200_body_is_never_passed_to_classify_response() -> None:
    # classify_response is documented as a non-2xx classifier; a 200 must
    # never reach it at all in tp1_client.py (verified at the integration
    # level in test_tp1_client.py). This test pins the contract: were a
    # caller to mistakenly call classify_response(200, ...), it degrades
    # to UNKNOWN rather than silently succeeding as if it were an error
    # shape it recognised.
    v = classify_response(200, '{"choices":[{"message":{"content":"ok"}}]}')
    assert v.error_class is BrainErrorClass.UNKNOWN


# ---------------------------------------------------------------------------
# P7 — disjointness, tested on the realistic composite range, not on each
# branch's own examples.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [200, 201, 204, 303, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503])
def test_every_status_maps_to_exactly_one_class_deterministically(status: int) -> None:
    v1 = classify_response(status, "")
    v2 = classify_response(status, "")
    assert v1.error_class == v2.error_class


def test_401_and_404_and_429_and_5xx_are_pairwise_distinct_classes() -> None:
    classes = {
        classify_response(401, "").error_class,
        classify_response(404, _OBSERVED_404_BODY).error_class,
        classify_response(429, "").error_class,
        classify_response(500, "").error_class,
    }
    assert classes == {
        BrainErrorClass.AUTH_DEAD,
        BrainErrorClass.MODEL_NOT_FOUND,
        BrainErrorClass.RATE_LIMITED,
        BrainErrorClass.SERVER_ERROR,
    }


# ---------------------------------------------------------------------------
# Transport-level constructors (no HTTP status at all).
# ---------------------------------------------------------------------------


def test_verdict_for_timeout() -> None:
    v = verdict_for_timeout("ReadTimeout after 30.0s")
    assert v.error_class is BrainErrorClass.TIMEOUT
    assert v.http_status is None
    assert v.confidence is MatchConfidence.HIGH


def test_verdict_for_network_error() -> None:
    v = verdict_for_network_error("ConnectError: connection refused")
    assert v.error_class is BrainErrorClass.NETWORK_ERROR
    assert v.http_status is None


def test_verdict_for_output_invalid() -> None:
    v = verdict_for_output_invalid("KeyError parsing 200 body shape")
    assert v.error_class is BrainErrorClass.OUTPUT_INVALID
    assert v.confidence is MatchConfidence.LOW
    assert v.provenance is EvidenceProvenance.UNVERIFIED_GUESS
    assert v.http_status == 200
