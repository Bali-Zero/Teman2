"""Unit tests for the activate_pack ops CLI (pure parts).

Uses the real signed pack fixture on main (rulepack-prod-001.signed.json)
for the field-mapping test — the exact document the operator will point
the tool at. No database, no network: the DB-touching path is the dry-run
(default), which these tests exercise end-to-end minus the final print.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.visa_engine import activate_pack
from backend.scripts.visa_engine.activate_pack import (
    _assert_production_separation,
    _b64url_nopad_decode,
    _build_insert_kwargs,
    _validate_token,
)

PACK_PATH = (
    Path(__file__).resolve().parents[4]
    / "backend/services/visa_engine/contracts/packs/rulepack-prod-001.signed.json"
)

PACK_ID = "446ee4ee-1bae-5b9e-b361-ea26f2ab5dd9"
PAYLOAD_SHA256_HEX = "47a97c32045c1f58798c8661473c265decbab5d8427e0e606406a29402db5fda"


class _FakeVerified:
    """Minimal stand-in for bundle.VerifiedRulePack (only the field the
    mapper reads)."""

    def __init__(self, payload_sha256: bytes) -> None:
        self.payload_sha256 = payload_sha256


def _load_bundle() -> dict:
    return json.loads(PACK_PATH.read_text())


def test_build_insert_kwargs_maps_signed_bundle_fields() -> None:
    bundle = _load_bundle()
    verified = _FakeVerified(bytes.fromhex(PAYLOAD_SHA256_HEX))
    kwargs = _build_insert_kwargs(bundle, verified)

    assert str(kwargs["id"]) == PACK_ID
    assert kwargs["environment"] == "PRODUCTION"
    assert kwargs["sequence"] == 1
    assert kwargs["pack_version"] == bundle["payload"]["version"]
    assert kwargs["engine_contract_version"] == "1.0.0"
    assert kwargs["engine_min_version"] == "1.0.0"
    assert kwargs["engine_max_version"] == "1.0.0"

    legal = kwargs["legal_period"]
    assert legal.lower.tzinfo is not None
    assert legal.lower_inc is True
    assert legal.upper_inc is False
    assert legal.upper is None  # valid_period.to is null in this pack

    assert kwargs["protected_header"]["kid"] == "prod-2026-07-1"
    assert kwargs["payload"]["rule_pack_id"] == PACK_ID
    assert kwargs["payload_sha256"] == bytes.fromhex(PAYLOAD_SHA256_HEX)
    assert kwargs["previous_payload_sha256"] is None  # first pack
    assert len(kwargs["signature"]) == 64  # Ed25519 raw signature bytes
    assert kwargs["signing_key_id"] == "prod-2026-07-1"
    assert kwargs["signed_at"].tzinfo is not None


def test_validate_token_accepts_opaque_tokens() -> None:
    assert _validate_token("actor", "operator.zero-2026-07") == "operator.zero-2026-07"
    assert _validate_token("reason", "w2-first-prod-pack") == "w2-first-prod-pack"


@pytest.mark.parametrize(
    "bad",
    ["", "free text with spaces", "under_score_ok?no", "x" * 121, "emoji-🚫"],
)
def test_validate_token_rejects_bad_values(bad: str) -> None:
    with pytest.raises(SystemExit):
        _validate_token("actor", bad)


def test_b64url_nopad_decode_roundtrip() -> None:
    raw = b"\x01\x02\x03\x04" * 8
    import base64

    encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    assert _b64url_nopad_decode(encoded) == raw


@pytest.mark.asyncio
async def test_production_activation_rejects_one_combined_database_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def same_identity(_pool: object) -> tuple[str, bool]:
        return "combined_operator", False

    monkeypatch.setattr(activate_pack, "_database_identity", same_identity)
    with pytest.raises(RuntimeError, match="distinct database logins"):
        await _assert_production_separation(object(), object())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_production_activation_rejects_superuser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identities = iter((("pack_writer", True), ("activator", False)))

    async def next_identity(_pool: object) -> tuple[str, bool]:
        return next(identities)

    monkeypatch.setattr(activate_pack, "_database_identity", next_identity)
    with pytest.raises(RuntimeError, match="refuses superuser"):
        await _assert_production_separation(object(), object())  # type: ignore[arg-type]
