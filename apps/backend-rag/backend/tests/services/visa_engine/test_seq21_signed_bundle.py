"""Gates for the SIGNED seq-21 artifact
(``rulepack-prod-021.signed.json``) — the consul's ceremony output, distinct
from ``test_seq21_pack.py`` (which gates the unsigned fold/source file and
never claims a signature).

Signed 2026-09-15, offline (``sign_pack.py``, never this process — see
``bundle.py``'s FIREBREAK docstring), key id ``prod-2026-07-1`` (the same
pinned production Ed25519 key that verified seq-17..seq-20).
``rule_pack_id=22c2718d-c001-55c2-8bcc-2b71b257185a`` matches ``fold_pack_
seq21.py``'s ``_rule_pack_id(21)`` UUID5 convention; this module does not
re-derive it, only asserts the signed envelope carries the same value the
source file does.

This module verifies the bundle with the REPO'S OWN Ed25519 verification
code (``bundle.verify_rule_pack``) against the pinned production trust
store — never trusting the signer's self-reported digest/kid/sequence.
Every literal below (digest, kid, sequence, previous-sha, rule count) is
re-derived from disk or from ``verify_rule_pack``'s own return value, not
copied from a print statement.

Beyond the seq-20 mirror, this module pins what THIS fold changed, against
the signed bytes: a signed artifact is the last place a wrong edit can still
be caught, and every one of these is a decision that changes what the public
funnel answers. The rule id / rule-row constants are IMPORTED from
``fold_pack_seq21`` rather than retyped — a retyped list drifts silently the
moment the fold's own constants move.

Most of this fold's substance — the nine retirements, the nine SUPPORT
rules' premises/purposes/catalogue-conformance, the two named-cause hard
filters, the 84-walk census replay — is already exhaustively pinned against
the UNSIGNED source by ``test_seq21_pack.py``. What is pinned below is
narrower and specific to what a *validly signed* artifact could still get
wrong: that the signed bytes carry the same retirements/insertions the fold
declares, that the two numeric bounds a HARD_FILTER mirrors from its SUPPORT
donor rules still agree with each other inside the signed payload, and that
tampering with any of it is rejected.

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

from backend.scripts.visa_engine.fold_pack_seq21 import (
    E33_GUARANTEE_REASON,
    E33_GUARANTEE_RULE_ID,
    EMPLOYMENT_SPONSOR_PRODUCT_CODES,
    EMPLOYMENT_SPONSOR_REASON,
    EMPLOYMENT_SPONSOR_RULE_ID,
    HARD_FILTER_RULE_IDS,
    NEW_RULE_IDS,
    RETIRED_REVIEW_RULES,
    SEQ20_PAYLOAD_SHA256,
    SUPPORT_RULE_IDS,
    SUPPORT_RULES,
    TARGET_PRODUCT_CODES,
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
_SEQ21_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-021.signed.json"
_SEQ21_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-021.source.json"


def test_signed_bundle_is_present_on_disk() -> None:
    """A deleted/missing artifact must turn this gate RED, never skip it.

    The seq-19 module carried a module-level
    ``pytestmark = pytest.mark.skipif(not <path>.exists(), ...)`` until it was
    removed, because that meant an accidentally deleted (or never-landed)
    signed bundle produced a silent, all-green-looking SKIP rather than a
    failure — the gate would not have noticed its own consumer disappearing.
    This hard assertion is the replacement, carried forward here: no file on
    disk means this test (and every other test below, which will error out
    trying to read it) fails loudly.
    """
    assert _SEQ21_SIGNED_PATH.exists(), (
        "rulepack-prod-021.signed.json does not exist on disk — the "
        "operator's offline signing ceremony (sign_pack.py) has not "
        "produced it, or it was deleted. This must FAIL, not skip."
    )


#: The pinned production Ed25519 public key — the same one that verifies
#: seq-17..seq-20 (see ``test_seq20_signed_bundle.py``).
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

#: seq-21's own verified payload digest, recomputed off disk below and
#: cross-checked against ``verify_rule_pack``'s return value.
SEQ21_PAYLOAD_SHA256 = "fda8c3121bdddb6a8e023cf246c241a34f754acaef44919bb8968b50ee8c98c7"

#: Shortly after the bundle's own ``signed_at`` (2026-09-15T08:41:16.833720Z)
#: — fixed, never ``datetime.now()``, so this test never rots.
OBSERVED_AT = datetime(2026, 9, 15, 8, 45, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def signed_envelope() -> dict[str, Any]:
    return _read_json(_SEQ21_SIGNED_PATH)


@pytest.fixture(scope="module")
def source_payload() -> dict[str, Any]:
    return _read_json(_SEQ21_SOURCE_PATH)


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

    def test_sequence_is_21(self, verified_pack) -> None:
        assert verified_pack.pack.payload.sequence == 21

    def test_rule_pack_id_matches_the_source_fold(
        self, verified_pack, source_payload: dict[str, Any]
    ) -> None:
        assert str(verified_pack.pack.payload.rule_pack_id) == source_payload["rule_pack_id"]
        assert source_payload["rule_pack_id"] == "22c2718d-c001-55c2-8bcc-2b71b257185a"

    def test_payload_sha256_is_the_pinned_digest(self, verified_pack) -> None:
        assert verified_pack.payload_sha256.hex() == SEQ21_PAYLOAD_SHA256

    def test_chain_anchor_matches_seq20(self, verified_pack) -> None:
        assert verified_pack.pack.payload.previous_payload_sha256 == SEQ20_PAYLOAD_SHA256

    def test_rule_count_is_111(self, verified_pack) -> None:
        assert len(verified_pack.pack.payload.rules) == 111


# ---------------------------------------------------------------------------
# Digest recomputation — independent of verify_rule_pack, straight off disk.
# ---------------------------------------------------------------------------


class TestDigestRecomputedIndependently:
    def test_sha256_of_canonicalized_source_matches_the_pinned_digest(
        self, source_payload: dict[str, Any]
    ) -> None:
        assert hashlib.sha256(canonicalize_json(source_payload)).hexdigest() == SEQ21_PAYLOAD_SHA256

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
        assert payload.sequence == 21
        assert payload.previous_payload_sha256 == SEQ20_PAYLOAD_SHA256


# ---------------------------------------------------------------------------
# What THIS fold changed, asserted against the SIGNED bytes. Ids and rows
# come from fold_pack_seq21's own constants — never retyped here.
# ---------------------------------------------------------------------------


class TestSeq21EditsSurvivedTheSigningCeremony:
    """The retirement of nine dormant review gates and the insertion of
    eleven new rules (nine SUPPORT + two named-cause HARD_FILTER), each read
    back off the verified pack.

    Every other property of these edits — premise shape, catalogue
    conformance, purposes coverage, the 84-walk census replay — is already
    exhaustively pinned against the UNSIGNED source by ``test_seq21_pack.py``.
    What is pinned here is what a wrong fold would still produce a *validly
    signed* artifact for.
    """

    @staticmethod
    def _by_id(verified_pack) -> dict[str, Any]:
        return {rule.rule_id: rule for rule in verified_pack.pack.payload.rules}

    def test_the_nine_retired_review_rules_are_absent(self, verified_pack) -> None:
        """Each of the nine dormant ``review.*`` rules this fold retires
        (``intent.requested_product_code``-gated, never fireable from the
        browser) must not survive into the signed pack."""
        assert len(RETIRED_REVIEW_RULES) == 9
        rule_ids = self._by_id(verified_pack)
        for rule_id in RETIRED_REVIEW_RULES:
            assert rule_id not in rule_ids, f"{rule_id} survived the fold into the signed pack"

    def test_the_nine_support_rules_ask_rather_than_deny_on_unknown(self, verified_pack) -> None:
        """Each new ELIGIBILITY/SUPPORT rule must be present, carry
        ``on_unknown: NEEDS_INPUT`` (never the fail-closed ``NO_EFFECT``), and
        carry the reason code the fold declares for it."""
        assert len(SUPPORT_RULES) == 9
        assert len(SUPPORT_RULE_IDS) == 9
        rules = self._by_id(verified_pack)
        by_row_id = {row["rule_id"]: row for row in SUPPORT_RULES}
        for rule_id in SUPPORT_RULE_IDS:
            assert rule_id in rules, f"{rule_id} vanished from the signed pack"
            rule = rules[rule_id]
            assert rule.effect.type == "SUPPORT"
            assert rule.on_unknown == "NEEDS_INPUT", (
                f"{rule_id}: on_unknown is {rule.on_unknown!r}, not NEEDS_INPUT — "
                "the seq-21 edit did not survive into the signed bytes"
            )
            assert rule.effect.reason_code == by_row_id[rule_id]["reason_code"]

    def test_the_nine_target_products_each_gain_exactly_one_support_rule(
        self, verified_pack
    ) -> None:
        assert len(TARGET_PRODUCT_CODES) == 9
        by_row_id = {row["rule_id"]: row for row in SUPPORT_RULES}
        product_codes = {rule_id: row["product_code"] for rule_id, row in by_row_id.items()}
        assert set(product_codes.values()) == set(TARGET_PRODUCT_CODES)

    def test_the_two_named_cause_hard_filters_never_fire_on_unknown(self, verified_pack) -> None:
        """Both new HARD_FILTER/EXCLUDE rules must be present and carry
        ``on_unknown: NO_EFFECT`` — an EXCLUDE that fires on an UNKNOWN fact
        would deny a product to an applicant who never answered."""
        assert HARD_FILTER_RULE_IDS == (E33_GUARANTEE_RULE_ID, EMPLOYMENT_SPONSOR_RULE_ID)
        rules = self._by_id(verified_pack)

        guarantee = rules[E33_GUARANTEE_RULE_ID]
        assert guarantee.effect.type == "EXCLUDE"
        assert guarantee.effect.reason_code == E33_GUARANTEE_REASON
        assert guarantee.on_unknown == "NO_EFFECT"

        employment = rules[EMPLOYMENT_SPONSOR_RULE_ID]
        assert employment.effect.type == "EXCLUDE"
        assert employment.effect.reason_code == EMPLOYMENT_SPONSOR_REASON
        assert employment.on_unknown == "NO_EFFECT"

    def test_employment_hard_filter_is_scoped_to_its_three_declared_products(
        self, verified_pack, signed_envelope: dict[str, Any]
    ) -> None:
        assert EMPLOYMENT_SPONSOR_PRODUCT_CODES == ("E23", "E23V", "E33B")
        raw = {rule["rule_id"]: rule for rule in signed_envelope["payload"]["rules"]}
        products_by_code = {p["product_code"]: p for p in signed_envelope["payload"]["products"]}
        expected_version_ids = {
            products_by_code[code]["product_version_id"] for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES
        }
        assert set(raw[EMPLOYMENT_SPONSOR_RULE_ID]["product_version_ids"]) == expected_version_ids

    def test_the_e33_guarantee_exclusion_mirrors_its_own_support_donors(
        self, signed_envelope: dict[str, Any]
    ) -> None:
        """The EXCLUDE's two numeric bounds must be the exact bounds the SUPPORT
        rules ``el.e33.deposit-basis``/``el.e33.property-basis`` already
        encode — extracted from the signed payload, never typed here, so a pack
        that simultaneously denies a product for being below X and grants it at
        Y would fail this test rather than ship."""
        raw = {rule["rule_id"]: rule for rule in signed_envelope["payload"]["rules"]}

        def _gte_bound(rule_id: str, fact: str) -> int:
            args = raw[rule_id]["when"]["args"]
            matches = [a["value"] for a in args if a.get("fact") == fact and a.get("op") == "gte"]
            assert len(matches) == 1, f"{rule_id}: expected exactly one '{fact} gte' bound"
            return matches[0]

        def _lt_bound(rule_id: str, fact: str) -> int:
            args = raw[rule_id]["when"]["args"]
            matches = [a["value"] for a in args if a.get("fact") == fact and a.get("op") == "lt"]
            assert len(matches) == 1, f"{rule_id}: expected exactly one '{fact} lt' bound"
            return matches[0]

        deposit_min = _gte_bound("el.e33.deposit-basis", "secondhome.bank_deposit_usd")
        property_min = _gte_bound("el.e33.property-basis", "secondhome.qualifying_property_value_usd")

        assert _lt_bound(E33_GUARANTEE_RULE_ID, "secondhome.bank_deposit_usd") == deposit_min
        assert _lt_bound(E33_GUARANTEE_RULE_ID, "secondhome.qualifying_property_value_usd") == property_min

    def test_new_rule_ids_are_exactly_the_retirements_plus_insertions_delta(
        self, verified_pack, source_payload: dict[str, Any]
    ) -> None:
        """Census-level check: 109 (seq-20) - 9 retired + 11 inserted = 111,
        and the inserted set is exactly ``NEW_RULE_IDS``."""
        assert len(NEW_RULE_IDS) == 11
        assert set(NEW_RULE_IDS) == set(SUPPORT_RULE_IDS) | set(HARD_FILTER_RULE_IDS)
        signed_ids = {rule.rule_id for rule in verified_pack.pack.payload.rules}
        source_ids = {rule["rule_id"] for rule in source_payload["rules"]}
        assert signed_ids == source_ids
        assert set(NEW_RULE_IDS) <= signed_ids
        assert set(RETIRED_REVIEW_RULES).isdisjoint(signed_ids)


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
        tampered["payload"]["sequence"] = 22
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

    def test_reverting_one_seq21_edit_fails(
        self, prod_trust_store_env: None, signed_envelope: dict[str, Any]
    ) -> None:
        """The fold-specific twin of the mutation above: flip one SUPPORT
        rule's ``on_unknown`` from ``NEEDS_INPUT`` back to the fail-closed
        ``NO_EFFECT`` this fold deliberately rejected, and the signature must
        reject it. Proves the "ask, don't deny" choice is inside the signed
        envelope, not merely inside a file this test happens to read."""
        tampered = copy.deepcopy(signed_envelope)
        target = SUPPORT_RULE_IDS[0]
        for rule in tampered["payload"]["rules"]:
            if rule["rule_id"] == target:
                rule["on_unknown"] = "NO_EFFECT"
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
    fresh = _read_json(_SEQ21_SIGNED_PATH)
    verified = verify_rule_pack(
        fresh, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
    )
    assert verified.pack.payload.sequence == 21
    assert verified.payload_sha256.hex() == SEQ21_PAYLOAD_SHA256
    rule_ids = {rule.rule_id for rule in verified.pack.payload.rules}
    assert set(NEW_RULE_IDS) <= rule_ids
    assert set(RETIRED_REVIEW_RULES).isdisjoint(rule_ids)
