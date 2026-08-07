"""Unit tests for the activate_pack ops CLI (pure parts).

Uses the real signed pack fixture on main (rulepack-prod-001.signed.json)
for the field-mapping test — the exact document the operator will point
the tool at. No database, no network: the DB-touching path is the dry-run
(default), which these tests exercise end-to-end minus the final print.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize(
    "content",
    [
        '{"protected": {}, "protected": {}}',
        '{"payload": {"sequence": 2, "sequence": 3}}',
        '{"payload": {"sequence": NaN}}',
    ],
)
def test_activate_pack_strict_json_rejects_ambiguous_documents(
    tmp_path: Path,
    content: str,
) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key|non-finite JSON number"):
        activate_pack._load_strict_json(bundle)


def test_activate_pack_strict_json_rejects_oversized_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.json"
    bundle.write_bytes(b" " * (activate_pack.MAX_SIGNED_BUNDLE_BYTES + 1))
    with pytest.raises(ValueError, match="2 MiB"):
        activate_pack._load_strict_json(bundle)


class _CapabilityConnection:
    def __init__(
        self,
        *,
        identity: str,
        table_privileges: set[tuple[str, str]],
        function_privileges: set[str],
        superuser: bool = False,
        session_identity: str | None = None,
        server_version_num: int = 150000,
    ) -> None:
        self.identity = identity
        self.session_identity = session_identity or identity
        self.table_privileges = table_privileges
        self.function_privileges = function_privileges
        self.superuser = superuser
        self.server_version_num = server_version_num

    async def fetchrow(self, query: str) -> dict[str, Any]:
        assert "session_user::text AS session_user" in query
        assert "current_user::text" in query
        return {"session_user": self.session_identity, "is_superuser": self.superuser}

    async def fetchval(self, query: str, *args: object) -> object:
        if "server_version_num" in query:
            return self.server_version_num
        if "has_table_privilege" in query:
            return (str(args[0]), str(args[1])) in self.table_privileges
        if "has_function_privilege" in query:
            return str(args[0]) in self.function_privileges
        raise AssertionError(f"unexpected capability query: {query}")


class _CapabilityAcquire:
    def __init__(self, connection: _CapabilityConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _CapabilityConnection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class _CapabilityPool:
    def __init__(self, connection: _CapabilityConnection) -> None:
        self.connection = connection

    def acquire(self) -> _CapabilityAcquire:
        return _CapabilityAcquire(self.connection)


def _writer_connection(
    *,
    activation_capabilities: set[str] | None = None,
) -> _CapabilityConnection:
    return _CapabilityConnection(
        identity="pack_writer_login",
        table_privileges={
            ("public.visa_rule_packs", "SELECT"),
            ("public.visa_rule_packs", "INSERT"),
        },
        function_privileges=activation_capabilities or set(),
    )


def _activation_connection(
    *,
    table_privileges: set[tuple[str, str]] | None = None,
) -> _CapabilityConnection:
    return _CapabilityConnection(
        identity="activation_login",
        table_privileges=table_privileges or set(),
        function_privileges={activate_pack.ACTIVATION_FUNCTION},
    )


@pytest.mark.asyncio
async def test_production_separation_accepts_exact_capabilities() -> None:
    await _assert_production_separation(
        _CapabilityPool(_writer_connection()),  # type: ignore[arg-type]
        _CapabilityPool(_activation_connection()),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_production_separation_rejects_replace_capability_or_direct_ledger_access() -> None:
    with pytest.raises(RuntimeError, match="pack writer"):
        await _assert_production_separation(
            _CapabilityPool(  # type: ignore[arg-type]
                _writer_connection(activation_capabilities={activate_pack.ACTIVATION_SET_FUNCTION})
            ),
            _CapabilityPool(_activation_connection()),  # type: ignore[arg-type]
        )

    with pytest.raises(RuntimeError, match="activation identity"):
        await _assert_production_separation(
            _CapabilityPool(_writer_connection()),  # type: ignore[arg-type]
            _CapabilityPool(  # type: ignore[arg-type]
                _activation_connection(
                    table_privileges={("public.visa_ruleset_activations", "INSERT")}
                )
            ),
        )


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
async def test_production_activation_rejects_one_login_using_two_set_roles() -> None:
    writer = _writer_connection()
    writer.session_identity = "shared_login"
    activator = _activation_connection()
    activator.session_identity = "shared_login"

    with pytest.raises(RuntimeError, match="distinct database logins"):
        await _assert_production_separation(
            _CapabilityPool(writer),  # type: ignore[arg-type]
            _CapabilityPool(activator),  # type: ignore[arg-type]
        )


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
