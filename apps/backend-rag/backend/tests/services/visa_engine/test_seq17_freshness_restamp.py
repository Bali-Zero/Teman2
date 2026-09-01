"""Gates for seq-17 (``rulepack-prod-017.source.json`` /
``rulepack-prod-017.signed.json``), see ``backend.scripts.visa_engine.
fold_pack_seq17``.

What seq-17 is (full rationale in the fold module's own docstring): a
**re-stamp-only fold**. The 18 ``OFFICIAL_PORTAL`` source records in the
live seq-16 payload were re-verified 2026-08-30 and got fresh
``verified_at``/``verified_by`` — nothing else in the payload changed.
``content_sha256`` is untouched on every record, ``rules``/``products`` are
untouched wholesale.

seq-16 itself never landed on ``main`` (the fold reads its chain anchor
from the live production activation, not from a sibling file in
``contracts/packs/``, per the fold module's docstring) — so unlike the
seq-14/seq-15 witness files, this module has no seq-16 sibling to diff
against and cannot assert a rule-level delta the way those two do. What it
CAN and does assert, all against real files on disk or the real fold code:
identity (sequence, uuid5 rule_pack_id convention, chain anchor), the
signed bundle's cryptographic verification against the pinned PRODUCTION
trust store, the JCS digest chain from source to signed payload, the
freshness shape produced by the restamp, and — the important part — the
``assert_only_expected_changes`` guard exercised directly, guilt AND
innocence (superscar #3).
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.fold_pack_seq17 import (
    PORTAL_AUTHORITY,
    RESTAMP_VERIFIED_AT,
    assert_only_expected_changes,
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
_SEQ17_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-017.signed.json"
_SEQ15_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-015.source.json"

pytestmark = pytest.mark.skipif(
    not _SEQ17_SOURCE_PATH.exists(),
    reason="rulepack-prod-017.source.json does not exist on disk — run "
    "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq17`",
)

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

SEQ16_PAYLOAD_SHA256 = "ef17dc122380d1e5ca7a7360c21d64fbfea05681bf30b1447f6c14026bc94100"
SEQ17_PAYLOAD_SHA256 = "97cb964780b114a2fa936230055327102a5af59efb010b6bf04090bb7321890b"
EXPECTED_VERIFIED_AT = "2026-08-30T13:18:00Z"

#: Same idiom as ``test_prod_sequence2_bundle.py`` — a pinned PRODUCTION
#: trust store, monkeypatched into the env var the trust-store loader reads.
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
#: ``signed_at`` (2026-08-30T15:16:36.65Z) so it never rots.
OBSERVED_AT = datetime(2026, 8, 30, 16, 0, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


@pytest.fixture(scope="module")
def seq17_source() -> dict[str, Any]:
    return _read_json(_SEQ17_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq17_signed() -> dict[str, Any]:
    return _read_json(_SEQ17_SIGNED_PATH)


@pytest.fixture
def verified_pack(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)
    raw = _read_json(_SEQ17_SIGNED_PATH)
    return verify_rule_pack(
        raw,
        trust_store=StaticTrustStore.from_env(),
        observed_at=OBSERVED_AT,
    )


# ---------------------------------------------------------------------------
# IDENTITY
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_sequence_is_17(self, seq17_source: dict[str, Any]) -> None:
        assert seq17_source["sequence"] == 17

    def test_rule_pack_id_follows_the_uuid5_convention(
        self, seq17_source: dict[str, Any]
    ) -> None:
        assert seq17_source["rule_pack_id"] == str(_rule_pack_id(17))

    def test_the_uuid5_convention_itself_is_witnessed_on_seq15(self) -> None:
        """Not just this pack: the convention that mints ``rule_pack_id``
        from ``uuid5(NAMESPACE_URL, <prefix><sequence>)`` is witnessed
        against an INDEPENDENT pack already on disk (seq-15), so a test
        that only checked seq-17 against its own formula would not catch
        the formula itself drifting for every pack at once."""
        seq15_source = _read_json(_SEQ15_SOURCE_PATH)
        assert seq15_source["sequence"] == 15
        assert seq15_source["rule_pack_id"] == str(_rule_pack_id(15))

    def test_previous_payload_sha256_chains_to_seq16(
        self, seq17_source: dict[str, Any]
    ) -> None:
        assert seq17_source["previous_payload_sha256"] == SEQ16_PAYLOAD_SHA256


# ---------------------------------------------------------------------------
# SIGNATURE / CHAIN
# ---------------------------------------------------------------------------


class TestSignatureAndChain:
    def test_signed_bundle_verifies_against_pinned_production_trust_store(
        self, verified_pack
    ) -> None:
        assert verified_pack.pack.protected.kid == "prod-2026-07-1"
        assert verified_pack.pack.protected.environment == "PRODUCTION"
        assert verified_pack.unsigned_dev is False
        assert verified_pack.pack.payload.sequence == 17

    def test_verified_payload_sha256_matches_the_pinned_digest(self, verified_pack) -> None:
        assert verified_pack.payload_sha256.hex() == SEQ17_PAYLOAD_SHA256

    def test_recomputed_jcs_digest_of_source_matches_signed_payload_sha256(
        self, seq17_source: dict[str, Any], seq17_signed: dict[str, Any]
    ) -> None:
        """The signed bundle's own declared ``payload_sha256`` and the
        RFC-8785 JCS digest recomputed from the SOURCE file must agree —
        proving the two artifacts on disk are the same payload, not two
        that merely look alike."""
        import hashlib

        recomputed = hashlib.sha256(canonicalize_json(seq17_source)).hexdigest()
        assert recomputed == SEQ17_PAYLOAD_SHA256
        assert seq17_signed["payload_sha256"] == SEQ17_PAYLOAD_SHA256
        assert canonicalize_json(seq17_signed["payload"]) == canonicalize_json(seq17_source)


# ---------------------------------------------------------------------------
# FRESHNESS SHAPE
# ---------------------------------------------------------------------------


class TestFreshnessShape:
    def test_exactly_eighteen_official_portal_records(
        self, seq17_source: dict[str, Any]
    ) -> None:
        portals = [
            r for r in seq17_source["source_records"] if r["authority_type"] == PORTAL_AUTHORITY
        ]
        assert len(portals) == 18

    def test_all_portal_records_carry_the_same_fresh_stamp(
        self, seq17_source: dict[str, Any]
    ) -> None:
        portals = [
            r for r in seq17_source["source_records"] if r["authority_type"] == PORTAL_AUTHORITY
        ]
        assert len(portals) == 18
        verified_at_values = {r["verified_at"] for r in portals}
        verified_by_values = {r["verified_by"] for r in portals}
        assert verified_at_values == {EXPECTED_VERIFIED_AT}
        assert verified_at_values == {RESTAMP_VERIFIED_AT}
        assert len(verified_by_values) == 1

    def test_freshness_policy_max_age_seconds_is_exactly_the_two_known_windows(
        self, seq17_source: dict[str, Any]
    ) -> None:
        windows = {
            record["freshness_policy"]["max_age_seconds"]
            for record in seq17_source["source_records"]
            if record.get("freshness_policy") is not None
        }
        assert windows == {604_800, 31_536_000}

    def test_payload_parses_as_rule_pack_payload(self, seq17_source: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq17_source)
        assert payload.sequence == 17


# ---------------------------------------------------------------------------
# THE GUARD — assert_only_expected_changes, guilt AND innocence
# ---------------------------------------------------------------------------

# WHY THIS IS TESTED THROUGH THE EXTRACTED FUNCTION, NEVER THROUGH fold():
# fold()'s FIRST act is to recompute the JCS digest of its `seq16` argument
# and compare it against the pinned SEQ16_PAYLOAD_SHA256 — any mutation
# applied to fold()'s INPUT changes that digest and aborts there, before
# assert_only_expected_changes ever runs. A guilt test written against
# fold() would therefore go green for every single mutation below, and it
# would be proving that the chain-anchor digest check works (a different,
# already-covered guard) — not that THIS guard catches the mutation. That
# is exactly how the fold module's own docstring says the first attempt at
# this test came back green while testing nothing. Testing
# assert_only_expected_changes directly, on hand-mutated before/after
# pairs, is the only way to give it real guilt cases.


def _seq17_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """An unmutated (before, after) pair derived from the real on-disk
    seq-17 source, deep-copied so mutating one side never touches the
    other. Used as both the innocence fixture and the base for every guilt
    mutation below."""

    before = _read_json(_SEQ17_SOURCE_PATH)
    after = copy.deepcopy(before)
    return before, after


def _first_portal_record(payload: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in payload["source_records"] if r["authority_type"] == PORTAL_AUTHORITY)


def _first_non_portal_record(payload: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in payload["source_records"] if r["authority_type"] != PORTAL_AUTHORITY)


class TestGuardInnocence:
    def test_the_unmutated_pair_passes(self) -> None:
        before, after = _seq17_pair()
        assert_only_expected_changes(before, after)  # must not raise


class TestGuardGuilt:
    def test_disallowed_top_level_key_change_is_rejected(self) -> None:
        """``jurisdiction`` is not in the fold's allowed-change set — a
        restamp must never touch it."""
        before, after = _seq17_pair()
        assert after["jurisdiction"] == "ID"
        after["jurisdiction"] = "XX"
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_engine_min_version_change_is_rejected(self) -> None:
        before, after = _seq17_pair()
        after["engine_min_version"] = "9.9.9"
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_version_change_is_rejected(self) -> None:
        before, after = _seq17_pair()
        after["version"] = "2099.1.1"
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_content_sha256_change_on_a_portal_record_is_rejected(self) -> None:
        """The one field whose drift would pair a fresh attestation with a
        stale fingerprint — must never move, even on the restamped set."""
        before, after = _seq17_pair()
        target = _first_portal_record(after)
        target["content_sha256"] = "0" * 64
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_verified_at_change_on_a_non_portal_record_is_rejected(self) -> None:
        """Only ``OFFICIAL_PORTAL`` records may move their stamp — a
        non-portal record's ``verified_at`` is frozen, same as everything
        else about it."""
        before, after = _seq17_pair()
        target = _first_non_portal_record(after)
        target["verified_at"] = "2099-01-01T00:00:00Z"
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_new_top_level_key_is_rejected(self) -> None:
        before, after = _seq17_pair()
        after["unexpected_new_key"] = True
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_removed_source_record_is_rejected(self) -> None:
        before, after = _seq17_pair()
        assert len(after["source_records"]) > 1
        after["source_records"] = list(after["source_records"])[:-1]
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_new_field_on_a_source_record_is_rejected(self) -> None:
        before, after = _seq17_pair()
        target = _first_portal_record(after)
        target["unexpected_new_field"] = "surprise"
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)
