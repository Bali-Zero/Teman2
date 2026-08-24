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
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Any

import rfc8785
from pydantic import BaseModel

from research_os.version import CONTRACT_VERSION

SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
_SHA256_HEX_RE = re.compile(SHA256_HEX_PATTERN)
# Recognizes a UTC-instant string in either wire-valid spelling CONTRACTS.md
# sec 3's UtcDateTime accepts (trailing "Z" or "+00:00"), with any fractional-
# second digit count. Disjoint, non-nested quantifiers over fixed-width digit
# classes -- linear time, no possessive/atomic constructs needed.
_UTC_TIMESTAMP_HASH_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)$")
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


def _fold_utc_timestamp_spelling(value: Any) -> Any:
    """Fold every wire-valid spelling of a UTC instant to one hashable form.

    ``UtcDateTime`` accepts both a trailing ``Z`` and a trailing ``+00:00``
    for the same instant, and places no constraint on fractional-second
    digit count -- "...T00:00:00Z" and "...T00:00:00.500Z" and
    "...T00:00:00.500000Z" are all independently wire-valid. RFC 8785 (the
    JCS step in `canonicalize`, below) fixes JSON *structure* only; it has no
    opinion on datetime *semantics*, so two of these spellings survive JCS as
    different byte strings and hash differently -- breaking CONTRACTS.md
    sec 2's "the hash procedure must be identical in every implementation"
    promise for the single most common field type in the contract family.
    Confirmed reproducible on both implemented foundation contracts
    (object_successor_edge, revocation_receipt): a document rewritten from
    ``Z`` to ``+00:00`` and re-hashed via this raw-dict path fails model
    validation with ``object_hash_mismatch``, because the model path
    re-renders through pydantic's ``model_dump(mode="json")``, which always
    normalizes to ``Z`` with 0-or-6 fractional digits.

    This folds every UTC-timestamp-shaped string to the exact rendering
    Python's own ``datetime.isoformat()`` produces for a UTC value (``Z``
    suffix; fractional seconds omitted when exactly zero, else zero-padded
    to 6 digits) before hashing, on BOTH the model path and the raw-dict
    path, so a document's hash depends on the instant it names, never the
    spelling a particular producer sent. Every other-language implementation
    computing this same `object_hash` independently (a pre-submission
    self-check, a content-addressed store) must apply this identical rule --
    see CONTRACTS.md sec 2 follow-up amendment tracked alongside this fix.

    Deliberately narrow, not a general timezone/format normalizer: only the
    two spellings the frozen schema itself declares equivalent are folded.
    A non-UTC offset, or a separator pydantic's parser tolerates but RFC3339
    does not (e.g. a space instead of "T"), does not match and is passed
    through unchanged -- those are schema-conformance gaps for
    `_utc_datetime`/`_UTC_OFFSET_PATTERN` to close, not a hashing concern.
    """

    if isinstance(value, str) and _UTC_TIMESTAMP_HASH_RE.match(value):
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
        microsecond = parsed.microsecond
        base = parsed.strftime("%Y-%m-%dT%H:%M:%S")
        return f"{base}.{microsecond:06d}Z" if microsecond else f"{base}Z"
    if isinstance(value, Mapping):
        return {key: _fold_utc_timestamp_spelling(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_fold_utc_timestamp_spelling(item) for item in value]
    return value


def canonicalize(value: Any) -> bytes:
    """Serialize a JSON-compatible value with RFC 8785 JCS semantics."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_unset=True)
    value = _fold_utc_timestamp_spelling(value)
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
