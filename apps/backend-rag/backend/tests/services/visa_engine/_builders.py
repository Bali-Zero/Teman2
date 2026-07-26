"""Shared plain-dict builders for ``bundle.py`` (``test_bundle_*.py``) tests.

Not collected as tests (no ``test_`` prefix / no test functions). Every
builder returns a plain JSON-safe ``dict`` — the same shape a signer/author
would hand the engine on the wire — so ``bundle.py``'s trust-boundary
functions (which operate on raw wire dicts, never on ``models.py`` objects
directly, see that module's docstring) can canonicalize/sign/tamper at
exactly the layer the tests care about.

Deliberately separate from ``conftest.py``: this package's other test files
(``test_rulepack_compiler.py`` etc.) build real ``models.py`` Pydantic
objects via ``conftest.py``'s fixtures — appropriate there, since those
tests exercise Pydantic-construction-time validation. ``bundle.py``'s tests
need the OPPOSITE: raw dicts that exist BEFORE any Pydantic parsing, so a
"guilt" test can tamper with exactly one wire byte/field without an
intervening model round-trip silently normalizing it away.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.services.visa_engine.bundle import canonicalize_json

UTC_NOW = "2026-07-18T00:00:00Z"

_SIGNING_DOMAIN = b"balizero.visa-rulepack.v1"


def new_uuid() -> str:
    return str(uuid.uuid4())


def sha256_hex(seed: str = "a") -> str:
    return (seed * 64)[:64]


def time_range(*, start: str = UTC_NOW, end: str | None = None) -> dict[str, Any]:
    return {"from": start, "to": end}


def source_record(*, source_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_record_id": source_id or new_uuid(),
        "source_key": "test-source",
        "version": 1,
        "authority_type": "PRIMARY_LAW",
        "status": "VERIFIED",
        "jurisdiction": "ID",
        "title": "Test Source",
        "publisher": "Test Publisher",
        "canonical_url": "https://example.com/source",
        "language": "en",
        "document_number": None,
        "locators": [],
        "content_sha256": sha256_hex("a"),
        "legal_period": time_range(),
        "recorded_period": time_range(),
        "retrieved_at": UTC_NOW,
        "verified_at": UTC_NOW,
        "verified_by": "test-verifier",
        "supersedes_source_record_id": None,
    }
    record.update(overrides)
    return record


def product(*, source_id: str, product_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    prod: dict[str, Any] = {
        "product_version_id": product_id or new_uuid(),
        "product_code": "C1",
        "legacy_codes": [],
        "legacy_slugs": [],
        "names": {"id": "Visa Turis", "en": "Tourist Visa"},
        "category": "SHORT_STAY",
        "status": "ACTIVE",
        "valid_period": time_range(),
        "covered_purposes": ["TOURISM"],
        "prohibited_activities": [],
        "sponsor_types": ["NONE"],
        "entry_policy": {"entry_count": "SINGLE"},
        "stay_policy": {"kind": "FIXED_DAYS", "minimum_days": 1, "maximum_days": 30},
        "extension_policy": {"allowed": True, "maximum_extensions": 1, "days_per_extension": 30},
        "clock_policy": {"available": False, "anchor": "NOT_APPLICABLE", "checkpoints": []},
        "pricing_key": {"category": "single_entry_visas", "item_key": "c1_tourist"},
        "source_refs": [source_id],
        "public_catalog": True,
    }
    prod.update(overrides)
    return prod


def rule(
    *,
    rule_id: str,
    stage: str,
    scope: str,
    when: dict[str, Any],
    effect: dict[str, Any],
    source_id: str,
    required_facts: list[str] | None = None,
    priority: int = 100,
    on_unknown: str = "NEEDS_INPUT",
    product_version_ids: list[str] | None = None,
    safety_critical: bool = False,
    **overrides: Any,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "rule_id": rule_id,
        "stage": stage,
        "scope": scope,
        "priority": priority,
        "valid_period": time_range(),
        "when": when,
        "effect": effect,
        "on_unknown": on_unknown,
        "required_facts": required_facts or [],
        "source_refs": [source_id],
        "explanation_key": f"{rule_id}-explanation",
        "safety_critical": safety_critical,
    }
    if scope == "PRODUCTS":
        r["product_version_ids"] = product_version_ids or []
    r.update(overrides)
    return r


def rule_pack_payload(
    *,
    rules: list[dict[str, Any]],
    products: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    sequence: int = 1,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_pack_id": new_uuid(),
        "sequence": sequence,
        "version": "1.0.0",
        "environment": "TEST",
        "jurisdiction": "ID",
        "decision_domain": "IMMIGRATION_VISA",
        "engine_contract_version": "1.0.0",
        "engine_min_version": "1.0.0",
        "engine_max_version": "1.0.0",
        "valid_period": time_range(),
        "created_at": UTC_NOW,
        "created_by": "test-author",
        "previous_payload_sha256": None if sequence == 1 else sha256_hex("d"),
        "rollback_of_payload_sha256": None,
        "hit_policy": {
            "hard_filter": "COLLECT_ALL",
            "eligibility": "COVER_ALL_DECLARED_PURPOSES",
            "human_review": "COLLECT_ALL",
            "ranking": "SUM_TRUE_INTEGER_WEIGHTS",
        },
        "source_records": source_records,
        "products": products,
        "rules": rules,
    }
    payload.update(overrides)
    return payload


def rule_pack_envelope(payload: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "canonicalization": "RFC8785",
        "protected": {
            "domain": "balizero.visa-rulepack.v1",
            "alg": "Ed25519",
            "kid": "test-key-1",
            "signed_at": UTC_NOW,
            "schema_version": "1.0.0",
            "environment": payload["environment"],
        },
        "payload": payload,
        "payload_sha256": sha256_hex("b"),
        "signature": "c" * 86,
    }
    envelope.update(overrides)
    return envelope


def minimal_valid_envelope() -> dict[str, Any]:
    """One GLOBAL hard-filter rule, one PRODUCTS eligibility rule, one GLOBAL
    ranking rule, one product, one source record — small but exercises every
    stage/effect pairing."""

    source_id = new_uuid()
    product_id = new_uuid()
    src = source_record(source_id=source_id)
    prod = product(product_id=product_id, source_id=source_id)

    hard_filter = rule(
        rule_id="hf-overstay",
        stage="HARD_FILTER",
        scope="GLOBAL",
        when={"op": "gt", "fact": "immigration.overstay_days", "value": 60},
        effect={"type": "EXCLUDE", "reason_code": "OVERSTAY_TOO_LONG"},
        source_id=source_id,
        required_facts=["immigration.overstay_days"],
        safety_critical=True,
    )
    eligibility = rule(
        rule_id="el-tourism",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={
            "op": "all",
            "args": [
                {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
                {"op": "lte", "fact": "intent.stay_days", "value": 30},
            ],
        },
        effect={
            "type": "SUPPORT",
            "reason_code": "TOURISM_SUPPORTED",
            "covered_purposes": ["TOURISM"],
        },
        source_id=source_id,
        required_facts=["intent.purposes", "intent.stay_days"],
    )
    ranking = rule(
        rule_id="rank-budget",
        stage="RANKING",
        scope="GLOBAL",
        when={"op": "known", "fact": "commercial.wants_quote"},
        effect={"type": "ADD_SCORE", "reason_code": "WANTS_QUOTE_BOOST", "points": 5},
        source_id=source_id,
        required_facts=["commercial.wants_quote"],
        on_unknown="NO_EFFECT",
    )

    payload = rule_pack_payload(
        rules=[hard_filter, eligibility, ranking], products=[prod], source_records=[src]
    )
    return rule_pack_envelope(payload)


# --- bundle.py (Ed25519 signing) test-only helpers --------------------------
#
# These generate EPHEMERAL Ed25519 keys in-fixture to produce signed test
# envelopes — a throwaway test key, never persisted, never the real offline
# signing ceremony (that stays entirely out of scope by design — FIREBREAK,
# see bundle.py's module docstring).


def ephemeral_ed25519_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def ed25519_public_key_b64url(public_key: Ed25519PublicKey) -> str:
    """43-char base64url (no padding) raw Ed25519 public key — the shape
    ``StaticTrustStore.from_env`` expects."""

    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sign_rule_pack_envelope(
    payload: dict[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    kid: str = "test-key-1",
    signed_at: str = UTC_NOW,
) -> dict[str, Any]:
    """Build a fully, REALLY signed RulePack envelope dict from a payload
    dict, independently re-deriving the spec §3 signing-input construction
    (rather than importing ``bundle.py``'s private helper) so this fixture
    doubles as a cross-check on the production signing-input formula::

        signed_bytes =
            UTF8("balizero.visa-rulepack.v1")
            || 0x00 || JCS(protected) || 0x00 || JCS(payload)
    """

    protected: dict[str, Any] = {
        "domain": "balizero.visa-rulepack.v1",
        "alg": "Ed25519",
        "kid": kid,
        "signed_at": signed_at,
        "schema_version": "1.0.0",
        "environment": payload["environment"],
    }
    protected_bytes = canonicalize_json(protected)
    payload_bytes = canonicalize_json(payload)
    payload_sha256 = hashlib.sha256(payload_bytes).digest()

    signed_bytes = _SIGNING_DOMAIN + b"\x00" + protected_bytes + b"\x00" + payload_bytes
    signature = private_key.sign(signed_bytes)
    signature_b64url = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")

    return {
        "canonicalization": "RFC8785",
        "protected": protected,
        "payload": payload,
        "payload_sha256": payload_sha256.hex(),
        "signature": signature_b64url,
    }
