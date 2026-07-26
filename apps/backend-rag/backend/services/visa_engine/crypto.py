"""STEP-6d — the real crypto-backed facts-fingerprint identity provider.

This module supplies the production ``evaluator.IdentityProvider`` that
``evaluate()`` needs for any non-``TEST`` rule pack. The default
``evaluator._placeholder_identity_provider`` uses a NON-secret placeholder HMAC
key and fail-closes outside ``environment=TEST``; this module replaces exactly
that one thing — the HMAC key — with an operator-provisioned SECRET, so
STAGING/PRODUCTION packs get a genuine, secret-keyed ``facts_fingerprint`` (and
therefore genuinely-unguessable ``decision_id``/``public_id``, derived from it).

Scope (deliberately narrow — see ``research/visa/2026-07-21-step6d-crypto-
identity-provider-design.md`` §1): ONLY the facts-fingerprint HMAC key store,
the real ``IdentityProvider``, and the env resolver. The broader ``crypto.py``
surface the engine spec sketches — ``AesGcmPayloadCipher`` / ``EncryptedPayload``
/ ``Pseudonymizer`` (subject/consent pseudonymization, encrypted
``visa_decision_payloads``) — is NOT built here: it serves tables migration 252
deliberately omitted (``visa_decision_payloads`` does not exist). Those remain a
documented deferral; adding them now is scope-creep against a non-existent
consumer.

Key management mirrors ``bundle.StaticTrustStore.from_env`` (the Ed25519
trust-store loader) as closely as the different key TYPE allows: a JSON-array
env var, ``kid``-keyed entries, strict base64url secret decode, environment
scoping, a validity window + revocation, and fail-closed typed errors on every
malformed shape. It performs NO filesystem access — the key ceremony
(generating and pinning the secret) is the operator's, offline, exactly the
``__init__.py`` FIREBREAK posture ("no key GENERATION"; key USE is fine). The
facts-fingerprint secret is SYMMETRIC (HMAC-SHA256) and is a DISTINCT key from
the asymmetric Ed25519 RulePack-signing trust store — the two never share
material.
"""

from __future__ import annotations

import json
import os
import re
from base64 import urlsafe_b64decode
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.visa_engine.enums import Environment
from backend.services.visa_engine.errors import (
    FactsFingerprintKeyError,
    FactsFingerprintKeyUnavailableError,
)
from backend.services.visa_engine.evaluator import (
    DecisionIdentity,
    IdentityProvider,
    _placeholder_identity_provider,
    build_decision_identity,
)
from backend.services.visa_engine.models import ApplicantFacts, RulePackRef

#: The one env var this module reads: a JSON array of facts-fingerprint HMAC
#: key entries (see ``FactsFingerprintKeyStore.from_env``).
FACTS_FINGERPRINT_KEYS_ENV_VAR = "VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON"

#: HMAC-SHA256 key floor: 256 bits. A shorter decoded secret is rejected
#: fail-closed (weak-key guard).
_MIN_SECRET_BYTES = 32

#: Strict unpadded-base64url alphabet for the secret material (mirrors the
#: bundle.py key-material decode posture — reject anything outside it rather
#: than let ``urlsafe_b64decode`` silently coerce).
_BASE64URL_UNPADDED_ALPHABET_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _decode_secret(raw: object, *, kid: str) -> bytes:
    """Strict unpadded-base64url -> raw secret bytes; fail-closed on any
    malformed shape or a secret below the HMAC floor.
    """
    if not isinstance(raw, str) or not _BASE64URL_UNPADDED_ALPHABET_RE.fullmatch(raw):
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: 'secret' must be a non-empty unpadded base64url string"
        )
    padding = "=" * (-len(raw) % 4)
    try:
        secret = urlsafe_b64decode(raw + padding)
    except ValueError as exc:  # pragma: no cover - regex-guarded, defensive
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: secret is not valid base64url"
        ) from exc
    if len(secret) < _MIN_SECRET_BYTES:
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: secret is {len(secret)} bytes, "
            f"below the {_MIN_SECRET_BYTES}-byte (256-bit) HMAC-SHA256 floor"
        )
    return secret


def _parse_dt(value: object, *, kid: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: {field!r} must be an ISO-8601 string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: {field!r} is not a valid ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None:
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: {field!r} must be timezone-aware "
            "(end with 'Z' or an explicit offset)"
        )
    return parsed


def _parse_optional_dt(value: object, *, kid: str, field: str) -> datetime | None:
    if value is None:
        return None
    return _parse_dt(value, kid=kid, field=field)


