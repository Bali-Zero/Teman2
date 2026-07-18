"""``verify_rule_pack`` — Ed25519 signature verification, trust-store gating,
payload integrity, and the UNSIGNED-DEV firebreak.

Every signed fixture is produced by ``_builders.sign_rule_pack_envelope``
with a fresh, ephemeral, in-fixture Ed25519 key (never persisted) — a
throwaway test key, never the real offline signing ceremony (FIREBREAK, out
of scope by design — see ``bundle.py``'s module docstring).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pytest
import rfc8785

from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    TrustedSigningKey,
    VerifiedRulePack,
    _decode_base64url_no_padding,
    canonicalize_json,
    resolve_allow_unsigned_default,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

from ._builders import (
    ed25519_public_key_b64url,
    ephemeral_ed25519_keypair,
    minimal_valid_envelope,
    sign_rule_pack_envelope,
)

_SIGNED_AT = datetime(2026, 7, 1, tzinfo=timezone.utc)
_OBSERVED_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)
_KID = "test-key-1"


def _trust_store_with(
    *,
    kid: str = _KID,
    public_key=None,
    valid_from: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc),
    valid_to: datetime | None = None,
    revoked_at: datetime | None = None,
) -> StaticTrustStore:
    if public_key is None:
        _, public_key = ephemeral_ed25519_keypair()
    return StaticTrustStore(
        [
            TrustedSigningKey(
                key_id=kid,
                public_key=public_key,
                valid_from=valid_from,
                valid_to=valid_to,
                revoked_at=revoked_at,
            )
        ]
    )


def _signed_envelope(**kwargs):
    private_key, public_key = ephemeral_ed25519_keypair()
    payload = minimal_valid_envelope()["payload"]
    envelope = sign_rule_pack_envelope(
        payload, private_key=private_key, kid=kwargs.pop("kid", _KID), **kwargs
    )
    return envelope, public_key


class TestHappyPath:
    def test_valid_signed_pack_verifies(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        result = verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

        assert isinstance(result, VerifiedRulePack)
        assert result.unsigned_dev is False
        assert str(result.pack.payload.rule_pack_id) == envelope["payload"]["rule_pack_id"]

    def test_payload_sha256_matches_sha256_of_canonical_payload(self) -> None:
        import hashlib

        from backend.services.visa_engine.bundle import canonicalize_json

        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        result = verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

        expected_bytes = canonicalize_json(envelope["payload"])
        assert result.canonical_payload == expected_bytes
        assert result.payload_sha256 == hashlib.sha256(expected_bytes).digest()
        assert result.payload_sha256.hex() == envelope["payload_sha256"]


class TestTamperingRejected:
    def test_tampered_payload_single_byte_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        tampered = copy.deepcopy(envelope)
        # Flip a single field deep in the signed payload — the stored
        # payload_sha256 field is left stale (mismatches) AND the signature
        # (computed over the OLD payload bytes) can no longer verify.
        tampered["payload"]["created_by"] = "attacker"

        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(tampered, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_wrong_key_rejected(self) -> None:
        envelope, _signing_public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        _, wrong_public_key = ephemeral_ed25519_keypair()
        trust_store = _trust_store_with(public_key=wrong_public_key)

        with pytest.raises(RulePackVerificationError, match="signature verification failed"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_unknown_key_id_rejected(self) -> None:
        envelope, public_key = _signed_envelope(
            kid="not-in-store", signed_at="2026-07-01T00:00:00Z"
        )
        trust_store = _trust_store_with(kid="a-different-kid", public_key=public_key)

        with pytest.raises(RulePackVerificationError, match="unknown signing key_id"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_key_not_yet_valid_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-01-01T00:00:00Z")
        trust_store = _trust_store_with(
            public_key=public_key,
            valid_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

        with pytest.raises(RulePackVerificationError, match="not yet valid"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_key_expired_at_signed_at_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-08-01T00:00:00Z")
        trust_store = _trust_store_with(
            public_key=public_key,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_to=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        with pytest.raises(RulePackVerificationError, match="expired"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_key_revoked_at_signed_at_rejected(self) -> None:
        # revoked_at takes effect immediately/inclusive — a signature timed
        # exactly AT revoked_at is rejected.
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(
            public_key=public_key,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            revoked_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )

        with pytest.raises(RulePackVerificationError, match="revoked"):
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)


class TestSignatureShapeRejected:
    def test_padded_base64url_signature_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        broken = copy.deepcopy(envelope)
        broken["signature"] = (
            broken["signature"][:-2] + "=="
        )  # pad it, 86 -> 86 (still wrong shape)

        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(broken, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_malformed_signature_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        broken = copy.deepcopy(envelope)
        broken["signature"] = "+" * 86  # '+' is standard-base64, not url-safe -> pattern violation

        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(broken, trust_store=trust_store, observed_at=_OBSERVED_AT)


class TestWireCanonicalizationNotModelReserialization:
    """P1-class regression: the signature covers the LITERAL WIRE BYTES of
    ``protected``/``payload``, never a Pydantic ``model_dump()``
    re-serialization of them. The two agree only when the model round-trips
    byte-identically to the wire object — they do NOT always agree.

    NOTE on the reproduction vector: "a wire payload that OMITS an
    optional-with-default field" does not reproduce the bug in THIS schema
    — every field involved is schema-REQUIRED (no Python default, see
    ``models.py``'s "no silent default on a signed-payload field"
    convention), so a wire object omitting one is schema-INVALID and
    rejected at the JSON-Schema-validation step regardless of which
    canonicalization source is used afterward.

    The vector actually used here is a REAL, schema-legitimate divergence
    surface with the identical root cause (a Pydantic normalization the raw
    wire object is not obligated to match): JSON Schema's ``format: uuid``
    accepts any letter casing, but Pydantic's ``UUID`` field type always
    normalizes to lowercase on ``model_dump``. An uppercase-cased
    ``rule_pack_id`` is exactly the kind of input a real offline signer
    could legitimately sign — and a model_dump-based implementation would
    reject it outright.
    """

    def test_model_dump_of_uppercase_uuid_payload_diverges_from_raw_wire_bytes(
        self,
    ) -> None:
        """Proves the divergence is REAL before trusting the fix: parsing
        the raw payload into the model and re-dumping it must NOT
        round-trip byte-identically to the raw wire dict — this is the
        exact bug class, demonstrated independently of `verify_rule_pack`."""

        payload = minimal_valid_envelope()["payload"]
        payload["rule_pack_id"] = payload["rule_pack_id"].upper()

        raw_bytes = canonicalize_json(payload)
        reserialized_bytes = canonicalize_json(
            RulePackPayload.model_validate(payload).model_dump(by_alias=True, mode="json")
        )

        assert raw_bytes != reserialized_bytes
        assert payload["rule_pack_id"].encode() in raw_bytes
        assert payload["rule_pack_id"].encode() not in reserialized_bytes

    def test_uppercase_uuid_on_wire_still_verifies_with_a_real_signature(self) -> None:
        """The end-to-end regression: this MUST fail under a model_dump-based
        canonicalization (signature verification would fail, since the
        re-canonicalized bytes never match what was actually signed) and
        MUST pass under the wire-canonicalization implementation."""

        private_key, public_key = ephemeral_ed25519_keypair()
        payload = minimal_valid_envelope()["payload"]
        payload["rule_pack_id"] = payload["rule_pack_id"].upper()
        envelope = sign_rule_pack_envelope(payload, private_key=private_key)
        trust_store = _trust_store_with(public_key=public_key)

        result = verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

        assert result.unsigned_dev is False
        assert str(result.pack.payload.rule_pack_id) == payload["rule_pack_id"].lower()
        assert result.canonical_payload == canonicalize_json(payload)


class TestProtectedPayloadEnvironmentCrossCheck:
    """The trust boundary itself cross-checks ``protected.environment ==
    payload.environment`` — it must not depend on the downstream compiler's
    own re-check ever running."""

    def test_environment_mismatch_rejected_inside_verify(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        tampered = copy.deepcopy(envelope)
        assert tampered["payload"]["environment"] == "TEST"
        tampered["protected"]["environment"] = "STAGING"

        with pytest.raises(RulePackVerificationError, match="does not match payload environment"):
            verify_rule_pack(tampered, trust_store=trust_store, observed_at=_OBSERVED_AT)

    def test_matching_environment_accepted(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        result = verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

        assert result.pack.protected.environment == result.pack.payload.environment == "TEST"


class TestPayloadShaMismatchRejected:
    def test_payload_sha256_mismatch_rejected(self) -> None:
        envelope, public_key = _signed_envelope(signed_at="2026-07-01T00:00:00Z")
        trust_store = _trust_store_with(public_key=public_key)

        broken = copy.deepcopy(envelope)
        # Corrupt ONLY the self-declared hash field — the signed bytes
        # (protected+payload) are untouched, so a naive "just check the
        # signature" implementation would happily accept this.
        broken["payload_sha256"] = "0" * 64

        with pytest.raises(RulePackVerificationError, match="payload_sha256 mismatch"):
            verify_rule_pack(broken, trust_store=trust_store, observed_at=_OBSERVED_AT)


class TestUnsignedDevFirebreak:
    def test_unsigned_without_flag_rejected(self) -> None:
        payload = minimal_valid_envelope()["payload"]
        envelope = {"payload": payload}  # no "signature" key at all

        with pytest.raises(RulePackVerificationError, match="allow_unsigned=False"):
            verify_rule_pack(
                envelope,
                trust_store=_trust_store_with(),
                observed_at=_OBSERVED_AT,
                allow_unsigned=False,
            )

    def test_unsigned_with_flag_non_production_accepted(self) -> None:
        payload = minimal_valid_envelope()["payload"]
        assert payload["environment"] == "TEST"
        envelope = {"payload": payload}

        result = verify_rule_pack(
            envelope,
            trust_store=_trust_store_with(),
            observed_at=_OBSERVED_AT,
            allow_unsigned=True,
        )

        assert result.unsigned_dev is True
        assert str(result.pack.payload.rule_pack_id) == payload["rule_pack_id"]
        assert result.pack.protected.environment == "TEST"

    def test_unsigned_with_flag_production_rejected(self) -> None:
        payload = minimal_valid_envelope()["payload"]
        payload = {**payload, "environment": "PRODUCTION", "previous_payload_sha256": None}
        payload["sequence"] = 1
        envelope = {"payload": payload}

        with pytest.raises(RulePackVerificationError, match="PRODUCTION"):
            verify_rule_pack(
                envelope,
                trust_store=_trust_store_with(),
                observed_at=_OBSERVED_AT,
                allow_unsigned=True,
            )

    def test_empty_string_signature_also_treated_as_unsigned(self) -> None:
        payload = minimal_valid_envelope()["payload"]
        envelope = {"payload": payload, "signature": ""}

        result = verify_rule_pack(
            envelope,
            trust_store=_trust_store_with(),
            observed_at=_OBSERVED_AT,
            allow_unsigned=True,
        )
        assert result.unsigned_dev is True


class TestAllowUnsignedEnvParsing:
    """Strict env-var parsing for the ``allow_unsigned`` default: only a
    case-insensitive ``"true"``/``"1"`` enables it."""

    @pytest.mark.parametrize(
        "raw_value",
        ["true", "TRUE", "True", "1"],
    )
    def test_truthy_values_enable(self, monkeypatch: pytest.MonkeyPatch, raw_value: str) -> None:
        monkeypatch.setenv("VISA_ENGINE_ALLOW_UNSIGNED_PACKS", raw_value)
        assert resolve_allow_unsigned_default() is True

    @pytest.mark.parametrize(
        "raw_value",
        ["false", "0", "yes", "TRUE ", " 1", "", "no", "2"],
    )
    def test_everything_else_disables(
        self, monkeypatch: pytest.MonkeyPatch, raw_value: str
    ) -> None:
        monkeypatch.setenv("VISA_ENGINE_ALLOW_UNSIGNED_PACKS", raw_value)
        assert resolve_allow_unsigned_default() is False

    def test_missing_env_var_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VISA_ENGINE_ALLOW_UNSIGNED_PACKS", raising=False)
        assert resolve_allow_unsigned_default() is False


class TestCanonicalizationErrorTypedContract:
    """``verify_rule_pack`` must never let a bare
    ``rfc8785.CanonicalizationError`` escape — the module's typed-error
    contract (and the function's own docstring) promise
    ``RulePackVerificationError`` only, even for a wire string RFC 8785
    itself cannot serialize.

    Reproduction: a lone UTF-16 surrogate (``"\\ud800"``) is a syntactically
    valid Python ``str`` (JSON Schema's unadorned ``type: string`` fields —
    e.g. ``SourceRecord.title``, no ``pattern``/``format`` — accept it,
    confirmed empirically), but RFC 8785 JCS cannot encode it as UTF-8 and
    raises ``CanonicalizationError``. The (throwaway, in-fixture) test
    signer would ALSO hit this same error trying to sign such a payload —
    there is no way to produce a "validly signed but unsignable" envelope —
    so this envelope is built by hand with a syntactically-shaped (but not
    cryptographically real) signature; the canonicalization failure must be
    hit and reported BEFORE signature verification is ever attempted.
    """

    @staticmethod
    def _poisoned_envelope(public_key_kid: str = "test-key-1") -> dict:
        payload = minimal_valid_envelope()["payload"]
        payload["source_records"][0]["title"] = "\ud800"
        return {
            "canonicalization": "RFC8785",
            "protected": {
                "domain": "balizero.visa-rulepack.v1",
                "alg": "Ed25519",
                "kid": public_key_kid,
                "signed_at": "2026-07-01T00:00:00Z",
                "schema_version": "1.0.0",
                "environment": payload["environment"],
            },
            "payload": payload,
            "payload_sha256": "0" * 64,
            "signature": "A" * 86,
        }

    def test_lone_surrogate_passes_schema_but_breaks_jcs(self) -> None:
        """Ground the reproduction: prove the poisoned field really does
        pass JSON Schema (so the failure the next test hits is genuinely
        the canonicalization step, not schema rejection) and really does
        break `canonicalize_json` on its own."""

        envelope = self._poisoned_envelope()

        with pytest.raises(rfc8785.CanonicalizationError):
            canonicalize_json(envelope["payload"])

    def test_verify_rule_pack_raises_typed_error_not_bare_rfc8785_error(self) -> None:
        envelope = self._poisoned_envelope()
        _, public_key = ephemeral_ed25519_keypair()
        trust_store = _trust_store_with(public_key=public_key)

        with pytest.raises(RulePackVerificationError) as exc_info:
            verify_rule_pack(envelope, trust_store=trust_store, observed_at=_OBSERVED_AT)

        assert not isinstance(exc_info.value, rfc8785.CanonicalizationError)
        assert "not JCS-canonicalizable" in str(exc_info.value)


class TestBase64urlAlphabetHardening:
    """``base64.urlsafe_b64decode`` runs with default ``validate=False``, so
    standard-alphabet ``+``/``/`` are silently ACCEPTED (only ``-``/``_``
    get translated, everything else passes straight to the decoder) and
    truly out-of-alphabet characters can be silently DROPPED rather than
    rejected. For an operator-supplied trust-store public key
    (``StaticTrustStore.from_env``), a ``-``-for-``+`` (or similar) typo
    would decode to 32 DIFFERENT bytes and still be accepted by
    ``Ed25519PublicKey.from_public_bytes`` — silently pinning the WRONG key
    with no error. Confirmed empirically: both a ``+``-suffixed and a
    ``/``-suffixed 43-char string decoded without error under the naive
    implementation.
    """

    def test_plus_character_rejected(self) -> None:
        with pytest.raises(RulePackVerificationError):
            _decode_base64url_no_padding("A" * 42 + "+")

    def test_slash_character_rejected(self) -> None:
        with pytest.raises(RulePackVerificationError):
            _decode_base64url_no_padding("A" * 42 + "/")

    def test_out_of_alphabet_asterisk_rejected(self) -> None:
        with pytest.raises(RulePackVerificationError):
            _decode_base64url_no_padding("A" * 42 + "*")

    def test_out_of_alphabet_space_rejected(self) -> None:
        with pytest.raises(RulePackVerificationError):
            _decode_base64url_no_padding("A" * 42 + " ")

    def test_valid_dash_underscore_alphabet_still_accepted(self) -> None:
        result = _decode_base64url_no_padding("A" * 41 + "-_")
        assert len(result) == 32

    def test_trust_store_public_key_with_plus_typo_rejected_at_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The security-relevant end-to-end case: a `+`-corrupted public
        key in a trust-store env entry must be REJECTED when building the
        StaticTrustStore — never silently decoded to 32 wrong bytes and
        pinned as if it were the intended key."""

        _, public_key = ephemeral_ed25519_keypair()
        valid_b64url = ed25519_public_key_b64url(public_key)
        corrupted = valid_b64url[:-1] + ("+" if valid_b64url[-1] != "+" else "-")

        entries_json = (
            "["
            '{"kid": "op-key-1", '
            f'"public_key": "{corrupted}", '
            '"valid_from": "2026-01-01T00:00:00Z", '
            '"valid_to": null, "revoked_at": null}'
            "]"
        )
        monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", entries_json)

        with pytest.raises(RulePackVerificationError):
            StaticTrustStore.from_env()
