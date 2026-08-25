"""Tests for the W1 evaluate read-path — ``POST /api/visa-oracle/evaluate``.

Covers both halves of the lane:

* ``services/visa_engine/evaluate_path.py`` — mode/allowlist resolvers,
  request_category derivation, TEMPORARILY_UNAVAILABLE fail-closed shape,
  and the full SHADOW-era orchestration (pack binding -> verify -> compile
  -> evaluate -> persist -> B.2 envelope).
* ``app/routers/visa_oracle_evaluate.py`` — the thin HTTP shell: content-
  type enforcement, the 32KB body cap, JSON/contract validation (422 with
  no input echo), the synthetic-``traffic_source`` trust gate, and the
  public/registry/rate-limit/manifest coherence the W0a pattern requires.

Tiers (same convention as ``test_shadow_match.py``): unit tests with an
inert sentinel pool (never dereferenced), HTTP tests against a bare FastAPI
app via httpx ASGITransport (pack/verify/compile/persist monkeypatched to
the real gold TEST pack — bundle.py's cryptography is its own test
surface), and DB-integration tests layering migrations 252+255+256+257 on
``conftest.py``'s ``db_pool``/``visa_schema`` for the real write path.

No test ever asserts against, or logs, raw applicant-fact values in ANY log
capture — matching ``evaluate_path.py``'s own PII-boundary contract
(SYMBIOSIS Law 2).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from backend.app.auth.public_endpoints import find_entry, is_public_path
from backend.app.routers import visa_oracle_evaluate
from backend.app.setup.router_manifest import _API, ROUTER_MANIFEST
from backend.db.migration_base import split_migration_sql
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine import (
    evaluate_path,
    idempotency,
    retention,
    schema_export,
    shadow,
)
from backend.services.visa_engine.api_models import (
    DisclosedReviewFlag,
    SourceFreshnessStatus,
    VisaOracleEvaluateRequest,
    VisaOracleEvaluateResponse,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    VerifiedRulePack,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.crypto import FactsFingerprintKey, resolve_engine_hmac_keyring
from backend.services.visa_engine.decision_seal import seal_decision, verify_decision_seal
from backend.services.visa_engine.enums import (
    DecisionState,
    EngineMode,
    Environment,
    FactPath,
    VisaPurpose,
)
from backend.services.visa_engine.evaluator import evaluate, evaluate_with_trace
from backend.services.visa_engine.idempotency import (
    IdempotencyConflictError,
    IdempotencyIntegrityError,
    IdempotencyReservation,
)
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
    Outage,
    PriceQuote,
    Reason,
    RulePack,
)
from backend.services.visa_engine.repository import VisaEngineRepository
from backend.services.visa_engine.shadow_evidence import collect_shadow_evidence
from backend.tests.security.test_mutating_routes_are_gated import (
    INTENTIONALLY_PUBLIC_MUTATIONS,
)
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine._builders import (
    ephemeral_ed25519_keypair,
    sign_rule_pack_envelope,
)
from backend.tests.services.visa_engine.conftest import make_applicant_facts
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader
from backend.tests.services.visa_engine.test_shadow_match import _seed_gold_rule_pack_row

pytestmark = pytest.mark.asyncio

_REAL_EVALUATE_URL = "/api/visa-oracle/evaluate?traffic_source=real"

# Arbitrary, deliberately NOT the real pricing catalog's date (see
# backend/data/bali_zero_official_prices_2026.json::metadata.last_updated).
# The mock pricing catalogs below only need SOME ISO-8601 string to prove
# pricing_adapter passes ``metadata.last_updated`` through to
# ``catalog_last_updated`` unmodified — using the real file's date here
# would silently couple this passthrough test to production data staleness,
# which is exactly the trap that let the real file go ~3.5 months stale
# unnoticed (see test_pricing_data_freshness.py).
_MOCK_CATALOG_LAST_UPDATED = "2020-01-01"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _facts_with_purposes(purposes: list[str] | None) -> ApplicantFacts:
    """A valid 35-key ApplicantFacts whose ``intent.purposes`` is KNOWN with
    exactly ``purposes`` (or UNKNOWN(NOT_ASKED) when ``purposes`` is None)."""
    facts = shadow.build_shadow_facts(
        nationality="US", purpose=Purpose.OTHER, duration_months=1, match_hash="category-hash"
    )
    assert facts is not None
    wire = facts.model_dump(mode="json", by_alias=True)
    if purposes is None:
        wire["facts"]["intent.purposes"] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
    else:
        wire["facts"]["intent.purposes"] = {"status": "KNOWN", "value": purposes}
    return ApplicantFacts.model_validate(wire)


def _wire_payload(facts: ApplicantFacts) -> dict:
    return facts.model_dump(mode="json", by_alias=True)


class _UntouchedPool:
    """Pool stand-in that FAILS the test if anything ever acquires a
    connection — proves a code path never touches the database."""

    def acquire(self) -> None:
        raise AssertionError("db_pool must not be touched on this path")


def _build_app(db_pool: object) -> FastAPI:
    app = FastAPI()
    app.include_router(visa_oracle_evaluate.router)
    app.state.db_pool = db_pool
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# §1 — mode resolvers (unit, no DB)
# ---------------------------------------------------------------------------


class TestResolveEvaluateShadowEnabled:
    def test_missing_env_defaults_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
        assert evaluate_path.resolve_evaluate_shadow_enabled() is False

    def test_off_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "OFF")
        assert evaluate_path.resolve_evaluate_shadow_enabled() is False

    def test_invalid_value_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "BOGUS")
        assert evaluate_path.resolve_evaluate_shadow_enabled() is False

    def test_shadow_is_true_case_insensitive_and_trims_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "  shadow  ")
        assert evaluate_path.resolve_evaluate_shadow_enabled() is True

    def test_enforce_is_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        assert evaluate_path.resolve_evaluate_shadow_enabled() is True
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.ENFORCE


class TestResolveResponseMode:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "CURATED"),
            ("OFF", "CURATED"),
            ("SHADOW", "CURATED"),
            ("ENFORCE", "ENGINE"),
            ("BOGUS", "CURATED"),
        ],
    )
    def test_authority_mapping(
        self,
        value: str | None,
        expected: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        if value is None:
            monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
        else:
            monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, value)
        assert evaluate_path.resolve_response_mode() == expected


class TestResolveAllowedSyntheticSources:
    def test_unset_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, raising=False)
        assert evaluate_path.resolve_allowed_synthetic_sources() == frozenset()

    def test_empty_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "")
        assert evaluate_path.resolve_allowed_synthetic_sources() == frozenset()

    def test_single_class(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
        assert evaluate_path.resolve_allowed_synthetic_sources() == frozenset({"synthetic_gold"})

    def test_multiple_classes_with_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold, synthetic_driver"
        )
        assert evaluate_path.resolve_allowed_synthetic_sources() == frozenset(
            {"synthetic_gold", "synthetic_driver"}
        )

    def test_real_and_garbage_are_never_allowlisted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A malformed env var can never WIDEN the accepted set: 'real' needs
        no allowlist (and must not be produced BY the allowlist parser), and
        arbitrary strings are ignored."""
        monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "real,bogus,synthetic_gold")
        assert evaluate_path.resolve_allowed_synthetic_sources() == frozenset({"synthetic_gold"})


# ---------------------------------------------------------------------------
# §2 — derive_request_category (unit, no DB)
# ---------------------------------------------------------------------------


class TestDeriveRequestCategory:
    @pytest.mark.parametrize(
        ("purpose", "expected"),
        [
            ("TOURISM", "long_tourism"),
            ("EMPLOYMENT", "work_employee"),
            ("REMOTE_WORK", "work_remote"),
            ("INVESTMENT", "investor"),
            ("BUSINESS_MEETINGS", "business"),
            ("FAMILY", "family"),
            ("RETIREMENT", "retirement"),
            ("STUDY", "student"),
            # Purposes with no v2 tile map to 'other' — never guessed into a
            # neighboring category (W1 brief: "unmapped -> other").
            ("SECOND_HOME", "other"),
            ("TRANSIT", "other"),
            ("MEDICAL", "other"),
            ("OTHER", "other"),
        ],
    )
    def test_single_known_purpose_maps(self, purpose: str, expected: str) -> None:
        assert (
            evaluate_path.derive_request_category(_facts_with_purposes([purpose]), None) == expected
        )

    def test_multi_purpose_facts_derive_other(self) -> None:
        """No honest primary tile exists for multi-purpose facts."""
        facts = _facts_with_purposes(["TOURISM", "FAMILY"])
        assert evaluate_path.derive_request_category(facts, None) == "other"

    def test_unknown_purposes_derive_other(self) -> None:
        facts = _facts_with_purposes(None)
        assert evaluate_path.derive_request_category(facts, None) == "other"

    def test_facts_win_over_hint_when_mappable(self) -> None:
        """A mappable single KNOWN purpose always beats the hint — the hint
        can never relabel an evaluation facts already express (G-a-vol
        category-gaming guard)."""
        facts = _facts_with_purposes(["TOURISM"])
        assert evaluate_path.derive_request_category(facts, "student") == "long_tourism"
        assert evaluate_path.derive_request_category(facts, "diaspora") == "long_tourism"

    def test_hint_honored_only_when_facts_derive_other(self) -> None:
        """The hint's only legitimate territory: UNKNOWN purposes, multi-
        purpose facts, and unmapped purposes (diaspora is reachable ONLY
        here — no VisaPurpose expresses it)."""
        unknown = _facts_with_purposes(None)
        assert evaluate_path.derive_request_category(unknown, "diaspora") == "diaspora"
        assert evaluate_path.derive_request_category(unknown, "business") == "business"
        multi = _facts_with_purposes(["TOURISM", "FAMILY"])
        assert evaluate_path.derive_request_category(multi, "diaspora") == "diaspora"
        unmapped = _facts_with_purposes(["SECOND_HOME"])
        assert evaluate_path.derive_request_category(unmapped, "diaspora") == "diaspora"

    def test_diaspora_is_only_reachable_via_the_hint(self) -> None:
        """No VisaPurpose expresses diaspora (the engine's closed vocabulary
        has none) — without the interview-tile hint the category can never be
        produced, which is exactly why the hint exists (Fable delta 3)."""
        tileless = [
            evaluate_path.derive_request_category(_facts_with_purposes([purpose.value]), None)
            for purpose in VisaPurpose
        ]
        assert "diaspora" not in tileless


# ---------------------------------------------------------------------------
# §3 — TEMPORARILY_UNAVAILABLE body shape (unit, no DB)
# ---------------------------------------------------------------------------


def test_temp_unavailable_body_shape() -> None:
    now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
    body = evaluate_path.build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")
    assert body["mode"] == "CURATED"
    decision = body["decision"]
    assert decision["state"] == "TEMPORARILY_UNAVAILABLE"
    assert decision["outage"] == {"code": "RULE_PACK_UNAVAILABLE", "retryable": True}
    assert decision["decision_id"] is None
    assert decision["public_id"] is None
    assert decision["rule_pack"] is None
    # Honest by construction: no evaluation happened, so no HMAC tag is
    # fabricated over facts that were never evaluated.
    assert decision["facts_fingerprint"] is None
    assert decision["candidates"] == [] and decision["quotes"] == []
    assert body["sources"] == []
    assert body["display"] == {"candidates": []}


def test_outage_precedes_source_freshness_hold_and_keeps_identity_absent() -> None:
    now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
    body = evaluate_path.build_temp_unavailable_body(
        now=now,
        code="RULE_PACK_UNAVAILABLE",
        mode=EngineMode.ENFORCE,
    )
    outage = VisaOracleEvaluateResponse.model_validate(body).decision
    held = evaluate_path._apply_safety_critical_source_hold(
        outage,
        gold_loader.load_and_compile_rule_pack(),
    )
    assert held == outage
    assert held.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert held.outage is not None
    assert held.decision_id is None
    assert held.public_id is None
    assert held.rule_pack is None
    assert held.facts_fingerprint is None
    assert held.trace_sha256 is None
    assert held.decision_integrity is None


def test_safety_source_hold_ignores_rules_not_yet_in_force() -> None:
    raw = gold_loader.load_rule_pack_raw()
    for rule in raw["payload"]["rules"]:
        if rule["safety_critical"]:
            rule["valid_period"] = {"from": "2099-01-01T00:00:00Z", "to": None}
    compiled = build_compiled_pack(RulePack.model_validate(raw))
    decision = evaluate(
        gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert evaluate_path._apply_safety_critical_source_hold(decision, compiled) == decision


def test_safety_source_hold_applies_when_safety_rules_are_in_force() -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    decision = evaluate(
        gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    held = evaluate_path._apply_safety_critical_source_hold(decision, compiled)
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.candidates == ()
    assert {reason.code for reason in held.review_reasons} == {
        "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE"
    }


# ---------------------------------------------------------------------------
# §4 — HTTP request-shape validation (bare app, no engine involvement)
# ---------------------------------------------------------------------------


async def test_wrong_content_type_is_415() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{}",
            headers={"content-type": "text/plain"},
        )
    assert response.status_code == 415


async def test_json_prefix_lookalike_content_type_is_415() -> None:
    """MIME validation compares the complete essence, never a prefix."""

    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{}",
            headers={"content-type": "application/jsonp"},
        )
    assert response.status_code == 415


@pytest.mark.parametrize(
    "content_types",
    [
        ("application/json", "text/plain"),
        ("text/plain", "application/json"),
        ("application/json", "application/json"),
    ],
)
async def test_duplicate_content_type_headers_are_400(
    content_types: tuple[str, str],
) -> None:
    raw = json.dumps(_wire_payload(_facts_with_purposes(["TOURISM"]))).encode()
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=raw,
            headers=[("content-type", value) for value in content_types],
        )
    assert response.status_code == 400


async def test_json_content_type_parameters_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
    raw = json.dumps(_wire_payload(_facts_with_purposes(["TOURISM"]))).encode()
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=raw,
            headers={"content-type": "application/json; charset=utf-8"},
        )
    assert response.status_code == 200, response.text


async def test_oversize_body_is_413() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"x" * (visa_oracle_evaluate.MAX_EVALUATE_BODY_BYTES + 1),
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413


async def test_chunked_oversize_body_aborts_stream_early() -> None:
    """OOM guard: a chunked body (no Content-Length) must be aborted with
    413 as soon as the cap is exceeded — the endpoint must NOT pull the
    whole stream first (a counting async iterator proves early abort)."""
    chunk_size = 8192
    total_chunks = 8  # 64 KB on offer; the cap is 32 KB
    pulled = 0

    async def _counting_chunks():
        nonlocal pulled
        for _ in range(total_chunks):
            pulled += 1
            yield b"x" * chunk_size

    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=_counting_chunks(),
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413
    # The cap trips after ceil((32768+1)/8192) = 5 chunks; the remaining 3
    # were never pulled (buffer-then-check would have pulled all 8).
    assert pulled < total_chunks


async def test_invalid_json_is_400() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


async def test_invalid_utf8_is_400() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b'{"marker":"\xff"}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "encoding",
    ("utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be"),
)
async def test_non_utf8_json_encodings_are_400(encoding: str) -> None:
    raw = json.dumps(_wire_payload(_facts_with_purposes(["TOURISM"]))).encode(encoding)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=raw,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


async def test_extreme_json_nesting_is_400_not_500() -> None:
    nested = ("[" * 2_000) + "0" + ("]" * 2_000)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=nested,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


@pytest.mark.parametrize("declared", ["1, 2", "-1", "+1", " 1"])
async def test_ambiguous_content_length_is_400(declared: str) -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{}",
            headers={"content-type": "application/json", "content-length": declared},
        )
    assert response.status_code == 400


async def test_multiple_content_length_headers_are_400() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{}",
            headers=[
                ("content-type", "application/json"),
                ("content-length", "2"),
                ("content-length", "2"),
            ],
        )
    assert response.status_code == 400


async def test_extreme_digit_count_content_length_is_400_not_500() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=b"{}",
            headers={
                "content-type": "application/json",
                "content-length": "9" * 5_000,
            },
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Content-Length header"}


async def test_extra_json_property_name_is_absent_from_validation_body_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "passport-ABC123456789-applicant-name"
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload[marker] = "sensitive-value"
    with caplog.at_level(logging.DEBUG):
        async with _client(_build_app(_UntouchedPool())) as client:
            response = await client.post(_REAL_EVALUATE_URL, json=payload)
    assert response.status_code == 422
    assert marker not in response.text
    assert "sensitive-value" not in response.text
    assert marker not in caplog.text
    assert "sensitive-value" not in caplog.text
    assert response.json()["detail"] == [
        {
            "loc": ["body", "field"],
            "type": "extra_forbidden",
            "msg": "Unexpected field",
        }
    ]


async def test_duplicate_top_level_json_key_is_400_without_key_echo() -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    wire = json.dumps(payload, separators=(",", ":"))
    needle = '"schema_version":"1.0.0"'
    assert wire.count(needle) == 1
    duplicate = wire.replace(
        needle,
        '"schema_version":"1.0.0","schema_version":"pii-duplicate-marker"',
        1,
    )
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=duplicate,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400
    assert "pii-duplicate-marker" not in response.text


async def test_duplicate_nested_json_key_is_400() -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    wire = json.dumps(payload, separators=(",", ":"))
    key = '"intent.stay_days"'
    assert wire.count(key) == 1
    duplicate = wire.replace(
        key, f"{key}:{json.dumps(payload['facts']['intent.stay_days'])},{key}", 1
    )
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=duplicate,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
async def test_non_finite_json_numbers_are_400(token: str) -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            content=f'{{"value":{token}}}',
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


async def test_missing_top_level_keys_is_422() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json={})
    assert response.status_code == 422


async def test_extra_top_level_key_is_422() -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["bogus"] = 1
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json=payload)
    assert response.status_code == 422


async def test_invalid_fact_value_is_422_and_never_echoes_input() -> None:
    """PII boundary on the error path: the 422 carries loc/type/msg only —
    the offending input value itself must not appear anywhere in the body."""
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["facts"]["intent.stay_days"] = {"status": "KNOWN", "value": -54321}
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json=payload)
    assert response.status_code == 422
    assert "-54321" not in response.text


@pytest.mark.parametrize("impossible_date", ["1985-02-30", "2001-02-29"])
async def test_custom_validation_messages_never_echo_impossible_date(
    impossible_date: str,
) -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["facts"]["person.birth_date"] = {
        "status": "KNOWN",
        "value": impossible_date,
    }
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json=payload)
    assert response.status_code == 422
    assert impossible_date not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"loc", "type", "msg"}
        assert error["msg"] in {
            "Required field is missing",
            "Unexpected field",
            "Value is outside the allowed vocabulary",
            "Invalid request field",
        }


async def test_thin_facts_are_never_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """An all-UNKNOWN payload is contract-valid (the engine abstains; it does
    not 422) — proven by reaching the mode gate, which responds 200 with the
    disabled-TEMP shape under the default OFF flag."""
    monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
    facts = shadow.build_shadow_facts(
        nationality="ZZZ",  # unmappable -> nationality stays UNKNOWN too
        purpose=Purpose.OTHER,
        duration_months=1,
        match_hash="thin-facts-hash",
    )
    assert facts is not None
    payload = _wire_payload(facts)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json=payload)
    assert response.status_code == 200
    assert response.json()["decision"]["state"] == "TEMPORARILY_UNAVAILABLE"


async def test_bogus_traffic_source_param_is_400_and_never_echoes() -> None:
    """In-route validation, no-echo discipline: the attacker's value must
    not appear anywhere in the rejection body."""
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=bogus-marker-12345",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 400
    assert "bogus-marker-12345" not in response.text


async def test_bogus_request_category_param_is_400_and_never_echoes() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?request_category=bogus-marker-67890&traffic_source=real",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 400
    assert "bogus-marker-67890" not in response.text