_REQUIRED_FIELDS = ("kid", "secret", "environment", "valid_from")


def _key_from_entry(entry: object) -> FactsFingerprintKey:
    if not isinstance(entry, Mapping):
        raise FactsFingerprintKeyError("each facts-fingerprint key entry must be a JSON object")
    kid = entry.get("kid")
    if not isinstance(kid, str) or not kid:
        raise FactsFingerprintKeyError(
            "facts-fingerprint key entry is missing a non-empty string 'kid'"
        )
    for required_field in _REQUIRED_FIELDS:
        if required_field not in entry:
            raise FactsFingerprintKeyError(
                f"facts-fingerprint key {kid!r}: missing required field {required_field!r}"
            )
    env_raw = entry.get("environment")
    if not isinstance(env_raw, str):
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: 'environment' must be a string"
        )
    try:
        environment = Environment(env_raw)
    except ValueError as exc:
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: unknown environment {env_raw!r} "
            f"(expected one of {[e.value for e in Environment]})"
        ) from exc
    secret = _decode_secret(entry.get("secret"), kid=kid)
    valid_from = _parse_dt(entry.get("valid_from"), kid=kid, field="valid_from")
    valid_to = _parse_optional_dt(entry.get("valid_to"), kid=kid, field="valid_to")
    revoked_at = _parse_optional_dt(entry.get("revoked_at"), kid=kid, field="revoked_at")
    if valid_to is not None and valid_to <= valid_from:
        raise FactsFingerprintKeyError(
            f"facts-fingerprint key {kid!r}: 'valid_to' must be after 'valid_from'"
        )
    return FactsFingerprintKey(
        kid=kid,
        secret=secret,
        environment=environment,
        valid_from=valid_from,
        valid_to=valid_to,
        revoked_at=revoked_at,
    )


@dataclass(frozen=True)
class FactsFingerprintKey:
    """One pinned symmetric HMAC-SHA256 secret for the facts fingerprint.

    ``environment``-scoped and validity-windowed exactly like
    ``bundle.TrustedSigningKey`` (the Ed25519 analogue), so key rotation and
    revocation are expressible without a schema change. ``secret`` is raw key
    material — NEVER logged, NEVER placed in an exception message.
    """

    kid: str
    secret: bytes = field(repr=False)  # NEVER in repr/logs (Law 2)
    environment: Environment
    valid_from: datetime
    valid_to: datetime | None
    revoked_at: datetime | None

    def is_active_at(self, moment: datetime) -> bool:
        """Half-open ``[valid_from, valid_to)`` window, minus revocation — same
        ``moment < upper_bound`` convention as the engine's ``_period_contains``.

        REVOCATION semantics (cross-family gate, Gemini 2026-07-21): a revoked
        key stays selectable for ``moment < revoked_at`` — DELIBERATE, so that
        re-evaluating a historical decision at its original ``effective_at``
        reproduces the fingerprint actually minted then (audit reproducibility).
        Safe for MINTING new decisions on the shadow path because that path
        always passes ``effective_at = now`` — a key revoked before now is
        therefore excluded from any NEW decision. A FUTURE flow that mints NEW
        (not reproduced) decisions from a caller-supplied HISTORICAL
        ``effective_at``, or that ever treats ``public_id`` as an access-control
        capability, MUST add a wall-clock (``observed_at``) revocation check so a
        compromised key can never mint a fresh identity.
        """
        if moment < self.valid_from:
            return False
        if self.valid_to is not None and moment >= self.valid_to:
            return False
        if self.revoked_at is not None and moment >= self.revoked_at:
            return False
        return True


