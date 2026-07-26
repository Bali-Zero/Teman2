"""Tests for STEP-6d (``services/visa_engine/crypto.py``) — the real
crypto-backed facts-fingerprint identity provider.

Design: ``research/visa/2026-07-21-step6d-crypto-identity-provider-design.md`` §7.

Reuses the pack/facts builders from ``test_evaluator_gate_round1.py``'s
``TestPlaceholderIdentityEnvironmentGuard`` (a minimal PRODUCTION-environment
pack with one ELIGIBILITY rule) and the fixture/equality conventions from
``test_evaluator_determinism.py`` — no new pack-construction pattern invented
here.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import pytest

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.crypto import (
    FACTS_FINGERPRINT_KEYS_ENV_VAR,
    FactsFingerprintKeyStore,
    build_identity_provider,
    resolve_identity_provider,
)
from backend.services.visa_engine.enums import DecisionState, Environment
from backend.services.visa_engine.errors import (
    FactsFingerprintKeyError,
    FactsFingerprintKeyUnavailableError,
)
from backend.services.visa_engine.evaluator import _placeholder_identity_provider, evaluate
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _known(value):
    return {"status": "KNOWN", "value": value}


def _facts(overrides: dict) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data.update(overrides)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _minimal_pack(*, environment: str) -> M.RulePack:
    """Same shape as ``test_evaluator_gate_round1.py``'s ``_minimal_pack``:
    one product, one PRODUCTS-scope ELIGIBILITY rule covering TOURISM."""
    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    prod = B.product(product_id=product_id, source_id=source_id, covered_purposes=["TOURISM"])
    eligibility = B.rule(
        rule_id="el.tourism",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
        effect={"type": "SUPPORT", "reason_code": "TOURISM", "covered_purposes": ["TOURISM"]},
        source_id=source_id,
        required_facts=["intent.purposes"],
    )
    payload = B.rule_pack_payload(
        rules=[eligibility], products=[prod], source_records=[src], environment=environment
    )
    return M.RulePack.model_validate(B.rule_pack_envelope(payload))


def _secret_b64(byte_value: int = 0, length: int = 32) -> str:
    """A deterministic, obviously-not-a-real-secret >=32-byte HMAC key,
    base64url-unpadded (the shape ``FactsFingerprintKeyStore`` expects). Never
    a plausible real-looking secret — a fixed zero/incrementing test buffer."""
    raw = bytes([byte_value] * length)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _key_entry(
    *,
    kid: str = "test-kid-1",
    secret: str | None = None,
    environment: str = "PRODUCTION",
    valid_from: str = "2020-01-01T00:00:00+00:00",
    valid_to: str | None = None,
    revoked_at: str | None = None,
) -> dict:
    entry = {
        "kid": kid,
        "secret": secret if secret is not None else _secret_b64(),
        "environment": environment,
        "valid_from": valid_from,
    }
    if valid_to is not None:
        entry["valid_to"] = valid_to
    if revoked_at is not None:
        entry["revoked_at"] = revoked_at
    return entry


# ---------------------------------------------------------------------------
# Store loading (from_env / from_iterable)
# ---------------------------------------------------------------------------


class TestFactsFingerprintKeyStoreLoading:
    def test_valid_single_key_loads(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable([_key_entry()])
        assert len(store.keys) == 1
        assert store.keys[0].kid == "test-kid-1"

    def test_env_unset_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, raising=False)
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_env()

    def test_env_blank_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "   ")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_env()

    def test_env_valid_json_array_loads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json

        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, json.dumps([_key_entry()]))
        store = FactsFingerprintKeyStore.from_env()
        assert len(store.keys) == 1

    def test_bad_json_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "{not valid json")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_env()

    def test_non_array_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "{}")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_env()

    def test_missing_required_field_raises(self) -> None:
        entry = _key_entry()
        del entry["valid_from"]
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable([entry])

    def test_bad_base64_secret_raises(self) -> None:
        entry = _key_entry(secret="not-base64url!!! chars")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable([entry])

    def test_secret_below_32_bytes_raises(self) -> None:
        entry = _key_entry(secret=_secret_b64(length=16))
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable([entry])

    def test_duplicate_kid_same_environment_raises(self) -> None:
        entries = [
            _key_entry(kid="dup", valid_from="2020-01-01T00:00:00+00:00"),
            _key_entry(kid="dup", valid_from="2021-01-01T00:00:00+00:00"),
        ]
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable(entries)

    def test_naive_datetime_raises(self) -> None:
        entry = _key_entry(valid_from="2020-01-01T00:00:00")  # no tz
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable([entry])

    def test_unknown_environment_raises(self) -> None:
        entry = _key_entry(environment="BOGUS")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable([entry])


# ---------------------------------------------------------------------------
# Selection (store.select)
# ---------------------------------------------------------------------------


class TestFactsFingerprintKeyStoreSelection:
    def test_single_open_ended_key_resolves(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable([_key_entry()])
        key = store.select(Environment.PRODUCTION, _EFFECTIVE_AT)
        assert key.kid == "test-kid-1"

    def test_environment_mismatch_is_unavailable(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable([_key_entry(environment="STAGING")])
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            store.select(Environment.PRODUCTION, _EFFECTIVE_AT)

    def test_revoked_key_is_unavailable(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable(
            [_key_entry(revoked_at="2026-01-01T00:00:00+00:00")]
        )
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            store.select(Environment.PRODUCTION, _EFFECTIVE_AT)

    def test_out_of_window_before_valid_from_is_unavailable(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable(
            [_key_entry(valid_from="2099-01-01T00:00:00+00:00")]
        )
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            store.select(Environment.PRODUCTION, _EFFECTIVE_AT)

    def test_out_of_window_at_or_after_valid_to_is_unavailable(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable(
            [
                _key_entry(
                    valid_from="2020-01-01T00:00:00+00:00",
                    valid_to="2021-01-01T00:00:00+00:00",
                )
            ]
        )
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            store.select(Environment.PRODUCTION, _EFFECTIVE_AT)

    def test_rotation_latest_valid_from_wins(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable(
            [
                _key_entry(kid="old", valid_from="2020-01-01T00:00:00+00:00"),
                _key_entry(kid="new", valid_from="2025-01-01T00:00:00+00:00"),
            ]
        )
        key = store.select(Environment.PRODUCTION, _EFFECTIVE_AT)
        assert key.kid == "new"

    def test_tiebreak_same_valid_from_highest_kid_wins(self) -> None:
        store = FactsFingerprintKeyStore.from_iterable(
            [
                _key_entry(kid="aaa", valid_from="2020-01-01T00:00:00+00:00"),
                _key_entry(kid="zzz", valid_from="2020-01-01T00:00:00+00:00"),
            ]
        )
        key = store.select(Environment.PRODUCTION, _EFFECTIVE_AT)
        assert key.kid == "zzz"


# ---------------------------------------------------------------------------
# Provider (build_identity_provider used via evaluate(..., identity_provider=))
# ---------------------------------------------------------------------------


class TestBuildIdentityProvider:
    def test_digest_depends_on_the_secret_not_just_the_kid(self) -> None:
        # Same facts + pack + kid, two DIFFERENT secrets -> different
        # facts_fingerprint.digest (and different decision_id/public_id). Proves
        # the HMAC digest is keyed by the real SECRET bytes, not merely labelled
        # with the kid: a bug computing the digest with the wrong/placeholder key
        # but stamping the right kid would still pass the key_id assertions.
        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        d_a = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=build_identity_provider(
                FactsFingerprintKeyStore.from_iterable(
                    [_key_entry(kid="k", secret=_secret_b64(byte_value=1))]
                )
            ),
        )
        d_b = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=build_identity_provider(
                FactsFingerprintKeyStore.from_iterable(
                    [_key_entry(kid="k", secret=_secret_b64(byte_value=2))]
                )
            ),
        )
        assert d_a.facts_fingerprint.digest != d_b.facts_fingerprint.digest
        assert d_a.decision_id != d_b.decision_id
        assert d_a.public_id != d_b.public_id

    def test_production_pack_with_real_provider_succeeds_no_raise(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        store = FactsFingerprintKeyStore.from_iterable([_key_entry(kid="prod-key-1")])
        provider = build_identity_provider(store)

        decision = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=provider,
        )
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert decision.facts_fingerprint.key_id == "prod-key-1"

    def test_decision_id_and_public_id_are_deterministic_across_repeats(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        store = FactsFingerprintKeyStore.from_iterable([_key_entry(kid="prod-key-1")])
        provider = build_identity_provider(store)

        d1 = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=provider,
        )
        d2 = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=provider,
        )
        assert d1.decision_id == d2.decision_id
        assert d1.public_id == d2.public_id
        assert d1.facts_fingerprint.digest == d2.facts_fingerprint.digest

    def test_no_active_key_propagates_unavailable_error(self) -> None:
        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        # Key scoped to STAGING only -> no key available for a PRODUCTION pack.
        store = FactsFingerprintKeyStore.from_iterable(
            [_key_entry(kid="staging-key", environment="STAGING")]
        )
        provider = build_identity_provider(store)
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            evaluate(
                facts,
                pack,
                effective_at=_EFFECTIVE_AT,
                observed_at=_EFFECTIVE_AT,
                identity_provider=provider,
            )


# ---------------------------------------------------------------------------
# Resolver (resolve_identity_provider)
# ---------------------------------------------------------------------------


class TestResolveIdentityProvider:
    def test_env_unset_returns_the_placeholder_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, raising=False)
        provider = resolve_identity_provider()
        assert provider is _placeholder_identity_provider

    def test_env_blank_returns_the_placeholder_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "   ")
        provider = resolve_identity_provider()
        assert provider is _placeholder_identity_provider

    def test_env_set_with_valid_prod_key_returns_a_working_real_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        monkeypatch.setenv(
            FACTS_FINGERPRINT_KEYS_ENV_VAR, json.dumps([_key_entry(kid="prod-key-1")])
        )
        provider = resolve_identity_provider()
        assert provider is not _placeholder_identity_provider

        pack = build_compiled_pack(_minimal_pack(environment="PRODUCTION"))
        facts = _facts({"intent.purposes": _known(["TOURISM"])})
        decision = evaluate(
            facts,
            pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            identity_provider=provider,
        )
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert decision.facts_fingerprint.key_id == "prod-key-1"

    def test_env_set_with_malformed_json_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "{not valid json")
        with pytest.raises(FactsFingerprintKeyError):
            resolve_identity_provider()


# ---------------------------------------------------------------------------
# STEP-6d hardening (cross-family gate — Kimi K3 findings, 2026-07-21)
# ---------------------------------------------------------------------------


class TestStep6dHardening:
    def test_secret_never_appears_in_repr(self) -> None:
        # MEDIUM (Kimi): dataclass auto-repr must not leak the raw HMAC secret
        # into logs/tracebacks. ``secret`` is field(repr=False).
        secret = _secret_b64(byte_value=7)
        store = FactsFingerprintKeyStore.from_iterable([_key_entry(kid="k", secret=secret)])
        key = store.keys[0]
        assert "secret" not in repr(key)
        assert repr(key.secret) not in repr(key)
        assert repr(key.secret) not in repr(store)

    def test_empty_json_array_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # LOW (Kimi): "[]" is set-but-empty; reject rather than silently break
        # the TEST placeholder path.
        monkeypatch.setenv(FACTS_FINGERPRINT_KEYS_ENV_VAR, "[]")
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_env()

    def test_duplicate_kid_across_environments_raises(self) -> None:
        # LOW (Kimi): kids must be globally unique — a Fingerprint.key_id keyed
        # on kid alone must unambiguously identify one secret.
        entries = [
            _key_entry(kid="shared", environment="STAGING"),
            _key_entry(kid="shared", environment="PRODUCTION"),
        ]
        with pytest.raises(FactsFingerprintKeyError):
            FactsFingerprintKeyStore.from_iterable(entries)

    def test_naive_effective_at_is_fail_closed(self) -> None:
        # LOW (Kimi): a naive effective_at is ambiguous and diverges from the
        # tz-aware id seed — fail closed rather than silently assume UTC.
        store = FactsFingerprintKeyStore.from_iterable([_key_entry(kid="k")])
        naive = datetime(2026, 7, 21)  # no tzinfo
        with pytest.raises(FactsFingerprintKeyUnavailableError):
            store.select(Environment.PRODUCTION, naive)
