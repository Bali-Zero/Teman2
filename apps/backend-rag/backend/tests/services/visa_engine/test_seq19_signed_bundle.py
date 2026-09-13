"""Gates for the SIGNED seq-19 artifact
(``rulepack-prod-019.signed.json``) — the consul's ceremony output, distinct
from ``test_seq19_pack.py`` (which gates the unsigned fold/source file and
never claims a signature).

Signed 2026-09-05 by the owner on M5, offline (``sign_pack.py``, never this
process — see ``bundle.py``'s FIREBREAK docstring), key id ``prod-2026-07-1``
(the same pinned production Ed25519 key that verified seq-17/seq-18).
``rule_pack_id=8c09e059-4ab2-5963-b5af-d1363d55e508`` matches ``fold_pack_
seq19.py``'s ``_rule_pack_id(19)`` UUID5 convention (already pinned in
``test_seq19_pack.py::TestIdentity``); this module does not re-derive it,
only asserts the signed envelope carries the same value the source file does.

This module verifies the bundle with the REPO'S OWN Ed25519 verification
code (``bundle.verify_rule_pack``) against the pinned production trust
store — never trusting the signer's self-reported digest/kid/sequence.
Every literal below (digest, kid, sequence, previous-sha, rule count,
the two E23 review-gate ids) is re-derived from disk or from
``verify_rule_pack``'s own return value, not copied from a print statement.

ACTIVATION IS OUT OF SCOPE HERE. This module never calls
``activate_pack.py`` (it needs a live Postgres DSN even in its default
dry-run mode — see that script's ``asyncpg.create_pool`` calls — which this
test suite must never touch) and never calls ``validate_activation`` either:
promoting this bundle into the currently-active production sequence is a
separate, Zero-only ceremony. What this module proves is narrower and
sufficient for a PR gate: the bytes on disk are a validly signed,
untampered, correctly-chained PRODUCTION candidate.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ19_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-019.signed.json"
_SEQ19_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-019.source.json"


def test_signed_bundle_is_present_on_disk() -> None:
    """A deleted/missing artifact must turn this gate RED, never skip it.

    This module previously carried a module-level
    ``pytestmark = pytest.mark.skipif(not _SEQ19_SIGNED_PATH.exists(), ...)``,
    which meant an accidentally deleted (or never-landed) signed bundle
    produced a silent, all-green-looking SKIP rather than a failure — the
    gate would not have noticed its own consumer disappearing. This hard
    assertion replaces that skip: no file on disk means this test (and every
    other test below, which will error out trying to read it) fails loudly.
    """
    assert _SEQ19_SIGNED_PATH.exists(), (
        "rulepack-prod-019.signed.json does not exist on disk — the "
        "operator's offline signing ceremony (sign_pack.py) has not "
        "produced it, or it was deleted. This must FAIL, not skip."
    )


#: The pinned production Ed25519 public key — the same one that verifies
#: seq-17/seq-18 (see ``test_seq18_freshness_window.py``/``test_seq19_pack.py``).
PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)

#: seq-18's own verified payload digest — the chain anchor seq-19 must
#: declare as its ``previous_payload_sha256`` (also pinned in
#: ``fold_pack_seq19.SEQ18_PAYLOAD_SHA256`` and ``test_seq19_pack.py``).
SEQ18_PAYLOAD_SHA256 = "5a24472d187f85c54628f23d6e37b2a4b814e54762478c099472f0437d255849"

#: Shortly after the bundle's own ``signed_at`` (2026-09-05T20:48:52.495779Z)
#: — fixed, never ``datetime.now()``, so this test never rots.
OBSERVED_AT = datetime(2026, 9, 5, 21, 0, 0, tzinfo=timezone.utc)

#: The two live HUMAN_REVIEW gates that must survive every fold onto the
#: signed production chain (see ``test_seq19_pack.py::TestRuleIdSetIsExactly
#: TheDeclaredDelta``) — re-asserted here against the SIGNED bytes, not just
#: the unsigned source.
_EXPECTED_REVIEW_GATE_IDS = frozenset(
    {"review.e23u.requested-product", "review.e23v.requested-product"}
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signed_envelope() -> dict[str, Any]:
    return _read_json(_SEQ19_SIGNED_PATH)


@pytest.fixture(scope="module")
def source_payload() -> dict[str, Any]:
    return _read_json(_SEQ19_SOURCE_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture
def verified_pack(prod_trust_store_env: None, signed_envelope: dict[str, Any]):
    return verify_rule_pack(
        signed_envelope,
        trust_store=StaticTrustStore.from_env(),
        observed_at=OBSERVED_AT,
    )


# ---------------------------------------------------------------------------
# Cryptographic verification (innocence) — the repo's own code, never the
# signer's self-report.
# ---------------------------------------------------------------------------


class TestSignatureVerifies:
    def test_the_committed_bundle_verifies_against_the_pinned_production_key(
        self, verified_pack
    ) -> None:
        assert verified_pack.unsigned_dev is False
        assert verified_pack.pack.protected.kid == "prod-2026-07-1"

    def test_kid_and_environment(self, verified_pack) -> None:
        assert verified_pack.pack.protected.environment == "PRODUCTION"
        assert verified_pack.pack.payload.environment == "PRODUCTION"

    def test_sequence_is_19(self, verified_pack) -> None:
        assert verified_pack.pack.payload.sequence == 19

    def test_rule_pack_id_matches_the_source_fold(
        self, verified_pack, source_payload: dict[str, Any]
    ) -> None:
        assert str(verified_pack.pack.payload.rule_pack_id) == source_payload["rule_pack_id"]
        assert source_payload["rule_pack_id"] == "8c09e059-4ab2-5963-b5af-d1363d55e508"

    def test_payload_sha256_is_the_pinned_digest(self, verified_pack) -> None:
        assert (
            verified_pack.payload_sha256.hex()
            == "bac5da8e4727e7f639c947c50211e6f95e15c1403cf6aef0dd57a92014d6e6ea"
        )

    def test_chain_anchor_matches_seq18(self, verified_pack) -> None:
        assert verified_pack.pack.payload.previous_payload_sha256 == SEQ18_PAYLOAD_SHA256

    def test_rule_count_is_109(self, verified_pack) -> None:
        assert len(verified_pack.pack.payload.rules) == 109

    def test_the_two_e23_review_gates_are_present(self, verified_pack) -> None:
        rule_ids = {rule.rule_id for rule in verified_pack.pack.payload.rules}
        assert _EXPECTED_REVIEW_GATE_IDS <= rule_ids


# ---------------------------------------------------------------------------
# Digest recomputation — independent of verify_rule_pack, straight off disk.
# ---------------------------------------------------------------------------


class TestDigestRecomputedIndependently:
    def test_sha256_of_canonicalized_source_matches_the_pinned_digest(
        self, source_payload: dict[str, Any]
    ) -> None:
        assert (
            hashlib.sha256(canonicalize_json(source_payload)).hexdigest()
            == "bac5da8e4727e7f639c947c50211e6f95e15c1403cf6aef0dd57a92014d6e6ea"
        )

    def test_sha256_of_canonicalized_signed_payload_matches_the_declared_field(
        self, signed_envelope: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(signed_envelope["payload"])).hexdigest()
        assert recomputed == signed_envelope["payload_sha256"]

    def test_signed_payload_is_byte_identical_to_source_under_jcs(
        self, signed_envelope: dict[str, Any], source_payload: dict[str, Any]
    ) -> None:
        """The artifact that was signed is the same artifact in version
        control — a divergence here would mean the tracked source.json is
        not what the operator actually signed."""
        assert canonicalize_json(signed_envelope["payload"]) == canonicalize_json(source_payload)

    def test_source_validates_against_the_payload_model(
        self, source_payload: dict[str, Any]
    ) -> None:
        payload = RulePackPayload.model_validate(source_payload)
        assert payload.sequence == 19
        assert payload.previous_payload_sha256 == SEQ18_PAYLOAD_SHA256


# ---------------------------------------------------------------------------
# Guilt — a tampered COPY must fail verification. Never mutates the
# committed file; every mutation is applied to an in-memory `copy.deepcopy`.
# ---------------------------------------------------------------------------


class TestTamperingIsRejected:
    def test_flipping_one_base64url_character_of_the_signature_fails(
        self, prod_trust_store_env: None, signed_envelope: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(signed_envelope)
        sig = tampered["signature"]
        # Flip the first character to a different, still-valid base64url
        # character — guarantees a different byte string, never an
        # accidental no-op.
        flipped_char = "A" if sig[0] != "A" else "B"
        tampered["signature"] = flipped_char + sig[1:]
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
            )

    def test_mutating_one_payload_field_fails_both_digest_and_signature(
        self, prod_trust_store_env: None, signed_envelope: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(signed_envelope)
        tampered["payload"]["sequence"] = 20
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
            )

    def test_mutating_a_rule_inside_the_payload_fails(
        self, prod_trust_store_env: None, signed_envelope: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(signed_envelope)
        tampered["payload"]["rules"][0]["priority"] = 999999
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
            )

    def test_wrong_trust_store_key_fails(
        self, signed_envelope: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A DIFFERENT (but validly-shaped) Ed25519 public key must never
        verify this bundle — proves the check is against the real pinned
        key, not merely "a key that parses". ``monkeypatch.setenv`` (not a
        raw ``os.environ`` mutation) so a pre-existing value of this env var
        in the invoking process is restored, never clobbered, once the test
        ends."""
        wrong_key_json = json.dumps(
            [
                {
                    "kid": "prod-2026-07-1",
                    # 32 zero bytes, base64url, unpadded — a different,
                    # validly-shaped Ed25519 public key.
                    "public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "environment": "PRODUCTION",
                    "valid_from": "2026-07-19T00:00:00Z",
                    "valid_to": None,
                    "revoked_at": None,
                }
            ]
        )
        monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", wrong_key_json)
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                signed_envelope,
                trust_store=StaticTrustStore.from_env(),
                observed_at=OBSERVED_AT,
            )


# ---------------------------------------------------------------------------
# The committed file itself is untouched by any of the guilt tests above —
# proven by re-reading it from disk and re-verifying, after the tampering
# section has run.
# ---------------------------------------------------------------------------


def test_the_committed_file_on_disk_is_unchanged_and_still_verifies(
    prod_trust_store_env: None,
) -> None:
    fresh = _read_json(_SEQ19_SIGNED_PATH)
    verified = verify_rule_pack(
        fresh, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
    )
    assert verified.pack.payload.sequence == 19
    assert (
        verified.payload_sha256.hex()
        == "bac5da8e4727e7f639c947c50211e6f95e15c1403cf6aef0dd57a92014d6e6ea"
    )