@dataclass(frozen=True)
class FactsFingerprintKeyStore:
    """An immutable set of pinned facts-fingerprint keys. Rejects a duplicate
    ``kid`` within one environment.
    """

    keys: tuple[FactsFingerprintKey, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for key in self.keys:
            if key.kid in seen:
                raise FactsFingerprintKeyError(
                    f"duplicate facts-fingerprint key {key.kid!r} — kids must be "
                    "globally unique across environments (the audit trail keys on "
                    "kid alone)"
                )
            seen.add(key.kid)

    @classmethod
    def from_iterable(cls, entries: Iterable[object]) -> FactsFingerprintKeyStore:
        return cls(tuple(_key_from_entry(entry) for entry in entries))

    @classmethod
    def from_env(cls, env_var: str = FACTS_FINGERPRINT_KEYS_ENV_VAR) -> FactsFingerprintKeyStore:
        """Build the store from a JSON-array env var. Fail-closed
        ``FactsFingerprintKeyError`` on unset/empty/non-JSON/non-array/malformed.
        Re-reads fresh every call; never cached at import (same convention as
        ``bundle.StaticTrustStore.from_env``).
        """
        raw = os.environ.get(env_var)
        if raw is None or not raw.strip():
            raise FactsFingerprintKeyError(
                f"environment variable {env_var!r} is not set — no "
                "facts-fingerprint key material available"
            )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FactsFingerprintKeyError(
                f"environment variable {env_var!r} is not valid JSON"
            ) from exc
        if not isinstance(parsed, list):
            raise FactsFingerprintKeyError(
                f"environment variable {env_var!r} must be a JSON array of key entries"
            )
        if not parsed:
            raise FactsFingerprintKeyError(
                f"environment variable {env_var!r} is an empty array — no "
                "facts-fingerprint key material (UNSET the variable to fall back "
                "to the TEST-only placeholder instead of provisioning zero keys)"
            )
        return cls.from_iterable(parsed)

    def select(self, environment: Environment, effective_at: datetime) -> FactsFingerprintKey:
        """The active signing key for ``environment`` at ``effective_at``: among
        in-window, non-revoked keys, the one with the latest ``valid_from``
        (tie-break: highest ``kid`` lexicographically). Raises
        ``FactsFingerprintKeyUnavailableError`` (fail-closed) if none qualifies.
        """
        if effective_at.tzinfo is None:
            # Fail-closed, not a silent UTC assumption: a naive instant is
            # ambiguous and would diverge from the tz-aware seed used for
            # decision_id (evaluator._deterministic_ids). Shadow always passes
            # tz-aware ``now``; a naive caller is a contract violation.
            raise FactsFingerprintKeyUnavailableError(
                "effective_at must be timezone-aware for deterministic "
                "facts-fingerprint key selection"
            )
        candidates = [
            key
            for key in self.keys
            if key.environment is environment and key.is_active_at(effective_at)
        ]
        if not candidates:
            raise FactsFingerprintKeyUnavailableError(
                f"no active facts-fingerprint key for environment "
                f"{environment.value!r} at {effective_at.isoformat()}"
            )
        candidates.sort(key=lambda k: (k.valid_from, k.kid), reverse=True)
        return candidates[0]


def build_identity_provider(store: FactsFingerprintKeyStore) -> IdentityProvider:
    """Wrap a key store as an ``evaluator.IdentityProvider``. The returned
    callable is PURE given the store (no env/wall-clock reads): it selects the
    active key for ``(environment, effective_at)`` and delegates the derivation
    to ``evaluator.build_decision_identity`` — so ``decision_id``/``public_id``
    use the exact same derivation as the placeholder, differing only because the
    HMAC key (hence ``facts_digest``) is now the real secret.
    """

    def _provider(
        facts: ApplicantFacts,
        rule_pack_ref: RulePackRef,
        effective_at: datetime,
        environment: Environment,
    ) -> DecisionIdentity:
        key = store.select(environment, effective_at)
        return build_decision_identity(
            facts,
            rule_pack_ref,
            effective_at,
            fingerprint_key=key.secret,
            fingerprint_key_id=key.kid,
        )

    return _provider


def resolve_identity_provider(
    env_var: str = FACTS_FINGERPRINT_KEYS_ENV_VAR,
) -> IdentityProvider:
    """The env-aware identity provider the SHADOW/ENFORCE wiring uses.

    If ``env_var`` is unset/empty -> return the default
    ``evaluator._placeholder_identity_provider`` UNCHANGED (TEST keeps working;
    STAGING/PRODUCTION keep fail-closing — zero behavior change on a deploy that
    has not provisioned a key). If it is set -> build the store and return the
    real crypto-backed provider (which itself fail-closes per-environment via
    ``store.select``). Re-read fresh every call, never cached at import.

    Raises ``FactsFingerprintKeyError`` ONLY when ``env_var`` IS set but its
    content is malformed — the SHADOW caller catches that (logging the error
    TYPE only, never the secret) and degrades to a no-op.
    """
    raw = os.environ.get(env_var)
    if raw is None or not raw.strip():
        return _placeholder_identity_provider
    return build_identity_provider(FactsFingerprintKeyStore.from_env(env_var))


__all__ = [
    "FACTS_FINGERPRINT_KEYS_ENV_VAR",
    "FactsFingerprintKey",
    "FactsFingerprintKeyStore",
    "build_identity_provider",
    "resolve_identity_provider",
]