def test_evaluate_request_review_flags_are_closed_unique_and_canonical() -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["disclosed_review_flags"] = ["NOT_CERTAIN", "CRIMINAL_RECORD"]
    request = VisaOracleEvaluateRequest.model_validate(payload)
    assert request.disclosed_review_flags == (
        DisclosedReviewFlag.CRIMINAL_RECORD,
        DisclosedReviewFlag.NOT_CERTAIN,
    )

    payload["disclosed_review_flags"] = ["NOT_CERTAIN", "NOT_CERTAIN"]
    with pytest.raises(ValidationError, match="unique items"):
        VisaOracleEvaluateRequest.model_validate(payload)

    payload["disclosed_review_flags"] = ["FREE_TEXT_POLICY_CHANNEL"]
    with pytest.raises(ValidationError):
        VisaOracleEvaluateRequest.model_validate(payload)


def test_temp_unavailable_is_a_real_typed_response() -> None:
    now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)
    response = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")
    )
    assert response.decision.state.value == "TEMPORARILY_UNAVAILABLE"
    assert response.decision.facts_fingerprint is None


def test_openapi_pins_named_request_response_and_operation_id() -> None:
    schema = _build_app(_UntouchedPool()).openapi()
    operation = schema["paths"]["/api/visa-oracle/evaluate"]["post"]
    assert operation["operationId"] == "evaluateVisaOracleV2"
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisaOracleEvaluateRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisaOracleEvaluateResponse"
    }
    assert operation["responses"]["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisaOracleErrorResponse"
    }
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisaOracleValidationErrorResponse"
    }
    header = next(parameter for parameter in operation["parameters"] if parameter["in"] == "header")
    assert header["name"] == "Idempotency-Key"
    assert header["required"] is False
    query_parameters = {
        parameter["name"]: parameter
        for parameter in operation["parameters"]
        if parameter["in"] == "query"
    }
    assert set(query_parameters["traffic_source"]["schema"]["enum"]) == {
        "real",
        "synthetic_gold",
        "synthetic_driver",
    }
    assert query_parameters["traffic_source"]["required"] is True
    assert "diaspora" in query_parameters["request_category"]["schema"]["enum"]


async def test_missing_traffic_source_is_sanitized_422_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_evaluation(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
        raise AssertionError("evaluation path must not run without an explicit traffic_source")

    monkeypatch.setattr(evaluate_path, "run_public_evaluation", _unexpected_evaluation)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["query", "field"],
                "type": "missing",
                "msg": "Required field is missing",
            }
        ]
    }


async def test_invalid_idempotency_key_is_400_without_echo() -> None:
    marker = "invalid key pii-marker"
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers={"idempotency-key": marker},
        )
    assert response.status_code == 400
    assert marker not in response.text


async def test_duplicate_idempotency_headers_are_400() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers=[("idempotency-key", "request-a"), ("idempotency-key", "request-b")],
        )
    assert response.status_code == 400


async def test_idempotency_conflict_is_static_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _conflict(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
        raise IdempotencyConflictError("must never reach response")

    monkeypatch.setattr(evaluate_path, "run_public_evaluation", _conflict)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers={"idempotency-key": "request-conflict"},
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "Idempotency-Key is already bound to a different request"}


async def test_canonical_request_hash_ignores_json_property_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hashes: list[bytes] = []

    async def _record_hash(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
        hashes.append(kwargs["canonical_request"])  # type: ignore[arg-type]
        return VisaOracleEvaluateResponse.model_validate(
            evaluate_path.build_temp_unavailable_body(
                now=datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc),
                code="EVALUATE_SURFACE_DISABLED",
            )
        )

    monkeypatch.setattr(evaluate_path, "run_public_evaluation", _record_hash)
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    reordered = dict(reversed(tuple(payload.items())))
    reordered["facts"] = dict(reversed(tuple(payload["facts"].items())))
    async with _client(_build_app(_UntouchedPool())) as client:
        first = await client.post(
            _REAL_EVALUATE_URL,
            json=payload,
            headers={"idempotency-key": "request-order-stable"},
        )
        second = await client.post(
            _REAL_EVALUATE_URL,
            json=reordered,
            headers={"idempotency-key": "request-order-stable"},
        )
    assert first.status_code == second.status_code == 200
    assert len(hashes) == 2
    assert hashes[0] == hashes[1]


# ---------------------------------------------------------------------------
# §5 — synthetic self-label gate (HTTP; validation order is mode-independent)
# ---------------------------------------------------------------------------


class TestVerifyDriverToken:
    def test_unset_env_rejects_even_matching_presentation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(evaluate_path.DRIVER_TOKEN_ENV, raising=False)
        assert evaluate_path.verify_driver_token("anything") is False

    def test_empty_env_rejects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "   ")
        assert evaluate_path.verify_driver_token("anything") is False

    def test_correct_token_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
        assert evaluate_path.verify_driver_token("w4-driver-secret") is True

    def test_wrong_or_missing_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
        assert evaluate_path.verify_driver_token("w4-driver-WRONG") is False
        assert evaluate_path.verify_driver_token(None) is False
        assert evaluate_path.verify_driver_token("") is False


async def test_synthetic_self_label_rejected_without_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, raising=False)
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 400


async def test_synthetic_class_not_in_allowlist_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The allowlist is per-class: arming gold does not arm driver."""
    monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_driver",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 400


async def test_armed_synthetic_without_driver_header_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allowlist armed but no X-Visa-Driver-Token header -> 400 (the W4
    credential is mandatory even on an armed deployment)."""
    monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
    monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 400


async def test_armed_synthetic_with_wrong_driver_token_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
    monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers={"x-visa-driver-token": "w4-driver-WRONG"},
        )
    assert response.status_code == 400


async def test_unarmed_synthetic_with_correct_driver_token_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid driver token never widens the allowlist: an unarmed class is
    rejected even with the correct credential."""
    monkeypatch.delenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, raising=False)
    monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers={"x-visa-driver-token": "w4-driver-secret"},
        )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# §6 — run_evaluation orchestration (unit + HTTP; engine chain monkeypatched
# to the real gold TEST pack, persist recorded)
# ---------------------------------------------------------------------------


def _patch_engine_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[dict], RulePack, object]:
    """Monkeypatch binding/verify/compile to the gold TEST pack and the
    decision writer to a recorder. Returns (save_calls, pack_model, compiled)."""
    compiled = gold_loader.load_and_compile_rule_pack()
    raw = gold_loader.load_rule_pack_raw()
    pack_model = RulePack.model_validate(raw)

    async def _fake_binding(
        pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
    ):
        return shadow._PackBinding(
            rule_pack_id=pack_model.payload.rule_pack_id,
            ruleset_activation_id=uuid.uuid4(),
            environment="TEST",
            raw_envelope=raw,
        )

    def _fake_verify(
        raw_envelope: object,
        *,
        trust_store: object,
        observed_at: datetime,
        allow_unsigned: bool = False,
    ):
        return VerifiedRulePack(
            pack=pack_model,
            canonical_payload=b"",
            payload_sha256=bytes.fromhex(pack_model.payload_sha256),
            unsigned_dev=False,
        )

    def _fake_compile(rule_pack: object, *, fact_registry: object = None):
        return compiled

    save_calls: list[dict] = []

    async def _recording_save(pool: object, **kwargs: object) -> None:
        save_calls.append(kwargs)

    async def _retention_available(*args: object, **kwargs: object) -> bool:
        return True

    pricing_rows = {
        product.pricing_key.item_key: product.pricing_key.category
        for product in compiled.source_pack.payload.products
        if product.pricing_key is not None
    }

    class _PricingCatalog:
        loaded = True

        def get_service_by_key(self, key: str) -> dict[str, object] | None:
            category = pricing_rows.get(key)
            if category is None:
                return None
            return {"key": key, "category": category, "price": "not-exposed"}

        def get_all_prices(self) -> dict[str, object]:
            return {
                "metadata": {"last_updated": _MOCK_CATALOG_LAST_UPDATED, "currency": "IDR"},
                "services": {},
            }

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _fake_binding)
    monkeypatch.setattr(evaluate_path, "verify_rule_pack", _fake_verify)
    monkeypatch.setattr(evaluate_path, "build_compiled_pack", _fake_compile)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _recording_save)
    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _retention_available,
    )
    monkeypatch.setattr(evaluate_path, "get_pricing_service", lambda: _PricingCatalog())
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")
    return save_calls, pack_model, compiled


async def _supported_engine_response(
    monkeypatch: pytest.MonkeyPatch,
) -> VisaOracleEvaluateResponse:
    """Return a sealed ENGINE response for replay/integrity adversarial tests.

    The gold pack intentionally has no signed freshness policy, so production
    orchestration correctly abstains. These tests need an older conclusive
    envelope solely to prove that replay can never resurrect it after current
    authority changes; bypassing both source holds is explicit and local.
    """

    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, compiled: decision,
    )
    body = await evaluate_path.run_evaluation(
        object(),
        facts=gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-supported-replay-fixture",
        evaluation_time=datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc),
    )
    response = VisaOracleEvaluateResponse.model_validate(body)
    assert response.mode.value == "ENGINE"
    assert response.decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert response.decision.candidates
    return response


def _public_request() -> VisaOracleEvaluateRequest:
    return VisaOracleEvaluateRequest.model_validate(
        _wire_payload(
            gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
        )
    )


async def test_run_evaluation_delegates_to_public_policy_helper_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    _, _, compiled = _patch_engine_chain(monkeypatch)
    facts = _facts_with_purposes(["TOURISM"])
    flags = (DisclosedReviewFlag.NOT_CERTAIN,)
    evaluations = []
    helper_calls = []
    original_evaluate = evaluate_path.evaluate_with_trace
    original_helper = evaluate_path.apply_public_policy_adapters

    def recording_evaluate(*args: object, **kwargs: object):
        evaluation = original_evaluate(*args, **kwargs)
        evaluations.append(evaluation)
        return evaluation

    def recording_helper(
        decision: Decision,
        current_facts: ApplicantFacts,
        current_compiled: object,
        *,
        disclosed_review_flags: tuple[DisclosedReviewFlag, ...] = (),
    ) -> Decision:
        helper_calls.append((decision, current_facts, current_compiled, disclosed_review_flags))
        return original_helper(
            decision,
            current_facts,
            current_compiled,
            disclosed_review_flags=disclosed_review_flags,
        )

    monkeypatch.setattr(evaluate_path, "evaluate_with_trace", recording_evaluate)
    monkeypatch.setattr(evaluate_path, "apply_public_policy_adapters", recording_helper)

    await evaluate_path.run_evaluation(
        object(),
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-public-policy-delegation",
        disclosed_review_flags=flags,
        evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
    )

    assert len(evaluations) == 1
    assert helper_calls == [(evaluations[0].decision, facts, compiled, flags)]


def _cached_reservation(response: VisaOracleEvaluateResponse | None) -> IdempotencyReservation:
    reserved_at = datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc)
    return IdempotencyReservation(
        key_sha256=b"k" * 32,
        request_hmac=b"h" * 32,
        request_hmac_key_id="test-v1",
        reserved_at=reserved_at,
        environment="TEST",
        retention_policy_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        expires_at=reserved_at + timedelta(hours=1),
        response=response,
    )


_SIGNED_SOURCE_OBSERVED_AT = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
_SIGNED_SOURCE_SIGNED_AT = "2026-08-03T12:00:00Z"
_DECISIVE_SOURCE_ID = "c43c40ab-387a-46a1-a2a0-996692ee833e"


def _real_signed_decisive_source_case(
    defect: str | None = None,
    *,
    persona_name: str = "02_business_c2.json",
    official_host: str = "www.imigrasi.go.id",
    freshness_max_age_seconds: int | None = None,
) -> tuple[CompiledRulePack, Decision, Decision]:
    """Verify -> compile -> evaluate -> source-gate using a real Ed25519 pack."""

    raw = gold_loader.load_rule_pack_raw()
    payload = raw["payload"]
    source = next(
        record
        for record in payload["source_records"]
        if record["source_record_id"] == _DECISIVE_SOURCE_ID
    )
    source.update(
        {
            "authority_type": "OFFICIAL_PORTAL",
            "status": "VERIFIED",
            "publisher": "Direktorat Jenderal Imigrasi",
            "canonical_url": f"https://{official_host}/visa-oracle-source",
            "legal_period": {"from": "2026-01-01T00:00:00Z", "to": None},
            "recorded_period": {"from": "2026-08-01T00:00:00Z", "to": None},
            "retrieved_at": "2026-08-03T10:00:00Z",
            "verified_at": "2026-08-03T11:00:00Z",
        }
    )
    if freshness_max_age_seconds is not None:
        source["freshness_policy"] = {
            "kind": "MAX_AGE_SINCE_VERIFIED_AT",
            "max_age_seconds": freshness_max_age_seconds,
        }

    if defect in {"SUPERSEDED", "REVOKED", "UNAVAILABLE"}:
        source["status"] = defect
    elif defect == "not_yet_effective":
        source["legal_period"] = {"from": "2026-08-05T00:00:00Z", "to": None}
    elif defect == "expired":
        source["legal_period"] = {
            "from": "2026-01-01T00:00:00Z",
            "to": "2026-08-04T12:00:00Z",
        }
    elif defect == "recorded_future":
        source["recorded_period"] = {"from": "2026-08-05T00:00:00Z", "to": None}
    elif defect == "recorded_after_retrieved":
        source["recorded_period"] = {"from": "2026-08-03T10:30:00Z", "to": None}
    elif defect == "recorded_to_before_verified":
        source["recorded_period"] = {
            "from": "2026-08-01T00:00:00Z",
            "to": "2026-08-03T11:00:00Z",
        }
    elif defect == "retrieved_after_verified":
        source["retrieved_at"] = "2026-08-03T11:30:00Z"
    elif defect == "verified_after_signing":
        source["verified_at"] = "2026-08-03T13:00:00Z"
    elif defect == "verified_after_observed":
        source["verified_at"] = "2026-08-05T00:00:00Z"
    elif defect == "verified_in_future_before_signing":
        source["verified_at"] = "2026-08-04T12:03:00Z"
    elif defect == "non_primary":
        source["authority_type"] = "BALI_ZERO_POLICY"
        source["canonical_url"] = "https://internal.balizero.dev/policy"
    elif defect == "url_http":
        source["canonical_url"] = "http://www.imigrasi.go.id/source"
    elif defect == "url_unapproved_host":
        source["canonical_url"] = "https://attacker.example/source"
    elif defect == "url_userinfo":
        source["canonical_url"] = "https://applicant@www.imigrasi.go.id/source"
    elif defect == "url_port":
        source["canonical_url"] = "https://www.imigrasi.go.id:443/source"

    private_key, public_key = ephemeral_ed25519_keypair()
    signed_at = (
        "2026-08-04T12:04:00Z"
        if defect == "verified_in_future_before_signing"
        else _SIGNED_SOURCE_SIGNED_AT
    )
    envelope = sign_rule_pack_envelope(
        payload,
        private_key=private_key,
        kid="decisive-source-real-signature",
        signed_at=signed_at,
    )
    trust_store = StaticTrustStore(
        [
            TrustedSigningKey(
                key_id="decisive-source-real-signature",
                public_key=public_key,
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                valid_to=None,
                revoked_at=None,
                environment="TEST",
            )
        ]
    )
    verified = verify_rule_pack(
        envelope,
        trust_store=trust_store,
        observed_at=_SIGNED_SOURCE_OBSERVED_AT,
    )
    assert verified.unsigned_dev is False
    compiled = build_compiled_pack(verified.pack)
    decision = evaluate(
        gold_loader.load_persona(gold_loader.PERSONAS_DIR / persona_name).facts,
        compiled,
        effective_at=_SIGNED_SOURCE_OBSERVED_AT,
        observed_at=_SIGNED_SOURCE_OBSERVED_AT,
    )
    held = evaluate_path._apply_decisive_source_authority_hold(decision, compiled)
    return compiled, decision, held


async def test_off_mode_is_temp_and_persists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
    save_calls, _, _ = _patch_engine_chain(monkeypatch)
    body = await evaluate_path.run_evaluation(
        _UntouchedPool(),  # sentinel: the mode gate fires before any DB access
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-off",
    )
    assert body["decision"]["state"] == "TEMPORARILY_UNAVAILABLE"
    assert body["decision"]["outage"] == {"code": "EVALUATE_SURFACE_DISABLED", "retryable": True}
    assert save_calls == []


async def test_idempotency_key_in_off_mode_does_not_reserve_or_resolve_hmac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public kill switch precedes every idempotency DB/key operation."""

    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "OFF")
    calls: list[str] = []

    async def _unexpected_reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        calls.append("reserve")
        raise AssertionError("OFF must not reserve an idempotency row")

    def _unexpected_keyring(*args: object, **kwargs: object) -> object:
        calls.append("keyring")
        raise AssertionError("OFF must not resolve HMAC material")

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _unexpected_reserve)
    monkeypatch.setattr(evaluate_path, "resolve_engine_hmac_keyring", _unexpected_keyring)
    response = await evaluate_path.run_public_evaluation(
        _UntouchedPool(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-off-idempotency",
        canonical_request=b"{}",
        idempotency_key="off-key",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "EVALUATE_SURFACE_DISABLED"
    assert response.decision.candidates == ()
    assert calls == []


@pytest.mark.parametrize("retention_failure", ["missing", "database"])
@pytest.mark.parametrize(
    ("engine_mode", "response_mode"),
    [("SHADOW", "CURATED"), ("ENFORCE", "ENGINE")],
)
async def test_decision_without_proven_retention_policy_abstains_before_pack_resolution(
    monkeypatch: pytest.MonkeyPatch,
    retention_failure: str,
    engine_mode: str,
    response_mode: str,
) -> None:
    """Neither SHADOW nor ENFORCE may retain data without a Zero policy."""

    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, engine_mode)
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    policy_checks: list[tuple[str, datetime]] = []

    async def _retention_check(
        pool: object,
        *,
        environment: str,
        evaluated_at: datetime,
    ) -> bool:
        policy_checks.append((environment, evaluated_at))
        if retention_failure == "database":
            raise asyncpg.InterfaceError("retention substrate unavailable")
        return False

    async def _unexpected_pack(*args: object, **kwargs: object) -> None:
        raise AssertionError("retention must gate RulePack resolution")

    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _retention_check,
    )
    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _unexpected_pack)
    body = await evaluate_path.run_evaluation(
        object(),
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-retention-gate",
    )
    assert len(policy_checks) == 1
    assert policy_checks[0][0] == "TEST"
    assert body["mode"] == response_mode
    assert body["decision"]["state"] == "TEMPORARILY_UNAVAILABLE"
    assert body["decision"]["outage"] == {
        "code": "RETENTION_POLICY_UNAVAILABLE",
        "retryable": True,
    }
    assert body["decision"]["candidates"] == []
    assert body["decision"]["decision_id"] is None


@pytest.mark.parametrize("engine_mode", ["SHADOW", "ENFORCE"])
async def test_idempotent_retention_gate_precedes_keyring_and_reservation(
    monkeypatch: pytest.MonkeyPatch,
    engine_mode: str,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, engine_mode)
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    calls: list[str] = []

    async def _missing_policy(*args: object, **kwargs: object) -> bool:
        calls.append("retention")
        return False

    async def _unexpected_reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        calls.append("reserve")
        raise AssertionError("missing retention policy must not reserve")

    def _unexpected_keyring(*args: object, **kwargs: object) -> object:
        calls.append("keyring")
        raise AssertionError("missing retention policy must precede key resolution")

    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _missing_policy,
    )
    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _unexpected_reserve)
    monkeypatch.setattr(evaluate_path, "resolve_engine_hmac_keyring", _unexpected_keyring)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-retention-before-reserve",
        canonical_request=b"{}",
        idempotency_key="retention-gated",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "RETENTION_POLICY_UNAVAILABLE"
    assert response.decision.candidates == ()
    assert calls == ["retention"]


