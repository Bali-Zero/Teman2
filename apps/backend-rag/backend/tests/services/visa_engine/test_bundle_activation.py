"""``validate_activation`` — the pure anti-rollback activation gate.

No persistence, no I/O: every test constructs a :class:`VerifiedRulePack`
via the real :func:`verify_rule_pack` (ephemeral in-fixture Ed25519 key,
never persisted) and asserts on the (non-)raise from
:func:`validate_activation` alone.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    VerifiedRulePack,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError

from ._builders import (
    ephemeral_ed25519_keypair,
    minimal_valid_envelope,
    sha256_hex,
    sign_rule_pack_envelope,
)

_OBSERVED_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)


def _verified(payload_overrides: dict | None = None) -> VerifiedRulePack:
    private_key, public_key = ephemeral_ed25519_keypair()
    payload = minimal_valid_envelope()["payload"]
    if payload_overrides:
        payload.update(payload_overrides)
    envelope = sign_rule_pack_envelope(payload, private_key=private_key)
    trust_store = StaticTrustStore(
        [
            TrustedSigningKey(
                key_id="test-key-1",
                public_key=public_key,
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                valid_to=None,
                revoked_at=None,
                environment="TEST",  # matches minimal_valid_envelope()'s payload environment
            )
        ]
    )
    return verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)


class TestSequence:
    def test_higher_sequence_accepted(self) -> None:
        verified = _verified({"sequence": 5, "previous_payload_sha256": sha256_hex("1")})
        result = validate_activation(
            verified,
            current_sequence=4,
            current_payload_sha256=bytes.fromhex(sha256_hex("1")),
            environment="TEST",
            engine_version="1.0.0",
        )
        assert result is None  # documents the "returns None on success" contract

    def test_equal_sequence_rejected(self) -> None:
        verified = _verified({"sequence": 4, "previous_payload_sha256": sha256_hex("1")})
        with pytest.raises(RulePackVerificationError, match="sequence"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("1")),
                environment="TEST",
                engine_version="1.0.0",
            )

    def test_lower_sequence_rejected(self) -> None:
        verified = _verified({"sequence": 3, "previous_payload_sha256": sha256_hex("1")})
        with pytest.raises(RulePackVerificationError, match="sequence"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("1")),
                environment="TEST",
                engine_version="1.0.0",
            )


class TestPreviousHashChain:
    def test_bootstrap_sequence_one_with_no_current_bundle_accepted(self) -> None:
        verified = _verified({"sequence": 1, "previous_payload_sha256": None})
        result = validate_activation(
            verified,
            current_sequence=0,
            current_payload_sha256=None,
            environment="TEST",
            engine_version="1.0.0",
        )
        assert result is None

    def test_previous_hash_mismatch_rejected(self) -> None:
        verified = _verified({"sequence": 5, "previous_payload_sha256": sha256_hex("1")})
        with pytest.raises(RulePackVerificationError, match="previous_payload_sha256"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("2")),  # different hash
                environment="TEST",
                engine_version="1.0.0",
            )

    def test_matching_previous_hash_accepted(self) -> None:
        current_hash_hex = sha256_hex("1")
        verified = _verified({"sequence": 5, "previous_payload_sha256": current_hash_hex})
        result = validate_activation(
            verified,
            current_sequence=4,
            current_payload_sha256=bytes.fromhex(current_hash_hex),
            environment="TEST",
            engine_version="1.0.0",
        )
        assert result is None

    def test_no_current_bundle_but_candidate_has_previous_hash_rejected(self) -> None:
        verified = _verified({"sequence": 5, "previous_payload_sha256": sha256_hex("1")})
        with pytest.raises(RulePackVerificationError, match="previous_payload_sha256"):
            validate_activation(
                verified,
                current_sequence=0,
                current_payload_sha256=None,
                environment="TEST",
                engine_version="1.0.0",
            )


class TestEnvironmentMismatch:
    def test_environment_mismatch_rejected(self) -> None:
        verified = _verified({"sequence": 5, "previous_payload_sha256": sha256_hex("1")})
        with pytest.raises(RulePackVerificationError, match="environment"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("1")),
                environment="STAGING",  # payload.environment is "TEST"
                engine_version="1.0.0",
            )


class TestEngineVersionCompatibility:
    def test_engine_version_within_range_accepted(self) -> None:
        verified = _verified(
            {
                "sequence": 5,
                "previous_payload_sha256": sha256_hex("1"),
                "engine_min_version": "1.0.0",
                "engine_max_version": "2.0.0",
            }
        )
        result = validate_activation(
            verified,
            current_sequence=4,
            current_payload_sha256=bytes.fromhex(sha256_hex("1")),
            environment="TEST",
            engine_version="1.5.0",
        )
        assert result is None

    def test_engine_version_below_range_rejected(self) -> None:
        verified = _verified(
            {
                "sequence": 5,
                "previous_payload_sha256": sha256_hex("1"),
                "engine_min_version": "1.0.0",
                "engine_max_version": "2.0.0",
            }
        )
        with pytest.raises(RulePackVerificationError, match="engine_version"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("1")),
                environment="TEST",
                engine_version="0.9.0",
            )

    def test_engine_version_above_range_rejected(self) -> None:
        verified = _verified(
            {
                "sequence": 5,
                "previous_payload_sha256": sha256_hex("1"),
                "engine_min_version": "1.0.0",
                "engine_max_version": "2.0.0",
            }
        )
        with pytest.raises(RulePackVerificationError, match="engine_version"):
            validate_activation(
                verified,
                current_sequence=4,
                current_payload_sha256=bytes.fromhex(sha256_hex("1")),
                environment="TEST",
                engine_version="2.0.1",
            )
