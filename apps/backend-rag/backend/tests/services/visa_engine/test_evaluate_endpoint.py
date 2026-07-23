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

from backend.app.auth.public_endpoints import find_entry, is_public_path
from backend.app.routers import visa_oracle_evaluate
from backend.app.setup.router_manifest import _API, ROUTER_MANIFEST
from backend.db.migration_base import split_migration_sql
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine import evaluate_path, shadow
from backend.services.visa_engine.bundle import VerifiedRulePack
from backend.services.visa_engine.enums import VisaPurpose
from backend.services.visa_engine.models import ApplicantFacts, RulePack
from backend.services.visa_engine.repository import VisaEngineRepository
from backend.services.visa_engine.shadow_evidence import collect_shadow_evidence
from backend.tests.security.test_mutating_routes_are_gated import (
    INTENTIONALLY_PUBLIC_MUTATIONS,
)
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader
from backend.tests.services.visa_engine.test_shadow_match import _seed_gold_rule_pack_row

pytestmark = pytest.mark.asyncio


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

    def test_enforce_is_true_and_warns_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
        monkeypatch.setattr(evaluate_path, "_enforce_not_implemented_warned", False)
        with caplog.at_level(logging.WARNING, logger="backend.services.visa_engine.evaluate_path"):
            assert evaluate_path.resolve_evaluate_shadow_enabled() is True
            assert evaluate_path.resolve_evaluate_shadow_enabled() is True
        warnings = [r for r in caplog.records if "enforcement is not implemented" in r.getMessage()]
        assert len(warnings) == 1


class TestResolveResponseMode:
    @pytest.mark.parametrize("value", [None, "OFF", "SHADOW", "ENFORCE", "BOGUS"])
    def test_never_returns_engine(self, value: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
        """The placeholder resolver defaults CURATED under EVERY flag value —
        the ENFORCE response-flip is a separate gate and this lane must never
        hardcode ENGINE."""
        if value is None:
            monkeypatch.delenv(evaluate_path.EVALUATE_MODE_ENV, raising=False)
        else:
            monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, value)
        assert evaluate_path.resolve_response_mode() == "CURATED"


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

    def test_hint_wins_over_derivation(self) -> None:
        facts = _facts_with_purposes(["TOURISM"])
        assert evaluate_path.derive_request_category(facts, "diaspora") == "diaspora"
        assert evaluate_path.derive_request_category(facts, "business") == "business"

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


# ---------------------------------------------------------------------------
# §4 — HTTP request-shape validation (bare app, no engine involvement)
# ---------------------------------------------------------------------------


async def test_wrong_content_type_is_415() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate",
            content=b"{}",
            headers={"content-type": "text/plain"},
        )
    assert response.status_code == 415


async def test_oversize_body_is_413() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate",
            content=b"x" * (visa_oracle_evaluate.MAX_EVALUATE_BODY_BYTES + 1),
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413


async def test_invalid_json_is_400() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 400


async def test_missing_top_level_keys_is_422() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post("/api/visa-oracle/evaluate", json={})
    assert response.status_code == 422


async def test_extra_top_level_key_is_422() -> None:
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["bogus"] = 1
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post("/api/visa-oracle/evaluate", json=payload)
    assert response.status_code == 422


async def test_invalid_fact_value_is_422_and_never_echoes_input() -> None:
    """PII boundary on the error path: the 422 carries loc/type/msg only —
    the offending input value itself must not appear anywhere in the body."""
    payload = _wire_payload(_facts_with_purposes(["TOURISM"]))
    payload["facts"]["intent.stay_days"] = {"status": "KNOWN", "value": -54321}
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post("/api/visa-oracle/evaluate", json=payload)
    assert response.status_code == 422
    assert "-54321" not in response.text


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
        response = await client.post("/api/visa-oracle/evaluate", json=payload)
    assert response.status_code == 200
    assert response.json()["decision"]["state"] == "TEMPORARILY_UNAVAILABLE"


async def test_bogus_traffic_source_param_is_422() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=bogus",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 422


async def test_bogus_request_category_param_is_422() -> None:
    async with _client(_build_app(_UntouchedPool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?request_category=bogus",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# §5 — synthetic self-label gate (HTTP; validation order is mode-independent)
# ---------------------------------------------------------------------------


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
            rule_pack_id=uuid.uuid4(),
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
            payload_sha256=b"\x00" * 32,
            unsigned_dev=False,
        )

    def _fake_compile(rule_pack: object, *, fact_registry: object = None):
        return compiled

    save_calls: list[dict] = []

    async def _recording_save(pool: object, **kwargs: object) -> None:
        save_calls.append(kwargs)

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _fake_binding)
    monkeypatch.setattr(evaluate_path, "verify_rule_pack", _fake_verify)
    monkeypatch.setattr(evaluate_path, "build_compiled_pack", _fake_compile)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _recording_save)
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")
    return save_calls, pack_model, compiled


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

    monkeypatch.setattr(evaluate_path, "_resolve_active_pack_binding", _no_binding)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _recording_save)

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
            "/api/visa-oracle/evaluate",
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
            "timeline",
            "requirements",
            "checklist",
        }
        assert set(entry["name"]) == {"id", "en"}

    assert len(save_calls) == 1
    saved = save_calls[0]
    assert saved["traffic_source"] == "real"
    assert saved["request_category"] == "long_tourism"
    assert saved["request_fingerprint"] == bytes.fromhex(digest)
    assert str(saved["decision"].decision_id) == body["decision"]["decision_id"]


async def test_enforce_mode_still_curated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with VISA_ENGINE_EVALUATE_MODE=ENFORCE the response mode stays
    CURATED (the flip is a separate gate) — evaluation and persistence still
    run with SHADOW semantics."""
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "ENFORCE")
    monkeypatch.setattr(evaluate_path, "_enforce_not_implemented_warned", False)
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    body = await evaluate_path.run_evaluation(
        object(),
        facts=_facts_with_purposes(["TOURISM"]),
        traffic_source="real",
        request_category_hint=None,
        request_trace="trace-enforce",
    )
    assert body["mode"] == "CURATED"
    assert body["decision"]["state"] != "TEMPORARILY_UNAVAILABLE"
    assert len(save_calls) == 1


async def test_allowlisted_synthetic_label_is_accepted_and_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?traffic_source=synthetic_gold",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 200
    assert len(save_calls) == 1
    assert save_calls[0]["traffic_source"] == "synthetic_gold"


async def test_request_category_hint_overrides_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
    save_calls, _, _ = _patch_engine_chain(monkeypatch)

    class _FakePool:
        def acquire(self) -> None:  # pragma: no cover - never reached (writer is faked)
            raise AssertionError("unexpected pool use")

    async with _client(_build_app(_FakePool())) as client:
        response = await client.post(
            "/api/visa-oracle/evaluate?request_category=diaspora",
            json=_wire_payload(_facts_with_purposes(["TOURISM"])),
        )
    assert response.status_code == 200
    assert save_calls[0]["request_category"] == "diaspora"


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


# ---------------------------------------------------------------------------
# §8 — DB integration: the real write path (migrations 252+255+256+257).
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
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)
        await conn.execute(forward_252)
        await conn.execute(forward_255)
        await conn.execute(forward_256)
        await conn.execute(forward_257)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_256)
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(rollback_257)


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