async def test_cached_engine_response_is_not_replayed_across_retention_policy_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = await _supported_engine_response(monkeypatch)
    policy_snapshots = iter([True, True, False])
    checks = 0

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(cached)

    async def _racing_retention(*args: object, **kwargs: object) -> bool:
        nonlocal checks
        checks += 1
        return next(policy_snapshots)

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _racing_retention,
    )
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-retention-race",
        canonical_request=b"{}",
        idempotency_key="cached-engine-retention-race",
    )
    assert checks == 3
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    assert response.decision.candidates == ()


@pytest.mark.parametrize(
    ("limit", "requested_by"),
    [
        (False, "worker"),
        (1.5, "worker"),
        (0, "worker"),
        (1_001, "worker"),
        (1, ""),
        (1, "contains spaces"),
        (1, "x" * 129),
    ],
)
@pytest.mark.parametrize(
    "purger",
    [retention.purge_expired_decisions, retention.purge_expired_idempotency],
)
async def test_retention_purge_primitive_rejects_unbounded_or_unaudited_calls(
    limit: object,
    requested_by: str,
    purger: object,
) -> None:
    with pytest.raises(ValueError):
        await purger(  # type: ignore[operator]
            _UntouchedPool(),  # type: ignore[arg-type]
            limit=limit,  # type: ignore[arg-type]
            requested_by=requested_by,
        )


async def test_cached_engine_response_is_not_replayed_in_shadow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = await _supported_engine_response(monkeypatch)
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(cached)

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-shadow-no-engine-replay",
        canonical_request=b"{}",
        idempotency_key="cached-engine",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    assert response.decision.candidates == ()


async def test_cached_engine_response_is_not_replayed_without_current_pack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = await _supported_engine_response(monkeypatch)

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(cached)

    async def _no_pack(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _no_pack)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-no-pack-replay",
        canonical_request=b"{}",
        idempotency_key="cached-engine-no-pack",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    assert response.decision.candidates == ()


async def test_cached_engine_response_is_not_replayed_after_pack_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = await _supported_engine_response(monkeypatch)

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(cached)

    async def _rotated_pack(*args: object, **kwargs: object) -> tuple[uuid.UUID, int, str, str]:
        return (uuid.uuid4(), 999, "rotated", "f" * 64)

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(evaluate_path, "_current_replay_pack_identity", _rotated_pack)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-rotated-pack-replay",
        canonical_request=b"{}",
        idempotency_key="cached-engine-rotated",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    assert response.decision.candidates == ()


async def test_cached_engine_response_is_not_replayed_across_pack_check_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = await _supported_engine_response(monkeypatch)
    assert cached.decision.rule_pack is not None
    current = cached.decision.rule_pack
    identities = iter(
        [
            (
                current.rule_pack_id,
                current.sequence,
                current.version,
                current.payload_sha256,
            ),
            None,
        ]
    )

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(cached)

    async def _racing_pack(*args: object, **kwargs: object):
        return next(identities)

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(evaluate_path, "_current_replay_pack_identity", _racing_pack)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-racing-pack-replay",
        canonical_request=b"{}",
        idempotency_key="cached-engine-race",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    assert response.decision.candidates == ()


async def test_mode_flip_to_off_before_completion_leaves_reservation_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine_response = await _supported_engine_response(monkeypatch)
    completion_calls: list[object] = []

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(None)

    async def _run(*args: object, **kwargs: object) -> dict:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "OFF")
        return engine_response.model_dump(mode="json")

    async def _complete(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
        completion_calls.append(kwargs.get("response"))
        raise AssertionError("OFF must not complete a reserved idempotency row")

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(evaluate_path, "run_evaluation", _run)
    monkeypatch.setattr(evaluate_path, "complete_idempotency", _complete)
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-flip-off-before-completion",
        canonical_request=b"{}",
        idempotency_key="flip-off",
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "EVALUATE_SURFACE_DISABLED"
    assert response.decision.candidates == ()
    assert completion_calls == []


async def test_off_temp_from_evaluator_is_never_persisted_as_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    completion_calls: list[object] = []

    async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
        return _cached_reservation(None)

    async def _run(*args: object, **kwargs: object) -> dict:
        return evaluate_path.build_temp_unavailable_body(
            now=datetime(2026, 8, 4, 1, 0, tzinfo=timezone.utc),
            code="EVALUATE_SURFACE_DISABLED",
            mode=EngineMode.OFF,
        )

    async def _complete(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
        completion_calls.append(kwargs.get("response"))
        raise AssertionError("an OFF response must not become a durable replay")

    async def _retention_available(*args: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
    monkeypatch.setattr(evaluate_path, "run_evaluation", _run)
    monkeypatch.setattr(evaluate_path, "complete_idempotency", _complete)
    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _retention_available,
    )
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=_public_request(),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-off-temp-no-completion",
        canonical_request=b"{}",
        idempotency_key="off-temp",
    )
    assert response.decision.outage is not None
    assert response.decision.outage.code == "EVALUATE_SURFACE_DISABLED"
    assert completion_calls == []


async def test_no_active_pack_is_temp_and_persists_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")

    async def _no_binding(
        pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
    ):
        return None

    save_calls: list[dict] = []

    async def _recording_save(pool: object, **kwargs: object) -> None:
        save_calls.append(kwargs)

    async def _retention_available(*args: object, **kwargs: object) -> bool:
        return True

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _no_binding)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _recording_save)
    monkeypatch.setattr(
        evaluate_path,
        "active_retention_policy_available",
        _retention_available,
    )

    body = await evaluate_path.run_evaluation(
        _UntouchedPool(),
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-nopack",
    )
    assert body["mode"] == "CURATED"
    assert body["decision"]["outage"] == {"code": "RULE_PACK_UNAVAILABLE", "retryable": True}
    assert save_calls == []


async def test_happy_path_http_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """SHADOW mode + active gold TEST pack: 200 with the B.2 envelope, the
    real engine decision, resolved sources, the pinned display shape, and a
    persist call carrying traffic_source=real + the derived category + the
    HMAC request fingerprint."""
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "CURATED"
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"
    assert body["decision"]["decision_id"] is not None
    digest = body["decision"]["facts_fingerprint"]["digest"]
    assert isinstance(digest, str) and len(digest) == 64
    assert isinstance(body["sources"], list)
    assert isinstance(body["display"]["candidates"], list)
    for entry in body["display"]["candidates"]:
        # The pinned P2-2 display contract (Track C 4a consumes this).
        assert set(entry) == {
            "product_code",
            "product_version_id",
            "rank",
            "name",
            "tagline",
            "stay_policy",
            "documentation",
            "processing_timeline",
            "availability",
            "pricing",
        }
        assert set(entry["name"]) == {"id", "en"}
        assert entry["availability"]["legal_eligibility"] == "SUPPORTED"
        assert entry["availability"]["operational_availability"]["status"] == "UNKNOWN"
        assert entry["availability"]["bali_zero_service_availability"]["status"] == "UNKNOWN"
        assert entry["documentation"]["status"] == "UNKNOWN"
        assert entry["documentation"]["requirements"] == []
        assert entry["documentation"]["checklist"] == []
        assert entry["processing_timeline"]["status"] == "UNKNOWN"
        assert entry["processing_timeline"]["anchor_date"] is None
        assert entry["pricing"]["status"] == "CONTACT_REQUIRED"
        assert entry["pricing"]["reason_code"] == "PRICING_ROW_NOT_EXACT_AMOUNT"
        assert entry["pricing"]["evaluated_at"] == body["decision"]["evaluated_at"]
        assert entry["pricing"]["catalog_last_updated"] == _MOCK_CATALOG_LAST_UPDATED
        assert len(entry["pricing"]["catalog_sha256"]) == 64
        assert len(entry["pricing"]["row_sha256"]) == 64

    assert len(save_calls) == 1
    saved = save_calls[0]
    assert saved["traffic_source"] == "real"
    assert saved["request_category"] == "long_tourism"
    assert saved["request_fingerprint"] == bytes.fromhex(digest)
    assert str(saved["decision"].decision_id) == body["decision"]["decision_id"]


async def test_exact_pricingtool_rows_are_signed_and_persisted_as_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, compiled = _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, _compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, _compiled: decision,
    )
    pricing_rows = {
        product.pricing_key.item_key: product.pricing_key.category
        for product in compiled.source_pack.payload.products
        if product.pricing_key is not None
    }

    class _ExactPricingCatalog:
        loaded = True

        def get_all_prices(self) -> dict[str, object]:
            return {
                "version": "test-2026.1",
                "metadata": {"last_updated": _MOCK_CATALOG_LAST_UPDATED, "currency": "IDR"},
                "services": {},
            }

        def get_service_by_key(self, key: str) -> dict[str, object] | None:
            category = pricing_rows.get(key)
            if category is None:
                return None
            return {"key": key, "category": category, "price": "2.300.000 IDR"}

    monkeypatch.setattr(evaluate_path, "get_pricing_service", _ExactPricingCatalog)
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    body = await evaluate_path.run_evaluation(
        object(),
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-exact-pricing",
        evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
    )

    assert body["decision"]["state"] == "SUPPORTED_CANDIDATES"
    quotes = body["decision"]["quotes"]
    assert quotes
    assert len(save_calls) == 1
    assert save_calls[0]["decision"].quotes
    for quote in quotes:
        assert quote["status"] == "AVAILABLE"
        assert quote["amount"] == 2_300_000
        assert quote["currency"] == "IDR"
        assert quote["catalog_version"] == "test-2026.1"
        assert quote["reason_code"] == "PRICE_AVAILABLE"
    for candidate in body["display"]["candidates"]:
        assert candidate["pricing"]["status"] == "AVAILABLE"
        assert candidate["pricing"]["reason_code"] == "PRICE_AVAILABLE"


