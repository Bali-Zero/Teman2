"""Gates for seq-18 (``rulepack-prod-018.source.json`` /
``rulepack-prod-018.signed.json``), see ``backend.scripts.visa_engine.
fold_pack_seq18``.

What seq-18 is: a **policy-only fold**. It moves
``freshness_policy.max_age_seconds`` on the eighteen ``OFFICIAL_PORTAL``
source records from 604800 (seven days) to 2764800 (thirty-two days), sets
``version`` to the fold date, and touches nothing else. Deliberately NOT a
re-stamp: ``verified_at``/``verified_by`` keep seq-17's values on every
record, because nobody re-read the pages between the two folds, and moving
a stamp without a reading is the false attestation seq-17's own review
named.

Unlike seq-17, this fold DOES have a sibling on disk to diff against
(``rulepack-prod-017.source.json``), so the delta assertions here are
real end-to-end comparisons, not shape checks.

The load-bearing test in this module is the DATE one. The whole point of
2764800 rather than a round month is that the resulting boundary lands on
the date Zero asked for; a wrong constant would be invisible until the
Oracle went silent again, exactly as it did on 2026-08-30. So the boundary
is recomputed from the payload's own numbers, never trusted from the fold's
print statement or docstring.

The guard (``assert_only_expected_changes``) is exercised directly, guilt
AND innocence (superscar #3), on hand-built pairs — mutating the fold's
INPUT is caught first by the chain-anchor digest check, so a test that does
that proves the digest gate works and says nothing about the guard.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.fold_pack_seq18 import (
    EXPECTED_PORTAL_COUNT,
    NEW_MAX_AGE_SECONDS,
    OLD_MAX_AGE_SECONDS,
    PORTAL_AUTHORITY,
    assert_anchor_is_a_verified_signed_artifact,
    assert_changed_fields_hold_their_expected_values,
    assert_only_expected_changes,
    fold,
)
from backend.scripts.visa_engine.sign_pack import (
    SignPackError,
    assert_created_before_signed,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.models import RulePackPayload

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ17_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-017.source.json"
_SEQ18_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-018.source.json"
_SEQ18_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-018.signed.json"
_SEQ17_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-017.signed.json"

pytestmark = pytest.mark.skipif(
    not _SEQ18_SOURCE_PATH.exists(),
    reason="rulepack-prod-018.source.json does not exist on disk — run "
    "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq18`",
)

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

#: The seq-17 chain anchor — the digest activated in production at
#: 2026-08-30T15:35:49Z, and the value the fold refuses to proceed without.
SEQ17_PAYLOAD_SHA256 = "97cb964780b114a2fa936230055327102a5af59efb010b6bf04090bb7321890b"

#: seq-17's stamp, inherited unchanged by seq-18 — see the module docstring.
INHERITED_VERIFIED_AT = "2026-08-30T13:18:00Z"

#: What Zero asked for, in words: "sposta la scadenza a 1 ottobre".
EXPECTED_BOUNDARY = datetime(2026, 10, 1, 13, 18, 0, tzinfo=timezone.utc)

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

#: Fixed instant, never ``datetime.now()``: shortly after the bundle's own
#: ``signed_at`` (2026-08-30T17:18:16.587039Z) so it never rots.
OBSERVED_AT = datetime(2026, 8, 30, 18, 0, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _portals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        r for r in payload["source_records"] if r.get("authority_type") == PORTAL_AUTHORITY
    ]


@pytest.fixture(scope="module")
def seq17_source() -> dict[str, Any]:
    return _read_json(_SEQ17_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq18_source() -> dict[str, Any]:
    return _read_json(_SEQ18_SOURCE_PATH)


@pytest.fixture
def verified_pack(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)
    return verify_rule_pack(
        _read_json(_SEQ18_SIGNED_PATH),
        trust_store=StaticTrustStore.from_env(),
        observed_at=OBSERVED_AT,
    )


# ---------------------------------------------------------------------------
# THE DATE — the reason this fold exists at all
# ---------------------------------------------------------------------------


class TestBoundaryDate:
    def test_the_new_window_lands_the_boundary_on_2026_10_01(
        self, seq18_source: dict[str, Any]
    ) -> None:
        """Recomputed from the payload, never read from the fold's print.

        2764800 is not a round number and is not a calendar month — it was
        chosen so that seq-17's stamp plus the window equals the date Zero
        named. An off-by-a-day constant here would be invisible until the
        Oracle went silent again.
        """
        for record in _portals(seq18_source):
            verified_at = datetime.fromisoformat(
                record["verified_at"].replace("Z", "+00:00")
            )
            boundary = verified_at + timedelta(
                seconds=record["freshness_policy"]["max_age_seconds"]
            )
            assert boundary == EXPECTED_BOUNDARY, (
                f"{record['source_record_id']} expires {boundary.isoformat()}, "
                f"not {EXPECTED_BOUNDARY.isoformat()}"
            )

    def test_the_constant_itself_is_thirty_two_days(self) -> None:
        assert NEW_MAX_AGE_SECONDS == 32 * 24 * 3600 == 2_764_800
        assert OLD_MAX_AGE_SECONDS == 7 * 24 * 3600 == 604_800


# ---------------------------------------------------------------------------
# IDENTITY + CHAIN
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_sequence_is_18(self, seq18_source: dict[str, Any]) -> None:
        assert seq18_source["sequence"] == 18

    def test_rule_pack_id_follows_the_uuid5_convention(
        self, seq18_source: dict[str, Any], seq17_source: dict[str, Any]
    ) -> None:
        """Verified against the SIBLING too, not asserted in isolation.

        ``rule_pack_id`` is the primary key of ``visa_rule_packs`` and packs
        are immutable there — seq-17 was first folded carrying seq-16's id
        and the activation refused it. The convention is checked against a
        pack known to satisfy it before being trusted for the new one.
        """
        assert seq17_source["rule_pack_id"] == str(_rule_pack_id(17))
        assert seq18_source["rule_pack_id"] == str(_rule_pack_id(18))
        assert seq18_source["rule_pack_id"] != seq17_source["rule_pack_id"]

    def test_chain_anchor_is_the_real_seq17_digest(
        self, seq17_source: dict[str, Any], seq18_source: dict[str, Any]
    ) -> None:
        """The anchor is RE-DERIVED here, not copied from the fold."""
        recomputed = __import__("hashlib").sha256(canonicalize_json(seq17_source)).hexdigest()
        assert recomputed == SEQ17_PAYLOAD_SHA256
        assert seq18_source["previous_payload_sha256"] == SEQ17_PAYLOAD_SHA256

    def test_version_is_the_fold_date_not_inherited(
        self, seq18_source: dict[str, Any], seq17_source: dict[str, Any]
    ) -> None:
        """seq-17 inherited seq-16's ``2026.8.26`` while being created on
        2026-08-30 — a finding from its own review that could only be
        corrected forward. This is that correction."""
        assert seq17_source["version"] == "2026.8.26"
        assert seq18_source["version"] == "2026.8.31"


class TestSignatureAndChain:
    def test_signed_bundle_verifies_against_pinned_production_trust_store(
        self, verified_pack
    ) -> None:
        assert verified_pack.pack.protected.kid == "prod-2026-07-1"

    def test_signed_payload_digest_matches_the_source_on_disk(
        self, seq18_source: dict[str, Any], verified_pack
    ) -> None:
        """The signed bundle's own verified digest and the RFC-8785 digest
        recomputed from the SOURCE file must agree — otherwise the file in
        version control is not the artifact that was signed."""
        assert (
            __import__("hashlib").sha256(canonicalize_json(seq18_source)).hexdigest()
            == verified_pack.payload_sha256.hex()
        )

    def test_source_validates_against_the_payload_model(
        self, seq18_source: dict[str, Any]
    ) -> None:
        payload = RulePackPayload.model_validate(seq18_source)
        assert payload.sequence == 18


# ---------------------------------------------------------------------------
# THE DELTA — a real diff against the sibling on disk
# ---------------------------------------------------------------------------


class TestDeltaAgainstSeq17:
    def test_every_portal_window_widened_and_no_other_record_moved(
        self, seq17_source: dict[str, Any], seq18_source: dict[str, Any]
    ) -> None:
        before = {r["source_record_id"]: r for r in seq17_source["source_records"]}
        after = {r["source_record_id"]: r for r in seq18_source["source_records"]}
        assert before.keys() == after.keys()

        widened: list[str] = []
        for rid, old in before.items():
            new = after[rid]
            if old.get("authority_type") == PORTAL_AUTHORITY:
                assert old["freshness_policy"]["max_age_seconds"] == OLD_MAX_AGE_SECONDS
                assert new["freshness_policy"]["max_age_seconds"] == NEW_MAX_AGE_SECONDS
                widened.append(rid)
                # everything else on the record is byte-identical
                old_rest = {k: v for k, v in old.items() if k != "freshness_policy"}
                new_rest = {k: v for k, v in new.items() if k != "freshness_policy"}
                assert old_rest == new_rest
                # and inside the policy, only the window moved
                assert new["freshness_policy"]["kind"] == old["freshness_policy"]["kind"]
                assert set(new["freshness_policy"]) == set(old["freshness_policy"])
            else:
                assert new == old, f"non-portal record {rid} moved"

        assert len(widened) == 18

    def test_no_stamp_moved(self, seq18_source: dict[str, Any]) -> None:
        """The fold changes a POLICY. A policy change needs no attestation,
        and asserting one nobody performed is the defect seq-17 recorded."""
        assert {r["verified_at"] for r in _portals(seq18_source)} == {
            INHERITED_VERIFIED_AT
        }

    def test_rules_and_products_are_untouched_wholesale(
        self, seq17_source: dict[str, Any], seq18_source: dict[str, Any]
    ) -> None:
        for key in ("rules", "products"):
            if key in seq17_source:
                assert seq18_source[key] == seq17_source[key]

    def test_non_portal_authorities_keep_their_own_window(
        self, seq18_source: dict[str, Any]
    ) -> None:
        """This fold has no opinion on PRIMARY_LAW / IMPLEMENTING_REGULATION."""
        others = [
            r
            for r in seq18_source["source_records"]
            if r.get("authority_type") != PORTAL_AUTHORITY
        ]
        assert others, "expected non-portal authorities to exist in this pack"
        for record in others:
            policy = record.get("freshness_policy")
            if isinstance(policy, dict) and "max_age_seconds" in policy:
                assert policy["max_age_seconds"] != NEW_MAX_AGE_SECONDS


# ---------------------------------------------------------------------------
# THE GUARD — exercised directly, on hand-built pairs
# ---------------------------------------------------------------------------


def _pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """A minimal before/after that the guard must accept."""
    before = {
        "sequence": 17,
        "rule_pack_id": "a51a3142-df1d-5467-b015-623d9a8644e6",
        "version": "2026.8.26",
        "created_at": "2026-08-30T13:18:00Z",
        "created_by": "someone",
        "previous_payload_sha256": "0" * 64,
        "rollback_of_payload_sha256": None,
        "rules": [{"id": "r1", "when": {"a": 1}}],
        "source_records": [
            {
                "source_record_id": "p1",
                "authority_type": PORTAL_AUTHORITY,
                "verified_at": INHERITED_VERIFIED_AT,
                "verified_by": "reader",
                "content_sha256": "a" * 64,
                "freshness_policy": {
                    "kind": "MAX_AGE_SINCE_VERIFIED_AT",
                    "max_age_seconds": OLD_MAX_AGE_SECONDS,
                },
            },
            {
                "source_record_id": "l1",
                "authority_type": "PRIMARY_LAW",
                "verified_at": INHERITED_VERIFIED_AT,
                "verified_by": "reader",
                "content_sha256": "b" * 64,
                "freshness_policy": {
                    "kind": "MAX_AGE_SINCE_VERIFIED_AT",
                    "max_age_seconds": 31_536_000,
                },
            },
        ],
    }
    after = copy.deepcopy(before)
    after["sequence"] = 18
    after["rule_pack_id"] = "23492882-679e-52d1-b643-f626aa7237f0"
    after["version"] = "2026.8.31"
    after["created_at"] = "2026-08-31T00:00:00Z"
    after["created_by"] = "the fold"
    after["previous_payload_sha256"] = "1" * 64
    after["source_records"][0]["freshness_policy"][
        "max_age_seconds"
    ] = NEW_MAX_AGE_SECONDS
    return before, after


class TestGuardInnocence:
    def test_the_real_shape_of_this_fold_passes(self) -> None:
        before, after = _pair()
        assert_only_expected_changes(before, after)  # must not raise


class TestGuardGuilt:
    """Each mutation is applied to the OUTPUT only, so the guard is what
    catches it — not the fold's input digest check.

    One parametrized case per mutation rather than a `_expect_fail` helper:
    `pytest.raises` has to be visible IN the test body, or the repo's
    anti-reward-hacking lint reads the test as asserting nothing — and it is
    right to, because a helper is exactly where a silently-weakened assertion
    would hide.
    """

    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(
                lambda a: a["rules"][0].__setitem__("when", {"a": 2}),
                id="a-rule-changes",
            ),
            pytest.param(lambda a: a.__setitem__("surprise", 1), id="top-level-key-added"),
            pytest.param(lambda a: a.pop("rules"), id="top-level-key-removed"),
            pytest.param(
                lambda a: a["source_records"][0].__setitem__(
                    "verified_at", "2026-08-31T00:00:00Z"
                ),
                id="a-portal-stamp-moves",
            ),
            pytest.param(
                lambda a: a["source_records"][0].__setitem__("content_sha256", "c" * 64),
                id="a-portal-content-digest-moves",
            ),
            # The allowed set is EMPTY for non-portals — this fold has no opinion
            # on the year-long authorities and must not touch them.
            pytest.param(
                lambda a: a["source_records"][1]["freshness_policy"].__setitem__(
                    "max_age_seconds", NEW_MAX_AGE_SECONDS
                ),
                id="a-non-portal-window-moves",
            ),
            pytest.param(
                lambda a: a["source_records"][0]["freshness_policy"].__setitem__(
                    "kind", "SOMETHING_ELSE"
                ),
                id="the-policy-discriminator-changes",
            ),
            pytest.param(
                lambda a: a["source_records"][0]["freshness_policy"].__setitem__(
                    "grace_seconds", 1
                ),
                id="the-policy-gains-a-key",
            ),
            pytest.param(
                lambda a: a["source_records"][0].__setitem__("note", "hello"),
                id="a-record-field-is-added",
            ),
            pytest.param(lambda a: a["source_records"].pop(), id="a-record-is-dropped"),
        ],
    )
    def test_the_guard_rejects(self, mutate) -> None:
        before, after = _pair()
        mutate(after)
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)


# ---------------------------------------------------------------------------
# THE VALUE GUARD — the gap adversarial review of this diff demonstrated
# ---------------------------------------------------------------------------


class TestChangedFieldsHoldExpectedValues:
    """`assert_only_expected_changes` names what MAY move and then excludes
    exactly those fields from comparison, so it is silent about whether they
    moved to the RIGHT value.

    The refuter proved this concretely: six mutations of ALLOWED fields passed
    both that guard and `RulePackPayload.model_validate`, because the model
    accepts any positive window and binds none of these to this fold's intent.
    Nothing reaches those states today — `fold()` writes the values itself — and
    that is exactly why it is worth pinning: a guard whose fail-closedness holds
    only while the code above it stays correct is not a guard, it is a comment.
    """

    def _after(self) -> dict[str, Any]:
        _, after = _pair()
        # `_pair()` is a minimal hand-built shape carrying ONE portal record;
        # the value guard also pins the count, so fan it out to the real 18.
        portal = after["source_records"][0]
        others = [r for r in after["source_records"] if r is not portal]
        portals = []
        for i in range(EXPECTED_PORTAL_COUNT):
            clone = copy.deepcopy(portal)
            clone["source_record_id"] = f"p{i:02d}"
            portals.append(clone)
        after["source_records"] = portals + others
        # Give it the real identity the value guard checks against.
        after["rule_pack_id"] = str(_rule_pack_id(18))
        after["created_by"] = (
            "agent.air-m5.backend-rag.visa-freshness-window.fold-2026-08-31"
        )
        after["created_at"] = "2026-08-31T00:00:00Z"
        after["previous_payload_sha256"] = SEQ17_PAYLOAD_SHA256
        return after

    def test_innocence_the_real_output_shape_passes(self) -> None:
        assert_changed_fields_hold_their_expected_values(self._after())

    @pytest.mark.parametrize(
        "key,bad_value",
        [
            ("sequence", 19),
            ("version", "2026.9.99"),
            ("created_at", "2099-01-01T00:00:00Z"),
            ("created_by", "someone-else"),
            ("previous_payload_sha256", "a" * 64),
            ("rollback_of_payload_sha256", "b" * 64),
            ("rule_pack_id", "00000000-0000-0000-0000-000000000000"),
        ],
    )
    def test_guilt_a_permitted_field_holding_a_wrong_value_aborts(
        self, key: str, bad_value: Any
    ) -> None:
        after = self._after()
        after[key] = bad_value
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(after)

    def test_guilt_a_window_of_one_second_aborts(self) -> None:
        """The refuter's sharpest case: `max_age_seconds = 1` is a valid model
        value and was invisible to the shape guard."""
        after = self._after()
        after["source_records"][0]["freshness_policy"]["max_age_seconds"] = 1
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(after)

    def test_guilt_a_window_left_at_the_old_value_aborts(self) -> None:
        after = self._after()
        after["source_records"][0]["freshness_policy"][
            "max_age_seconds"
        ] = OLD_MAX_AGE_SECONDS
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(after)


# ---------------------------------------------------------------------------
# THE ARTIFACT'S OWN TEMPORAL INCOHERENCE — recorded, not hidden
# ---------------------------------------------------------------------------


def test_seq18_claims_to_be_created_after_it_was_signed() -> None:
    """seq-18 says `created_at` 2026-08-31T00:00:00Z while its own envelope says
    `signed_at` 2026-08-30T17:18:16.587039Z — it claims to have been created
    6h41m AFTER the signature that proves those bytes already existed.

    Found by adversarial review of this diff. `FOLD_CREATED_AT` was written as a
    round placeholder while the real fold and signing happened on the evening of
    the 30th. seq-17 is coherent (created 13:20Z, signed 15:16Z), so this is a
    regression this fold introduced, not an inherited habit.

    It CANNOT be fixed here: the artifact is signed and active in production, and
    editing a signed artifact is not a thing that exists. The honest remedies are
    (a) this test, which pins the defect so nobody later reads the timestamp as
    trustworthy, and (b) `assert_created_before_signed` in `sign_pack.py`, which
    stops the next pack from doing it. Corrected forward in seq-19.

    This test asserts the DEFECT, deliberately, and it is PERMANENT — adversarial
    review was right that "replace it when seq-19 lands" was wrong: no forward pack
    can make seq-18's own signed file coherent, so the positive invariant can never
    hold HERE. It holds for every pack after this one, and `sign_pack.py` is where
    it is enforced. The only thing that can turn this test red is someone tampering
    with an immutable artifact — which is exactly when it should go red.
    """
    signed = _read_json(_SEQ18_SIGNED_PATH)
    payload = signed.get("payload", signed)
    created = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    signed_at = datetime.fromisoformat(
        signed["protected"]["signed_at"].replace("Z", "+00:00")
    )
    assert created > signed_at, (
        "seq-18's known temporal incoherence is gone — if a seq-19 forward pack "
        "fixed it, replace this test with the positive invariant "
        "(created_at <= signed_at) rather than deleting it"
    )


# ---------------------------------------------------------------------------
# THE ANCHOR — "matches a constant I wrote" is not provenance
# ---------------------------------------------------------------------------


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


def test_anchor_accepts_the_real_signed_seq17_bundle(prod_trust_store_env: None) -> None:
    """Innocence: the actual seq-17 artifact, at its actual digest, passes."""
    assert_anchor_is_a_verified_signed_artifact(
        _read_json(_SEQ17_SIGNED_PATH),
        SEQ17_PAYLOAD_SHA256,
        observed_at=OBSERVED_AT,
    )


def test_anchor_rejects_a_digest_that_is_not_the_signed_payloads(
    prod_trust_store_env: None,
) -> None:
    """The whole point: the digest must come from the SIGNED artifact.

    Pinning the digest of a pack that was never signed is precisely the hole
    adversarial review named — the fold's failure message calls its input "the
    activated artifact" while checking only a constant in its own source.
    """
    with pytest.raises(SystemExit):
        assert_anchor_is_a_verified_signed_artifact(
            _read_json(_SEQ17_SIGNED_PATH), "b" * 64, observed_at=OBSERVED_AT
        )


def test_anchor_rejects_a_tampered_signed_bundle(prod_trust_store_env: None) -> None:
    """A payload edited after signing must fail the signature, not the digest."""
    tampered = _read_json(_SEQ17_SIGNED_PATH)
    portals = _portals(tampered["payload"])
    assert portals, "seq-17 must have portal records for this mutation to mean anything"
    portals[0]["freshness_policy"]["max_age_seconds"] = 1
    with pytest.raises(SystemExit):
        assert_anchor_is_a_verified_signed_artifact(
            tampered, SEQ17_PAYLOAD_SHA256, observed_at=OBSERVED_AT
        )


def test_anchor_rejects_the_wrong_sequence(prod_trust_store_env: None) -> None:
    """seq-18 verifies perfectly well — and is still not seq-17's anchor."""
    with pytest.raises(SystemExit):
        assert_anchor_is_a_verified_signed_artifact(
            _read_json(_SEQ18_SIGNED_PATH),
            __import__("hashlib")
            .sha256(canonicalize_json(_read_json(_SEQ18_SIGNED_PATH)["payload"]))
            .hexdigest(),
            observed_at=OBSERVED_AT,
        )


