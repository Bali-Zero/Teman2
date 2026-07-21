"""Tests for STEP-6c SHADOW wiring (``services/visa_engine/shadow.py``).

Design: ``research/visa/2026-07-20-step6c-shadow-wiring-design.md`` §4.

Two tiers:

* **Unit** (no DB): ``resolve_match_shadow_enabled``, ``build_shadow_facts``,
  and ``_shadow_evaluate_match``'s two silent-no-op paths (no active pack /
  a PRODUCTION pack hitting the STEP-6d placeholder-identity fail-closed
  guard) — the latter two are pure-Python once the resolver/verify/compile
  chain is monkeypatched, so a real Postgres connection is never touched
  (proved with an inert ``object()`` sentinel standing in for ``db_pool``).
  ``maybe_spawn_shadow_match``'s gating (spawns iff enabled; never raises)
  is also unit-level via a monkeypatched ``spawn``.
* **Integration** (real Postgres, ``conftest.py``'s ``db_pool``/``visa_schema``
  fixtures + this file's own ``shadow_schema`` fixture layering migration
  252 on top): the resolver against real ``visa_rule_packs``/
  ``visa_ruleset_activations`` rows, the writer (``_save_shadow_decision``)
  against a real gold-pack-derived ``Decision``, and the full chain
  (``maybe_spawn_shadow_match`` -> ``spawn`` -> ``_shadow_evaluate_match``)
  with the crypto verify/compile steps monkeypatched to the real gold
  ``CompiledRulePack`` (STEP-6c's own tests never need a genuinely
  Ed25519-signed envelope — that is ``bundle.py``'s own test surface).

No test ever asserts against, or logs, raw nationality/purpose/duration
values in ANY log capture — matching ``shadow.py``'s own PII-boundary
contract (SYMBIOSIS Law 2).
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
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.common import background as background_module
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine import evaluator, shadow
from backend.services.visa_engine.bundle import VerifiedRulePack
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import UnknownReason, VisaPurpose
from backend.services.visa_engine.models import RulePack
from backend.services.visa_engine.repository import VisaEngineRepository
from backend.tests.services.visa_engine import _builders as builders
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader
from backend.tests.services.visa_engine.test_repository import (
    _ENV,
    _insert_pack,
    _open_range,
    _pack_hash,
)

pytestmark = pytest.mark.asyncio

_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, _UTC_FMT).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# §1 — resolve_match_shadow_enabled (unit, no DB)
# ---------------------------------------------------------------------------


class TestResolveMatchShadowEnabled:
    def test_missing_env_defaults_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(shadow.MATCH_MODE_ENV, raising=False)
        assert shadow.resolve_match_shadow_enabled() is False

    def test_off_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "OFF")
        assert shadow.resolve_match_shadow_enabled() is False

    def test_invalid_value_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "BOGUS")
        assert shadow.resolve_match_shadow_enabled() is False

    def test_shadow_is_true_case_insensitive_and_trims_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "  shadow  ")
        assert shadow.resolve_match_shadow_enabled() is True

    def test_enforce_is_true_and_warns_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "ENFORCE")
        monkeypatch.setattr(shadow, "_enforce_not_implemented_warned", False)
        with caplog.at_level(logging.WARNING, logger="backend.services.visa_engine.shadow"):
            assert shadow.resolve_match_shadow_enabled() is True
            assert shadow.resolve_match_shadow_enabled() is True
        warnings = [r for r in caplog.records if "enforcement is not implemented" in r.getMessage()]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# §2 — build_shadow_facts (unit, no DB)
# ---------------------------------------------------------------------------


class TestBuildShadowFacts:
    @pytest.mark.parametrize(
        ("purpose", "expected"),
        [
            (Purpose.WORK_REMOTE, VisaPurpose.REMOTE_WORK),
            (Purpose.INVESTOR, VisaPurpose.INVESTMENT),
            (Purpose.WORK_EMPLOYEE, VisaPurpose.EMPLOYMENT),
            (Purpose.FAMILY, VisaPurpose.FAMILY),
            (Purpose.LONG_TOURISM, VisaPurpose.TOURISM),
            (Purpose.RETIREMENT, VisaPurpose.RETIREMENT),
            (Purpose.STUDENT, VisaPurpose.STUDY),
            (Purpose.OTHER, VisaPurpose.OTHER),
        ],
    )
    def test_purpose_remap(self, purpose: Purpose, expected: VisaPurpose) -> None:
        facts = shadow.build_shadow_facts(
            nationality="US", purpose=purpose, duration_months=6, match_hash="hash-purpose"
        )
        assert facts is not None
        intent_purposes = facts.facts.intent_purposes
        assert intent_purposes.status == "KNOWN"
        assert intent_purposes.value == (expected.value,)

    def test_every_purpose_member_is_remapped(self) -> None:
        assert set(Purpose) == set(shadow._PURPOSE_REMAP.keys())

    def test_duration_months_converted_to_days(self) -> None:
        facts = shadow.build_shadow_facts(
            nationality="US", purpose=Purpose.LONG_TOURISM, duration_months=4, match_hash="h1"
        )
        assert facts is not None
        assert facts.facts.intent_stay_days.status == "KNOWN"
        assert facts.facts.intent_stay_days.value == 120

    def test_nationality_alpha2_used_directly(self) -> None:
        facts = shadow.build_shadow_facts(
            nationality="us", purpose=Purpose.LONG_TOURISM, duration_months=1, match_hash="h2"
        )
        assert facts is not None
        nat = facts.facts.person_nationalities
        assert nat.status == "KNOWN"
        assert nat.value == ("US",)

    def test_nationality_alpha3_best_effort_mapped(self) -> None:
        facts = shadow.build_shadow_facts(
            nationality="usa", purpose=Purpose.LONG_TOURISM, duration_months=1, match_hash="h3"
        )
        assert facts is not None
        assert facts.facts.person_nationalities.value == ("US",)

    def test_nationality_unmappable_falls_back_to_unknown_not_provided(self) -> None:
        facts = shadow.build_shadow_facts(
            nationality="ZZZ", purpose=Purpose.LONG_TOURISM, duration_months=1, match_hash="h4"
        )
        assert facts is not None
        nat = facts.facts.person_nationalities
        assert nat.status == "UNKNOWN"
        assert nat.reason == UnknownReason.NOT_PROVIDED

    def test_assessment_id_is_deterministic_per_match_hash(self) -> None:
        f1 = shadow.build_shadow_facts(
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="stable-hash",
        )
        f2 = shadow.build_shadow_facts(
            nationality="GB", purpose=Purpose.STUDENT, duration_months=12, match_hash="stable-hash"
        )
        assert f1 is not None and f2 is not None
        assert f1.assessment_id == f2.assessment_id

    def test_different_match_hash_yields_different_assessment_id(self) -> None:
        f1 = shadow.build_shadow_facts(
            nationality="US", purpose=Purpose.LONG_TOURISM, duration_months=1, match_hash="hash-a"
        )
        f2 = shadow.build_shadow_facts(
            nationality="US", purpose=Purpose.LONG_TOURISM, duration_months=1, match_hash="hash-b"
        )
        assert f1 is not None and f2 is not None
        assert f1.assessment_id != f2.assessment_id

    def test_exactly_3_known_and_32_unknown_fields(self) -> None:
        facts = shadow.build_shadow_facts(
            nationality="US", purpose=Purpose.LONG_TOURISM, duration_months=2, match_hash="h5"
        )
        assert facts is not None
        statuses = [getattr(facts.facts, name).status for name in type(facts.facts).model_fields]
        assert len(statuses) == 35
        assert statuses.count("KNOWN") == 3
        assert statuses.count("UNKNOWN") == 32


# ---------------------------------------------------------------------------
# §3 — _shadow_evaluate_match silent-no-op paths (unit, no DB — db_pool is an
# inert sentinel on both paths below, proved by never dereferencing it before
# the early return).
# ---------------------------------------------------------------------------


class TestShadowEvaluateMatchNoopPaths:
    async def test_no_active_pack_is_a_silent_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_resolver(
            pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
        ):
            return None

        save_calls: list[object] = []

        async def _recording_save(pool: object, **kwargs: object) -> None:
            save_calls.append(kwargs)

        monkeypatch.setattr(shadow, "_resolve_active_pack_binding", _fake_resolver)
        monkeypatch.setattr(shadow, "_save_shadow_decision", _recording_save)

        await shadow._shadow_evaluate_match(
            object(),  # sentinel: never touched on this path
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="no-pack-hash",
        )
        # No active pack -> the writer is never reached (silent no-op), and
        # no exception propagated (reaching this assertion proves it).
        assert save_calls == []

    async def test_production_pack_placeholder_identity_is_a_silent_noop(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Valid ONLY when ``VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON`` is
        UNSET (STEP-6d): ``resolve_identity_provider()`` then returns the
        default placeholder, which still fail-closes on a PRODUCTION pack —
        see ``test_provisioned_prod_key_writes_a_real_shadow_row`` below for
        the sibling case where a PRODUCTION key IS provisioned and a row
        gets written instead."""
        monkeypatch.delenv("VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON", raising=False)
        src = builders.source_record()
        product_id = builders.new_uuid()
        prod = builders.product(source_id=src["source_record_id"], product_id=product_id)
        rule = builders.rule(
            rule_id="el.tiny.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_SUPPORTED",
                "covered_purposes": ["TOURISM"],
            },
            source_id=src["source_record_id"],
            required_facts=["intent.purposes"],
        )
        payload = builders.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[src], environment="PRODUCTION"
        )
        envelope = builders.rule_pack_envelope(payload)
        pack = RulePack.model_validate(envelope)
        compiled = build_compiled_pack(pack)

        async def _fake_resolver(
            pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
        ):
            return shadow._PackBinding(
                rule_pack_id=uuid.uuid4(),
                ruleset_activation_id=uuid.uuid4(),
                environment="PRODUCTION",
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
                pack=pack, canonical_payload=b"", payload_sha256=b"\x00" * 32, unsigned_dev=False
            )

        def _fake_compile(rule_pack: object, *, fact_registry: object = None):
            return compiled

        monkeypatch.setattr(shadow, "_resolve_active_pack_binding", _fake_resolver)
        monkeypatch.setattr(shadow, "verify_rule_pack", _fake_verify)
        monkeypatch.setattr(shadow, "build_compiled_pack", _fake_compile)
        monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")

        with caplog.at_level(logging.WARNING, logger="backend.services.visa_engine.shadow"):
            await shadow._shadow_evaluate_match(
                object(),  # sentinel: evaluate() raises before any DB write is attempted
                nationality="US",
                purpose=Purpose.LONG_TOURISM,
                duration_months=1,
                match_hash="prod-noop-hash",
            )

        assert any("STEP-6d" in r.getMessage() for r in caplog.records)

    async def test_provisioned_prod_key_writes_a_real_shadow_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sibling of the noop test above (STEP-6d): with a PRODUCTION
        facts-fingerprint key provisioned via
        ``VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON``, the same PRODUCTION pack
        no longer hits the placeholder fail-closed guard — the real
        crypto-backed identity provider succeeds and the SHADOW writer
        (``_save_shadow_decision``) IS invoked (still an audit-only SHADOW
        row, never rendered to any caller)."""
        import base64
        import json as json_module

        secret = base64.urlsafe_b64encode(b"\x00" * 32).rstrip(b"=").decode("ascii")
        monkeypatch.setenv(
            "VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON",
            json_module.dumps(
                [
                    {
                        "kid": "prod-key-1",
                        "secret": secret,
                        "environment": "PRODUCTION",
                        "valid_from": "2020-01-01T00:00:00+00:00",
                    }
                ]
            ),
        )

        src = builders.source_record()
        product_id = builders.new_uuid()
        prod = builders.product(source_id=src["source_record_id"], product_id=product_id)
        rule = builders.rule(
            rule_id="el.tiny.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_SUPPORTED",
                "covered_purposes": ["TOURISM"],
            },
            source_id=src["source_record_id"],
            required_facts=["intent.purposes"],
        )
        payload = builders.rule_pack_payload(
            rules=[rule], products=[prod], source_records=[src], environment="PRODUCTION"
        )
        envelope = builders.rule_pack_envelope(payload)
        pack = RulePack.model_validate(envelope)
        compiled = build_compiled_pack(pack)

        async def _fake_resolver(
            pool: object, *, environment: str, effective_at: datetime, observed_at: datetime
        ):
            return shadow._PackBinding(
                rule_pack_id=uuid.uuid4(),
                ruleset_activation_id=uuid.uuid4(),
                environment="PRODUCTION",
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
                pack=pack, canonical_payload=b"", payload_sha256=b"\x00" * 32, unsigned_dev=False
            )

        def _fake_compile(rule_pack: object, *, fact_registry: object = None):
            return compiled

        save_calls: list[object] = []

        async def _recording_save(pool: object, **kwargs: object) -> None:
            save_calls.append(kwargs)

        monkeypatch.setattr(shadow, "_resolve_active_pack_binding", _fake_resolver)
        monkeypatch.setattr(shadow, "verify_rule_pack", _fake_verify)
        monkeypatch.setattr(shadow, "build_compiled_pack", _fake_compile)
        monkeypatch.setattr(shadow, "_save_shadow_decision", _recording_save)
        monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")

        await shadow._shadow_evaluate_match(
            object(),  # sentinel: never dereferenced — _save_shadow_decision is monkeypatched
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="prod-provisioned-hash",
        )

        assert len(save_calls) == 1
        written_decision = save_calls[0]["decision"]
        assert written_decision.facts_fingerprint.key_id == "prod-key-1"


# ---------------------------------------------------------------------------
# §4 — maybe_spawn_shadow_match gating (unit, no DB — spawn is monkeypatched)
# ---------------------------------------------------------------------------


class TestMaybeSpawnShadowMatch:
    def test_disabled_does_not_spawn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(shadow.MATCH_MODE_ENV, raising=False)
        calls: list[object] = []
        monkeypatch.setattr(shadow, "spawn", lambda coro, **kw: calls.append(coro))
        shadow.maybe_spawn_shadow_match(
            object(),
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="disabled-hash",
        )
        assert calls == []

    def test_enabled_spawns_exactly_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "SHADOW")
        spawned_names: list[str | None] = []

        async def _stub_evaluate(*args: object, **kwargs: object) -> None:
            return None

        def _fake_spawn(coro: object, *, name: str | None = None) -> None:
            spawned_names.append(name)
            coro.close()  # never actually run — only scheduling intent is asserted here

        monkeypatch.setattr(shadow, "_shadow_evaluate_match", _stub_evaluate)
        monkeypatch.setattr(shadow, "spawn", _fake_spawn)

        shadow.maybe_spawn_shadow_match(
            object(),
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="enabled-hash",
        )
        trace = hashlib.sha256(b"enabled-hash").hexdigest()[:12]
        assert spawned_names == [f"shadow-match-{trace}"]

    def test_resolve_shadow_enabled_raising_never_propagates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom() -> bool:
            raise RuntimeError("boom")

        spawn_calls: list[object] = []
        monkeypatch.setattr(shadow, "resolve_match_shadow_enabled", _boom)
        monkeypatch.setattr(shadow, "spawn", lambda coro, **kw: spawn_calls.append(coro))
        shadow.maybe_spawn_shadow_match(
            object(),
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="boom-hash-1",
        )
        # The gate check raised, so spawn is never reached; reaching this
        # assertion proves the RuntimeError never propagated into the handler.
        assert spawn_calls == []

    def test_spawn_raising_never_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(shadow.MATCH_MODE_ENV, "SHADOW")

        async def _stub_evaluate(*args: object, **kwargs: object) -> None:
            return None

        spawn_calls: list[str | None] = []

        def _boom_spawn(coro: object, *, name: str | None = None) -> None:
            spawn_calls.append(name)
            coro.close()
            raise RuntimeError("spawn boom")

        monkeypatch.setattr(shadow, "_shadow_evaluate_match", _stub_evaluate)
        monkeypatch.setattr(shadow, "spawn", _boom_spawn)
        shadow.maybe_spawn_shadow_match(
            object(),
            nationality="US",
            purpose=Purpose.LONG_TOURISM,
            duration_months=1,
            match_hash="boom-hash-2",
        )
        # spawn WAS reached (the SHADOW gate opened) and its RuntimeError was
        # swallowed inside maybe_spawn; reaching this assertion proves it never
        # propagated into the request handler.
        trace = hashlib.sha256(b"boom-hash-2").hexdigest()[:12]
        assert spawn_calls == [f"shadow-match-{trace}"]


# ---------------------------------------------------------------------------
# §5 — integration fixtures: layer migrations 252+255 on conftest.py's own
# db_pool/visa_schema (250+251+253+254). Defensively rolls back 252 first
# (mirrors visa_schema's own rollback-then-forward convention) so this is
# correct whether or not the shared test DB already carries 252 from a prior
# full "apply-all" migration run — every statement in 252's rollback is
# ``IF EXISTS``. Torn down BEFORE visa_schema's own teardown (pytest tears
# fixtures down in reverse dependency order), which matters because
# visa_decisions FKs onto visa_rule_packs/visa_ruleset_activations.
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_MIGRATION_252_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "252_visa_engine_write_substrate.sql"
_MIGRATION_255_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "255_visa_shadow_evidence.sql"


def _read_migration_252() -> tuple[str, str]:
    sql = _MIGRATION_252_PATH.read_text(encoding="utf-8")
    forward, rollback = split_migration_sql(sql)
    assert rollback, "migration 252 must carry a '-- === ROLLBACK ===' section"
    return forward, rollback


def _read_migration_255() -> tuple[str, str]:
    sql = _MIGRATION_255_PATH.read_text(encoding="utf-8")
    forward, rollback = split_migration_sql(sql)
    assert rollback, "migration 255 must carry a '-- === ROLLBACK ===' section"
    return forward, rollback


@pytest_asyncio.fixture
async def shadow_schema(db_pool: asyncpg.Pool, visa_schema: None) -> AsyncIterator[None]:
    forward_252, rollback_252 = _read_migration_252()
    forward_255, rollback_255 = _read_migration_255()
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)
        await conn.execute(forward_252)
        await conn.execute(forward_255)
    yield
    async with db_pool.acquire() as conn:
        await conn.execute(rollback_255)
        await conn.execute(rollback_252)


def _seed_gold_rule_pack_row(*, raw: dict, signature_seed: bytes) -> dict:
    """Build the ``insert_rule_pack`` kwargs for the gold rule pack's own
    envelope — shared by the writer and full-chain integration tests below."""

    payload = raw["payload"]
    protected = raw["protected"]
    lower = _parse_utc(payload["valid_period"]["from"])
    upper = _parse_utc(payload["valid_period"]["to"]) if payload["valid_period"].get("to") else None
    legal_period = asyncpg.Range(lower, upper, lower_inc=True, upper_inc=False)
    return {
        "id": uuid.UUID(payload["rule_pack_id"]),
        "environment": payload["environment"],
        "sequence": payload["sequence"],
        "pack_version": payload["version"],
        "engine_contract_version": payload["engine_contract_version"],
        "engine_min_version": payload["engine_min_version"],
        "engine_max_version": payload["engine_max_version"],
        "legal_period": legal_period,
        "protected_header": protected,
        "payload": payload,
        "payload_sha256": bytes.fromhex(raw["payload_sha256"]),
        "previous_payload_sha256": None,
        "signature": hashlib.sha256(signature_seed).digest() * 2,
        "signing_key_id": protected["kid"],
        "signed_at": _parse_utc(protected["signed_at"]),
    }


# ---------------------------------------------------------------------------
# §6 — _resolve_active_pack_binding (integration: real visa_rule_packs /
# visa_ruleset_activations, no migration 252 needed).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.database
async def test_resolve_active_pack_binding_finds_active_pack_and_none_otherwise(
    repo: VisaEngineRepository, db_pool: asyncpg.Pool
) -> None:
    pack_id = uuid.uuid4()
    signed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    legal = _open_range(datetime(2026, 1, 1, tzinfo=timezone.utc))
    await _insert_pack(
        repo,
        pack_id=pack_id,
        sequence=1,
        legal_period=legal,
        kid="shadow-resolver-key",
        signed_at=signed_at,
        note="shadow-resolver-test",
        payload_sha256=_pack_hash(7),
        environment=_ENV,
    )
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=pack_id, activated_by="shadow-test", activation_reason="w6c-resolver-test"
    )

    effective_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    observed_at = datetime.now(timezone.utc) + timedelta(seconds=1)

    binding = await shadow._resolve_active_pack_binding(
        db_pool, environment=_ENV, effective_at=effective_at, observed_at=observed_at
    )
    assert binding is not None
    assert binding.rule_pack_id == pack_id
    assert binding.ruleset_activation_id == activation_id
    assert binding.environment == _ENV
    assert binding.raw_envelope["payload_sha256"] == _pack_hash(7).hex()
    assert binding.raw_envelope["canonicalization"] == "RFC8785"

    none_binding = await shadow._resolve_active_pack_binding(
        db_pool, environment="STAGING", effective_at=effective_at, observed_at=observed_at
    )
    assert none_binding is None


# ---------------------------------------------------------------------------
# §7 — _save_shadow_decision writer (integration: needs migration 252).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.database
async def test_save_shadow_decision_inserts_one_row_and_dedupes_on_conflict(
    db_pool: asyncpg.Pool, shadow_schema: None
) -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    raw = gold_loader.load_rule_pack_raw()
    persona = gold_loader.load_all_personas()[0]

    kwargs = _seed_gold_rule_pack_row(raw=raw, signature_seed=b"gold-harness-shadow-writer-test")
    rule_pack_db_id = kwargs["id"]
    repo = VisaEngineRepository(db_pool)
    await repo.insert_rule_pack(**kwargs)
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=rule_pack_db_id,
        activated_by="shadow-writer-test",
        activation_reason="shadow-evidence-writer",
    )
    observed_at = datetime.now(timezone.utc) + timedelta(seconds=1)

    decision = evaluator.evaluate(
        persona.facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=observed_at,
    )

    await shadow._save_shadow_decision(
        db_pool,
        decision=decision,
        rule_pack_db_id=rule_pack_db_id,
        ruleset_activation_id=activation_id,
        environment="TEST",
        request_fingerprint=shadow._request_fingerprint("writer-hash"),
        request_category=Purpose.OTHER,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM visa_decisions WHERE decision_id = $1", decision.decision_id
        )
    assert len(rows) == 1
    row = rows[0]
    assert row["engine_mode"] == "SHADOW"
    assert row["engine_surface"] == "MATCH"
    assert row["verdict"] == decision.state.value
    assert row["rule_pack_id"] == rule_pack_db_id
    assert row["ruleset_activation_id"] == activation_id
    assert row["engine_version"] == shadow.ENGINE_VERSION
    assert row["environment"] == "TEST"
    assert row["request_fingerprint"] == hashlib.sha256(b"writer-hash").digest()
    assert row["request_category"] == Purpose.OTHER.value
    candidate_summary = json.loads(row["candidate_summary"])
    grounding_summary = json.loads(row["grounding_summary"])
    citations = json.loads(row["citations"])
    assert isinstance(candidate_summary, list)
    assert grounding_summary[0]["claim_kind"] == "VERDICT"
    assert {item["source_record_id"] for item in citations} == set(
        grounding_summary[0]["source_record_ids"]
    )

    # Calling again with the SAME decision (same decision_id) is an
    # idempotent no-op — ON CONFLICT (decision_id) DO NOTHING.
    await shadow._save_shadow_decision(
        db_pool,
        decision=decision,
        rule_pack_db_id=rule_pack_db_id,
        ruleset_activation_id=activation_id,
        environment="TEST",
        request_fingerprint=shadow._request_fingerprint("writer-hash"),
        request_category=Purpose.OTHER,
    )
    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM visa_decisions WHERE decision_id = $1", decision.decision_id
        )
    assert count == 1


# ---------------------------------------------------------------------------
# §8 — full chain via maybe_spawn_shadow_match -> spawn -> _shadow_evaluate_match
# (integration: needs migration 252). Crypto verify/compile are monkeypatched
# to the real gold CompiledRulePack — this suite's own concern is the wiring,
# not re-proving bundle.py's cryptography (that is bundle.py's own test
# surface).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.database
async def test_shadow_match_end_to_end_via_maybe_spawn_writes_one_row(
    db_pool: asyncpg.Pool, shadow_schema: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    compiled = gold_loader.load_and_compile_rule_pack()
    raw = gold_loader.load_rule_pack_raw()
    pack_model = RulePack.model_validate(raw)

    kwargs = _seed_gold_rule_pack_row(raw=raw, signature_seed=b"gold-harness-shadow-flow-test")
    rule_pack_db_id = kwargs["id"]
    repo = VisaEngineRepository(db_pool)
    await repo.insert_rule_pack(**kwargs)
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=rule_pack_db_id,
        activated_by="shadow-flow-test",
        activation_reason="shadow-evidence-flow",
    )

    async def _fake_resolver(
        pool: asyncpg.Pool, *, environment: str, effective_at: datetime, observed_at: datetime
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
            pack=pack_model, canonical_payload=b"", payload_sha256=b"\x00" * 32, unsigned_dev=False
        )

    def _fake_compile(rule_pack: object, *, fact_registry: object = None):
        return compiled

    monkeypatch.setattr(shadow, "_resolve_active_pack_binding", _fake_resolver)
    monkeypatch.setattr(shadow, "verify_rule_pack", _fake_verify)
    monkeypatch.setattr(shadow, "build_compiled_pack", _fake_compile)
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", "[]")
    monkeypatch.setenv(shadow.MATCH_MODE_ENV, "SHADOW")
    monkeypatch.setenv(shadow.MATCH_ENVIRONMENT_ENV, "TEST")

    captured: list[asyncio.Task] = []
    real_spawn = background_module.spawn

    def _capturing_spawn(coro: object, *, name: str | None = None) -> asyncio.Task:
        task = real_spawn(coro, name=name)
        captured.append(task)
        return task

    monkeypatch.setattr(shadow, "spawn", _capturing_spawn)

    shadow.maybe_spawn_shadow_match(
        db_pool,
        nationality="US",
        purpose=Purpose.LONG_TOURISM,
        duration_months=2,
        match_hash="flow-hash-1",
    )
    assert len(captured) == 1
    await captured[0]  # await the real background task to completion

    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM visa_decisions")
    assert count == 1
