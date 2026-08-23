"""RFC 8785 canonicalization and frozen SHA-256 wire rules.

``research-os/v1.0.0`` uses presence-preserving null semantics (option b):
an absent Pydantic field is omitted, while a field explicitly set to ``None``
is serialized as JSON ``null``. Mapping inputs already preserve that distinction.
Only the versioned hash-omission fields below are removed from a present wire
object; producers in every language must implement the same rule.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from hashlib import sha256
from types import MappingProxyType
from typing import Any

import rfc8785
from pydantic import BaseModel

from research_os.version import CONTRACT_VERSION

SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
_SHA256_HEX_RE = re.compile(SHA256_HEX_PATTERN)
TRANSPORT_METADATA_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        # v1.0.0 marks no field as transport metadata. Adding one changes
        # canonical object identity and therefore requires a MAJOR version
        # under CONTRACTS.md rule 1.10.
        CONTRACT_VERSION: frozenset(),
    }
)
HASH_OMISSION_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {CONTRACT_VERSION: frozenset({"object_hash"}) | TRANSPORT_METADATA_FIELDS[CONTRACT_VERSION]}
)


class CanonicalizationError(ValueError):
    """A value at the Research OS trust boundary is not JCS-canonicalizable."""


class HashFormatError(ValueError):
    """A canonical SHA-256 value violates the lowercase unprefixed wire rule."""


def canonicalize(value: Any) -> bytes:
    """Serialize a JSON-compatible value with RFC 8785 JCS semantics."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_unset=True)
    try:
        return rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as exc:
        raise CanonicalizationError(f"value is not JCS-canonicalizable: {exc}") from exc


def _contract_version_from_object(obj: Mapping[str, Any]) -> str:
    version = obj.get("contract_version")
    if not isinstance(version, str):
        raise ValueError("object must contain a string contract_version")
    if version not in HASH_OMISSION_FIELDS:
        raise ValueError(f"unsupported hash omission contract version: {version!r}")
    return version


def object_hash(obj: Mapping[str, Any] | BaseModel) -> str:
    """Hash an object using the omission set selected by its contract version."""

    wire_object = (
        obj.model_dump(mode="json", exclude_unset=True) if isinstance(obj, BaseModel) else dict(obj)
    )
    contract_version = _contract_version_from_object(wire_object)
    omission_fields = HASH_OMISSION_FIELDS[contract_version]
    hashable_object = {
        key: value for key, value in wire_object.items() if key not in omission_fields
    }
    return sha256(canonicalize(hashable_object)).hexdigest()


def validate_sha256_hex(value: str) -> str:
    """Validate and return a canonical lowercase, unprefixed SHA-256 value."""

    if _SHA256_HEX_RE.fullmatch(value) is None:
        raise HashFormatError(f"invalid canonical SHA-256 value: {value!r}")
    return value