def test_anchor_refuses_to_run_without_a_trust_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No trust store is a REFUSAL, never a silent skip of the check."""
    monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
    with pytest.raises(SystemExit):
        assert_anchor_is_a_verified_signed_artifact(
            _read_json(_SEQ17_SIGNED_PATH),
            SEQ17_PAYLOAD_SHA256,
            observed_at=OBSERVED_AT,
        )


# ---------------------------------------------------------------------------
# THE FORWARD GUARD — what stops seq-19 repeating seq-18's timestamp defect
# ---------------------------------------------------------------------------


def test_signer_refuses_a_payload_created_after_its_own_signature() -> None:
    """The exact shape seq-18 shipped: created_at 6h41m43s after signed_at."""
    created = datetime(2026, 8, 31, 0, 0, 0, tzinfo=timezone.utc)
    signed = datetime(2026, 8, 30, 17, 18, 16, 587039, tzinfo=timezone.utc)
    with pytest.raises(SignPackError) as exc:
        assert_created_before_signed(created, signed)
    assert "created_at" in str(exc.value)


@pytest.mark.parametrize(
    "delta",
    [timedelta(seconds=1), timedelta(hours=6), timedelta(days=365)],
    ids=["one-second", "six-hours", "a-year"],
)
def test_signer_refuses_any_amount_of_future(delta: timedelta) -> None:
    """Not a tolerance band — one second in the future is still a false claim."""
    signed = datetime(2026, 8, 30, 17, 18, 16, tzinfo=timezone.utc)
    with pytest.raises(SignPackError):
        assert_created_before_signed(signed + delta, signed)


@pytest.mark.parametrize(
    "delta",
    [timedelta(0), timedelta(seconds=-1), timedelta(hours=-2)],
    ids=["same-instant", "one-second-before", "two-hours-before"],
)
def test_signer_accepts_created_at_or_before_signed_at(delta: timedelta) -> None:
    """Innocence, including the boundary: folded and signed in the same instant
    is coherent, and must not be refused."""
    signed = datetime(2026, 8, 30, 17, 18, 16, tzinfo=timezone.utc)
    assert_created_before_signed(signed + delta, signed)


def test_seq17_would_have_passed_the_forward_guard() -> None:
    """The guard is not retroactively hostile to the packs already on disk."""
    seq17 = _read_json(_SEQ17_SIGNED_PATH)
    created = datetime.fromisoformat(seq17["payload"]["created_at"].replace("Z", "+00:00"))
    signed = datetime.fromisoformat(
        seq17["protected"]["signed_at"].replace("Z", "+00:00")
    )
    assert_created_before_signed(created, signed)


# ---------------------------------------------------------------------------
# THE FOLD ITSELF — a guard fold() does not call is not a guard
# ---------------------------------------------------------------------------


def test_fold_reproduces_the_shipped_seq18_payload(
    prod_trust_store_env: None, seq17_source: dict[str, Any], seq18_source: dict[str, Any]
) -> None:
    """End-to-end: re-running the ceremony on the same input yields the artifact
    that is signed and active in production, byte-for-byte under JCS."""
    rebuilt = fold(seq17_source, _read_json(_SEQ17_SIGNED_PATH))
    assert canonicalize_json(rebuilt) == canonicalize_json(seq18_source)


def test_fold_refuses_an_anchor_bundle_that_is_not_the_signed_seq17(
    prod_trust_store_env: None, seq17_source: dict[str, Any]
) -> None:
    """The anchor check must fire from INSIDE fold(), not only when a test calls
    it directly — the failure mode adversarial review named for the digest
    constant applies just as much to a guard that is defined and never invoked."""
    tampered = _read_json(_SEQ17_SIGNED_PATH)
    _portals(tampered["payload"])[0]["freshness_policy"]["max_age_seconds"] = 1
    with pytest.raises(SystemExit):
        fold(seq17_source, tampered)


def test_fold_refuses_when_no_trust_store_is_configured(
    monkeypatch: pytest.MonkeyPatch, seq17_source: dict[str, Any]
) -> None:
    """Absent key material is a refusal to fold, never a silently skipped check."""
    monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
    with pytest.raises(SystemExit):
        fold(seq17_source, _read_json(_SEQ17_SIGNED_PATH))
