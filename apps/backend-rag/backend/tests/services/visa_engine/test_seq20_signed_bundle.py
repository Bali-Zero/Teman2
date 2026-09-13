"""Gates for the SIGNED seq-20 artifact
(``rulepack-prod-020.signed.json``) — the consul's ceremony output, distinct
from ``test_seq20_pack.py`` (which gates the unsigned fold/source file and
never claims a signature).

Signed 2026-09-06 by the owner on M5, offline (``sign_pack.py``, never this
process — see ``bundle.py``'s FIREBREAK docstring), key id ``prod-2026-07-1``
(the same pinned production Ed25519 key that verified seq-17/seq-18/seq-19).
``rule_pack_id=ac0a792d-a38d-512e-9ead-54a5d008fb68`` matches ``fold_pack_
seq20.py``'s ``_rule_pack_id(20)`` UUID5 convention; this module does not
re-derive it, only asserts the signed envelope carries the same value the
source file does.

This module verifies the bundle with the REPO'S OWN Ed25519 verification
code (``bundle.verify_rule_pack``) against the pinned production trust
store — never trusting the signer's self-reported digest/kid/sequence.
Every literal below (digest, kid, sequence, previous-sha, rule count) is
re-derived from disk or from ``verify_rule_pack``'s own return value, not
copied from a print statement.

Beyond the seq-19 mirror, this module pins the FIVE EDITS this fold made,
against the signed bytes: a signed artifact is the last place a wrong edit
can still be caught, and every one of these is a decision that changes what
the public funnel answers. The rule id lists are IMPORTED from
``fold_pack_seq20`` rather than retyped — a retyped list drifts silently the
moment the fold's own constants move.

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

from backend.scripts.visa_engine.fold_pack_seq20 import (
    BRIDGING_RULE_IDS,
    NEW_RULE_ID,
    REMOVED_RULE_IDS,
    REQUESTED_PRODUCT_FACT,
    SEQ19_PAYLOAD_SHA256,
    SPONSOR_STATUS_NO_EFFECT_RULE_IDS,
)
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
_SEQ20_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-020.signed.json"
_SEQ20_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-020.source.json"


def test_signed_bundle_is_present_on_disk() -> None:
    """A deleted/missing artifact must turn this gate RED, never skip it.

    The seq-19 module carried a module-level
    ``pytestmark = pytest.mark.skipif(not <path>.exists(), ...)`` until it was
    removed, because that meant an accidentally deleted (or never-landed)
    signed bundle produced a silent, all-green-looking SKIP rather than a
    failure — the gate would not have noticed its own consumer disappearing.
    This hard assertion is the replacement, carried forward here from the
    start: no file on disk means this test (and every other test below, which
    will error out trying to read it) fails loudly.
    """
    assert _SEQ20_SIGNED_PATH.exists(), (
        "rulepack-prod-020.signed.json does not exist on disk — the "
        "operator's offline signing ceremony (sign_pack.py) has not "
        "produced it, or it was deleted. This must FAIL, not skip."
    )


#: The pinned production Ed25519 public key — the same one that verifies
#: seq-17/seq-18/seq-19 (see ``test_seq19_signed_bundle.py``).
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

#: seq-20's own verified payload digest, recomputed off disk below and
#: cross-checked against ``verify_rule_pack``'s return value.
SEQ20_PAYLOAD_SHA256 = "df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d"

#: Shortly after the bundle's own ``signed_at`` (2026-09-06T14:59:27.320080Z)
#: — fixed, never ``datetime.now()``, so this test never rots.
OBSERVED_AT = datetime(2026, 9, 6, 15, 0, 0, tzinfo=timezone.utc)

#: The two live HUMAN_REVIEW gates that must survive every fold onto the
#: signed production chain — re-asserted here against the SIGNED bytes.
_EXPECTED_REVIEW_GATE_IDS = frozenset(
    {"review.e23u.requested-product", "review.e23v.requested-product"}
)

#: Edit 5's reason code, as the fold writes it. A literal here on purpose:
#: ``fold_pack_seq20`` inlines it in the rule body rather than naming it, so
#: pinning it in the test is what makes a silent reason-code edit visible.
_NEW_RULE_REASON_CODE = "BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signed_envelope() -> dict[str, Any]:
    return _read_json(_SEQ20_SIGNED_PATH)


@pytest.fixture(scope="module")
def source_payload() -> dict[str, Any]:
    return _read_json(_SEQ20_SOURCE_PATH)


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

    def test_sequence_is_20(self, verified_pack) -> None:
        assert verified_pack.pack.payload.sequence == 20

    def test_rule_pack_id_matches_the_source_fold(
        self, verified_pack, source_payload: dict[str, Any]
    ) -> None:
        assert str(verified_pack.pack.payload.rule_pack_id) == source_payload["rule_pack_id"]
        assert source_payload["rule_pack_id"] == "ac0a792d-a38d-512e-9ead-54a5d008fb68"

    def test_payload_sha256_is_the_pinned_digest(self, verified_pack) -> None:
        assert verified_pack.payload_sha256.hex() == SEQ20_PAYLOAD_SHA256

    def test_chain_anchor_matches_seq19(self, verified_pack) -> None:
        assert verified_pack.pack.payload.previous_payload_sha256 == SEQ19_PAYLOAD_SHA256

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
        assert hashlib.sha256(canonicalize_json(source_payload)).hexdigest() == SEQ20_PAYLOAD_SHA256

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
        assert payload.sequence == 20
        assert payload.previous_payload_sha256 == SEQ19_PAYLOAD_SHA256


# ---------------------------------------------------------------------------
# What THIS fold changed, asserted against the SIGNED bytes. Ids come from
# fold_pack_seq20's own constants — never retyped here.
# ---------------------------------------------------------------------------


class TestSeq20EditsSurvivedTheSigningCeremony:
    """Edits 2-5, each read back off the verified pack.

    Edit 1 (the stay-day cap widening) is not re-pinned here: ``test_seq20_
    pack.py`` already compares every ``STAY_DAY_CAPS`` bound against the
    source file, and this module's JCS-equality test proves the signed payload
    IS that source file byte-for-byte. What is pinned below is what a wrong
    fold would still produce a *validly signed* artifact for.
    """

    @staticmethod
    def _by_id(verified_pack) -> dict[str, Any]:
        return {rule.rule_id: rule for rule in verified_pack.pack.payload.rules}

    def test_edit2_the_retired_e33g_review_gate_is_absent(self, verified_pack) -> None:
        """``review.e33g.income-evidence`` was retired because its ``when``
        was a byte-copy of its SUPPORT twin's — a gate that could only ever
        fire when the product was already supported."""
        assert REMOVED_RULE_IDS == frozenset({"review.e33g.income-evidence"})
        assert REMOVED_RULE_IDS.isdisjoint(self._by_id(verified_pack))

    def test_edit3_the_eight_sponsor_status_rules_are_no_effect_on_unknown(
        self, verified_pack
    ) -> None:
        """``family.sponsor_status_code`` can never be certified by the
        browser (fact-mapper returns ``unknownFact(UNVERIFIED)`` for every
        answer), so these eight must not block the whole decision on it."""
        rules = self._by_id(verified_pack)
        assert len(SPONSOR_STATUS_NO_EFFECT_RULE_IDS) == 8
        for rule_id in SPONSOR_STATUS_NO_EFFECT_RULE_IDS:
            assert rule_id in rules, f"{rule_id} vanished from the signed pack"
            assert rules[rule_id].on_unknown == "NO_EFFECT", (
                f"{rule_id}: on_unknown is {rules[rule_id].on_unknown!r}, not NO_EFFECT — "
                "the seq-20 edit did not survive into the signed bytes"
            )

    def test_edit4_each_bridging_rule_carries_exactly_one_known_premise(
        self, verified_pack, signed_envelope: dict[str, Any]
    ) -> None:
        """The four BRIDGING SUPPORT rules were guarded so they only fire once
        the applicant has actually named a product. Read off the raw signed
        payload (not the model) because the premise shape is what is signed."""
        raw = {rule["rule_id"]: rule for rule in signed_envelope["payload"]["rules"]}
        assert len(BRIDGING_RULE_IDS) == 4
        for rule_id in BRIDGING_RULE_IDS:
            assert rule_id in raw, f"{rule_id} vanished from the signed pack"
            known_premises = [
                arg
                for arg in raw[rule_id]["when"]["args"]
                if arg.get("fact") == REQUESTED_PRODUCT_FACT and arg.get("op") == "known"
            ]
            assert len(known_premises) == 1, (
                f"{rule_id}: expected exactly one {REQUESTED_PRODUCT_FACT} `known` premise, "
                f"found {len(known_premises)}"
            )
            assert rule_id in self._by_id(verified_pack)

    def test_edit5_the_new_d2_compensation_hard_filter_is_present_and_excludes(
        self, verified_pack
    ) -> None:
        rules = self._by_id(verified_pack)
        assert NEW_RULE_ID == "hf.d2.indonesia-source-compensation"
        assert NEW_RULE_ID in rules, "the seq-20 hard filter is missing from the signed pack"
        rule = rules[NEW_RULE_ID]
        assert rule.effect.type == "EXCLUDE"
        assert rule.effect.reason_code == _NEW_RULE_REASON_CODE


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
        tampered["payload"]["sequence"] = 21
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

    def test_reverting_one_seq20_edit_fails(
        self, prod_trust_store_env: None, signed_envelope: dict[str, Any]
    ) -> None:
        """The fold-specific twin of the mutation above: put edit 3 back the
        way seq-19 had it (``on_unknown: NEEDS_INPUT``) and the signature must
        reject it. Proves the eight NO_EFFECT values above are inside the
        signed envelope, not merely inside a file this test happens to read."""
        tampered = copy.deepcopy(signed_envelope)
        target = SPONSOR_STATUS_NO_EFFECT_RULE_IDS[0]
        for rule in tampered["payload"]["rules"]:
            if rule["rule_id"] == target:
                rule["on_unknown"] = "NEEDS_INPUT"
                break
        else:  # pragma: no cover - the id is imported from the fold itself
            raise AssertionError(f"{target} not in the signed pack")
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
    fresh = _read_json(_SEQ20_SIGNED_PATH)
    verified = verify_rule_pack(
        fresh, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
    )
    assert verified.pack.payload.sequence == 20
    assert verified.payload_sha256.hex() == SEQ20_PAYLOAD_SHA256
    assert NEW_RULE_ID in {rule.rule_id for rule in verified.pack.payload.rules}
