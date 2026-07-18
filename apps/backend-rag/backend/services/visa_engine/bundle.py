"""Ed25519 signature verification + anti-rollback bundle trust (spec §3).

This module is the ONLY place in the engine that trusts a signed
``RulePack`` envelope. It never signs anything — the Ed25519 signing key
exists only in the offline signing environment (§3), and this module ships
no ``sign_pack.py`` script (FIREBREAK: key generation/registration is the
operator's ceremony, never autonomous code). Tests MAY generate ephemeral
Ed25519 keys in-fixture to produce signed fixtures; that is a throwaway test
key, not a ceremony.

Two independent responsibilities live here:

* **Cryptographic verification** (:func:`verify_rule_pack`) — RFC 8785 JCS
  canonicalization (:func:`canonicalize_json`), the exact signing-input
  construction from spec §3, Ed25519 verification against a pinned
  :class:`TrustStore`, and the ``payload_sha256`` self-consistency check.
* **Anti-rollback activation gating** (:func:`validate_activation`) — a
  PURE function (no I/O, no persistence) enforcing the spec §3 rejection
  list that is expressible without a database: sequence must advance,
  ``previous_payload_sha256`` must chain to the current bundle, environment
  must match, engine version must be compatible. Legal-period-vs-activation-
  window and jurisdiction/domain checks are deliberately NOT implemented
  here — jurisdiction (``"ID"``) and domain (``"IMMIGRATION_VISA"``) are
  ``Literal``-pinned in ``RulePackPayload``/``ProtectedHeader`` already, so
  a mismatch is schema-structurally impossible for any pack that reached
  this function; the activation-window/legal-period check needs the
  "what's the current effective moment for activation" context that only
  the (out-of-scope-for-this-module) persistence layer (PR4) has.

Runtime never reads a private key. :class:`StaticTrustStore` is built from
explicit :class:`TrustedSigningKey` instances supplied at construction, or
from base64url-encoded raw Ed25519 public keys in an environment variable
via :meth:`StaticTrustStore.from_env` — no filesystem key reads in the
FastAPI process, and a rule pack can never supply its own trusted key (the
trust store is always injected by the caller, never derived from
``raw_envelope``).

PR2b adaptation note (2026-07-18): this module was first built against an
earlier, since-discarded ``models.py`` generation (the "B" API — a
different, now-superseded PR1 draft with e.g. ``UtcDateTime`` as a bare
validated string and ``PurposeEnum``/``KnownDate(value: date)`` instead of
this package's ``VisaPurpose``/``IsoDate``-pattern strings). The port to
this package's actual API (the "A" generation — ``models.py`` with
``RulePack``/JSON Schema contracts committed under ``contracts/``, no
``_types.py``) required ZERO changes to the trust-boundary logic itself:
``verify_rule_pack``/``validate_activation`` operate exclusively on raw
JSON-safe wire dicts (``Mapping[str, JsonValue]``) and datetime objects
already parsed by the caller — never on any of ``models.py``'s internal
per-fact-shape classes — and the signed envelope's own top-level shape
(``canonicalization``/``protected``/``payload``/``payload_sha256``/
``signature``, and ``ProtectedHeader``'s ``domain``/``alg``/``kid``/
``signed_at``/``schema_version``/``environment``) is identical across both
generations. The two adaptations that WERE needed: (1) ``JsonValue`` has no
importable home in this package (the discarded generation defined it in
``fact_registry.py``; this generation's ``fact_registry.py`` does not) — it
is now defined locally, just below; (2) the packaged JSON Schema contract
lives at ``contracts/contract.schema.json`` in this generation (a static,
committed, hand-reviewed file — see ``schema_export.py``'s and
``test_schema_contracts.py``'s docstrings), not a ``schemas/`` directory
generated ad hoc.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol, TypeAlias

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError as PydanticValidationError

from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import ProtectedHeader, RulePack, RulePackPayload

logger = logging.getLogger(__name__)

#: A raw, JSON-safe value — exactly what a wire envelope is made of before
#: any Pydantic parsing happens. Defined locally (no shared home elsewhere in
#: this package — see module docstring's PR2b adaptation note).
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

_SIGNING_DOMAIN = b"balizero.visa-rulepack.v1"
_SCHEMA_VERSION = "1.0.0"
_PRODUCTION_ENVIRONMENT = "PRODUCTION"
_UNSIGNED_DEV_KID = "UNSIGNED-DEV"
_UNSIGNED_DEV_SIGNATURE = "0" * 86  # matches Identifier-shaped signature pattern, never verified

#: Clock-skew allowance for `verify_rule_pack`'s future-dating guard
#: (3-seat verify FIX-NOW #3): a `signed_at` more than this far ahead of
#: `observed_at` is rejected. Small and fixed (not configurable) — this is
#: a defense against a pack whose declared signing instant is implausibly
#: in the future (clock skew between the signer and this process should
#: never legitimately exceed a few minutes), not a business-tunable knob.
_SIGNED_AT_FUTURE_TOLERANCE = timedelta(minutes=5)

ALLOW_UNSIGNED_ENV_VAR = "VISA_ENGINE_ALLOW_UNSIGNED_PACKS"
TRUST_STORE_KEYS_ENV_VAR = "VISA_ENGINE_TRUST_STORE_KEYS_JSON"

#: Static, committed, hand-reviewed schema contract (see
#: ``schema_export.py``'s and ``test_schema_contracts.py``'s docstrings for
#: why this directory is the reviewed ground truth, not a build artifact).
_CONTRACTS_DIR = Path(__file__).parent / "contracts"
_CONTRACT_SCHEMA_PATH = _CONTRACTS_DIR / "contract.schema.json"

_BASE64URL_UNPADDED_ALPHABET_RE = re.compile(r"^[A-Za-z0-9_-]*$")
"""The unpadded base64url alphabet, exactly (RFC 4648 §5): letters, digits,
``-``, ``_``. Deliberately excludes standard-base64's ``+``/``/`` — those
must be REJECTED, not silently accepted, everywhere this module decodes
base64url (``base64.urlsafe_b64decode`` runs with default ``validate=False``,
which only translates ``-``/``_`` and passes everything else — including
standard ``+``/``/`` and any other character — straight through to the
decoder, which can then silently drop truly out-of-alphabet bytes rather
than reject them. For a trust-store public key, a single-character typo
decoding to 32 DIFFERENT-but-still-valid bytes means the WRONG Ed25519 key
gets silently pinned, with no error)."""


# --- TrustStore --------------------------------------------------------------


@dataclass(frozen=True)
class TrustedSigningKey:
    """One pinned Ed25519 public key entry in a :class:`TrustStore`.

    ``environment`` (3-seat verify FIX-NOW #4): the single environment this
    key is trusted to sign for (``"TEST"``/``"STAGING"``/``"PRODUCTION"``).
    NOT part of the FIREBREAK's "no key generation/registration" boundary —
    that firebreak is about never generating or auto-registering key
    MATERIAL; scoping a trust-store ENTRY (metadata about an already-issued
    key) to one environment is ordinary trust-store schema, the operator's
    own choice when pinning the key. Without this, a STAGING key that leaks
    or is reused could sign a PRODUCTION pack and `resolve()` would have no
    way to refuse it — the protected/payload environment cross-check in
    `verify_rule_pack` only proves internal consistency of the pack, never
    that THIS key is allowed to speak for THAT environment.
    """

    key_id: str
    public_key: Ed25519PublicKey
    valid_from: datetime
    valid_to: datetime | None
    revoked_at: datetime | None
    environment: str


class TrustStore(Protocol):
    """Resolves a ``(key_id, signed_at, environment)`` triple to a
    :class:`TrustedSigningKey`, or raises :class:`RulePackVerificationError`
    if the key is unknown, not scoped to ``environment``, not yet valid,
    expired, or revoked at ``signed_at``."""

    def resolve(
        self,
        *,
        key_id: str,
        signed_at: datetime,
        environment: str,
    ) -> TrustedSigningKey: ...


class StaticTrustStore:
    """A :class:`TrustStore` built from pinned public keys supplied at
    construction — the ONLY constructor path production code should use.
    Never reads a rule pack's own claimed key material; never reads the
    filesystem.

    Validity semantics (§3: "Trust entries include validity and revocation
    dates"):

    * ``valid_from`` is inclusive: a signature timestamped exactly at
      ``valid_from`` is accepted.
    * ``valid_to`` is inclusive-through (certificate-``NotAfter`` style): a
      signature timestamped exactly at ``valid_to`` is still accepted; only
      strictly after it is expired.
    * ``revoked_at`` takes effect immediately, inclusive: a signature
      timestamped AT or after ``revoked_at`` is rejected — unlike
      ``valid_to``, an emergency revocation cannot be assumed safe up to and
      including its own boundary instant.
    """

    def __init__(self, keys: Iterable[TrustedSigningKey]) -> None:
        by_id: dict[str, TrustedSigningKey] = {}
        for key in keys:
            if key.key_id in by_id:
                raise ValueError(f"duplicate key_id in trust store: {key.key_id!r}")
            by_id[key.key_id] = key
        self._keys = by_id

    def resolve(
        self,
        *,
        key_id: str,
        signed_at: datetime,
        environment: str,
    ) -> TrustedSigningKey:
        try:
            key = self._keys[key_id]
        except KeyError as exc:
            raise RulePackVerificationError(f"unknown signing key_id: {key_id!r}") from exc

        # Environment-scoped keys (3-seat verify FIX-NOW #4): a key pinned
        # for one environment must never be accepted as trusted for
        # another — this is independent of, and does not depend on,
        # verify_rule_pack's own protected/payload environment cross-check
        # (that check only proves the PACK is internally consistent about
        # which environment it claims; it says nothing about whether THIS
        # key is allowed to speak for that environment).
        if key.environment != environment:
            raise RulePackVerificationError(
                f"key {key_id!r} is scoped to environment {key.environment!r}, "
                f"cannot be trusted to sign for environment {environment!r}"
            )

        if signed_at < key.valid_from:
            raise RulePackVerificationError(
                f"key {key_id!r} is not yet valid at {signed_at.isoformat()!r} "
                f"(valid_from={key.valid_from.isoformat()!r})"
            )
        if key.valid_to is not None and signed_at > key.valid_to:
            raise RulePackVerificationError(
                f"key {key_id!r} expired at {signed_at.isoformat()!r} "
                f"(valid_to={key.valid_to.isoformat()!r})"
            )
        if key.revoked_at is not None and signed_at >= key.revoked_at:
            raise RulePackVerificationError(
                f"key {key_id!r} was revoked at {key.revoked_at.isoformat()!r}, "
                f"on or before signed_at={signed_at.isoformat()!r}"
            )
        return key

    @classmethod
    def from_env(cls, env_var: str = TRUST_STORE_KEYS_ENV_VAR) -> StaticTrustStore:
        """Build a trust store from a JSON array of pinned public keys in an
        environment variable — the only key-material source this process
        ever reads besides an explicit constructor call. Each entry:

        .. code-block:: json

            {
              "kid": "2026-07-prod-1",
              "public_key": "<43-char base64url raw Ed25519 public key, no padding>",
              "environment": "PRODUCTION",
              "valid_from": "2026-07-01T00:00:00Z",
              "valid_to": null,
              "revoked_at": null
            }

        ``environment`` (3-seat verify FIX-NOW #4) is REQUIRED on every
        entry — a key is pinned to speak for exactly one environment
        (``"TEST"``/``"STAGING"``/``"PRODUCTION"``); see
        :class:`TrustedSigningKey`'s docstring for why this is not a
        FIREBREAK violation.

        Raises :class:`RulePackVerificationError` if the variable is unset,
        not valid JSON, not a JSON array, or any entry is malformed. This
        method performs NO filesystem access — the key ceremony (generating
        and pinning the actual key material) is the operator's, offline.
        """

        raw = os.environ.get(env_var)
        if raw is None:
            raise RulePackVerificationError(
                f"environment variable {env_var!r} is not set — no trust store "
                "key material available"
            )
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RulePackVerificationError(
                f"environment variable {env_var!r} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(entries, list):
            raise RulePackVerificationError(
                f"environment variable {env_var!r} must decode to a JSON array, "
                f"got {type(entries).__name__!r}"
            )
        return cls(_trusted_key_from_env_entry(entry) for entry in entries)


def _trusted_key_from_env_entry(entry: object) -> TrustedSigningKey:
    if not isinstance(entry, Mapping):
        raise RulePackVerificationError(f"trust store entry is not a JSON object: {entry!r}")

    try:
        kid = entry["kid"]
        public_key_b64url = entry["public_key"]
        valid_from_raw = entry["valid_from"]
        # environment (3-seat verify FIX-NOW #4): required on every entry —
        # see TrustedSigningKey's and from_env's docstrings.
        environment = entry["environment"]
    except KeyError as exc:
        raise RulePackVerificationError(f"trust store entry missing required key: {exc}") from exc

    valid_to_raw = entry.get("valid_to")
    revoked_at_raw = entry.get("revoked_at")

    try:
        public_key_bytes = _decode_base64url_no_padding(public_key_b64url)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except (RulePackVerificationError, ValueError, TypeError) as exc:
        raise RulePackVerificationError(
            f"trust store entry {kid!r} has an invalid Ed25519 public key: {exc}"
        ) from exc

    return TrustedSigningKey(
        key_id=kid,
        public_key=public_key,
        valid_from=_parse_utc_datetime(valid_from_raw),
        valid_to=_parse_utc_datetime(valid_to_raw) if valid_to_raw is not None else None,
        revoked_at=_parse_utc_datetime(revoked_at_raw) if revoked_at_raw is not None else None,
        environment=environment,
    )


# --- Canonicalization ---------------------------------------------------------


def canonicalize_json(value: Mapping[str, JsonValue]) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) serialization of ``value``.

    Thin pass-through to the ``rfc8785`` library (Trail of Bits, spec §3) —
    deliberately NOT ``json.dumps(sort_keys=True)``, which does not
    normalize number formatting or property ordering per the ECMAScript
    ``JSON.stringify`` rules JCS requires. Any ``rfc8785.CanonicalizationError``
    (NaN/Infinity, lone surrogates, integers outside the safe JSON-number
    range) propagates unwrapped from THIS function — it stays a generic,
    honest JCS canonicalizer usable outside the trust boundary too (e.g. the
    test-only signing fixture in ``_builders.sign_rule_pack_envelope``,
    where a ``RulePackVerificationError`` would be the wrong error to see
    while *producing* a signature).

    Trust-boundary callers do NOT call this directly: ``verify_rule_pack``/
    ``_verify_unsigned_dev`` route every wire-object canonicalization
    through the private ``_canonicalize_wire_object`` wrapper below, which
    is what actually translates a ``CanonicalizationError`` into
    :class:`~backend.services.visa_engine.errors.RulePackVerificationError`
    — a wire string that is syntactically valid JSON (passes JSON Schema's
    unadorned ``type: string``, e.g. a lone UTF-16 surrogate) but that RFC
    8785 cannot serialize must never escape ``verify_rule_pack`` as a bare
    third-party exception.
    """

    return rfc8785.dumps(value)


def _canonicalize_wire_object(value: Mapping[str, JsonValue], *, label: str) -> bytes:
    """Canonicalize a signed-envelope wire sub-object (``"protected"`` or
    ``"payload"``) for the trust boundary, translating any RFC 8785
    canonicalization failure into the module's typed error contract.
    ``label`` names the sub-object in the raised message (``"protected"``/
    ``"payload"``) for diagnosability."""

    try:
        return canonicalize_json(value)
    except rfc8785.CanonicalizationError as exc:
        raise RulePackVerificationError(f"{label} is not JCS-canonicalizable: {exc}") from exc


def _build_signed_bytes(protected_bytes: bytes, payload_bytes: bytes) -> bytes:
    """Exact signing input per spec §3::

    signed_bytes =
        UTF8("balizero.visa-rulepack.v1")
        || 0x00
        || JCS(protected)
        || 0x00
        || JCS(payload)
    """

    return _SIGNING_DOMAIN + b"\x00" + protected_bytes + b"\x00" + payload_bytes


def _decode_base64url_no_padding(value: str) -> bytes:
    """Base64url-decode ``value``, which must carry NO padding characters —
    a correctly unpadded base64url string never contains ``=``. Used for
    both the RulePack ``signature`` field and trust-store public keys.

    Rejects, BEFORE ever calling the stdlib decoder, any character outside
    the unpadded base64url alphabet ``[A-Za-z0-9_-]`` — ``base64.
    urlsafe_b64decode`` alone runs with ``validate=False`` and would
    otherwise silently accept standard-base64 ``+``/``/`` or silently drop
    a truly out-of-alphabet byte, either of which decodes to different
    bytes than the caller's typo-free input intended (security-relevant
    for a trust-store public key: a one-character corruption must never
    quietly resolve to 32 different-but-still-valid bytes)."""

    if not isinstance(value, str):
        raise RulePackVerificationError(f"base64url value must be a string, got {value!r}")
    if "=" in value:
        raise RulePackVerificationError(f"base64url value must not be padded: {value!r}")
    if not _BASE64URL_UNPADDED_ALPHABET_RE.match(value):
        raise RulePackVerificationError(
            "base64url value contains a character outside the unpadded "
            f"base64url alphabet [A-Za-z0-9_-]: {value!r}"
        )
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (binascii.Error, ValueError) as exc:
        raise RulePackVerificationError(f"malformed base64url value {value!r}: {exc}") from exc


def _decode_signature(signature: str) -> bytes:
    raw = _decode_base64url_no_padding(signature)
    if len(raw) != 64:
        raise RulePackVerificationError(
            f"decoded signature has {len(raw)} bytes, expected 64 (Ed25519)"
        )
    return raw


def _parse_utc_datetime(value: str) -> datetime:
    """Parse a ``UtcDateTime`` wire string (``models.UtcDateTime``: ends in
    ``"Z"``) into an aware ``datetime``. By the time this is called on a
    signed pack's ``protected.signed_at``, the string has already been
    pattern-validated by the ``RulePack``/``ProtectedHeader`` Pydantic
    model — this is a defensive re-check for the (also-validated, but
    independently-typed) trust-store env entries."""

    if not isinstance(value, str) or not value.endswith("Z"):
        raise RulePackVerificationError(f"not a UTC date-time (must end in 'Z'): {value!r}")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RulePackVerificationError(f"not a valid date-time: {value!r}") from exc


def _format_utc_datetime(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    isoformatted = aware.astimezone(timezone.utc).isoformat()
    assert isoformatted.endswith("+00:00")
    return isoformatted[: -len("+00:00")] + "Z"


# --- JSON Schema validation ----------------------------------------------


@lru_cache(maxsize=1)
def _rule_pack_validator() -> Draft202012Validator:
    """A ``Draft202012Validator`` for the full signed ``RulePack`` envelope.

    ``contracts/contract.schema.json`` is fully self-contained (no external
    ``$ref`` — every ``$defs`` entry, including ``RulePack``, resolves within
    the one document), so this needs no external ``$ref`` registry: the
    packaged ``rule-pack.schema.json`` is itself just
    ``{"$ref": "contract.schema.json#/$defs/RulePack"}``, reproduced here by
    pointing straight at ``contract.schema.json``'s own ``$defs``.
    """

    contract = json.loads(_CONTRACT_SCHEMA_PATH.read_text())
    schema = {
        "$schema": contract["$schema"],
        "$id": contract["$id"],
        "$defs": contract["$defs"],
        "$ref": "#/$defs/RulePack",
    }
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_envelope_against_schema(raw_envelope: Mapping[str, JsonValue]) -> None:
    validator = _rule_pack_validator()
    errors = sorted(validator.iter_errors(raw_envelope), key=lambda e: list(e.path))
    if errors:
        rendered = "; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors)
        raise RulePackVerificationError(
            f"rule pack envelope failed JSON Schema validation: {rendered}"
        )


# --- Verification --------------------------------------------------------


def _snapshot_envelope(raw_envelope: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Read ``raw_envelope`` EXACTLY ONCE, at the trust boundary's entry
    point, into a plain, JSON round-tripped ``dict`` — every check
    downstream (schema validation, canonicalization, hashing, key
    resolution, ``model_validate``) reads only this snapshot, never the
    caller's original object again.

    Kills the entire TOCTOU class (3-seat verify FIX-NOW #2): a mutable or
    hostile ``Mapping`` whose ``.get()``/``__getitem__``/iteration answer
    differently across separate reads can otherwise show one value to an
    early check and a different one to a later check — the exact
    vulnerability FIX-NOW #1 patched one instance of (a stateful dict lying
    on its first ``.get("environment")`` call, telling the truth on the
    next). Snapshotting once, up front, removes the live object from the
    picture entirely: there is no second read left to diverge.

    ``json.loads(json.dumps(value))`` rather than a manual recursive walk:
    JSON round-tripping of dict/list/str/int/bool/None is byte-safe for JCS
    purposes (JCS's canonical form is defined over the JSON data model
    itself, not over Python object identity) — a legitimate wire envelope
    may only ever carry these JSON-primitive types to begin with, so the
    round-trip changes nothing a real signer could have meant.
    """

    try:
        return json.loads(json.dumps(raw_envelope))
    except (TypeError, ValueError) as exc:
        raise RulePackVerificationError(
            f"rule pack envelope is not a plain JSON-safe structure: {exc}"
        ) from exc


@dataclass(frozen=True)
class VerifiedRulePack:
    """A ``RulePack`` that has passed either full cryptographic
    verification, or the explicit non-PRODUCTION ``allow_unsigned`` dev
    override (:attr:`unsigned_dev` ``is True`` in that case only)."""

    pack: RulePack
    canonical_payload: bytes
    payload_sha256: bytes
    unsigned_dev: bool = False


def resolve_allow_unsigned_default(env_var: str = ALLOW_UNSIGNED_ENV_VAR) -> bool:
    """Resolve the ``allow_unsigned`` default from the environment, parsed
    STRICTLY: only a case-insensitive ``"true"`` or ``"1"`` enables it —
    missing, empty, whitespace-padded, or any other value (``"false"``,
    ``"0"``, ``"yes"``, ``" 1"``, ``"TRUE "``, ...) resolves to ``False``.
    No trimming: strict means exact (case-folded) match only, not
    "forgiving of stray whitespace" — a padded value is far more likely to
    be a copy-paste/quoting bug in whatever set the env var than deliberate
    intent, and this flag's failure mode (silently enabling unsigned packs)
    is exactly the one to fail closed on.

    Call this at the call site on every invocation that needs the default —
    NEVER cache its result at import time. The engine spec requires the
    flag to be re-resolved fresh per call (it can change between requests,
    e.g. under test with ``monkeypatch.setenv``, or via a live config flip
    without a process restart)."""

    raw = os.environ.get(env_var)
    if raw is None:
        return False
    return raw.lower() in ("true", "1")


def _has_signature(raw_envelope: Mapping[str, JsonValue]) -> bool:
    signature = raw_envelope.get("signature")
    return isinstance(signature, str) and signature != ""


def verify_rule_pack(
    raw_envelope: Mapping[str, JsonValue],
    *,
    trust_store: TrustStore,
    observed_at: datetime,
    allow_unsigned: bool = False,
) -> VerifiedRulePack:
    """Verify a raw rule-pack envelope and return a :class:`VerifiedRulePack`.

    Always raises :class:`RulePackVerificationError` (never a bare
    ``jsonschema`` / ``pydantic`` / ``cryptography`` exception) on any
    failure — schema violation, protected/payload environment mismatch,
    unknown/invalid/expired/revoked key, malformed signature, tampered
    payload, or ``payload_sha256`` mismatch.

    THE TRUST-BOUNDARY INVARIANT: the bytes the signature covers are derived
    from the LITERAL WIRE OBJECTS in ``raw_envelope["protected"]``/
    ``raw_envelope["payload"]`` — never from a Pydantic re-serialization.
    ``model_dump()`` can diverge byte-for-byte from the raw wire dict it was
    parsed from (e.g. a JSON Schema ``format: uuid`` field accepts any
    letter casing, but Pydantic's ``UUID`` type normalizes to lowercase on
    dump), which would silently reject a legitimately-signed pack whose wire
    shape merely differs from its own re-serialization. Canonicalization
    therefore ALWAYS runs on the raw dicts, and the typed ``RulePack`` model
    is only constructed AFTER the signature has verified — it is a
    downstream convenience for callers, never part of the trust boundary
    itself.

    UNSIGNED-DEV FIREBREAK: if ``raw_envelope`` carries no signature at all
    (``signature`` key absent, ``null``, or empty), this is refused UNLESS
    ``allow_unsigned=True`` — and even then, a payload declaring
    ``environment == "PRODUCTION"`` is ALWAYS refused unsigned, regardless
    of the flag. This is the only path that can return
    ``VerifiedRulePack(unsigned_dev=True)``; nothing downstream needs its
    own PRODUCTION-unsigned guard because this function never lets one
    through.

    FUTURE-SKEW GUARD (3-seat verify FIX-NOW #3, signed path only): a
    ``signed_at`` more than :data:`_SIGNED_AT_FUTURE_TOLERANCE` ahead of
    ``observed_at`` is refused — this is a PARTIAL, stateless mitigation
    against a backdated/future-dated signature, checked after
    ``trust_store.resolve()`` so a key that is independently invalid at
    ``signed_at`` (not-yet-valid/expired/revoked) is still reported as
    that, not shadowed by this check. TODO (later PR): this does NOT solve
    revocation-at-activation-time against a key that is compromised AND
    whose signature is backdated to before the compromise/revocation was
    known — that needs an authoritative clock plus persistence (looking up
    what was already active), which is out of a pure, I/O-free verification
    function's reach.

    ANTI-TOCTOU SNAPSHOT (3-seat verify FIX-NOW #2): ``raw_envelope`` is
    read exactly once, right here, via :func:`_snapshot_envelope` — every
    check below (schema validation, canonicalization, hashing, key
    resolution, ``model_validate``) operates on that snapshot, never on the
    caller's original object again. See that function's docstring.
    """

    envelope = _snapshot_envelope(raw_envelope)

    if not _has_signature(envelope):
        return _verify_unsigned_dev(
            envelope, allow_unsigned=allow_unsigned, observed_at=observed_at
        )

    _validate_envelope_against_schema(envelope)

    raw_protected = envelope["protected"]
    raw_payload = envelope["payload"]
    if not isinstance(raw_protected, Mapping) or not isinstance(raw_payload, Mapping):
        # Schema validation above already enforces object shape for both —
        # this is unreachable in practice, but keeps the type-narrowing
        # honest rather than trusting an untyped Mapping[str, JsonValue].
        raise RulePackVerificationError(
            "rule pack envelope 'protected'/'payload' must be JSON objects"
        )

    # Belt-and-suspenders: the compiler's own header/environment check
    # re-enforces this too, but the cryptographic trust boundary should not
    # depend on a downstream compile step ever running.
    protected_environment = raw_protected.get("environment")
    payload_environment = raw_payload.get("environment")
    if protected_environment != payload_environment:
        raise RulePackVerificationError(
            f"protected header environment {protected_environment!r} does not "
            f"match payload environment {payload_environment!r}"
        )

    protected_bytes = _canonicalize_wire_object(raw_protected, label="protected")
    payload_bytes = _canonicalize_wire_object(raw_payload, label="payload")

    computed_payload_sha256 = hashlib.sha256(payload_bytes).digest()
    declared_payload_sha256 = envelope.get("payload_sha256")
    if computed_payload_sha256.hex() != declared_payload_sha256:
        raise RulePackVerificationError(
            f"payload_sha256 mismatch: envelope declares {declared_payload_sha256!r}, "
            f"computed {computed_payload_sha256.hex()!r} from SHA256(JCS(payload)) "
            "— the payload was tampered with, or the declared hash is stale"
        )

    raw_kid = raw_protected.get("kid")
    raw_signed_at = raw_protected.get("signed_at")
    signed_at = _parse_utc_datetime(raw_signed_at)
    signing_key = trust_store.resolve(
        key_id=raw_kid,
        signed_at=signed_at,
        environment=protected_environment,
    )

    # Future-skew guard (3-seat verify FIX-NOW #3): `observed_at` was
    # accepted as a parameter but never actually used on the signed path —
    # a pack signed_at any arbitrary point in the future relative to
    # observed_at sailed through untouched (a partial backdating/
    # future-dating defense gap). Checked AFTER trust_store.resolve()
    # succeeds so a key already invalid/expired/revoked/not-yet-valid at
    # signed_at is still reported as exactly that, not shadowed by this
    # check. NOT a fix for revocation-at-activation-time against a
    # compromised+backdated key — that needs an authoritative clock plus
    # persistence (current_sequence/current_payload_sha256 lookups), which
    # is `validate_activation`'s caller's job in a later PR; this is only
    # the partial, stateless mitigation available at verify-on-load time.
    if signed_at > observed_at + _SIGNED_AT_FUTURE_TOLERANCE:
        raise RulePackVerificationError(
            f"signed_at {signed_at.isoformat()!r} is in the future relative "
            f"to observed_at {observed_at.isoformat()!r} beyond the "
            f"{_SIGNED_AT_FUTURE_TOLERANCE} tolerance"
        )

    raw_signature = envelope.get("signature")
    signature_bytes = _decode_signature(raw_signature)
    signed_bytes = _build_signed_bytes(protected_bytes, payload_bytes)

    try:
        signing_key.public_key.verify(signature_bytes, signed_bytes)
    except InvalidSignature as exc:
        raise RulePackVerificationError(
            f"Ed25519 signature verification failed for key {raw_kid!r}"
        ) from exc

    # ONLY AFTER the signature verifies do we build the typed model — see
    # the trust-boundary invariant in the docstring above.
    try:
        pack = RulePack.model_validate(envelope)
    except PydanticValidationError as exc:
        raise RulePackVerificationError(
            f"rule pack envelope failed model validation: {exc}"
        ) from exc

    logger.info(
        "verified rule pack %s sequence=%s kid=%s",
        pack.payload.rule_pack_id,
        pack.payload.sequence,
        raw_kid,
    )

    return VerifiedRulePack(
        pack=pack,
        canonical_payload=payload_bytes,
        payload_sha256=computed_payload_sha256,
        unsigned_dev=False,
    )


def _verify_unsigned_dev(
    envelope: Mapping[str, JsonValue],
    *,
    allow_unsigned: bool,
    observed_at: datetime,
) -> VerifiedRulePack:
    """Private; called ONLY from :func:`verify_rule_pack`, which already
    ran ``envelope`` through :func:`_snapshot_envelope` — this function
    performs no further defensive copying and assumes ``envelope`` is
    already an inert, plain JSON structure (no live/hostile Mapping)."""

    raw_payload = envelope.get("payload")
    if not isinstance(raw_payload, Mapping):
        raise RulePackVerificationError("unsigned rule pack envelope is missing a 'payload' object")

    environment = raw_payload.get("environment")
    if environment == _PRODUCTION_ENVIRONMENT:
        raise RulePackVerificationError(
            "PRODUCTION rule packs must always be signed — allow_unsigned "
            "never applies to environment=PRODUCTION, regardless of the flag"
        )

    if not allow_unsigned:
        raise RulePackVerificationError(
            "rule pack envelope has no signature and allow_unsigned=False"
        )

    try:
        payload = RulePackPayload.model_validate(raw_payload)
    except PydanticValidationError as exc:
        raise RulePackVerificationError(
            f"unsigned dev rule pack payload failed model validation: {exc}"
        ) from exc

    # TOCTOU re-check (3-seat verify, FIX-NOW #1): the PRODUCTION-unsigned
    # refusal above reads `raw_payload.get("environment")` — a plain dict
    # read. If `raw_payload` is ever a hostile/stateful Mapping whose
    # `.get()` returns a DIFFERENT value on a later call (the same object is
    # read again by Pydantic inside `model_validate` above), the first read
    # could see a harmless environment while the validated model ends up
    # with `environment=PRODUCTION` — the guard above would have been
    # checking a value that no longer describes the payload actually
    # accepted. Re-assert against the VALIDATED model (never re-readable
    # out from under us — `RulePackPayload` is frozen) as the authoritative
    # gate. Empirically reproduced: a `dict` subclass whose `.get(
    # "environment")` returns "TEST" on its first call and "PRODUCTION" on
    # every call thereafter sails past the raw-dict check above and lands
    # here with `payload.environment is Environment.PRODUCTION`.
    if payload.environment == _PRODUCTION_ENVIRONMENT:
        raise RulePackVerificationError(
            "PRODUCTION rule packs must always be signed — allow_unsigned "
            "never applies to environment=PRODUCTION, regardless of the "
            "flag (post-validation re-check)"
        )

    # Same trust-boundary invariant as the signed path: canonicalize the
    # LITERAL wire payload, not a Pydantic re-serialization, so an
    # unsigned-dev pack's payload_sha256 is defined identically to a signed
    # pack's — never divergent depending on which path produced it. Routed
    # through the same typed-error wrapper as the signed path.
    payload_bytes = _canonicalize_wire_object(raw_payload, label="payload")
    payload_sha256 = hashlib.sha256(payload_bytes).digest()

    protected = ProtectedHeader.model_validate(
        {
            "domain": "balizero.visa-rulepack.v1",
            "alg": "Ed25519",
            "kid": _UNSIGNED_DEV_KID,
            "signed_at": _format_utc_datetime(observed_at),
            "schema_version": _SCHEMA_VERSION,
            "environment": payload.environment,
        }
    )

    pack = RulePack(
        canonicalization="RFC8785",
        protected=protected,
        payload=payload,
        payload_sha256=payload_sha256.hex(),
        signature=_UNSIGNED_DEV_SIGNATURE,
    )

    logger.warning(
        "UNSIGNED-DEV rule pack accepted (environment=%s, rule_pack_id=%s) — "
        "never valid for PRODUCTION, gated by VISA_ENGINE_ALLOW_UNSIGNED_PACKS",
        payload.environment,
        payload.rule_pack_id,
    )

    return VerifiedRulePack(
        pack=pack,
        canonical_payload=payload_bytes,
        payload_sha256=payload_sha256,
        unsigned_dev=True,
    )


# --- Anti-rollback activation gating --------------------------------------


def _parse_semver(value: str) -> tuple[int, int, int]:
    try:
        major, minor, patch = (int(part) for part in value.split("."))
    except ValueError as exc:
        raise RulePackVerificationError(f"invalid semantic version: {value!r}") from exc
    return (major, minor, patch)


def _engine_version_compatible(*, min_version: str, max_version: str, engine_version: str) -> bool:
    engine = _parse_semver(engine_version)
    return _parse_semver(min_version) <= engine <= _parse_semver(max_version)


def validate_activation(
    candidate: VerifiedRulePack,
    *,
    current_sequence: int,
    current_payload_sha256: bytes | None,
    environment: str,
    engine_version: str,
) -> None:
    """Pure anti-rollback activation gate (spec §3 rejection list, minus
    key validity/revocation — already enforced in :func:`verify_rule_pack`
    — and minus legal-period/jurisdiction/domain, see module docstring).

    Raises :class:`RulePackVerificationError` on the first violation found,
    in this order: unsigned-dev-into-PRODUCTION, sequence regression,
    broken ``previous_payload_sha256`` chain, environment mismatch,
    incompatible engine version. Never touches a database or the
    filesystem — persistence (looking up
    ``current_sequence``/``current_payload_sha256`` for real) is a later
    PR's job; this function only compares values its caller already holds.

    Raises :class:`TypeError` (not :class:`RulePackVerificationError`) if
    ``current_payload_sha256`` is not ``bytes`` or ``None`` — a caller
    passing a hex ``str`` by mistake must fail loudly, never silently
    (``bytes.fromhex(payload.previous_payload_sha256) != "deadbeef..."`` is
    always ``True``, which would reject every legitimate update; see
    3-seat verify FIX-NOW #7).
    """

    if current_payload_sha256 is not None and not isinstance(current_payload_sha256, bytes):
        raise TypeError(
            "current_payload_sha256 must be bytes or None, got "
            f"{type(current_payload_sha256).__name__} — likely a hex str "
            "that was never decoded with bytes.fromhex(...)"
        )

    # Defense in depth (3-seat verify FIX-NOW #5): verify_rule_pack already
    # refuses to produce an unsigned_dev=True candidate for
    # environment=PRODUCTION (both at the pre-validation dict-read gate and,
    # per FIX-NOW #1, again on the validated model) — but activation must
    # never TRUST that wrapper's guarantee. A candidate is checked against
    # ITS OWN unsigned_dev flag and the environment it is being activated
    # into, independent of how it got here.
    if candidate.unsigned_dev and environment == _PRODUCTION_ENVIRONMENT:
        raise RulePackVerificationError(
            "refusing to activate an unsigned_dev rule pack into "
            f"environment={_PRODUCTION_ENVIRONMENT!r} — PRODUCTION must "
            "always be a cryptographically verified candidate, regardless "
            "of how the candidate was constructed"
        )

    payload = candidate.pack.payload

    if payload.sequence <= current_sequence:
        raise RulePackVerificationError(
            f"candidate sequence {payload.sequence} is not greater than the "
            f"current sequence {current_sequence}"
        )

    if current_payload_sha256 is None:
        if payload.previous_payload_sha256 is not None:
            raise RulePackVerificationError(
                "no current production bundle exists (current_payload_sha256 is "
                f"None) but candidate declares previous_payload_sha256="
                f"{payload.previous_payload_sha256!r} — expected a sequence=1 "
                "bootstrap bundle with previous_payload_sha256=null"
            )
    else:
        if payload.previous_payload_sha256 is None:
            raise RulePackVerificationError(
                "a current production bundle exists but candidate has "
                "previous_payload_sha256=null — this would orphan the "
                "anti-rollback chain"
            )
        if bytes.fromhex(payload.previous_payload_sha256) != current_payload_sha256:
            raise RulePackVerificationError(
                "candidate previous_payload_sha256 does not match the current "
                "production bundle's payload_sha256 — rejecting to preserve "
                "the anti-rollback chain"
            )

    if payload.environment != environment:
        raise RulePackVerificationError(
            f"candidate environment {payload.environment!r} does not match "
            f"the activation environment {environment!r}"
        )

    if not _engine_version_compatible(
        min_version=payload.engine_min_version,
        max_version=payload.engine_max_version,
        engine_version=engine_version,
    ):
        raise RulePackVerificationError(
            f"engine_version {engine_version!r} is not compatible with the "
            f"candidate's [{payload.engine_min_version!r}, "
            f"{payload.engine_max_version!r}] range"
        )