async def test_human_review_required_carries_supported_candidate_with_contact_required_pricing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defect 2 ledgered alongside owner ruling #5 (2026-08-24-visa-oracle-
    live/OWNER-RULINGS-2026-08-25.md §5): the engine fix (models.py /
    evaluator.py) lets HUMAN_REVIEW_REQUIRED carry an already-SUPPORTED
    candidate (e.g. an E28A-eligible investor asking about E28B) — but
    ``_build_display`` used to call ``resolve_candidate_pricing``
    unconditionally for every candidate regardless of decision state. A
    candidate with a genuinely resolvable price then made
    ``VisaOracleEvaluateResponse._check_projection_integrity`` raise ("a
    candidate without a quote cannot claim a price" — ``quotes`` is frozen
    empty on HUMAN_REVIEW_REQUIRED, contract C1), which ``run_evaluation``
    caught and degraded the WHOLE response to TEMPORARILY_UNAVAILABLE: an
    outage screen in place of the honest "you qualify, talk to a
    consultant" screen the ruling demands.

    ``test_evaluator_state_precedence.py`` and
    ``test_e28_investor_golden_visa_reachability.py`` stay green through
    this exact defect because they only call ``evaluate()`` — they never
    assemble the HTTP/projection envelope (``_build_display`` +
    ``VisaOracleEvaluateResponse.model_validate``). This test exercises
    exactly the layer that broke: a real ``run_evaluation()`` call, with a
    pricing catalog that WOULD resolve an ``AVAILABLE`` price for the
    supported candidate if asked (proving the guard is what suppresses it,
    not an absence of anything to suppress).

    Two products, one purpose, same shape as
    ``test_evaluator_state_precedence.py``'s ``_four_product_pack`` sized
    down to the two that matter here: SUPP (genuinely SUPPORTED, priceable)
    and REV (PRODUCTS-scope HUMAN_REVIEW rule, unrelated fact).
    """
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")

    at = datetime(2026, 7, 19, tzinfo=timezone.utc)
    source_id = B.new_uuid()
    supp_id = B.new_uuid()
    rev_id = B.new_uuid()
    # canonical_url must be on the approved-HTTPS-source allowlist
    # (api_models.py::_PUBLIC_SOURCE_HOSTS) — the builder's plain
    # "https://example.com/source" default is rejected there.
    src = B.source_record(source_id=source_id, canonical_url="https://www.imigrasi.go.id/")
    products = [
        B.product(
            source_id=source_id,
            product_id=supp_id,
            product_code="SUPP",
            covered_purposes=["TOURISM"],
        ),
        B.product(
            source_id=source_id,
            product_id=rev_id,
            product_code="REV",
            covered_purposes=["TOURISM"],
        ),
    ]
    rules = [
        B.rule(
            rule_id="supp.eligibility",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[supp_id],
            when={"op": "eq", "fact": "work.employer_is_indonesian_entity", "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "SUPP_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["work.employer_is_indonesian_entity"],
        ),
        B.rule(
            rule_id="rev.review",
            stage="HUMAN_REVIEW",
            scope="PRODUCTS",
            product_version_ids=[rev_id],
            when={"op": "eq", "fact": "work.serves_indonesian_clients", "value": True},
            effect={"type": "REQUIRE_REVIEW", "reason_code": "REV_REVIEW"},
            source_id=source_id,
            required_facts=["work.serves_indonesian_clients"],
        ),
    ]
    payload = B.rule_pack_payload(rules=rules, products=products, source_records=[src])
    envelope = B.rule_pack_envelope(payload)
    pack_model = RulePack.model_validate(envelope)
    compiled = build_compiled_pack(pack_model)

    async def _fake_binding(
        pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
    ):
        return shadow._PackBinding(
            rule_pack_id=pack_model.payload.rule_pack_id,
            ruleset_activation_id=uuid.uuid4(),
            environment="TEST",
            raw_envelope=envelope,
        )

    def _fake_verify(
        raw_envelope: object,
        *,
        trust_store: object,
        observed_at: datetime,
        allow_unsigned: bool = False,
    ):
        return VerifiedRulePack(
            pack=pack_model,
            canonical_payload=b"",
            payload_sha256=bytes.fromhex(pack_model.payload_sha256),
            unsigned_dev=False,
        )

    def _fake_compile(rule_pack: object, *, fact_registry: object = None):
        return compiled

    async def _recording_save(pool: object, **kwargs: object) -> None:
        return None

    async def _retention_available(*args: object, **kwargs: object) -> bool:
        return True

    class _ExactPricingCatalog:
        """Would resolve to AVAILABLE — proves the fix actively suppresses
        a real price rather than merely never encountering one."""

        loaded = True

        def get_all_prices(self) -> dict[str, object]:
            return {
                "version": "test-2026.1",
                "metadata": {"last_updated": _MOCK_CATALOG_LAST_UPDATED, "currency": "IDR"},
                "services": {},
            }

        def get_service_by_key(self, key: str) -> dict[str, object] | None:
            if key != "c1_tourist":
                return None
            return {"key": key, "category": "single_entry_visas", "price": "2.300.000 IDR"}

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _fake_binding)
    monkeypatch.setattr(evaluate_path, "verify_rule_pack", _fake_verify)
    monkeypatch.setattr(evaluate_path, "build_compiled_pack", _fake_compile)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _recording_save)
    monkeypatch.setattr(evaluate_path, "active_retention_policy_available", _retention_available)
    monkeypatch.setattr(evaluate_path, "get_pricing_service", _ExactPricingCatalog)
    monkeypatch.setattr(
        evaluate_path, "_apply_safety_critical_source_hold", lambda decision, _compiled: decision
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, _compiled: decision,
    )
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")

    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    data["work.employer_is_indonesian_entity"] = {"status": "KNOWN", "value": True}
    data["work.serves_indonesian_clients"] = {"status": "KNOWN", "value": True}
    facts = ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )

    body = await evaluate_path.run_evaluation(
        object(),
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-owner-ruling-5-projection",
        evaluation_time=at,
    )

    assert body["decision"]["state"] == "HUMAN_REVIEW_REQUIRED", body["decision"]
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"
    assert body["decision"]["outage"] is None
    decision_codes = {c["product_code"] for c in body["decision"]["candidates"]}
    assert decision_codes == {"SUPP"}
    assert body["decision"]["quotes"] == []

    assert body["display"]["candidates"]
    display_codes = {c["product_code"] for c in body["display"]["candidates"]}
    assert display_codes == {"SUPP"}
    for candidate in body["display"]["candidates"]:
        assert candidate["availability"]["legal_eligibility"] == "SUPPORTED"
        assert candidate["pricing"]["status"] == "CONTACT_REQUIRED"
        assert candidate["pricing"]["reason_code"] == "PRICING_PENDING_HUMAN_REVIEW"


async def test_pricing_catalog_outage_does_not_overwrite_legal_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    _, _, compiled = _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, _compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, _compiled: decision,
    )

    class _UnavailablePricingCatalog:
        loaded = False

        def get_service_by_key(self, key: str) -> None:
            raise AssertionError(f"catalog outage must not look up {key}")

        def get_all_prices(self) -> dict[str, object]:
            raise AssertionError("catalog outage must not read prices")

    monkeypatch.setattr(evaluate_path, "get_pricing_service", _UnavailablePricingCatalog)
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    expected = evaluate(
        facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert expected.state is DecisionState.SUPPORTED_CANDIDATES

    body = await evaluate_path.run_evaluation(
        object(),
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-pricing-outage",
        evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
    )

    assert body["decision"]["state"] == expected.state.value
    assert body["decision"]["outage"] is None
    assert body["display"]["candidates"]
    for candidate in body["display"]["candidates"]:
        assert candidate["pricing"]["status"] == "UNKNOWN"
        assert candidate["pricing"]["reason_code"] == "PRICING_CATALOG_UNAVAILABLE"


async def test_pricing_catalog_acquisition_failure_keeps_approved_legal_decision(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, compiled = _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, _compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, _compiled: decision,
    )
    sensitive_marker = "adapter-error-must-not-reach-logs"

    def _pricing_adapter_failure() -> None:
        raise RuntimeError(sensitive_marker)

    monkeypatch.setattr(evaluate_path, "get_pricing_service", _pricing_adapter_failure)
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    expected = evaluate(
        facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert expected.state is DecisionState.SUPPORTED_CANDIDATES

    with caplog.at_level(logging.WARNING, logger="backend.services.visa_engine.evaluate_path"):
        body = await evaluate_path.run_evaluation(
            object(),
            facts=facts,
            traffic_source="real",
            request_category_hint=None,
            request_trace="trace-pricing-adapter-failure",
            evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
        )

    assert body["decision"]["state"] == expected.state.value
    assert body["decision"]["outage"] is None
    assert body["display"]["candidates"]
    assert len(save_calls) == 1
    for candidate in body["display"]["candidates"]:
        assert candidate["pricing"]["status"] == "UNKNOWN"
        assert candidate["pricing"]["reason_code"] == "PRICING_CATALOG_UNAVAILABLE"
    assert "pricing catalog acquisition failed: RuntimeError" in caplog.text
    assert sensitive_marker not in caplog.text


async def test_malformed_pricing_row_keeps_approved_legal_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, compiled = _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, _compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, _compiled: decision,
    )

    class _MalformedRowCatalog:
        loaded = True

        def get_all_prices(self) -> dict[str, object]:
            return {"metadata": {"last_updated": _MOCK_CATALOG_LAST_UPDATED}, "services": {}}

        def get_service_by_key(self, key: str) -> list[str]:
            return [key, "malformed-row"]

    monkeypatch.setattr(evaluate_path, "get_pricing_service", _MalformedRowCatalog)
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    body = await evaluate_path.run_evaluation(
        object(),
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-malformed-pricing-row",
        evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
    )

    assert body["decision"]["state"] == "SUPPORTED_CANDIDATES"
    assert body["decision"]["outage"] is None
    assert body["display"]["candidates"]
    assert len(save_calls) == 1
    for candidate in body["display"]["candidates"]:
        assert candidate["pricing"]["status"] == "UNKNOWN"
        assert candidate["pricing"]["reason_code"] == "PRICING_CATALOG_UNAVAILABLE"


async def test_disclosed_review_flag_can_only_replace_support_with_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Out-of-pack disclosures abstain; they never become eligibility rules."""

    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    _, _, compiled = _patch_engine_chain(monkeypatch)
    supported_facts = gold_loader.load_persona(
        gold_loader.PERSONAS_DIR / "02_business_c2.json"
    ).facts
    baseline = evaluate(
        supported_facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert baseline.state.value == "SUPPORTED_CANDIDATES"
    assert baseline.candidates

    reviewed = evaluate_path._apply_disclosed_review_flags(
        baseline,
        (DisclosedReviewFlag.CRIMINAL_RECORD,),
    )
    assert reviewed.state.value == "HUMAN_REVIEW_REQUIRED"
    assert reviewed.candidates == ()
    assert [reason.code for reason in reviewed.review_reasons] == [
        "DISCLOSED_CRIMINAL_RECORD_REVIEW"
    ]
    assert reviewed.review_reasons[0].source_refs == ()


def test_minor_privacy_hold_is_global_monotone_and_uncited() -> None:
    """A minor cannot inherit an automated supported outcome from any path."""

    compiled = gold_loader.load_and_compile_rule_pack()
    adult_facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    wire = adult_facts.model_dump(mode="json", by_alias=True)
    wire["facts"]["person.birth_date"] = {
        "status": "KNOWN",
        "value": "2012-01-01",
    }
    # This avoids relying on the fixture pack's narrower family-sponsor rule;
    # the privacy adapter must independently cover every product family.
    wire["facts"]["family.sponsor_confirmed"] = {
        "status": "KNOWN",
        "value": True,
    }
    minor_facts = ApplicantFacts.model_validate(wire)
    baseline = evaluate(
        minor_facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert baseline.state is DecisionState.SUPPORTED_CANDIDATES

    held = evaluate_path._apply_minor_privacy_hold(baseline, minor_facts)
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.candidates == ()
    assert [reason.code for reason in held.review_reasons] == ["MINOR_GUARDIAN_PRIVACY_REVIEW"]
    assert held.review_reasons[0].source_refs == ()


def test_unknown_minor_status_cannot_preserve_supported_candidates() -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    adult_facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    baseline = evaluate(
        adult_facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert baseline.state is DecisionState.SUPPORTED_CANDIDATES
    wire = adult_facts.model_dump(mode="json", by_alias=True)
    wire["facts"]["person.birth_date"] = {
        "status": "UNKNOWN",
        "reason": "NOT_PROVIDED",
    }
    unknown_age_facts = ApplicantFacts.model_validate(wire)

    held = evaluate_path._apply_minor_privacy_hold(baseline, unknown_age_facts)
    assert held.state is DecisionState.NEEDS_INPUT
    assert held.candidates == ()
    assert FactPath.PERSON_BIRTH_DATE in held.missing_facts


async def test_public_evaluation_applies_minor_privacy_hold_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, compiled: decision,
    )
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    wire = facts.model_dump(mode="json", by_alias=True)
    wire["facts"]["person.birth_date"] = {
        "status": "KNOWN",
        "value": "2012-01-01",
    }
    wire["facts"]["family.sponsor_confirmed"] = {
        "status": "KNOWN",
        "value": True,
    }

    body = await evaluate_path.run_evaluation(
        object(),
        facts=ApplicantFacts.model_validate(wire),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-minor-privacy-hold",
        evaluation_time=gold_loader.GOLD_EFFECTIVE_AT,
    )

    assert body["decision"]["state"] == "HUMAN_REVIEW_REQUIRED"
    assert body["decision"]["candidates"] == []
    assert [reason["code"] for reason in body["decision"]["review_reasons"]] == [
        "MINOR_GUARDIAN_PRIVACY_REVIEW"
    ]
    assert body["display"] == {"candidates": []}
    assert len(save_calls) == 1
    assert save_calls[0]["decision"].state is DecisionState.HUMAN_REVIEW_REQUIRED


@pytest.mark.parametrize(
    ("currently_in_indonesia", "overstay_fact", "expected_overstay", "expect_conflict"),
    [
        (
            False,
            {"status": "UNKNOWN", "reason": "NOT_ASKED"},
            {"status": "UNKNOWN", "reason": "NOT_ASKED"},
            False,
        ),
        (
            True,
            {"status": "UNKNOWN", "reason": "NOT_ASKED"},
            {"status": "UNKNOWN", "reason": "NOT_ASKED"},
            False,
        ),
        (False, {"status": "KNOWN", "value": 0}, {"status": "KNOWN", "value": 0}, False),
        (False, {"status": "KNOWN", "value": 2}, {"status": "KNOWN", "value": 2}, True),
    ],
)
def test_applicant_facts_preserve_overstay_and_conflicts_abstain(
    currently_in_indonesia: bool,
    overstay_fact: dict[str, object],
    expected_overstay: dict[str, object],
    expect_conflict: bool,
) -> None:
    wire = _wire_payload(_facts_with_purposes(["TOURISM"]))
    wire["facts"]["immigration.currently_in_indonesia"] = {
        "status": "KNOWN",
        "value": currently_in_indonesia,
    }
    wire["facts"]["immigration.overstay_days"] = overstay_fact
    before = json.loads(json.dumps(wire["facts"]))
    request = VisaOracleEvaluateRequest.model_validate(wire)

    canonical = request.applicant_facts().model_dump(mode="json", by_alias=True)["facts"]
    assert canonical["immigration.overstay_days"] == expected_overstay
    before.pop("immigration.overstay_days")
    canonical_without_overstay = dict(canonical)
    canonical_without_overstay.pop("immigration.overstay_days")
    assert canonical_without_overstay == before
    conflict_present = (
        DisclosedReviewFlag.CONFLICTING_IMMIGRATION_STATUS in request.effective_review_flags()
    )
    assert conflict_present is expect_conflict


def test_offshore_unknown_overstay_cannot_manufacture_c2_support() -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    known_facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    known_decision = evaluate(
        known_facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert known_decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert [candidate.product_code for candidate in known_decision.candidates] == ["C2"]

    wire = _wire_payload(known_facts)
    assert wire["facts"]["immigration.currently_in_indonesia"] == {
        "status": "KNOWN",
        "value": False,
    }
    wire["facts"]["immigration.overstay_days"] = {
        "status": "UNKNOWN",
        "reason": "NOT_ASKED",
    }
    request = VisaOracleEvaluateRequest.model_validate(wire)
    canonical = request.applicant_facts()
    assert canonical.facts.immigration_overstay_days.status == "UNKNOWN"

    unknown_decision = evaluate(
        canonical,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert unknown_decision.state is DecisionState.NEEDS_INPUT
    assert unknown_decision.candidates == ()
    assert FactPath.IMMIGRATION_OVERSTAY_DAYS in unknown_decision.missing_facts


async def test_http_offshore_unknown_overstay_remains_needs_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    _patch_engine_chain(monkeypatch)
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    wire = _wire_payload(facts)
    wire["facts"]["immigration.overstay_days"] = {
        "status": "UNKNOWN",
        "reason": "NOT_ASKED",
    }

    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(_REAL_EVALUATE_URL, json=wire)

    assert response.status_code == 200, response.text
    decision = response.json()["decision"]
    assert decision["state"] == "NEEDS_INPUT"
    assert decision["candidates"] == []
    assert "immigration.overstay_days" in decision["missing_facts"]


async def test_offshore_positive_overstay_conflict_forces_human_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    _patch_engine_chain(monkeypatch)
    wire = _wire_payload(_facts_with_purposes(["TOURISM"]))
    wire["facts"]["immigration.currently_in_indonesia"] = {
        "status": "KNOWN",
        "value": False,
    }
    wire["facts"]["immigration.overstay_days"] = {"status": "KNOWN", "value": 2}
    response = await evaluate_path.run_public_evaluation(
        object(),
        request=VisaOracleEvaluateRequest.model_validate(wire),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-conflicting-overstay",
        canonical_request=b"{}",
        idempotency_key=None,
    )
    assert response.decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert "CONFLICTING_IMMIGRATION_STATUS_REVIEW" in {
        reason.code for reason in response.decision.review_reasons
    }


async def test_source_projection_exposes_bitemporal_freshness_without_invented_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    _patch_engine_chain(monkeypatch)
    supported_facts = gold_loader.load_persona(
        gold_loader.PERSONAS_DIR / "02_business_c2.json"
    ).facts
    body = await evaluate_path.run_evaluation(
        object(),
        facts=supported_facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-source-freshness",
    )
    assert body["sources"]
    for source in body["sources"]:
        assert source["legal_period_from"]
        assert "legal_period_to" in source
        assert source["recorded_period_from"]
        assert source["retrieved_at"]
        assert source["verified_at"]
        assert source["applicability"]["status"] == "APPLICABLE"
        assert source["freshness"] == {
            "status": "UNKNOWN",
            "reason_code": "FRESHNESS_POLICY_NOT_DEFINED",
            "evaluated_at": body["sources"][0]["freshness"]["evaluated_at"],
            "verified_at": source["verified_at"],
            "max_age_seconds": None,
        }
        source_effective = datetime.fromisoformat(source["applicability"]["effective_at"])
        source_observed = datetime.fromisoformat(source["applicability"]["observed_at"])
        decision_effective = datetime.fromisoformat(
            body["decision"]["effective_at"].replace("Z", "+00:00")
        )
        decision_observed = datetime.fromisoformat(
            body["decision"]["observed_at"].replace("Z", "+00:00")
        )
        assert source_effective == decision_effective
        assert source_observed == decision_observed
    assert body["decision"]["state"] == "HUMAN_REVIEW_REQUIRED"
    assert "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE" in {
        reason["code"] for reason in body["decision"]["review_reasons"]
    }
    assert body["decision"]["trace_sha256"] is not None
    assert body["decision"]["decision_integrity"] is not None


def test_real_signed_decisive_source_without_freshness_policy_abstains() -> None:
    compiled, decision, held = _real_signed_decisive_source_case()
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert decision.candidates
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.candidates == ()
    assert held.no_path_reasons == ()
    assert {reason.code for reason in held.review_reasons} == {"DECISIVE_SOURCE_FRESHNESS_UNKNOWN"}
    safety_held = evaluate_path._apply_safety_critical_source_hold(decision, compiled)
    assert {reason.code for reason in safety_held.review_reasons} == {
        "SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN"
    }


def test_real_signed_source_is_current_at_inclusive_freshness_boundary() -> None:
    compiled, decision, held = _real_signed_decisive_source_case(
        freshness_max_age_seconds=90_000,
    )
    assert decision.observed_at - timedelta(seconds=90_000) == datetime(
        2026, 8, 3, 11, 0, tzinfo=timezone.utc
    )
    assert held == decision
    assert evaluate_path._apply_safety_critical_source_hold(decision, compiled) == decision

    sources = evaluate_path._build_sources_dto(
        decision,
        compiled,
        request_trace="trace-current-boundary",
    )
    assert sources[0]["freshness"] == {
        "status": "CURRENT",
        "reason_code": "SOURCE_FRESHNESS_CURRENT",
        "evaluated_at": "2026-08-04T12:00:00Z",
        "verified_at": "2026-08-03T11:00:00Z",
        "max_age_seconds": 90_000,
    }


def test_real_signed_stale_source_forces_decisive_and_safety_holds() -> None:
    compiled, decision, held = _real_signed_decisive_source_case(
        freshness_max_age_seconds=89_999,
    )
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.candidates == ()
    assert {reason.code for reason in held.review_reasons} == {"DECISIVE_SOURCE_STALE"}

    safety_held = evaluate_path._apply_safety_critical_source_hold(decision, compiled)
    assert safety_held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert {reason.code for reason in safety_held.review_reasons} == {
        "SAFETY_CRITICAL_SOURCE_STALE"
    }


@pytest.mark.parametrize("defect", ["REVOKED", "non_primary", "expired"])
def test_current_but_invalid_source_never_passes_global_safety_hold(defect: str) -> None:
    compiled, decision, _ = _real_signed_decisive_source_case(
        defect,
        freshness_max_age_seconds=90_000,
    )
    safety_held = evaluate_path._apply_safety_critical_source_hold(decision, compiled)
    assert safety_held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert safety_held.candidates == ()
    assert {reason.code for reason in safety_held.review_reasons} == {
        "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE"
    }


def test_freshness_is_monotone_from_current_to_stale_after_boundary() -> None:
    compiled, _, _ = _real_signed_decisive_source_case(
        freshness_max_age_seconds=90_000,
    )
    source = next(
        item
        for item in compiled.source_pack.payload.source_records
        if str(item.source_record_id) == _DECISIVE_SOURCE_ID
    )
    boundary = source.verified_at + timedelta(seconds=90_000)
    statuses = [
        evaluate_path._evaluate_source_freshness(source, evaluated_at=instant).status
        for instant in (
            boundary - timedelta(seconds=1),
            boundary,
            boundary + timedelta(microseconds=1),
        )
    ]
    assert statuses == [
        SourceFreshnessStatus.CURRENT,
        SourceFreshnessStatus.CURRENT,
        SourceFreshnessStatus.STALE,
    ]


def test_future_verified_at_projects_unknown_and_never_passes_decisive_gate() -> None:
    compiled, decision, held = _real_signed_decisive_source_case(
        "verified_in_future_before_signing",
        freshness_max_age_seconds=90_000,
    )
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert {reason.code for reason in held.review_reasons} == {"DECISIVE_SOURCE_FRESHNESS_UNKNOWN"}
    sources = evaluate_path._build_sources_dto(
        decision,
        compiled,
        request_trace="trace-future-verified-at",
    )
    assert sources[0]["freshness"] == {
        "status": "UNKNOWN",
        "reason_code": "SOURCE_VERIFIED_AT_IN_FUTURE",
        "evaluated_at": "2026-08-04T12:00:00Z",
        "verified_at": "2026-08-04T12:03:00Z",
        "max_age_seconds": 90_000,
    }


@pytest.mark.parametrize(
    "defect",
    [
        "SUPERSEDED",
        "REVOKED",
        "UNAVAILABLE",
        "not_yet_effective",
        "expired",
        "recorded_future",
        "recorded_after_retrieved",
        "recorded_to_before_verified",
        "retrieved_after_verified",
        "verified_after_signing",
        "verified_after_observed",
        "non_primary",
        "url_http",
        "url_unapproved_host",
        "url_userinfo",
        "url_port",
    ],
)
def test_real_signed_invalid_decisive_source_never_emits_candidate(defect: str) -> None:
    _, decision, held = _real_signed_decisive_source_case(defect)
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert decision.candidates
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.candidates == ()
    assert held.quotes == ()
    assert held.no_path_reasons == ()
    assert {reason.code for reason in held.review_reasons} == {
        "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE"
    }
    assert held.review_reasons[0].source_refs == (uuid.UUID(_DECISIVE_SOURCE_ID),)


@pytest.mark.parametrize(
    "official_host",
    [
        "www.imigrasi.go.id",
        "evisa.imigrasi.go.id",
        "peraturan.bpk.go.id",
        "kemenimipas.go.id",
        "www.peraturan.go.id",
    ],
)
def test_real_signed_exact_official_hosts_are_primary_but_still_freshness_unknown(
    official_host: str,
) -> None:
    _, decision, held = _real_signed_decisive_source_case(official_host=official_host)
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert {reason.code for reason in held.review_reasons} == {"DECISIVE_SOURCE_FRESHNESS_UNKNOWN"}


def test_real_signed_regional_official_host_is_projectable_but_not_decisive_primary() -> None:
    compiled, decision, held = _real_signed_decisive_source_case(
        official_host="kanwilsultra.imigrasi.go.id"
    )
    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert {reason.code for reason in held.review_reasons} == {
        "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE"
    }
    sealed = seal_decision(
        held,
        key=resolve_engine_hmac_keyring(Environment.TEST, held.observed_at).minting_key,
    )
    sources = evaluate_path._build_sources_dto(
        sealed,
        compiled,
        request_trace="trace-regional-source",
    )
    assert sources[0]["canonical_url"].startswith("https://kanwilsultra.imigrasi.go.id/")
    assert sources[0]["is_primary_authority"] is False
    projected = VisaOracleEvaluateResponse.model_validate(
        {
            "mode": "ENGINE",
            "decision": sealed.model_dump(mode="json"),
            "sources": sources,
            "display": {"candidates": []},
        }
    )
    assert projected.sources[0].is_primary_authority is False


def test_real_signed_no_path_also_abstains_without_freshness_policy() -> None:
    _, decision, held = _real_signed_decisive_source_case(
        persona_name="20_contradictory_facts_no_crash.json"
    )
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    assert decision.no_path_reasons
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert held.no_path_reasons == ()
    assert held.candidates == ()
    assert {reason.code for reason in held.review_reasons} == {"DECISIVE_SOURCE_FRESHNESS_UNKNOWN"}


def test_revoked_signed_source_is_projected_for_human_review_without_candidates() -> None:
    compiled, _, held = _real_signed_decisive_source_case("REVOKED")
    keyring = resolve_engine_hmac_keyring(Environment.TEST, held.observed_at)
    sealed = seal_decision(held, key=keyring.minting_key)
    sources = evaluate_path._build_sources_dto(
        sealed,
        compiled,
        request_trace="trace-revoked-source-projection",
    )
    assert len(sources) == 1
    assert sources[0]["status"] == "REVOKED"
    assert sources[0]["applicability"]["status"] == "REVOKED"
    response = VisaOracleEvaluateResponse.model_validate(
        {
            "mode": "ENGINE",
            "decision": sealed.model_dump(mode="json"),
            "sources": sources,
            "display": {"candidates": []},
        }
    )
    assert response.decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert response.decision.candidates == ()
    assert response.sources[0].status.value == "REVOKED"


async def test_source_freshness_clock_must_equal_decision_observed_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await _supported_engine_response(monkeypatch)
    body = response.model_dump(mode="json")
    body["sources"][0]["freshness"]["evaluated_at"] = (
        response.decision.observed_at + timedelta(seconds=1)
    ).isoformat()
    with pytest.raises(
        ValidationError,
        match="source freshness evaluated_at must match decision observed_at",
    ):
        VisaOracleEvaluateResponse.model_validate(body)


async def test_source_primary_flag_cannot_promote_bali_zero_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await _supported_engine_response(monkeypatch)
    body = response.model_dump(mode="json")
    policy_source = next(
        source for source in body["sources"] if source["authority_type"] == "BALI_ZERO_POLICY"
    )
    assert policy_source["canonical_url"].startswith("https://internal.balizero.dev/")
    assert policy_source["is_primary_authority"] is False
    policy_source["is_primary_authority"] = True
    with pytest.raises(
        ValidationError,
        match="is_primary_authority must match authority type and official host",
    ):
        VisaOracleEvaluateResponse.model_validate(body)


async def test_non_unknown_availability_requires_resolved_current_primary_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = await _supported_engine_response(monkeypatch)
    body = response.model_dump(mode="json")
    assessment = body["display"]["candidates"][0]["availability"]["operational_availability"]
    assessment["status"] = "AVAILABLE"
    assessment["reason_code"] = "OPERATIONALLY_AVAILABLE"

    with pytest.raises(ValidationError, match="non-UNKNOWN availability requires source_refs"):
        VisaOracleEvaluateResponse.model_validate(body)

    assessment["source_refs"] = [str(uuid.uuid4())]
    with pytest.raises(
        ValidationError,
        match="every decision and availability source_ref must resolve in sources",
    ):
        VisaOracleEvaluateResponse.model_validate(body)

    evidence_source = body["sources"][0]
    assessment["source_refs"] = [evidence_source["source_record_id"]]
    with pytest.raises(
        ValidationError,
        match="availability claims require current, applicable primary sources",
    ):
        VisaOracleEvaluateResponse.model_validate(body)

    evidence_source["authority_type"] = "OFFICIAL_PORTAL"
    evidence_source["canonical_url"] = "https://www.imigrasi.go.id/"
    evidence_source["is_primary_authority"] = True
    evidence_source["freshness"]["status"] = "CURRENT"
    validated = VisaOracleEvaluateResponse.model_validate(body)
    assert (
        validated.display.candidates[0].availability.operational_availability.status.value
        == "AVAILABLE"
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("freshness_verified", "source freshness verified_at must match source verified_at"),
        ("applicability_clock", "source applicability clocks must match the decision clocks"),
        ("recorded_future", "source cannot be recorded after the decision observed_at"),
        ("retrieved_after_verified", "source evidence clocks must not be in the future"),
        ("legal_period", "APPLICABLE source legal period must contain effective_at"),
    ],
)
async def test_source_dto_rejects_cross_clock_forgery(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    response = await _supported_engine_response(monkeypatch)
    body = response.model_dump(mode="json")
    source = body["sources"][0]
    observed = response.decision.observed_at
    if mutation == "freshness_verified":
        source_verified = datetime.fromisoformat(source["verified_at"])
        source["freshness"]["verified_at"] = source_verified + timedelta(seconds=1)
    elif mutation == "applicability_clock":
        source["applicability"]["effective_at"] = response.decision.effective_at + timedelta(
            seconds=1
        )
    elif mutation == "recorded_future":
        source["recorded_period_from"] = observed + timedelta(seconds=1)
    elif mutation == "retrieved_after_verified":
        source_verified = datetime.fromisoformat(source["verified_at"])
        source["retrieved_at"] = source_verified + timedelta(seconds=1)
    else:
        source["legal_period_from"] = response.decision.effective_at + timedelta(seconds=1)

    with pytest.raises(ValidationError, match=message):
        VisaOracleEvaluateResponse.model_validate(body)


@pytest.mark.parametrize("defect", ["source", "product", "quote"])
@pytest.mark.parametrize("use_idempotency", [False, True])
async def test_public_projection_defects_fail_closed_without_500(
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
    use_idempotency: bool,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    _patch_engine_chain(monkeypatch)
    monkeypatch.setattr(
        evaluate_path,
        "_apply_safety_critical_source_hold",
        lambda decision, compiled: decision,
    )
    monkeypatch.setattr(
        evaluate_path,
        "_apply_decisive_source_authority_hold",
        lambda decision, compiled: decision,
    )

    if defect == "source":
        monkeypatch.setattr(
            evaluate_path,
            "_build_sources_dto",
            lambda decision, compiled, *, request_trace: [],
        )
    elif defect == "product":
        monkeypatch.setattr(
            evaluate_path,
            "_build_display",
            lambda decision, compiled, *, request_trace: {"candidates": []},
        )
    else:

        def _malformed_quote_seal(decision, *, key, trace=None):
            sealed = seal_decision(decision, key=key, trace=trace)
            return sealed.model_copy(update={"quotes": ({"malformed": True},)})

        monkeypatch.setattr(evaluate_path, "seal_decision", _malformed_quote_seal)

    if use_idempotency:
        reserved_at = datetime.now(timezone.utc)

        async def _reserve(*args: object, **kwargs: object) -> IdempotencyReservation:
            return IdempotencyReservation(
                key_sha256=b"k" * 32,
                request_hmac=b"h" * 32,
                request_hmac_key_id="test-key",
                reserved_at=reserved_at,
                environment="TEST",
                retention_policy_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                expires_at=reserved_at + timedelta(hours=1),
                response=None,
            )

        async def _complete(*args: object, **kwargs: object) -> VisaOracleEvaluateResponse:
            return kwargs["response"]  # type: ignore[return-value]

        monkeypatch.setattr(evaluate_path, "reserve_idempotency", _reserve)
        monkeypatch.setattr(evaluate_path, "complete_idempotency", _complete)

    headers = {"Idempotency-Key": "projection-defect"} if use_idempotency else {}
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            _REAL_EVALUATE_URL,
            json=_wire_payload(_facts_with_purposes(["BUSINESS_MEETINGS"])),
            headers=headers,
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"]["state"] == "TEMPORARILY_UNAVAILABLE"
    assert body["decision"]["outage"] == {
        "code": "PUBLIC_PROJECTION_UNAVAILABLE",
        "retryable": True,
    }
    assert body["decision"]["candidates"] == []
    assert body["sources"] == []
    assert body["display"] == {"candidates": []}


def test_final_decision_trace_and_integrity_are_deterministic_and_cover_disclosures() -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    evaluation = evaluate_with_trace(
        facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    decision = evaluation.decision
    key = resolve_engine_hmac_keyring(
        Environment.TEST,
        gold_loader.GOLD_EFFECTIVE_AT,
    ).minting_key
    first = seal_decision(decision, key=key, trace=evaluation.trace)
    second = seal_decision(decision, key=key, trace=evaluation.trace)
    assert first.trace_sha256 == second.trace_sha256
    assert first.decision_integrity == second.decision_integrity
    assert first.trace_sha256 is not None
    assert first.decision_integrity is not None
    assert verify_decision_seal(first, key=key, trace=evaluation.trace)

    disclosed = evaluate_path._apply_disclosed_review_flags(
        first,
        (DisclosedReviewFlag.NOT_CERTAIN,),
    )
    assert disclosed.trace_sha256 == first.trace_sha256
    assert disclosed.decision_integrity is None
    resealed = seal_decision(disclosed, key=key, trace=evaluation.trace)
    assert resealed.trace_sha256 == first.trace_sha256
    assert resealed.decision_integrity != first.decision_integrity
    assert verify_decision_seal(resealed, key=key, trace=evaluation.trace)


def test_decision_seal_detects_tampering_of_every_top_level_field() -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    facts = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json").facts
    decision = evaluate(
        facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    key = resolve_engine_hmac_keyring(
        Environment.TEST,
        gold_loader.GOLD_EFFECTIVE_AT,
    ).minting_key
    sealed = seal_decision(decision, key=key)
    assert sealed.rule_pack is not None
    assert sealed.facts_fingerprint is not None
    assert sealed.candidates
    assert sealed.decision_integrity is not None
    candidate = sealed.candidates[0]
    product = next(
        product
        for product in compiled.source_pack.payload.products
        if product.product_version_id == candidate.product_version_id
    )
    assert product.pricing_key is not None
    tamper_reason = Reason(
        code="TAMPERED_FIELD",
        rule_ids=("system.tamper-test",),
        source_refs=(),
    )
    tamper_quote = PriceQuote(
        quote_id=uuid.uuid5(sealed.decision_id, "tamper-quote"),
        product_version_id=candidate.product_version_id,
        product_code=candidate.product_code,
        status="CONTACT_REQUIRED",
        currency="IDR",
        amount=None,
        pricing_key=product.pricing_key,
        catalog_version=None,
        catalog_sha256=None,
        row_sha256=None,
        quoted_at=sealed.evaluated_at,
        valid_until=None,
        reason_code="TAMPERED_PRICE",
    )
    mutations: dict[str, object] = {
        "schema_version": "1.0.1",
        "decision_id": uuid.uuid5(sealed.decision_id, "tampered"),
        "public_id": "0" * 16,
        "state": DecisionState.NO_SUPPORTED_PATH,
        "effective_at": sealed.effective_at + timedelta(seconds=1),
        "observed_at": sealed.observed_at + timedelta(seconds=1),
        "evaluated_at": sealed.evaluated_at + timedelta(seconds=1),
        "rule_pack": sealed.rule_pack.model_copy(
            update={"sequence": sealed.rule_pack.sequence + 1}
        ),
        "facts_fingerprint": sealed.facts_fingerprint.model_copy(update={"digest": "0" * 64}),
        "candidates": (
            candidate.model_copy(update={"score": candidate.score + 1}),
            *sealed.candidates[1:],
        ),
        # Owner ruling #5 (2026-08-25) reuses `candidates` itself (see
        # `evaluator.py`'s review branch / `models.py::
        # Decision._check_state_conditionals`) rather than adding a new
        # top-level field, so there is no additional field to seal-cover
        # here — the `candidates` mutation above already exercises it.
        "missing_facts": (FactPath.INTENT_STAY_DAYS,),
        "review_reasons": (tamper_reason,),
        "no_path_reasons": (tamper_reason,),
        "outage": Outage(code="TAMPERED_OUTAGE", retryable=True),
        "quotes": (tamper_quote,),
        "notices": (*sealed.notices, tamper_reason),
        "trace_sha256": "0" * 64,
        "decision_integrity": sealed.decision_integrity.model_copy(update={"digest": "0" * 64}),
    }
    assert set(mutations) == set(type(sealed).model_fields)
    for field_name, tampered_value in mutations.items():
        tampered = sealed.model_copy(update={field_name: tampered_value})
        assert not verify_decision_seal(tampered, key=key), field_name


async def test_enforce_mode_is_engine_after_durable_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    body = await evaluate_path.run_evaluation(
        object(),
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-enforce",
    )
    assert body["mode"] == "ENGINE"
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"
    assert len(save_calls) == 1
    assert save_calls[0]["engine_mode"] is EngineMode.ENFORCE


@pytest.mark.parametrize(
    ("engine_mode", "expected_mode", "expected_state"),
    [
        ("SHADOW", "CURATED", "HUMAN_REVIEW_REQUIRED"),
        ("ENFORCE", "ENGINE", "TEMPORARILY_UNAVAILABLE"),
    ],
)
async def test_persistence_failure_obeys_authority_gate(
    monkeypatch: pytest.MonkeyPatch,
    engine_mode: str,
    expected_mode: str,
    expected_state: str,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, engine_mode)
    _patch_engine_chain(monkeypatch)

    async def _failing_save(pool: object, **kwargs: object) -> None:
        raise RuntimeError("persistence unavailable")

    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _failing_save)
    body = await evaluate_path.run_evaluation(
        object(),
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-persistence-gate",
    )
    assert body["mode"] == expected_mode
    assert body["decision"]["state"] == expected_state
    if engine_mode == "ENFORCE":
        assert body["decision"]["outage"] == {
            "code": "DECISION_PERSISTENCE_UNAVAILABLE",
            "retryable": True,
        }
        assert body["decision"]["decision_id"] is None
        assert body["decision"]["public_id"] is None
        assert body["decision"]["rule_pack"] is None
        assert body["decision"]["facts_fingerprint"] is None


async def test_allowlisted_synthetic_label_is_accepted_and_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
    monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, "w4-driver-secret")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
            headers={"x-visa-driver-token": "w4-driver-secret"},
        )
    assert response.status_code == 200
    assert len(save_calls) == 1
    assert save_calls[0]["traffic_source"] == "synthetic_gold"


async def test_request_category_hint_honored_when_facts_derive_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNKNOWN-purposes facts + hint=diaspora -> 'diaspora' (the hint's only
    legitimate territory)."""
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?request_category=diaspora&traffic_source=real",
            json=_wire_payload(_facts_with_purposes(None)),
        )
    assert response.status_code == 200
    assert save_calls[0]["request_category"] == "diaspora"


async def test_request_category_hint_loses_to_mappable_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TOURISM facts + hint=student -> 'long_tourism': facts speak first."""
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?request_category=student&traffic_source=real",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 200
    assert save_calls[0]["request_category"] == "long_tourism"


async def test_happy_path_logs_carry_no_fact_values(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """PII boundary (Law 2): no log line may contain a fact value — only the
    caller-supplied trace, the environment, the verdict, and counts."""
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    facts = shadow.build_shadow_facts(
        nationality="ZW",  # distinctive marker
        purpose=Purpose.LONG_TOURISM,
        duration_months=181,  # -> stay_days 5430, distinctive marker
        match_hash="pii-marker-hash",
    )
    assert facts is not None
    with caplog.at_level(logging.DEBUG, logger="backend.services.visa_engine.evaluate_path"):
        await evaluate_path.run_evaluation(
            object(),
            facts=facts,
            traffic_source="real",
            request_category_hint=None,
            request_trace="trace-pii-safe",
        )
    assert len(save_calls) == 1
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "ZW" not in logged
    assert "5430" not in logged
    assert "pii-marker-hash" not in logged
    # ...while the operational correlators ARE logged (the trace works).
    assert "trace-pii-safe" in logged


# ---------------------------------------------------------------------------
# §7 — registry / security-gate / rate-limit / manifest coherence
# ---------------------------------------------------------------------------


def test_evaluate_path_registered_public_exact() -> None:
    entry = find_entry("/api/visa-oracle/evaluate")
    assert entry is not None
    assert entry.match == "exact"
    assert is_public_path("/api/visa-oracle/evaluate")
    # Innocence: the exact entry must not bleed onto sibling paths.
    assert find_entry("/api/visa-oracle/evaluate/anything") is None
    assert find_entry("/api/visa-oracle/other") is None


def test_security_gate_allowlist_coherence() -> None:
    assert ("POST", "/api/visa-oracle/evaluate") in {
        (entry.method, entry.path) for entry in INTENTIONALLY_PUBLIC_MUTATIONS
    }


def test_rate_limit_dedicated_bucket_beats_api_prefix() -> None:
    assert RateLimitMiddleware.RATE_LIMITS["/api/visa-oracle/evaluate"] == (30, 60)
    middleware = RateLimitMiddleware(app=FastAPI())
    assert middleware._get_rate_limit("/api/visa-oracle/evaluate") == (30, 60)
    # Guilt guard: without the exact entry this path would fall into the
    # generic 120/min bucket — the dedicated bucket must actually win.
    assert RateLimitMiddleware.RATE_LIMITS["/api/"] == (120, 60)
    assert middleware._get_rate_limit("/api/visa-oracle/other") == (120, 60)


def test_manifest_declares_evaluate_router_for_api_group() -> None:
    entries = [entry for entry in ROUTER_MANIFEST if entry.name == "visa_oracle_evaluate"]
    assert len(entries) == 1
    assert entries[0].process_groups == _API


async def test_runtime_openapi_and_exported_contract_share_five_decision_conditionals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runtime document consumed by TS generation must match G1 state gates."""

    from backend.app.setup.app_factory import create_app

    valid_response = await _supported_engine_response(monkeypatch)
    valid_decision = valid_response.decision.model_dump(mode="json")

    runtime_openapi = create_app().openapi()
    runtime_decision = runtime_openapi["components"]["schemas"]["Decision"]
    exported_contract = schema_export.build_schemas()["contract.schema.json"]
    exported_decision = exported_contract["$defs"]["Decision"]
    assert len(runtime_decision["allOf"]) == len(exported_decision["allOf"]) == 5

    runtime_root = {
        **runtime_openapi,
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/components/schemas/Decision",
    }
    exported_root = {
        **exported_contract,
        "$ref": "#/$defs/Decision",
    }
    validators = (
        Draft202012Validator(runtime_root),
        Draft202012Validator(exported_root),
    )
    for validator in validators:
        assert list(validator.iter_errors(valid_decision)) == []

    for state in (
        "SUPPORTED_CANDIDATES",
        "NEEDS_INPUT",
        "HUMAN_REVIEW_REQUIRED",
        "NO_SUPPORTED_PATH",
        "TEMPORARILY_UNAVAILABLE",
    ):
        invalid = json.loads(json.dumps(valid_decision))
        invalid["state"] = state
        if state == "SUPPORTED_CANDIDATES":
            invalid["candidates"] = []
        for validator in validators:
            assert list(validator.iter_errors(invalid)), state


# ---------------------------------------------------------------------------
# §8 — DB integration: the real write path
# (migrations 252+255+256+257+262+263+264+265+266).
# Fixture ordering mirrors shadow_evidence_schema's documented ordering note
# (257's rollback re-validates surviving rows, so it always runs AFTER 252's
# table drop).
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parents[3]


def _read_migration(number: int, name: str) -> tuple[str, str]:
    path = _BACKEND_DIR / "db" / "migrations_v2" / f"{number}_{name}.sql"
    forward, rollback = split_migration_sql(path.read_text(encoding="utf-8"))
    assert rollback, f"migration {number} must carry a '-- === ROLLBACK ===' section"
    return forward, rollback


@pytest_asyncio.fixture
async def evaluate_schema(db_pool: asyncpg.Pool, visa_schema: None) -> AsyncIterator[None]:
    forward_252, rollback_252 = _read_migration(252, "visa_engine_write_substrate")
    forward_255, rollback_255 = _read_migration(255, "visa_shadow_evidence")
    forward_256, rollback_256 = _read_migration(256, "visa_traffic_source")
    forward_257, rollback_257 = _read_migration(257, "visa_request_category_extension")
    forward_262, rollback_262 = _read_migration(262, "visa_evaluate_idempotency")
    forward_263, rollback_263 = _read_migration(263, "visa_evaluate_response_hmac")
    forward_264, rollback_264 = _read_migration(264, "visa_decision_retention_policy")
    forward_265, rollback_265 = _read_migration(265, "visa_decision_trace_integrity")
    forward_266, rollback_266 = _read_migration(266, "visa_retention_evidence")
    async with db_pool.acquire() as conn:
        if await conn.fetchval(
            "SELECT to_regprocedure('public.visa_decision_retention_evidence()') IS NOT NULL"
        ):
            await conn.execute(rollback_266)
        if await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'visa_decisions' "
            "AND column_name = 'trace_sha256'"
        ):
            await conn.execute(rollback_265)
        if await conn.fetchval("SELECT to_regclass('public.visa_decision_retention_policies')"):
            await conn.execute(rollback_264)
        if await conn.fetchval("SELECT to_regclass('public.visa_evaluate_idempotency')"):
            await conn.execute(rollback_263)
        await conn.execute(rollback_262)
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)
        await conn.execute(forward_252)
        await conn.execute(forward_255)
        await conn.execute(forward_256)
        await conn.execute(forward_257)
        await conn.execute(forward_262)
        await conn.execute(forward_263)
        await conn.execute(forward_264)
        await conn.execute(forward_265)
        await conn.execute(forward_266)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_266)
        await conn.execute(rollback_265)
        await conn.execute(rollback_264)
        await conn.execute(rollback_263)
        await conn.execute(rollback_262)
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)


async def _insert_retention_policy(
    conn: asyncpg.Connection,
    *,
    effective_from: datetime,
    retention_interval: timedelta,
    idempotency_retention_interval: timedelta,
    policy_version: str = "zero-test-v1",
    retention_anchor: str = "EVALUATED_AT",
) -> uuid.UUID:
    return await conn.fetchval(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor,
            effective_period, approved_by, approval_reference
        ) VALUES (
            'TEST', $1, $2, $3, INTERVAL '30 days', $4,
            tstzrange($5, NULL, '[)'),
            'zero-test-approver', 'ZERO-RETENTION-TEST-APPROVAL'
        )
        RETURNING id
        """,
        policy_version,
        retention_interval,
        idempotency_retention_interval,
        retention_anchor,
        effective_from,
    )


async def _set_test_legal_hold(
    conn: asyncpg.Connection,
    *,
    decision_row_id: uuid.UUID,
    legal_hold: bool,
    reason_code: str,
) -> bool:
    domain_decision_id = await conn.fetchval(
        "SELECT decision_id FROM public.visa_decisions WHERE id = $1",
        decision_row_id,
    )
    review_due_at = datetime.now(timezone.utc) + timedelta(days=29) if legal_hold else None
    return bool(
        await conn.fetchval(
            "SELECT public.set_visa_decision_legal_hold($1, $2, $3, $4, $5, $6, $7)",
            domain_decision_id,
            legal_hold,
            "privacy.test.operator",
            "PRIVACY-TEST-CASE",
            reason_code,
            "zero-test-approver",
            review_due_at,
        )
    )


async def _insert_current_test_retention_policy(db_pool: asyncpg.Pool) -> uuid.UUID:
    """Install an explicit test-only policy; production migration seeds none."""

    async with db_pool.acquire() as conn:
        return await _insert_retention_policy(
            conn,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            retention_interval=timedelta(days=1),
            idempotency_retention_interval=timedelta(hours=1),
        )


async def _insert_temp_decision(
    conn: asyncpg.Connection,
    *,
    engine_mode: str,
    evaluated_at: datetime,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO public.visa_decisions (
            decision_id, environment, engine_surface, engine_mode, verdict,
            engine_version, effective_at, observed_at, evaluated_at
        ) VALUES (
            $1, 'TEST', 'RECOMMEND', $2,
            'TEMPORARILY_UNAVAILABLE', 'retention-test', $3, $3, $3
        )
        RETURNING id, decision_id, retention_policy_id, retention_until, legal_hold
        """,
        uuid.uuid4(),
        engine_mode,
        evaluated_at,
    )


async def _insert_temp_payload(
    conn: asyncpg.Connection,
    *,
    decision_id: uuid.UUID,
    purge_after: datetime,
    legal_hold: bool = False,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO public.visa_decision_payloads (
            decision_id, encryption_key_id, nonce, ciphertext, aad,
            ciphertext_sha256, purge_after, legal_hold
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING decision_id, purge_after, legal_hold
        """,
        decision_id,
        f"retention-test-{uuid.uuid4()}",
        b"n" * 12,
        b"opaque-ciphertext",
        b"retention-test-aad",
        b"s" * 32,
        purge_after,
        legal_hold,
    )


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.parametrize("engine_mode", ["SHADOW", "ENFORCE"])
async def test_retention_policy_is_unseeded_and_new_decision_insert_fails_closed(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    engine_mode: str,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM public.visa_decision_retention_policies") == 0
        )
        defaults = await conn.fetch(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'visa_decision_retention_policies'
              AND column_name IN (
                  'retention_interval',
                  'idempotency_retention_interval',
                  'retention_anchor'
              )
            ORDER BY column_name
            """
        )
        assert {row["column_name"]: row["column_default"] for row in defaults} == {
            "idempotency_retention_interval": None,
            "retention_anchor": None,
            "retention_interval": None,
        }
        assert (
            await conn.fetchval(
                """
            SELECT convalidated
            FROM pg_constraint
            WHERE conname = 'visa_decisions_retention_required'
            """
            )
            is False
        )
        assert (
            await conn.fetchval(
                """
                SELECT convalidated
                FROM pg_constraint
                WHERE conname = 'visa_evaluate_idempotency_retention_required'
                """
            )
            is False
        )
        assert (
            await conn.fetchval(
                """
                SELECT column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'visa_evaluate_idempotency'
                  AND column_name = 'expires_at'
                """
            )
            is None
        )

        with pytest.raises(
            asyncpg.RaiseError,
            match="decision has no active Zero-approved retention policy",
        ):
            await _insert_temp_decision(
                conn,
                engine_mode=engine_mode,
                evaluated_at=now,
            )
        assert await conn.fetchval("SELECT count(*) FROM public.visa_decisions") == 0
        with pytest.raises(
            asyncpg.RaiseError,
            match="idempotency reservation has no active Zero-approved retention policy",
        ):
            await conn.execute(
                """
                INSERT INTO public.visa_evaluate_idempotency (
                    key_sha256, request_hmac, request_hmac_key_id, environment
                ) VALUES ($1, $2, 'test-key', 'TEST')
                """,
                b"u" * 32,
                b"v" * 32,
            )

    assert not await retention.active_policy_available(
        db_pool,
        environment="TEST",
        evaluated_at=now,
    )


@pytest.mark.integration
@pytest.mark.database
async def test_retention_policy_is_non_overlapping_append_only_authority(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    effective_from = datetime.now(timezone.utc) - timedelta(days=1)
    close_at = effective_from + timedelta(hours=12)
    async with db_pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_retention_policy(
                conn,
                effective_from=effective_from,
                retention_interval=timedelta(hours=1),
                idempotency_retention_interval=timedelta(hours=2),
                policy_version="invalid-idempotency-retention",
            )
        policy_id = await _insert_retention_policy(
            conn,
            effective_from=effective_from,
            retention_interval=timedelta(hours=1),
            idempotency_retention_interval=timedelta(minutes=30),
        )
        with pytest.raises(asyncpg.ExclusionViolationError):
            await _insert_retention_policy(
                conn,
                effective_from=effective_from + timedelta(minutes=1),
                retention_interval=timedelta(hours=2),
                idempotency_retention_interval=timedelta(minutes=30),
                policy_version="zero-test-overlap",
            )
        with pytest.raises(
            asyncpg.RaiseError,
            match="update may only close one open effective_period",
        ):
            await conn.execute(
                """
                UPDATE public.visa_decision_retention_policies
                SET retention_interval = INTERVAL '2 hours'
                WHERE id = $1
                """,
                policy_id,
            )
        await conn.execute(
            """
            UPDATE public.visa_decision_retention_policies
            SET effective_period = tstzrange(lower(effective_period), $2, '[)')
            WHERE id = $1
            """,
            policy_id,
            close_at,
        )
        with pytest.raises(asyncpg.RaiseError, match="is append-only"):
            await conn.execute(
                "DELETE FROM public.visa_decision_retention_policies WHERE id = $1",
                policy_id,
            )

    assert await retention.active_policy_available(
        db_pool,
        environment="TEST",
        evaluated_at=close_at - timedelta(seconds=1),
    )
    assert not await retention.active_policy_available(
        db_pool,
        environment="TEST",
        evaluated_at=close_at,
    )


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.parametrize("binding_kind", ["decision", "idempotency"])
async def test_retention_policy_close_cannot_strand_existing_binding(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    binding_kind: str,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        policy_id = await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(days=1),
            idempotency_retention_interval=timedelta(hours=1),
        )
        if binding_kind == "decision":
            await _insert_temp_decision(conn, engine_mode="SHADOW", evaluated_at=now)
        else:
            keyring = resolve_engine_hmac_keyring(Environment.TEST, now)
            await idempotency.reserve(
                db_pool,
                key_sha256=b"b" * 32,
                canonical_request=b'{"binding":"policy-close"}',
                environment="TEST",
                minting_key=keyring.minting_key,
                verification_keys=keyring.verification_keys,
            )

        with pytest.raises(
            asyncpg.RaiseError,
            match="retention policy close would strand an existing binding",
        ):
            await conn.execute(
                """
                UPDATE public.visa_decision_retention_policies
                SET effective_period = tstzrange(lower(effective_period), $2, '[)')
                WHERE id = $1
                """,
                policy_id,
                now - timedelta(seconds=1),
            )
        assert await conn.fetchval(
            "SELECT upper(effective_period) IS NULL FROM public.visa_decision_retention_policies WHERE id = $1",
            policy_id,
        )


@pytest.mark.integration
@pytest.mark.database
async def test_retention_policy_close_serializes_with_idempotency_reservation(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        policy_id = await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(days=1),
            idempotency_retention_interval=timedelta(hours=1),
        )

    locking_conn = await db_pool.acquire()
    transaction = locking_conn.transaction()
    await transaction.start()
    transaction_ended = False
    try:
        close_at = datetime.now(timezone.utc)
        await locking_conn.execute(
            """
            UPDATE public.visa_decision_retention_policies
            SET effective_period = tstzrange(lower(effective_period), $2, '[)')
            WHERE id = $1
            """,
            policy_id,
            close_at,
        )
        keyring = resolve_engine_hmac_keyring(Environment.TEST, close_at)
        reservation_task = asyncio.create_task(
            idempotency.reserve(
                db_pool,
                key_sha256=b"q" * 32,
                canonical_request=b'{"race":"policy-close"}',
                environment="TEST",
                minting_key=keyring.minting_key,
                verification_keys=keyring.verification_keys,
            )
        )
        await asyncio.sleep(0.05)
        assert not reservation_task.done()
        await transaction.commit()
        transaction_ended = True
        with pytest.raises(
            asyncpg.RaiseError,
            match="no active Zero-approved retention policy",
        ):
            await asyncio.wait_for(reservation_task, timeout=3)
    finally:
        if not transaction_ended:
            await transaction.rollback()
        await db_pool.release(locking_conn)

    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM visa_evaluate_idempotency WHERE key_sha256 = $1",
                b"q" * 32,
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.database
async def test_retention_capabilities_are_revoked_security_definers(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    async with db_pool.acquire() as conn:
        boundaries = await conn.fetch(
            """
            SELECT
                procedure.prosecdef,
                procedure.proowner = decisions.relowner AS same_owner_as_table,
                array_to_string(procedure.proconfig, ',') AS settings,
                NOT EXISTS (
                    SELECT 1
                    FROM aclexplode(
                        COALESCE(
                            procedure.proacl,
                            acldefault('f', procedure.proowner)
                        )
                    ) AS privilege
                    WHERE privilege.grantee = 0
                      AND privilege.privilege_type = 'EXECUTE'
                ) AS public_execute_revoked
            FROM pg_proc AS procedure
            JOIN pg_namespace AS namespace
              ON namespace.oid = procedure.pronamespace
            JOIN pg_class AS decisions
              ON decisions.relname = CASE
                    WHEN procedure.proname = 'purge_visa_decisions'
                        THEN 'visa_decisions'
                    ELSE 'visa_evaluate_idempotency'
                 END
             AND decisions.relnamespace = namespace.oid
            WHERE namespace.nspname = 'public'
              AND procedure.proname = ANY($1::text[])
            """,
            [
                "purge_visa_decisions",
                "purge_visa_evaluate_idempotency",
                "prepare_visa_evaluate_idempotency_reservation",
                "visa_idempotency_retention_evidence",
                "visa_idempotency_key_usage_evidence",
            ],
        )
    assert len(boundaries) == 5
    for boundary in boundaries:
        assert boundary["prosecdef"] is True
        assert boundary["same_owner_as_table"] is True
        assert boundary["public_execute_revoked"] is True
        assert boundary["settings"] == "search_path=pg_catalog, pg_temp"


@pytest.mark.integration
@pytest.mark.database
async def test_payload_deadline_and_legal_hold_are_parent_authoritative(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(hours=1),
            idempotency_retention_interval=timedelta(minutes=30),
        )
        decision = await _insert_temp_decision(
            conn,
            engine_mode="ENFORCE",
            evaluated_at=now,
        )
        with pytest.raises(
            asyncpg.RaiseError,
            match="payload retention deadline must equal the parent policy deadline",
        ):
            await _insert_temp_payload(
                conn,
                decision_id=decision["id"],
                purge_after=decision["retention_until"] - timedelta(minutes=1),
            )
        with pytest.raises(asyncpg.RaiseError, match="cannot begin under legal hold"):
            await _insert_temp_payload(
                conn,
                decision_id=decision["id"],
                purge_after=decision["retention_until"],
                legal_hold=True,
            )
        payload = await _insert_temp_payload(
            conn,
            decision_id=decision["id"],
            purge_after=decision["retention_until"],
        )
        assert payload["purge_after"] == decision["retention_until"]
        assert payload["legal_hold"] is False

        assert await _set_test_legal_hold(
            conn,
            decision_row_id=decision["id"],
            legal_hold=True,
            reason_code="TEST-HOLD",
        )
        assert await conn.fetchval(
            "SELECT legal_hold FROM public.visa_decision_payloads WHERE decision_id = $1",
            decision["id"],
        )
        await conn.execute("SELECT set_config('visa.parent_hold_sync', '1', FALSE)")
        try:
            with pytest.raises(
                asyncpg.RaiseError,
                match="must be synchronized by its parent decision",
            ):
                await conn.execute(
                    "UPDATE public.visa_decision_payloads SET legal_hold = FALSE WHERE decision_id = $1",
                    decision["id"],
                )
        finally:
            await conn.execute("RESET visa.parent_hold_sync")
        assert await _set_test_legal_hold(
            conn,
            decision_row_id=decision["id"],
            legal_hold=False,
            reason_code="TEST-RELEASE",
        )
        assert not await conn.fetchval(
            "SELECT legal_hold FROM public.visa_decision_payloads WHERE decision_id = $1",
            decision["id"],
        )
        history = await conn.fetch(
            """
            SELECT decision_row_id, event_type, old_legal_hold, new_legal_hold
            FROM public.visa_decision_legal_hold_events
            ORDER BY id
            """
        )
    assert [row["decision_row_id"] for row in history] == [decision["id"], decision["id"]]
    assert [
        (row["event_type"], row["old_legal_hold"], row["new_legal_hold"]) for row in history
    ] == [
        ("LEGAL_HOLD_SET", False, True),
        ("LEGAL_HOLD_RELEASED", True, False),
    ]


@pytest.mark.integration
@pytest.mark.database
async def test_database_clocks_and_elapsed_deadlines_fail_closed(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(seconds=2),
            idempotency_retention_interval=timedelta(seconds=1),
        )
        with pytest.raises(
            asyncpg.RaiseError, match="decision retention deadline has already elapsed"
        ):
            await _insert_temp_decision(
                conn,
                engine_mode="SHADOW",
                evaluated_at=now - timedelta(seconds=10),
            )
        with pytest.raises(
            asyncpg.RaiseError,
            match="must use the database statement clock",
        ):
            await conn.execute(
                """
                INSERT INTO public.visa_evaluate_idempotency (
                    key_sha256, request_hmac, request_hmac_key_id,
                    reserved_at, created_at, environment
                ) VALUES ($1, $2, 'test-key', $3, $3, 'TEST')
                """,
                b"x" * 32,
                b"y" * 32,
                now - timedelta(seconds=1),
            )
        with pytest.raises(asyncpg.RaiseError, match="must use the database statement clock"):
            await conn.execute(
                """
                INSERT INTO public.visa_evaluate_idempotency (
                    key_sha256, request_hmac, request_hmac_key_id,
                    reserved_at, created_at, environment
                ) VALUES ($1, $2, 'test-key', $3, $3, 'TEST')
                """,
                b"w" * 32,
                b"z" * 32,
                now + timedelta(days=1),
            )
        with pytest.raises(asyncpg.RaiseError, match="must use the database transaction clock"):
            await conn.execute(
                """
                INSERT INTO public.visa_decisions (
                    decision_id, environment, engine_surface, engine_mode, verdict,
                    engine_version, effective_at, observed_at, evaluated_at, created_at
                ) VALUES (
                    $1, 'TEST', 'RECOMMEND', 'SHADOW',
                    'TEMPORARILY_UNAVAILABLE', 'retention-test', $2, $2, $2, $3
                )
                """,
                uuid.uuid4(),
                now,
                now + timedelta(days=1),
            )
        decision = await _insert_temp_decision(
            conn,
            engine_mode="SHADOW",
            evaluated_at=datetime.now(timezone.utc),
        )
        await asyncio.sleep(2.2)
        with pytest.raises(asyncpg.RaiseError, match="expired decision cannot receive a payload"):
            await _insert_temp_payload(
                conn,
                decision_id=decision["id"],
                purge_after=decision["retention_until"],
            )


@pytest.mark.integration
@pytest.mark.database
async def test_runtime_role_cannot_spoof_retention_capability_gucs(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(seconds=5),
            idempotency_retention_interval=timedelta(seconds=5),
        )
        free_decision = await _insert_temp_decision(
            conn,
            engine_mode="SHADOW",
            evaluated_at=now,
        )
        held_decision = await _insert_temp_decision(
            conn,
            engine_mode="SHADOW",
            evaluated_at=now,
        )
        for decision in (free_decision, held_decision):
            await _insert_temp_payload(
                conn,
                decision_id=decision["id"],
                purge_after=decision["retention_until"],
            )
        assert await _set_test_legal_hold(
            conn,
            decision_row_id=held_decision["id"],
            legal_hold=True,
            reason_code="TEST-BOUNDARY-HOLD",
        )
        hold_event_id = await conn.fetchval(
            "SELECT id FROM public.visa_decision_legal_hold_events WHERE decision_row_id = $1",
            held_decision["id"],
        )
    keyring = resolve_engine_hmac_keyring(Environment.TEST, now)
    replay = await idempotency.reserve(
        db_pool,
        key_sha256=b"g" * 32,
        canonical_request=b'{"guc":"spoof"}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    await asyncio.sleep(5.5)

    probe_role = f"visa_retention_probe_{uuid.uuid4().hex}"
    async with db_pool.acquire() as conn:
        try:
            await conn.execute(f"CREATE ROLE {probe_role} NOLOGIN")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {probe_role}")
            await conn.execute(
                f"GRANT SELECT, UPDATE, DELETE ON "
                f"public.visa_decisions, public.visa_decision_payloads, "
                f"public.visa_evaluate_idempotency, "
                f"public.visa_decision_legal_hold_events TO {probe_role}"
            )
            await conn.execute(f"SET ROLE {probe_role}")
            await conn.execute(
                "SELECT set_config('visa.retention_requested_by', 'spoofed-worker', FALSE)"
            )
            await conn.execute(
                "SELECT set_config('visa.idempotency_retention_requested_by', 'spoofed-worker', FALSE)"
            )
            with pytest.raises(asyncpg.RaiseError, match="bounded retention capability"):
                await conn.execute(
                    "DELETE FROM public.visa_evaluate_idempotency WHERE key_sha256 = $1",
                    replay.key_sha256,
                )
            with pytest.raises(asyncpg.RaiseError, match="bounded retention purge"):
                await conn.execute(
                    "DELETE FROM public.visa_decision_payloads WHERE decision_id = $1",
                    free_decision["id"],
                )
            with pytest.raises(asyncpg.RaiseError, match="bounded retention purge"):
                await conn.execute(
                    "DELETE FROM public.visa_decisions WHERE id = $1",
                    free_decision["id"],
                )
            with pytest.raises(
                asyncpg.RaiseError,
                match="must be synchronized by its parent decision",
            ):
                await conn.execute(
                    "UPDATE public.visa_decision_payloads SET legal_hold = FALSE WHERE decision_id = $1",
                    held_decision["id"],
                )
            with pytest.raises(asyncpg.RaiseError, match="parent retention purge"):
                await conn.execute(
                    "DELETE FROM public.visa_decision_legal_hold_events WHERE id = $1",
                    hold_event_id,
                )
        finally:
            await conn.execute("RESET ROLE")
            await conn.execute("RESET visa.retention_requested_by")
            await conn.execute("RESET visa.idempotency_retention_requested_by")
            if await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = $1)", probe_role
            ):
                await conn.execute(f"DROP OWNED BY {probe_role}")
                await conn.execute(f"DROP ROLE {probe_role}")


@pytest.mark.integration
@pytest.mark.database
async def test_retention_binding_legal_hold_and_bounded_purge_are_audited(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    retention_interval = timedelta(seconds=3)
    async with db_pool.acquire() as conn:
        policy_id = await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=retention_interval,
            idempotency_retention_interval=timedelta(seconds=1),
        )
        expired_held = await _insert_temp_decision(
            conn,
            engine_mode="SHADOW",
            evaluated_at=now,
        )
        expired_free = await _insert_temp_decision(
            conn,
            engine_mode="ENFORCE",
            evaluated_at=now,
        )
        await _insert_temp_payload(
            conn,
            decision_id=expired_held["id"],
            purge_after=expired_held["retention_until"],
        )
        assert await _set_test_legal_hold(
            conn,
            decision_row_id=expired_held["id"],
            legal_hold=True,
            reason_code="TEST-RETENTION-HOLD",
        )
        assert await conn.fetchval(
            "SELECT legal_hold FROM public.visa_decision_payloads WHERE decision_id = $1",
            expired_held["id"],
        )
        await asyncio.sleep(3.5)
        evidence = await retention.decision_retention_evidence(db_pool)
        assert evidence.expired_rows == 1
        assert evidence.expired_held_rows == 1
        assert evidence.max_lag_seconds > 0
        assert evidence.observed_at.tzinfo is not None
        fresh_at = datetime.now(timezone.utc)
        fresh = await _insert_temp_decision(
            conn,
            engine_mode="SHADOW",
            evaluated_at=fresh_at,
        )

        for row, evaluated_at in (
            (expired_held, now),
            (expired_free, now),
            (fresh, fresh_at),
        ):
            assert row["retention_policy_id"] == policy_id
            assert row["retention_until"] == evaluated_at + retention_interval
            assert row["legal_hold"] is False

        with pytest.raises(
            asyncpg.RaiseError,
            match="delete must use the bounded retention purge",
        ):
            await conn.execute(
                "DELETE FROM public.visa_decisions WHERE id = $1",
                expired_free["id"],
            )
        with pytest.raises(
            asyncpg.RaiseError,
            match="payload delete must use the bounded retention purge",
        ):
            await conn.execute(
                "DELETE FROM public.visa_decision_payloads WHERE decision_id = $1",
                expired_held["id"],
            )
        with pytest.raises(
            asyncpg.RaiseError,
            match="update may only change legal_hold",
        ):
            await conn.execute(
                "UPDATE public.visa_decisions SET legal_hold = TRUE WHERE id = $1",
                expired_held["id"],
            )

    assert (
        await retention.purge_expired_decisions(
            db_pool,
            limit=1,
            requested_by="retention-worker-test",
        )
        == 1
    )
    async with db_pool.acquire() as conn:
        remaining = set(await conn.fetch("SELECT id FROM public.visa_decisions"))
        assert {row["id"] for row in remaining} == {expired_held["id"], fresh["id"]}
        assert await _set_test_legal_hold(
            conn,
            decision_row_id=expired_held["id"],
            legal_hold=False,
            reason_code="TEST-RETENTION-RELEASE",
        )
        assert not await conn.fetchval(
            "SELECT legal_hold FROM public.visa_decision_payloads WHERE decision_id = $1",
            expired_held["id"],
        )
        hold_history = await conn.fetch(
            """
            SELECT event_type, old_legal_hold, new_legal_hold
            FROM public.visa_decision_legal_hold_events
            WHERE decision_row_id = $1
            ORDER BY id
            """,
            expired_held["id"],
        )
        assert [row["event_type"] for row in hold_history] == [
            "LEGAL_HOLD_SET",
            "LEGAL_HOLD_RELEASED",
        ]

    assert (
        await retention.purge_expired_decisions(
            db_pool,
            limit=1,
            requested_by="retention-worker-test",
        )
        == 1
    )
    assert (
        await retention.purge_expired_decisions(
            db_pool,
            limit=1,
            requested_by="retention-worker-test",
        )
        == 0
    )

    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_decisions WHERE id = $1",
                fresh["id"],
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_decision_payloads WHERE decision_id = $1",
                expired_held["id"],
            )
            == 0
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_decision_legal_hold_events WHERE decision_row_id = $1",
                expired_held["id"],
            )
            == 0
        )
        session_user = await conn.fetchval("SELECT session_user")
        batches = await conn.fetch(
            """
            SELECT retention_policy_id, affected_count, executor_label
            FROM public.visa_decision_retention_batches
            ORDER BY id
            """
        )
        assert [(row["retention_policy_id"], row["affected_count"]) for row in batches] == [
            (policy_id, 1),
            (policy_id, 1),
        ]
        assert all(
            row["executor_label"] == f"{session_user}:retention-worker-test" for row in batches
        )
        with pytest.raises(asyncpg.RaiseError, match="is append-only"):
            await conn.execute(
                "UPDATE public.visa_decision_retention_batches SET executor_label = 'tampered'"
            )
        with pytest.raises(asyncpg.RaiseError, match="purge limit must be between 1 and 1000"):
            await conn.fetchval(
                "SELECT public.purge_visa_decisions($1, $2)",
                1_001,
                "retention-worker-test",
            )


@pytest.mark.integration
@pytest.mark.database
async def test_dsr_erasure_is_early_bounded_idempotent_and_blocked_by_hold(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    domain_decision_id: uuid.UUID
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(days=30),
            idempotency_retention_interval=timedelta(hours=24),
        )
        decision = await _insert_temp_decision(
            conn,
            engine_mode="ENFORCE",
            evaluated_at=now,
        )
        domain_decision_id = await conn.fetchval(
            "SELECT decision_id FROM public.visa_decisions WHERE id = $1",
            decision["id"],
        )
        await _insert_temp_payload(
            conn,
            decision_id=decision["id"],
            purge_after=decision["retention_until"],
        )
        replay_key = b"d" * 32
        await conn.execute(
            """
            INSERT INTO public.visa_evaluate_idempotency (
                key_sha256, request_hmac, request_hmac_key_id, environment
            ) VALUES ($1, $2, 'dsr-test-key', 'TEST')
            """,
            replay_key,
            b"r" * 32,
        )
        await conn.execute(
            """
            UPDATE public.visa_evaluate_idempotency
               SET response_body = jsonb_build_object(
                       'decision', jsonb_build_object('decision_id', $2::text)
                   ),
                   response_sha256 = $3,
                   response_hmac = $4,
                   response_hmac_key_id = 'dsr-response-key',
                   completed_at = clock_timestamp()
             WHERE key_sha256 = $1
            """,
            replay_key,
            str(domain_decision_id),
            b"s" * 32,
            b"h" * 32,
        )

        with pytest.raises(asyncpg.RaiseError, match="bounded retention purge"):
            await conn.execute(
                "DELETE FROM public.visa_decisions WHERE id = $1",
                decision["id"],
            )

    with pytest.raises(asyncpg.RaiseError, match="exceeds the approved interval"):
        await retention.set_decision_legal_hold(
            db_pool,
            decision_id=domain_decision_id,
            legal_hold=True,
            requested_by="privacy.operator",
            case_reference="DSR-2026-001",
            reason_code="DSR-IDENTITY-VERIFICATION",
            approved_by="privacy.approver",
            review_due_at=now + timedelta(days=31),
        )

    assert await retention.set_decision_legal_hold(
        db_pool,
        decision_id=domain_decision_id,
        legal_hold=True,
        requested_by="privacy.operator",
        case_reference="DSR-2026-001",
        reason_code="DSR-IDENTITY-VERIFICATION",
        approved_by="privacy.approver",
        review_due_at=now + timedelta(days=29),
    )
    async with db_pool.acquire() as conn:
        hold_event = await conn.fetchrow(
            """
            SELECT case_reference, reason_code, approved_by, review_due_at
              FROM public.visa_decision_legal_hold_events
             WHERE decision_row_id = $1 AND event_type = 'LEGAL_HOLD_SET'
            """,
            decision["id"],
        )
    assert hold_event is not None
    assert hold_event["case_reference"] == "DSR-2026-001"
    assert hold_event["reason_code"] == "DSR-IDENTITY-VERIFICATION"
    assert hold_event["approved_by"] == "privacy.approver"
    assert hold_event["review_due_at"] == now + timedelta(days=29)
    with pytest.raises(asyncpg.RaiseError, match="blocked by active legal hold"):
        await retention.erase_decision_for_dsr(
            db_pool,
            decision_id=domain_decision_id,
            case_reference="DSR-2026-001",
            requested_by="privacy.operator",
        )
    assert await retention.set_decision_legal_hold(
        db_pool,
        decision_id=domain_decision_id,
        legal_hold=False,
        requested_by="privacy.operator",
        case_reference="DSR-2026-001",
        reason_code="DSR-RELEASE-AFTER-VERIFICATION",
        approved_by="privacy.approver",
        review_due_at=None,
    )
    assert (
        await retention.erase_decision_for_dsr(
            db_pool,
            decision_id=domain_decision_id,
            case_reference="DSR-2026-001",
            requested_by="privacy.operator",
        )
        == 1
    )
    assert (
        await retention.erase_decision_for_dsr(
            db_pool,
            decision_id=domain_decision_id,
            case_reference="DSR-2026-001",
            requested_by="privacy.operator",
        )
        == 0
    )

    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_decisions WHERE decision_id = $1",
                domain_decision_id,
            )
            == 0
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_decision_payloads WHERE decision_id = $1",
                decision["id"],
            )
            == 0
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM public.visa_evaluate_idempotency WHERE key_sha256 = $1",
                replay_key,
            )
            == 0
        )
        batch = await conn.fetchrow(
            """
            SELECT case_reference, decision_rows_deleted, payload_rows_deleted,
                   idempotency_rows_deleted
              FROM public.visa_decision_dsr_erasure_batches
            """
        )
        assert dict(batch) == {
            "case_reference": "DSR-2026-001",
            "decision_rows_deleted": 1,
            "payload_rows_deleted": 1,
            "idempotency_rows_deleted": 1,
        }
        with pytest.raises(asyncpg.RaiseError, match="is append-only"):
            await conn.execute(
                "UPDATE public.visa_decision_dsr_erasure_batches SET case_reference = 'tampered'"
            )


class _FutureNowDatetime(datetime):
    """``datetime.now()`` shifted +2s — cross-machine clock-skew guard.

    The activation's ``system_period`` lower bound is the DB SERVER's wall
    clock (Pro, via the test tunnel), while ``run_evaluation`` stamps
    ``observed_at`` from the TEST RUNNER's clock (Air-M5), which lags the
    Pro's by tens of ms — so migration 252's bitemporal binding trigger
    otherwise rejects the insert with ``observed_at ... is outside
    referenced activation ... system_period``. Mirrors ``test_shadow_match.
    py``'s own ``datetime.now(...) + timedelta(seconds=1)`` convention for
    the same trigger.
    """

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return datetime.now(tz) + timedelta(seconds=2)


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_worker_purge_has_no_traffic_dependency_and_reports_lag(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    now = datetime.now(timezone.utc)
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(seconds=1),
            idempotency_retention_interval=timedelta(seconds=1),
        )
    keyring = resolve_engine_hmac_keyring(Environment.TEST, now)
    for byte in (b"1", b"2"):
        await idempotency.reserve(
            db_pool,
            key_sha256=byte * 32,
            canonical_request=b'{"retention":"worker"}' + byte,
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
    await asyncio.sleep(1.3)

    evidence = await retention.idempotency_retention_evidence(db_pool)
    assert evidence.expired_rows == 2
    assert evidence.max_lag_seconds > 0
    assert evidence.observed_at.tzinfo is not None
    async with db_pool.acquire() as conn:
        with pytest.raises(
            asyncpg.RaiseError,
            match="idempotency delete must use a bounded retention capability",
        ):
            await conn.execute(
                "DELETE FROM public.visa_evaluate_idempotency WHERE key_sha256 = $1",
                b"1" * 32,
            )

    assert (
        await retention.purge_expired_idempotency(
            db_pool,
            limit=1,
            requested_by="x" * 128,
        )
        == 1
    )
    assert (await retention.idempotency_retention_evidence(db_pool)).expired_rows == 1
    assert (
        await retention.purge_expired_idempotency(
            db_pool,
            limit=1,
            requested_by="idempotency-worker-test",
        )
        == 1
    )
    assert (await retention.idempotency_retention_evidence(db_pool)).expired_rows == 0

    async with db_pool.acquire() as conn:
        session_user = await conn.fetchval("SELECT session_user")
        batches = await conn.fetch(
            """
            SELECT operation_type, expired_rows_before, max_lag_seconds_before,
                   deleted_count, executor_label
            FROM public.visa_idempotency_retention_batches
            ORDER BY id
            """
        )
        assert [row["operation_type"] for row in batches] == ["WORKER_PURGE", "WORKER_PURGE"]
        assert [row["expired_rows_before"] for row in batches] == [2, 1]
        assert all(row["max_lag_seconds_before"] > 0 for row in batches)
        assert [row["deleted_count"] for row in batches] == [1, 1]
        assert [row["executor_label"] for row in batches] == [
            f"{session_user}:{'x' * 128}",
            f"{session_user}:idempotency-worker-test",
        ]
        with pytest.raises(asyncpg.RaiseError, match="is append-only"):
            await conn.execute(
                "UPDATE public.visa_idempotency_retention_batches SET deleted_count = 9"
            )


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_store_replays_exact_response_and_conflicts_on_new_request(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    policy_id = await _insert_current_test_retention_policy(db_pool)
    key_sha256 = b"k" * 32
    canonical_request = b'{"request":"one"}'
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=key_sha256,
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    assert reservation.response is None
    response = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=reservation.reserved_at,
            code="EVALUATE_SURFACE_DISABLED",
        )
    )
    completed = await idempotency.complete(
        db_pool,
        reservation=reservation,
        response=response,
        response_signing_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    replay = await idempotency.reserve(
        db_pool,
        key_sha256=key_sha256,
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    assert replay.reserved_at == reservation.reserved_at
    assert replay.response == completed == response

    with pytest.raises(IdempotencyConflictError):
        await idempotency.reserve(
            db_pool,
            key_sha256=key_sha256,
            canonical_request=b'{"request":"different"}',
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT key_sha256, request_hmac, request_hmac_key_id,
                   response_body::text AS body,
                   response_hmac, response_hmac_key_id,
                   environment, retention_policy_id,
                   expires_at - created_at AS retention
            FROM visa_evaluate_idempotency
            WHERE key_sha256 = $1
            """,
            key_sha256,
        )
    assert row is not None
    assert bytes(row["key_sha256"]) == key_sha256
    assert len(bytes(row["request_hmac"])) == 32
    assert bytes(row["request_hmac"]) != canonical_request
    assert row["request_hmac_key_id"] == keyring.minting_key.kid
    assert len(bytes(row["response_hmac"])) == 32
    assert row["response_hmac_key_id"] == keyring.minting_key.kid
    assert row["environment"] == "TEST"
    assert row["retention_policy_id"] == policy_id
    assert "assessment_id" not in row["body"]
    assert row["retention"] == timedelta(hours=1)


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_tampered_stored_body_hash_fails_closed(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    idempotency_key = "tampered-replay"
    canonical_request = b'{"canonical":"tampered"}'
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=idempotency.hash_idempotency_key(idempotency_key),
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    valid_body = evaluate_path.build_temp_unavailable_body(
        now=reservation.reserved_at,
        code="RULE_PACK_UNAVAILABLE",
    )
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE visa_evaluate_idempotency
            SET response_body = $2::text::jsonb,
                response_sha256 = $3,
                response_hmac = $4,
                response_hmac_key_id = $5,
                completed_at = clock_timestamp()
            WHERE key_sha256 = $1
            """,
            reservation.key_sha256,
            json.dumps(valid_body),
            b"x" * 32,
            b"y" * 32,
            keyring.minting_key.kid,
        )

    request = VisaOracleEvaluateRequest.model_validate(
        _wire_payload(_facts_with_purposes(["TOURISM"]))
    )
    response = await evaluate_path.run_public_evaluation(
        db_pool,
        request=request,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-tampered-replay",
        canonical_request=canonical_request,
        idempotency_key=idempotency_key,
    )
    assert response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
    assert response.decision.outage is not None
    assert response.decision.outage.code == "IDEMPOTENCY_UNAVAILABLE"


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.parametrize("projection", ["source", "display"])
async def test_idempotency_projection_tamper_with_recomputed_sha_fails_response_hmac(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
    projection: str,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    response = await _supported_engine_response(monkeypatch)
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    assert response.decision.decision_integrity is not None
    assert response.decision.decision_integrity.key_id == keyring.minting_key.kid
    canonical_request = f'{{"projection":"{projection}"}}'.encode()
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=hashlib.sha256(canonical_request).digest(),
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    original_body = response.model_dump(mode="json")
    original_canonical = idempotency._canonical_response(original_body)
    original_response_hmac = idempotency._response_hmac(
        original_canonical,
        keyring.minting_key,
    )
    tampered_body = json.loads(json.dumps(original_body))
    if projection == "source":
        tampered_body["sources"][0]["title"] = "forged source title"
    else:
        tampered_body["display"]["candidates"][0]["name"]["en"] = "forged display name"
    tampered_canonical = idempotency._canonical_response(tampered_body)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE visa_evaluate_idempotency
            SET response_body = $2::text::jsonb,
                response_sha256 = $3,
                response_hmac = $4,
                response_hmac_key_id = $5,
                completed_at = clock_timestamp()
            WHERE key_sha256 = $1
            """,
            reservation.key_sha256,
            tampered_canonical.decode(),
            hashlib.sha256(tampered_canonical).digest(),
            original_response_hmac,
            keyring.minting_key.kid,
        )

    with pytest.raises(IdempotencyIntegrityError, match="authentication mismatch"):
        await idempotency.reserve(
            db_pool,
            key_sha256=reservation.key_sha256,
            canonical_request=canonical_request,
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_decision_tamper_fails_seal_even_with_recomputed_response_hmac(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    response = await _supported_engine_response(monkeypatch)
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    canonical_request = b'{"decision":"seal-tamper"}'
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=hashlib.sha256(canonical_request).digest(),
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    tampered_body = response.model_dump(mode="json")
    tampered_body["decision"]["trace_sha256"] = "0" * 64
    tampered_canonical = idempotency._canonical_response(tampered_body)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE visa_evaluate_idempotency
            SET response_body = $2::text::jsonb,
                response_sha256 = $3,
                response_hmac = $4,
                response_hmac_key_id = $5,
                completed_at = clock_timestamp()
            WHERE key_sha256 = $1
            """,
            reservation.key_sha256,
            tampered_canonical.decode(),
            hashlib.sha256(tampered_canonical).digest(),
            idempotency._response_hmac(tampered_canonical, keyring.minting_key),
            keyring.minting_key.kid,
        )

    with pytest.raises(IdempotencyIntegrityError, match="decision seal invalid"):
        await idempotency.reserve(
            db_pool,
            key_sha256=reservation.key_sha256,
            canonical_request=canonical_request,
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )


def _test_hmac_key(
    *,
    kid: str,
    secret_byte: bytes,
    now: datetime,
    valid_to: datetime | None = None,
    revoked_at: datetime | None = None,
) -> FactsFingerprintKey:
    return FactsFingerprintKey(
        kid=kid,
        secret=secret_byte * 32,
        environment=Environment.TEST,
        valid_from=now - timedelta(days=2),
        valid_to=valid_to,
        revoked_at=revoked_at,
    )


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_rotation_overlap_verifies_response_and_decision_with_old_key(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    now = datetime.now(timezone.utc)
    old_key = _test_hmac_key(
        kid="rotation-old",
        secret_byte=b"o",
        now=now,
        valid_to=now - timedelta(minutes=1),
    )
    new_key = _test_hmac_key(kid="rotation-new", secret_byte=b"n", now=now)
    response = await _supported_engine_response(monkeypatch)
    unsealed = response.decision.model_copy(update={"decision_integrity": None})
    rotated_response = VisaOracleEvaluateResponse.model_validate(
        response.model_copy(update={"decision": seal_decision(unsealed, key=old_key)}).model_dump(
            mode="json"
        )
    )
    canonical_request = b'{"rotation":"overlap"}'
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=hashlib.sha256(canonical_request).digest(),
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=new_key,
        verification_keys=(new_key, old_key),
    )
    completed = await idempotency.complete(
        db_pool,
        reservation=reservation,
        response=rotated_response,
        response_signing_key=old_key,
        verification_keys=(new_key, old_key),
    )
    replay = await idempotency.reserve(
        db_pool,
        key_sha256=reservation.key_sha256,
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=new_key,
        verification_keys=(new_key, old_key),
    )
    assert replay.response == completed == rotated_response
    usage = await retention.idempotency_key_usage_evidence(db_pool)
    assert {(row.key_purpose, row.key_id, row.active_rows, row.latest_expiry) for row in usage} == {
        ("REQUEST_HMAC", new_key.kid, 1, reservation.expires_at),
        ("RESPONSE_HMAC", old_key.kid, 1, reservation.expires_at),
        ("DECISION_INTEGRITY_HMAC", old_key.kid, 1, reservation.expires_at),
    }
    assert all(row.observed_at.tzinfo is not None for row in usage)


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.parametrize("key_state", ["missing", "revoked"])
async def test_idempotency_missing_or_revoked_response_key_fails_closed(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
    key_state: str,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    now = datetime.now(timezone.utc)
    old_key = _test_hmac_key(kid="retained-old", secret_byte=b"r", now=now)
    new_key = _test_hmac_key(kid="minting-new", secret_byte=b"m", now=now)
    response = await _supported_engine_response(monkeypatch)
    unsealed = response.decision.model_copy(update={"decision_integrity": None})
    old_response = VisaOracleEvaluateResponse.model_validate(
        response.model_copy(update={"decision": seal_decision(unsealed, key=old_key)}).model_dump(
            mode="json"
        )
    )
    canonical_request = f'{{"key_state":"{key_state}"}}'.encode()
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=hashlib.sha256(canonical_request).digest(),
        canonical_request=canonical_request,
        environment="TEST",
        minting_key=new_key,
        verification_keys=(new_key, old_key),
    )
    await idempotency.complete(
        db_pool,
        reservation=reservation,
        response=old_response,
        response_signing_key=old_key,
        verification_keys=(new_key, old_key),
    )
    replay_keys = (new_key,)
    if key_state == "revoked":
        replay_keys = (
            new_key,
            _test_hmac_key(
                kid=old_key.kid,
                secret_byte=b"r",
                now=now,
                revoked_at=now - timedelta(seconds=1),
            ),
        )
    with pytest.raises(IdempotencyIntegrityError, match="authentication mismatch"):
        await idempotency.reserve(
            db_pool,
            key_sha256=reservation.key_sha256,
            canonical_request=canonical_request,
            environment="TEST",
            minting_key=new_key,
            verification_keys=replay_keys,
        )


@pytest.mark.integration
@pytest.mark.database
async def test_response_hmac_and_retention_migrations_refuse_legacy_replay_binding(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    forward_263, rollback_263 = _read_migration(263, "visa_evaluate_response_hmac")
    forward_264, rollback_264 = _read_migration(264, "visa_decision_retention_policy")
    now = datetime.now(timezone.utc)
    keyring = resolve_engine_hmac_keyring(Environment.TEST, now)
    canonical_request = b'{"legacy":"bound-request"}'
    key_sha256 = b"l" * 32
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_264)
        await conn.execute(rollback_263)
        legacy = await conn.fetchrow(
            """
            INSERT INTO visa_evaluate_idempotency (
                key_sha256, request_hmac, request_hmac_key_id,
                response_body, response_sha256, completed_at
            ) VALUES ($1, $2, $3, '{}'::jsonb, $4, clock_timestamp())
            RETURNING reserved_at, expires_at
            """,
            key_sha256,
            idempotency._request_hmac(canonical_request, keyring.minting_key),
            keyring.minting_key.kid,
            hashlib.sha256(b"{}").digest(),
        )
        assert legacy is not None
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM visa_evaluate_idempotency WHERE response_body IS NOT NULL"
            )
            == 1
        )
        await conn.execute(forward_263)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM visa_evaluate_idempotency WHERE response_body IS NOT NULL"
            )
            == 0
        )
        await conn.execute(forward_264)
        await _insert_retention_policy(
            conn,
            effective_from=now - timedelta(days=1),
            retention_interval=timedelta(days=1),
            idempotency_retention_interval=timedelta(hours=1),
        )
        preserved = await conn.fetchrow(
            """
            SELECT reserved_at, expires_at, response_body, response_hmac,
                   environment, retention_policy_id
            FROM visa_evaluate_idempotency
            WHERE key_sha256 = $1
            """,
            key_sha256,
        )
    assert preserved is not None
    assert preserved["reserved_at"] == legacy["reserved_at"]
    assert preserved["expires_at"] == legacy["expires_at"]
    assert preserved["response_body"] is None
    assert preserved["response_hmac"] is None
    assert preserved["environment"] is None
    assert preserved["retention_policy_id"] is None

    with pytest.raises(
        IdempotencyIntegrityError,
        match="legacy idempotency reservation has no Zero-approved retention binding",
    ):
        await idempotency.reserve(
            db_pool,
            key_sha256=key_sha256,
            canonical_request=canonical_request,
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
    with pytest.raises(
        IdempotencyIntegrityError,
        match="legacy idempotency reservation has no Zero-approved retention binding",
    ):
        await idempotency.reserve(
            db_pool,
            key_sha256=key_sha256,
            canonical_request=b'{"legacy":"different-request"}',
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_valid_first_envelope_wins_over_different_completion(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    reservation = await idempotency.reserve(
        db_pool,
        key_sha256=b"v" * 32,
        canonical_request=b'{"canonical":"winner"}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    winner = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=reservation.reserved_at,
            code="FIRST_ENVELOPE",
        )
    )
    loser = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=reservation.reserved_at,
            code="DIFFERENT_VALID_ENVELOPE",
        )
    )
    assert (
        await idempotency.complete(
            db_pool,
            reservation=reservation,
            response=winner,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
        == winner
    )
    with caplog.at_level(logging.WARNING, logger="backend.services.visa_engine.idempotency"):
        replay = await idempotency.complete(
            db_pool,
            reservation=reservation,
            response=loser,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
    assert replay == winner
    assert "deterministic mismatch" in caplog.text


@pytest.mark.integration
@pytest.mark.database
async def test_concurrent_same_idempotency_key_shares_clock_and_one_response(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))

    async def _reserve() -> IdempotencyReservation:
        return await idempotency.reserve(
            db_pool,
            key_sha256=b"c" * 32,
            canonical_request=b'{"canonical":"concurrent"}',
            environment="TEST",
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )

    first, second = await asyncio.gather(_reserve(), _reserve())
    assert first.reserved_at == second.reserved_at
    assert first.request_hmac == second.request_hmac
    response = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=first.reserved_at,
            code="CONCURRENT_WINNER",
        )
    )
    completed = await asyncio.gather(
        idempotency.complete(
            db_pool,
            reservation=first,
            response=response,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        ),
        idempotency.complete(
            db_pool,
            reservation=second,
            response=response,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        ),
    )
    assert completed == [response, response]
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM visa_evaluate_idempotency WHERE key_sha256 = $1",
            first.key_sha256,
        )
    assert count == 1


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_retention_forbids_early_delete_and_reclaims_expired_key(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            retention_interval=timedelta(seconds=1),
            idempotency_retention_interval=timedelta(seconds=1),
        )
    active_key = b"a" * 32
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    await idempotency.reserve(
        db_pool,
        key_sha256=active_key,
        canonical_request=b'{"active":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    async with db_pool.acquire() as conn:
        with pytest.raises(asyncpg.PostgresError, match="bounded retention capability"):
            await conn.execute(
                "DELETE FROM visa_evaluate_idempotency WHERE key_sha256 = $1",
                active_key,
            )

    expired_key = b"e" * 32
    abandoned_key = b"z" * 32
    expired_reservation = await idempotency.reserve(
        db_pool,
        key_sha256=expired_key,
        canonical_request=b'{"old":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    await idempotency.reserve(
        db_pool,
        key_sha256=abandoned_key,
        canonical_request=b'{"abandoned":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    await asyncio.sleep(1.3)
    await idempotency.reserve(
        db_pool,
        key_sha256=b"s" * 32,
        canonical_request=b'{"sweep":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    async with db_pool.acquire() as conn:
        expired_count = await conn.fetchval(
            """
            SELECT count(*) FROM visa_evaluate_idempotency
            WHERE key_sha256 = ANY($1::bytea[])
            """,
            [expired_key, abandoned_key],
        )
    assert expired_count == 0

    reclaimed = await idempotency.reserve(
        db_pool,
        key_sha256=expired_key,
        canonical_request=b'{"new":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    assert reclaimed.request_hmac != expired_reservation.request_hmac
    assert reclaimed.response is None


@pytest.mark.integration
@pytest.mark.database
async def test_idempotency_reclaims_requested_expired_key_before_bounded_sweep(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            retention_interval=timedelta(seconds=2),
            idempotency_retention_interval=timedelta(seconds=1),
        )
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    requested_key = b"t" * 32
    decoy_rows = [
        (index.to_bytes(32, "big"), b"d" * 32, keyring.minting_key.kid) for index in range(1, 130)
    ]
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO visa_evaluate_idempotency (
                key_sha256, request_hmac, request_hmac_key_id, environment
            )
            SELECT key_sha256, request_hmac, request_hmac_key_id, 'TEST'
            FROM unnest($1::bytea[], $2::bytea[], $3::text[])
                AS rows(key_sha256, request_hmac, request_hmac_key_id)
            """,
            [row[0] for row in decoy_rows],
            [row[1] for row in decoy_rows],
            [row[2] for row in decoy_rows],
        )
        await conn.execute(
            """
            INSERT INTO visa_evaluate_idempotency (
                key_sha256, request_hmac, request_hmac_key_id, environment
            ) VALUES (
                $1, $2, $3, 'TEST'
            )
            """,
            requested_key,
            b"o" * 32,
            keyring.minting_key.kid,
        )
    await asyncio.sleep(1.2)

    reclaimed = await idempotency.reserve(
        db_pool,
        key_sha256=requested_key,
        canonical_request=b'{"after_expiry":true}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )

    assert reclaimed.request_hmac != b"o" * 32
    assert reclaimed.response is None
    async with db_pool.acquire() as conn:
        remaining_decoys = await conn.fetchval(
            """
            SELECT count(*)
            FROM visa_evaluate_idempotency
            WHERE key_sha256 = ANY($1::bytea[])
            """,
            [row[0] for row in decoy_rows],
        )
    assert remaining_decoys == 2


@pytest.mark.integration
@pytest.mark.database
async def test_expired_idempotency_completer_cannot_write_reclaimed_binding(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
) -> None:
    async with db_pool.acquire() as conn:
        await _insert_retention_policy(
            conn,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
            retention_interval=timedelta(seconds=1),
            idempotency_retention_interval=timedelta(seconds=1),
        )
    keyring = resolve_engine_hmac_keyring(Environment.TEST, datetime.now(timezone.utc))
    key_sha256 = b"r" * 32
    old_reservation = await idempotency.reserve(
        db_pool,
        key_sha256=key_sha256,
        canonical_request=b'{"binding":"old"}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    await asyncio.sleep(1.3)

    new_reservation = await idempotency.reserve(
        db_pool,
        key_sha256=key_sha256,
        canonical_request=b'{"binding":"new"}',
        environment="TEST",
        minting_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    assert new_reservation.request_hmac != old_reservation.request_hmac
    assert new_reservation.reserved_at != old_reservation.reserved_at

    stale_response = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=old_reservation.reserved_at,
            code="STALE_COMPLETER",
        )
    )
    with pytest.raises(IdempotencyConflictError, match="changed request binding"):
        await idempotency.complete(
            db_pool,
            reservation=old_reservation,
            response=stale_response,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )

    async with db_pool.acquire() as conn:
        current = await conn.fetchrow(
            """
            SELECT request_hmac, reserved_at, response_body
            FROM visa_evaluate_idempotency
            WHERE key_sha256 = $1
            """,
            key_sha256,
        )
    assert current is not None
    assert bytes(current["request_hmac"]) == new_reservation.request_hmac
    assert current["reserved_at"] == new_reservation.reserved_at
    assert current["response_body"] is None

    current_response = VisaOracleEvaluateResponse.model_validate(
        evaluate_path.build_temp_unavailable_body(
            now=new_reservation.reserved_at,
            code="CURRENT_COMPLETER",
        )
    )
    completed = await idempotency.complete(
        db_pool,
        reservation=new_reservation,
        response=current_response,
        response_signing_key=keyring.minting_key,
        verification_keys=keyring.verification_keys,
    )
    assert completed.decision.outage is not None
    assert completed.decision.outage.code == "CURRENT_COMPLETER"


@pytest.mark.integration
@pytest.mark.database
async def test_public_evaluation_same_key_runs_once_and_replays_stored_envelope(
    db_pool: asyncpg.Pool,
    evaluate_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_current_test_retention_policy(db_pool)
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    calls: list[datetime] = []

    async def _frozen_temp(*args: object, **kwargs: object) -> dict:
        evaluation_time = kwargs["evaluation_time"]
        assert isinstance(evaluation_time, datetime)
        calls.append(evaluation_time)
        return evaluate_path.build_temp_unavailable_body(
            now=evaluation_time,
            code="RULE_PACK_UNAVAILABLE",
        )

    monkeypatch.setattr(evaluate_path, "run_evaluation", _frozen_temp)
    request = VisaOracleEvaluateRequest.model_validate(
        _wire_payload(_facts_with_purposes(["TOURISM"]))
    )
    canonical_request = b'{"canonical":"request"}'
    kwargs = {
        "request": request,
        "traffic_source": "real",
        "request_category_hint": None,
        "request_trace": "trace-idempotent",
        "canonical_request": canonical_request,
        "idempotency_key": "request-run-once",
    }
    first = await evaluate_path.run_public_evaluation(db_pool, **kwargs)
    second = await evaluate_path.run_public_evaluation(db_pool, **kwargs)
    assert first == second
    assert len(calls) == 1

    with pytest.raises(IdempotencyConflictError):
        await evaluate_path.run_public_evaluation(
            db_pool,
            **{**kwargs, "canonical_request": b'{"canonical":"different"}'},
        )


def _patch_binding_to_db_pack(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rule_pack_db_id: uuid.UUID,
    activation_id: uuid.UUID,
    raw: dict,
    pack_model: RulePack,
    compiled: object,
) -> None:
    async def _fake_binding(
        pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
    ):
        return shadow._PackBinding(
            rule_pack_id=rule_pack_db_id,
            ruleset_activation_id=activation_id,
            environment="TEST",
            raw_envelope=raw,
        )

    def _fake_verify(
        raw_envelope: object,
        *,
        trust_store: object,
        observed_at: datetime,
        allow_unsigned: bool = False,
    ):
        return VerifiedRulePack(
            pack=pack_model,
            canonical_payload=b"",
            payload_sha256=b"\x00" * 32,
            unsigned_dev=False,
        )

    def _fake_compile(rule_pack: object, *, fact_registry: object = None):
        return compiled

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _fake_binding)
    monkeypatch.setattr(evaluate_path, "verify_rule_pack", _fake_verify)
    monkeypatch.setattr(evaluate_path, "build_compiled_pack", _fake_compile)
    monkeypatch.setattr(evaluate_path, "datetime", _FutureNowDatetime)
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")


@pytest.mark.integration
@pytest.mark.database
async def test_evaluate_persists_full_fat_row_and_collector_reads_it(
    db_pool: asyncpg.Pool, evaluate_schema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance loop, end to end: one evaluation -> one visa_decisions
    row carrying traffic_source + request_category + full summaries -> the
    collector reads it back as RECOMMEND-surface G-a-vol evidence."""
    await _insert_current_test_retention_policy(db_pool)
    compiled = gold_loader.load_and_compile_rule_pack()
    raw = gold_loader.load_rule_pack_raw()
    pack_model = RulePack.model_validate(raw)

    kwargs = _seed_gold_rule_pack_row(raw=raw, signature_seed=b"evaluate-path-writer-test")
    rule_pack_db_id = kwargs["id"]
    repo = VisaEngineRepository(db_pool)
    await repo.insert_rule_pack(**kwargs)
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=rule_pack_db_id,
        activated_by="evaluate-path-test",
        activation_reason="evaluate-path-writer",
    )
    _patch_binding_to_db_pack(
        monkeypatch,
        rule_pack_db_id=rule_pack_db_id,
        activation_id=activation_id,
        raw=raw,
        pack_model=pack_model,
        compiled=compiled,
    )

    facts = shadow.build_shadow_facts(
        nationality="US",
        purpose=Purpose.LONG_TOURISM,
        duration_months=2,
        match_hash="evaluate-db-hash",
    )
    assert facts is not None
    body = await evaluate_path.run_evaluation(
        db_pool,
        facts=facts,
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-db",
    )
    assert body["mode"] == "CURATED"
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM visa_decisions")
    assert len(rows) == 1
    row = rows[0]
    assert row["engine_surface"] == "RECOMMEND"
    assert row["engine_mode"] == "SHADOW"
    assert row["environment"] == "TEST"
    assert row["traffic_source"] == "real"
    assert row["request_category"] == "long_tourism"
    assert row["ruleset_activation_id"] == activation_id
    assert row["rule_pack_id"] == rule_pack_db_id
    assert row["engine_version"] == shadow.ENGINE_VERSION
    assert row["request_fingerprint"] == bytes.fromhex(
        body["decision"]["facts_fingerprint"]["digest"]
    )
    assert row["trace_sha256"] == bytes.fromhex(body["decision"]["trace_sha256"])
    assert row["decision_hmac"] == bytes.fromhex(body["decision"]["decision_integrity"]["digest"])
    assert row["decision_hmac_key_id"] == body["decision"]["decision_integrity"]["key_id"]
    decision = VisaOracleEvaluateResponse.model_validate(body).decision
    request_fingerprint = bytes.fromhex(body["decision"]["facts_fingerprint"]["digest"])

    writer_kwargs = {
        "decision": decision,
        "rule_pack_db_id": rule_pack_db_id,
        "ruleset_activation_id": activation_id,
        "environment": "TEST",
        "engine_mode": EngineMode.SHADOW,
        "request_fingerprint": request_fingerprint,
        "request_category": "long_tourism",
        "traffic_source": "real",
    }
    await asyncio.gather(
        evaluate_path._save_evaluate_decision(db_pool, **writer_kwargs),
        evaluate_path._save_evaluate_decision(db_pool, **writer_kwargs),
    )
    async with db_pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM visa_decisions WHERE decision_id = $1",
                decision.decision_id,
            )
            == 1
        )
    with pytest.raises(RuntimeError, match="incompatible"):
        await evaluate_path._save_evaluate_decision(
            db_pool,
            **{**writer_kwargs, "request_fingerprint": b"x" * 32},
        )

    grounding = json.loads(row["grounding_summary"])
    assert grounding[0]["claim_kind"] == "VERDICT"
    assert grounding[0]["claim_code"] == body["decision"]["state"]

    now = datetime.now(timezone.utc)
    report = await collect_shadow_evidence(
        db_pool,
        window_start=now - timedelta(hours=1),
        window_end=now + timedelta(hours=1),
        environment="TEST",
    )
    assert report["gates"]["G-a-vol"]["total_audit_rows"] == 1
    assert report["gates"]["G-a-vol"]["distinct_requests"] == 1
    assert report["surfaces"] == {"RECOMMEND": 1}
    assert report["traffic_source"] == {
        "real": 1,
        "synthetic_gold": 0,
        "synthetic_driver": 0,
        "legacy": 0,
        "total_audit_rows": 1,
    }


@pytest.mark.integration
@pytest.mark.database
async def test_evaluate_writes_business_category_end_to_end(
    db_pool: asyncpg.Pool, evaluate_schema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A BUSINESS_MEETINGS evaluation derives request_category='business' and
    the migration-257 CHECK accepts the row the endpoint writes."""
    await _insert_current_test_retention_policy(db_pool)
    compiled = gold_loader.load_and_compile_rule_pack()
    raw = gold_loader.load_rule_pack_raw()
    pack_model = RulePack.model_validate(raw)

    kwargs = _seed_gold_rule_pack_row(raw=raw, signature_seed=b"evaluate-path-business-test")
    rule_pack_db_id = kwargs["id"]
    repo = VisaEngineRepository(db_pool)
    await repo.insert_rule_pack(**kwargs)
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=rule_pack_db_id,
        activated_by="evaluate-path-test",
        activation_reason="evaluate-path-business",
    )
    _patch_binding_to_db_pack(
        monkeypatch,
        rule_pack_db_id=rule_pack_db_id,
        activation_id=activation_id,
        raw=raw,
        pack_model=pack_model,
        compiled=compiled,
    )

    body = await evaluate_path.run_evaluation(
        db_pool,
        facts=_facts_with_purposes(["BUSINESS_MEETINGS"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-db-business",
    )
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"

    async with db_pool.acquire() as conn:
        category = await conn.fetchval("SELECT request_category FROM visa_decisions")
    assert category == "business"


@pytest.mark.integration
@pytest.mark.database
async def test_no_active_pack_persists_nothing(
    db_pool: asyncpg.Pool, evaluate_schema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-closed against the REAL binding resolver: an empty schema yields
    the TEMP shape and zero rows — the W1 acceptance criterion verbatim."""
    await _insert_current_test_retention_policy(db_pool)
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.EVALUATE_ENVIRONMENT_ENV, "TEST")

    body = await evaluate_path.run_evaluation(
        db_pool,
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-db-nopack",
    )
    assert body["decision"]["outage"] == {"code": "RULE_PACK_UNAVAILABLE", "retryable": True}
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM visa_decisions")
    assert count == 0
