"""Visa Oracle v2 deterministic evaluate read-path (RECOMMEND surface).

Backing service for the public ``POST /api/visa-oracle/evaluate`` endpoint
(``app/routers/visa_oracle_evaluate.py``): canonical ``ApplicantFacts`` in,
the Kimi-spec B.2 envelope out — ``{mode, decision, sources, display}``
(``research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`` §A.4.1/B.2) —
and a privacy-preserving ``visa_decisions`` audit row persisted for completed
evaluations only under an explicit retention policy (migrations
252/255/256/257/264).

Spec: ``research/visa/2026-07-23-w1-evidence-machinery-brief.md`` Item 2.

Relationship to ``shadow.py`` (STEP-6c/6d): same fail-closed pack binding,
same crypto posture, same PII boundary — different surface. ``shadow.py``
is the fire-and-forget MATCH-surface audit twin whose response is never
rendered; THIS module is the RECOMMEND-surface read-path whose response may
become the product authority in ``ENFORCE`` mode. The private
helpers are IMPORTED from ``shadow.py`` read-only — the file itself is not
touched — rather than triplicated: the pack-binding SQL and the 255
candidate/grounding/citation writers have exactly one home each
(``shadow.py``), the same single-home trade-off ``shadow.py`` itself
documented when it mirrored ``repository.py``.

Mode discipline (mirrors ``shadow.resolve_match_shadow_enabled``):

- ``VISA_ENGINE_EVALUATE_MODE`` — OFF (default) | SHADOW | ENFORCE. OFF is
  a disabled surface: the endpoint responds with the TEMPORARILY_UNAVAILABLE
  shape (``retryable=true``, HTTP 200) and persists NOTHING. SHADOW runs the
  evaluation and persists the audit row best-effort while returning
  ``mode="CURATED"``. ENFORCE returns ``mode="ENGINE"`` and fails closed if
  decision persistence cannot be proven. Both modes abstain before RulePack
  resolution unless a Zero-approved retention policy covers the evaluation
  clock; no SHADOW exemption exists for retained pseudonymous audit data.
- ``VISA_ENGINE_EVALUATE_ENVIRONMENT`` — which rule-pack environment the
  bitemporal binding resolves against. Defaults to PRODUCTION (the v2 UI's
  audience is production traffic; SHADOW audits what the engine *would*
  have said against the production pack).
- ``VISA_ENGINE_EVALUATE_ALLOW_SYNTHETIC_SOURCES`` — comma-separated
  allowlist drawn from migration 256's synthetic ``traffic_source``
  classes (``synthetic_gold``, ``synthetic_driver``). Anonymous callers may
  NEVER self-label synthetic: a request asking for a synthetic class that
  is not allowlisted here is rejected by the router (400). Default unset —
  only ``real`` is accepted. This is how the W4 gold-corpus replay driver
  labels its rows on an operator-armed deployment, without opening the
  label to the public.
- ``VISA_ENGINE_DRIVER_TOKEN`` — the shared secret backing the
  ``X-Visa-Driver-Token`` header. Arming the allowlist alone would let ANY
  anonymous caller self-label synthetic (Gemini adversarial pass
  2026-07-24, adjudicated HIGH), so a synthetic class is accepted only
  when BOTH the class is allowlisted AND the presented token matches this
  secret (constant-time compare). Unset: synthetic is always rejected
  (fail-closed). This token IS the W4 driver credential.

PII boundary (SYMBIOSIS Law 2 / UU PDP): applicant facts are NEVER logged
and never persisted — the audit row carries only engine identifiers, reason
codes, source-record UUIDs, the derived category, and the HMAC
facts-fingerprint (the STEP-6d identity provider's output, reused as this
surface's request correlator: keyed, non-reversible, 32 bytes — the same
granularity the G-a "distinct requests" counter needs, and strictly
stronger than ``shadow.py``'s plain SHA-256 of the match token, which the
MATCH surface uses only because it never sees the facts at all).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias
from urllib.parse import urlsplit

import asyncpg

from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.visa_engine.api_models import (
    DisclosedReviewFlag,
    SourceApplicabilityStatus,
    SourceFreshnessDTO,
    SourceFreshnessStatus,
    VisaOracleEvaluateRequest,
    VisaOracleEvaluateResponse,
)
from backend.services.visa_engine.ast import UnknownFact
from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.crypto import (
    resolve_engine_hmac_keyring,
    resolve_identity_provider,
)
from backend.services.visa_engine.decision_seal import seal_decision
from backend.services.visa_engine.enums import (
    DecisionState,
    EngineMode,
    EngineSurface,
    Environment,
    FactPath,
    SourceAuthorityType,
    SourceStatus,
    VisaPurpose,
)
from backend.services.visa_engine.errors import (
    FactsFingerprintKeyError,
    FactsFingerprintKeyUnavailableError,
    PlaceholderIdentityNotAllowedError,
    RulePackCompilationError,
    RulePackVerificationError,
)
from backend.services.visa_engine.evaluator import evaluate_with_trace
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.idempotency import (
    IdempotencyConflictError,
    hash_idempotency_key,
)
from backend.services.visa_engine.idempotency import (
    complete as complete_idempotency,
)
from backend.services.visa_engine.idempotency import (
    reserve as reserve_idempotency,
)
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
    Reason,
    SourceRecord,
)
from backend.services.visa_engine.pricing_adapter import (
    ExactPricingCatalog,
    PricingResolution,
    UnavailablePricingCatalog,
    build_price_quote,
    resolve_candidate_pricing,
)
from backend.services.visa_engine.retention import (
    active_policy_available as active_retention_policy_available,
)
from backend.services.visa_engine.shadow import (
    ENGINE_VERSION,
    _build_candidate_summary,
    _build_grounding_summary,
    _collect_citations,
    _resolve_active_pack_binding,
)
from backend.services.visa_engine.shadow_evidence import (
    SYNTHETIC_TRAFFIC_SOURCES,
)

logger = logging.getLogger(__name__)

#: A raw, JSON-safe value. Defined locally — no importable shared home in
#: this package (same convention as ``shadow.py``/``bundle.py``/
#: ``repository.py``: every module duplicates this alias rather than
#: inventing a shared one).
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

#: Evaluate-surface engine mode gate (OFF|SHADOW|ENFORCE; any other/missing
#: value resolves to OFF). Re-read fresh on every call — never cached at
#: import time — so a live config flip (or ``monkeypatch.setenv`` in tests)
#: takes effect immediately, matching ``shadow.resolve_match_shadow_enabled``'s
#: own contract.
EVALUATE_MODE_ENV = "VISA_ENGINE_EVALUATE_MODE"

#: Which rule-pack environment the evaluate read-path resolves against.
#: Defaults to PRODUCTION (mirrors ``shadow.MATCH_ENVIRONMENT_ENV``'s own
#: default and rationale).
EVALUATE_ENVIRONMENT_ENV = "VISA_ENGINE_EVALUATE_ENVIRONMENT"
_DEFAULT_EVALUATE_ENVIRONMENT = "PRODUCTION"

#: Comma-separated server-side allowlist of synthetic ``traffic_source``
#: classes this deployment accepts from callers (migration 256's CHECK
#: classes minus ``real``). Default unset: only ``real`` is accepted.
ALLOW_SYNTHETIC_SOURCES_ENV = "VISA_ENGINE_EVALUATE_ALLOW_SYNTHETIC_SOURCES"

#: The shared secret a caller must present (via the router's
#: ``X-Visa-Driver-Token`` header) to use an allowlisted synthetic class —
#: the W4 gold-corpus replay driver credential (see module docstring).
DRIVER_TOKEN_ENV = "VISA_ENGINE_DRIVER_TOKEN"

#: The engine surface every persisted row and every log line of this module
#: belongs to (migration 252's ``engine_surface`` CHECK admits it verbatim).
_SURFACE = EngineSurface.RECOMMEND

#: ``visa_engine.enums.VisaPurpose`` (the engine's closed purpose vocabulary,
#: carried by a KNOWN ``intent.purposes`` fact) -> ``request_category``
#: (migration 257's 10-value CHECK). This is the W1 brief Item 3 tile->enum
#: table with the tile step composed away (the v2 interview's tiles bind to
#: these purposes): TOURISM->long_tourism, EMPLOYMENT->work_employee,
#: REMOTE_WORK->work_remote, INVESTMENT->investor,
#: BUSINESS_MEETINGS->business, FAMILY->family, RETIREMENT->retirement,
#: STUDY->student. Purposes with no tile (SECOND_HOME, TRANSIT, MEDICAL,
#: OTHER) deliberately have NO entry — they derive to ``other`` (W1 brief:
#: "unmapped -> other"), never guessed into a neighboring category.
_VISA_PURPOSE_TO_REQUEST_CATEGORY: MappingProxyType[VisaPurpose, str] = MappingProxyType(
    {
        VisaPurpose.TOURISM: "long_tourism",
        VisaPurpose.EMPLOYMENT: "work_employee",
        VisaPurpose.REMOTE_WORK: "work_remote",
        VisaPurpose.INVESTMENT: "investor",
        VisaPurpose.BUSINESS_MEETINGS: "business",
        VisaPurpose.FAMILY: "family",
        VisaPurpose.RETIREMENT: "retirement",
        VisaPurpose.STUDY: "student",
    }
)


#: The owner switchboard signature manifest (MANDATE.md 2026-08-24 §5).
#: Build-time data, not runtime state — a signature is a deliberate, reviewable,
#: committed act — so it is read once and cached, unlike ``EVALUATE_MODE_ENV``
#: which must stay live-flippable.
_IGNITION_SIGNATURES_PATH = Path(__file__).resolve().parent / "contracts" / "ignition_signatures.json"


@lru_cache(maxsize=1)
def unsigned_ignition_decisions() -> tuple[str, ...]:
    """Names of the §5 switchboard decisions the owner has NOT yet signed.

    Empty tuple == ignition is authorised. A missing/unreadable/malformed
    manifest fails CLOSED (reports every decision as unsigned): the safe
    direction for a consent record is to assume consent was NOT given.
    """

    try:
        raw = json.loads(_IGNITION_SIGNATURES_PATH.read_text(encoding="utf-8"))
        entries = raw["signatures"]
        if not entries:
            raise ValueError("empty signature manifest")
        return tuple(
            str(entry["decision"]) for entry in entries if entry.get("signed") is not True
        )
    except Exception:
        logger.error(
            "visa-engine ignition: signature manifest unreadable at %s — "
            "treating every owner signature as MISSING (fail-closed)",
            _IGNITION_SIGNATURES_PATH,
        )
        return ("<manifest unreadable — all signatures assumed missing>",)


def resolve_evaluate_mode() -> EngineMode:
    """Resolve the public authority lever; unknown values fail closed to OFF.

    ENFORCE additionally requires every owner switchboard signature
    (MANDATE.md 2026-08-24 §5, verbatim: "ENFORCE stays OFF until every §5
    signature exists — no exception, no partial ignition"). Until 2026-08-25
    that sentence lived only in prose, so a single env flip would have made
    the engine the product authority for real visitors with zero signatures
    collected — the repo's own rule applies ("se una regola critica è
    violabile, scrivi un hook; la documentazione non basta").

    An unsigned ENFORCE degrades to SHADOW, deliberately NOT to OFF: SHADOW
    is the state the mandate says to build in, so a premature flip loses the
    authority it was not entitled to while keeping the observation it was.
    It is loud about it — silence here would reproduce the exact failure this
    guard exists to prevent (a surface that looks armed and is not).
    """

    raw = os.environ.get(EVALUATE_MODE_ENV, EngineMode.OFF.value).strip().upper()
    try:
        mode = EngineMode(raw)
    except ValueError:
        return EngineMode.OFF
    if mode is EngineMode.ENFORCE:
        missing = unsigned_ignition_decisions()
        if missing:
            logger.error(
                "visa-engine ignition REFUSED: %s requested ENFORCE but %d owner "
                "signature(s) are missing (%s) — serving SHADOW. Ignition needs "
                "the owner's decision recorded in %s, not an env flip.",
                EVALUATE_MODE_ENV,
                len(missing),
                ", ".join(missing),
                _IGNITION_SIGNATURES_PATH.name,
            )
            return EngineMode.SHADOW
    return mode


def resolve_evaluate_shadow_enabled() -> bool:
    """Re-read ``EVALUATE_MODE_ENV`` fresh on every call.

    True iff the resolved mode is ``SHADOW`` or ``ENFORCE``; anything else
    resolves to ``False``. Authority and persistence semantics are handled by
    :func:`run_evaluation`, which resolves the same lever once per request.
    """

    return resolve_evaluate_mode() in (EngineMode.SHADOW, EngineMode.ENFORCE)


def resolve_response_mode(mode: EngineMode | None = None) -> str:
    """Map the authority lever to the public response contract.

    SHADOW is comparison-only and therefore CURATED. ENFORCE is authoritative
    and therefore ENGINE, but only after the durable decision write succeeds;
    :func:`run_evaluation` fail-closes a failed ENFORCE write to an ENGINE-mode
    TEMPORARILY_UNAVAILABLE response.
    """

    resolved = mode or resolve_evaluate_mode()
    return "ENGINE" if resolved is EngineMode.ENFORCE else "CURATED"


def resolve_allowed_synthetic_sources() -> frozenset[str]:
    """The synthetic ``traffic_source`` classes currently allowed from
    callers, parsed fresh from ``ALLOW_SYNTHETIC_SOURCES_ENV`` on every call
    (never cached at import).

    Comma-separated; each entry is stripped and kept only if it is one of
    migration 256's two synthetic CHECK classes — anything else (including
    ``real``, which needs no allowlist, and arbitrary garbage) is ignored,
    so a malformed env var can never widen the accepted set.
    """

    raw = os.environ.get(ALLOW_SYNTHETIC_SOURCES_ENV, "")
    return frozenset(
        entry
        for entry in (part.strip() for part in raw.split(","))
        if entry in SYNTHETIC_TRAFFIC_SOURCES
    )


def _resolve_evaluate_environment() -> str:
    raw = os.environ.get(EVALUATE_ENVIRONMENT_ENV, _DEFAULT_EVALUATE_ENVIRONMENT).strip()
    return raw or _DEFAULT_EVALUATE_ENVIRONMENT


async def _retention_gate_allows_persistence(
    db_pool: asyncpg.Pool,
    *,
    environment: str,
    evaluated_at: datetime,
    request_trace: str,
) -> bool:
    """Fail durable decision processing closed without a Zero policy."""

    try:
        available = await active_retention_policy_available(
            db_pool,
            environment=environment,
            evaluated_at=evaluated_at,
        )
    except Exception as exc:
        logger.warning(
            "evaluate path: retention policy check failed: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        return False
    if not available:
        logger.warning(
            "evaluate path: no Zero-approved decision retention policy "
            "for environment=%s (trace=%s)",
            environment,
            request_trace,
        )
    return available


_ReplayPackIdentity: TypeAlias = tuple[uuid.UUID, int, str, str]


async def _current_replay_pack_identity(
    db_pool: asyncpg.Pool,
    *,
    environment: str,
    moment: datetime,
) -> _ReplayPackIdentity | None:
    """Resolve and cryptographically verify the authority active *now*."""

    binding = await _resolve_active_pack_binding(
        db_pool,
        environment=environment,
        effective_at=moment,
        observed_at=moment,
    )
    if binding is None:
        return None
    verified = verify_rule_pack(
        binding.raw_envelope,
        trust_store=StaticTrustStore.from_env(),
        observed_at=moment,
    )
    payload = verified.pack.payload
    if binding.rule_pack_id != payload.rule_pack_id:
        return None
    return (
        payload.rule_pack_id,
        payload.sequence,
        payload.version,
        verified.payload_sha256.hex(),
    )


async def _replay_authority_matches(
    db_pool: asyncpg.Pool,
    *,
    response: VisaOracleEvaluateResponse,
    expected_environment: str,
    request_trace: str,
) -> tuple[bool, EngineMode]:
    """Double-check mode and active RulePack immediately before replay.

    Two snapshots make a concurrent activation flip observable. An evaluated
    replay is valid only while its signed RulePack remains the current active
    authority. A TEMP replay has no legal claim, but its response mode must
    still match the live mode.
    """

    expected_pack: _ReplayPackIdentity | None = None
    if response.decision.state is not DecisionState.TEMPORARILY_UNAVAILABLE:
        rule_pack = response.decision.rule_pack
        if rule_pack is None:  # pragma: no cover - Decision invariant
            return False, resolve_evaluate_mode()
        expected_pack = (
            rule_pack.rule_pack_id,
            rule_pack.sequence,
            rule_pack.version,
            rule_pack.payload_sha256,
        )

    previous_snapshot: tuple[EngineMode, str, _ReplayPackIdentity | None] | None = None
    for _ in range(2):
        mode = resolve_evaluate_mode()
        environment = _resolve_evaluate_environment()
        moment = datetime.now(timezone.utc)
        if mode is EngineMode.OFF:
            return False, mode
        if environment != expected_environment or response.mode.value != resolve_response_mode(
            mode
        ):
            return False, mode
        if not await _retention_gate_allows_persistence(
            db_pool,
            environment=environment,
            evaluated_at=moment,
            request_trace=request_trace,
        ):
            return False, mode
        try:
            active_pack = (
                None
                if expected_pack is None
                else await _current_replay_pack_identity(
                    db_pool,
                    environment=environment,
                    moment=moment,
                )
            )
        except Exception as exc:
            logger.warning(
                "evaluate path: replay authority check failed: %s (trace=%s)",
                type(exc).__name__,
                request_trace,
            )
            return False, mode
        snapshot = (mode, environment, active_pack)
        if expected_pack is not None and active_pack != expected_pack:
            return False, mode
        if previous_snapshot is not None and snapshot != previous_snapshot:
            return False, mode
        previous_snapshot = snapshot
    return True, previous_snapshot[0]


def _replay_rejection_response(*, mode: EngineMode, now: datetime) -> VisaOracleEvaluateResponse:
    code = (
        "EVALUATE_SURFACE_DISABLED"
        if mode is EngineMode.OFF
        else "IDEMPOTENCY_REPLAY_AUTHORITY_CHANGED"
    )
    return VisaOracleEvaluateResponse.model_validate(
        build_temp_unavailable_body(now=now, code=code, mode=mode)
    )


def verify_driver_token(presented: str | None) -> bool:
    """Constant-time check of the W4 driver credential.

    True iff ``DRIVER_TOKEN_ENV`` is provisioned (non-empty after strip)
    AND ``presented`` matches it under ``secrets.compare_digest``. Every
    other shape — unset/empty env, missing header, mismatched token, a
    non-ASCII header value — is False (fail-closed). The env is re-read on
    every call, never cached at import (same convention as the allowlist).
    """

    expected = os.environ.get(DRIVER_TOKEN_ENV, "").strip()
    if not expected or not presented:
        return False
    try:
        return secrets.compare_digest(presented, expected)
    except TypeError:
        return False


def derive_request_category(facts: ApplicantFacts, hint: str | None) -> str:
    """The ``request_category`` for this evaluation (migration 257's CHECK).

    Facts speak first; the hint is honored ONLY when facts derive
    ``other`` (Gemini adversarial pass 2026-07-24, adjudicated MEDIUM — an
    unconditional hint would let any caller relabel a mappable evaluation
    and game the G-a-vol category counts). Resolution order:

    1. Facts-derived — a KNOWN ``intent.purposes`` fact holding EXACTLY
       ONE purpose maps via ``_VISA_PURPOSE_TO_REQUEST_CATEGORY``. A
       mappable single purpose always wins over any hint.
    2. ``hint`` — the v2 interview's tile, supplied by the caller and
       ALREADY validated against the 10-value enum by the router. Honored
       only in the cases facts cannot express: UNKNOWN purposes,
       multi-purpose facts (no honest primary tile), and purposes with no
       v2 tile (SECOND_HOME/TRANSIT/MEDICAL/OTHER). This is the only path
       that can ever produce ``diaspora``: the engine's closed
       ``VisaPurpose`` vocabulary has no diaspora value (W1 brief Item 3 —
       rejecting the hint would silently miscount diaspora demand as
       ``other``, the exact outcome Fable rejected).
    3. ``other`` — the floor, never guessed.
    """

    derived = "other"
    purposes_fact = facts.facts.intent_purposes
    if purposes_fact.status == "KNOWN":
        values = purposes_fact.value
        if len(values) == 1:
            derived = _VISA_PURPOSE_TO_REQUEST_CATEGORY.get(values[0], "other")
    if derived != "other":
        return derived
    return hint if hint is not None else "other"


def build_temp_unavailable_body(
    *,
    now: datetime,
    code: str,
    mode: EngineMode | None = None,
) -> dict[str, JsonValue]:
    """The TEMPORARILY_UNAVAILABLE-shaped envelope body (HTTP 200).

    Returned — with no successful decision claimed — whenever evaluation cannot run:
    surface disabled (OFF), no active pack, pack verification/compilation
    failure, or the crypto/evaluation layer fail-closing. ``mode`` is still
    ``resolve_response_mode()`` so callers can distinguish comparison-only
    SHADOW responses from authoritative ENFORCE responses.

    ``facts_fingerprint`` is null because no evaluation happened; fabricating
    an HMAC tag over unevaluated facts would be a dishonest integrity claim.
    """

    iso_now = now.astimezone(timezone.utc).isoformat()
    return {
        "mode": resolve_response_mode(mode),
        "decision": {
            "schema_version": "1.0.0",
            "decision_id": None,
            "public_id": None,
            "state": "TEMPORARILY_UNAVAILABLE",
            "effective_at": iso_now,
            "observed_at": iso_now,
            "evaluated_at": iso_now,
            "rule_pack": None,
            "facts_fingerprint": None,
            "candidates": [],
            "missing_facts": [],
            "review_reasons": [],
            "no_path_reasons": [],
            "outage": {"code": code, "retryable": True},
            "quotes": [],
            "notices": [],
            "trace_sha256": None,
            "decision_integrity": None,
        },
        "sources": [],
        "display": {"candidates": []},
    }


def _source_applicability_status(
    *,
    source_status: SourceStatus,
    legal_from: datetime,
    legal_to: datetime | None,
    recorded_from: datetime,
    recorded_to: datetime | None,
    effective_at: datetime,
    observed_at: datetime,
) -> SourceApplicabilityStatus:
    """Classify only applicability facts in the signed bitemporal record.

    This deliberately makes no external freshness assertion. A signed
    legal/system period can establish applicability, never that the source
    was re-verified recently enough for a decision.
    """

    status_map = {
        SourceStatus.SUPERSEDED: SourceApplicabilityStatus.SUPERSEDED,
        SourceStatus.REVOKED: SourceApplicabilityStatus.REVOKED,
        SourceStatus.UNAVAILABLE: SourceApplicabilityStatus.UNAVAILABLE,
    }
    mapped = status_map.get(source_status)
    if mapped is not None:
        return mapped
    if effective_at < legal_from:
        return SourceApplicabilityStatus.NOT_YET_EFFECTIVE
    if legal_to is not None and effective_at >= legal_to:
        return SourceApplicabilityStatus.EXPIRED
    if observed_at < recorded_from or (recorded_to is not None and observed_at >= recorded_to):
        return SourceApplicabilityStatus.UNKNOWN
    return SourceApplicabilityStatus.APPLICABLE


def _evaluate_source_freshness(
    source: SourceRecord,
    *,
    evaluated_at: datetime,
) -> SourceFreshnessDTO:
    """Evaluate a signed source policy against the decision observation clock.

    The boundary is inclusive: a source is CURRENT through exactly
    ``verified_at + max_age_seconds`` and STALE after it.  Integer timedelta
    components avoid floating-point rounding and support the model's complete
    positive-integer domain without constructing an overflowing timedelta.
    """

    policy = source.freshness_policy
    if source.verified_at > evaluated_at:
        return SourceFreshnessDTO(
            status=SourceFreshnessStatus.UNKNOWN,
            reason_code="SOURCE_VERIFIED_AT_IN_FUTURE",
            evaluated_at=evaluated_at,
            verified_at=source.verified_at,
            max_age_seconds=None if policy is None else policy.max_age_seconds,
        )
    if policy is None:
        return SourceFreshnessDTO(
            status=SourceFreshnessStatus.UNKNOWN,
            reason_code="FRESHNESS_POLICY_NOT_DEFINED",
            evaluated_at=evaluated_at,
            verified_at=source.verified_at,
            max_age_seconds=None,
        )

    age = evaluated_at - source.verified_at
    age_whole_seconds = age.days * 86_400 + age.seconds
    within_policy = age_whole_seconds < policy.max_age_seconds or (
        age_whole_seconds == policy.max_age_seconds and age.microseconds == 0
    )
    status = SourceFreshnessStatus.CURRENT if within_policy else SourceFreshnessStatus.STALE
    return SourceFreshnessDTO(
        status=status,
        reason_code=(
            "SOURCE_FRESHNESS_CURRENT"
            if status is SourceFreshnessStatus.CURRENT
            else "SOURCE_FRESHNESS_STALE"
        ),
        evaluated_at=evaluated_at,
        verified_at=source.verified_at,
        max_age_seconds=policy.max_age_seconds,
    )


_PRIMARY_AUTHORITY_TYPES = frozenset(
    {
        SourceAuthorityType.PRIMARY_LAW,
        SourceAuthorityType.IMPLEMENTING_REGULATION,
        SourceAuthorityType.OFFICIAL_PORTAL,
        SourceAuthorityType.OFFICIAL_CIRCULAR,
    }
)

_OFFICIAL_SOURCE_HOSTS = frozenset(
    {
        "www.imigrasi.go.id",
        "evisa.imigrasi.go.id",
        "peraturan.bpk.go.id",
        "kemenimipas.go.id",
        "www.peraturan.go.id",
    }
)


def _has_official_source_url(canonical_url: str) -> bool:
    """Accept only pinned HTTPS authority hosts, without credential/port tricks."""

    try:
        parsed = urlsplit(canonical_url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.hostname is not None
        and parsed.hostname.lower() in _OFFICIAL_SOURCE_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port is None
    )


def _source_is_authoritative_and_applicable(
    source: SourceRecord,
    *,
    decision: Decision,
    compiled: CompiledRulePack,
) -> bool:
    """Validate signed authority, bitemporal, and provenance-clock integrity."""

    applicability = _source_applicability_status(
        source_status=source.status,
        legal_from=source.legal_period.from_,
        legal_to=source.legal_period.to,
        recorded_from=source.recorded_period.from_,
        recorded_to=source.recorded_period.to,
        effective_at=decision.effective_at,
        observed_at=decision.observed_at,
    )
    return (
        source.status is SourceStatus.VERIFIED
        and source.authority_type in _PRIMARY_AUTHORITY_TYPES
        and _has_official_source_url(source.canonical_url)
        and applicability is SourceApplicabilityStatus.APPLICABLE
        and source.recorded_period.from_ <= source.retrieved_at
        and source.retrieved_at <= source.verified_at
        and (source.recorded_period.to is None or source.verified_at < source.recorded_period.to)
        and source.verified_at <= compiled.source_pack.protected.signed_at
    )


def _build_sources_dto(
    decision: Decision,
    compiled: CompiledRulePack,
    *,
    request_trace: str,
) -> list[dict[str, JsonValue]]:
    """Resolve the decision's ``source_refs`` against the pack's own
    ``source_records`` — the A.4.1 wire projection (one roundtrip, the
    backend already owns the pack, the UI never does UUID-join gymnastics).

    ``source_record_id`` is included alongside A.4.1's display fields: the
    UI matches ``Decision.source_refs`` UUIDs to DTOs by it, so omitting it
    would make the projection unjoinable. First-seen reference order is
    preserved (deterministic — mirrors the decision's own candidate/reason
    ordering). A reference unresolvable against the pack is a pack-integrity
    defect: it is omitted from the DTO list and counted in a warning (the
    G-c collector independently flags the same defect from the audit row).
    """

    referenced: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    def collect(refs: tuple[uuid.UUID, ...]) -> None:
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                referenced.append(ref)

    for candidate in decision.candidates:
        collect(candidate.source_refs)
    for reason in (*decision.review_reasons, *decision.no_path_reasons, *decision.notices):
        collect(reason.source_refs)

    index = {
        source.source_record_id: source for source in compiled.source_pack.payload.source_records
    }
    dtos: list[dict[str, JsonValue]] = []
    unresolved = 0
    for ref in referenced:
        source = index.get(ref)
        if source is None:
            unresolved += 1
            continue
        freshness = _evaluate_source_freshness(
            source,
            evaluated_at=decision.observed_at,
        )
        dtos.append(
            {
                "source_record_id": str(source.source_record_id),
                "source_key": source.source_key,
                "title": source.title,
                "publisher": source.publisher,
                "authority_type": source.authority_type.value,
                "is_primary_authority": (
                    source.authority_type in _PRIMARY_AUTHORITY_TYPES
                    and _has_official_source_url(source.canonical_url)
                ),
                "status": source.status.value,
                "document_number": source.document_number,
                "canonical_url": source.canonical_url,
                "locators": [
                    {"kind": locator.kind.value, "value": locator.value}
                    for locator in source.locators
                ],
                "legal_period_from": source.legal_period.from_.isoformat(),
                "legal_period_to": (
                    source.legal_period.to.isoformat()
                    if source.legal_period.to is not None
                    else None
                ),
                "recorded_period_from": source.recorded_period.from_.isoformat(),
                "retrieved_at": source.retrieved_at.isoformat(),
                "verified_at": source.verified_at.isoformat(),
                "applicability": {
                    "status": _source_applicability_status(
                        source_status=source.status,
                        legal_from=source.legal_period.from_,
                        legal_to=source.legal_period.to,
                        recorded_from=source.recorded_period.from_,
                        recorded_to=source.recorded_period.to,
                        effective_at=decision.effective_at,
                        observed_at=decision.observed_at,
                    ).value,
                    "effective_at": decision.effective_at.isoformat(),
                    "observed_at": decision.observed_at.isoformat(),
                },
                "freshness": freshness.model_dump(mode="json"),
            }
        )
    if unresolved:
        logger.warning(
            "evaluate path: %d referenced source(s) unresolvable in pack (trace=%s)",
            unresolved,
            request_trace,
        )
    return dtos


def _build_display(
    decision: Decision,
    compiled: CompiledRulePack,
    *,
    request_trace: str,
    pricing_catalog: ExactPricingCatalog,
) -> dict[str, JsonValue]:
    """The B.2 ``display`` block — pack-backed candidate display data.

    Product names and stay/extension policy come from the signed RulePack.
    Documentation and processing-time assessments remain explicit UNKNOWN
    until authoritative catalog adapters provide evidence; pricing comes only
    from the exact-key PricingTool adapter and never invents an amount.
    """

    products = {
        product.product_version_id: product for product in compiled.source_pack.payload.products
    }
    entries: list[dict[str, JsonValue]] = []
    unresolved = 0
    for candidate in decision.candidates:
        product = products.get(candidate.product_version_id)
        if product is None:
            unresolved += 1
            continue
        if decision.state is DecisionState.HUMAN_REVIEW_REQUIRED:
            # Owner ruling #5 (2026-08-25, docs/plans/2026-08-24-visa-
            # oracle-live/OWNER-RULINGS-2026-08-25.md §5): "zero-risultati
            # è vietato come schermata". A candidate carried alongside a
            # HUMAN_REVIEW_REQUIRED verdict is INFORMATIONAL — the visitor
            # is told plainly they qualify (``legal_eligibility`` stays
            # "SUPPORTED" below), but no price may accompany it. `quotes`
            # is frozen empty on this state (models.py's
            # `_check_state_conditionals` bans it with no exception), so a
            # real resolved price here would violate contract C1 and trip
            # `_check_projection_integrity` ("a candidate without a quote
            # cannot claim a price") — which previously degraded the
            # WHOLE response to TEMPORARILY_UNAVAILABLE, an outage screen
            # in place of the honest "you qualify, talk to a consultant"
            # screen the ruling demands. Skip `resolve_candidate_pricing`
            # entirely here rather than let a genuinely resolvable price
            # leak through and reach that guard.
            pricing = PricingResolution(
                status="CONTACT_REQUIRED",
                reason_code="PRICING_PENDING_HUMAN_REVIEW",
                evaluated_at=decision.evaluated_at,
            )
        else:
            pricing = resolve_candidate_pricing(
                product,
                pricing_catalog=pricing_catalog,
                evaluated_at=decision.evaluated_at,
            )
        entries.append(
            {
                "product_code": str(candidate.product_code),
                "product_version_id": str(candidate.product_version_id),
                "rank": candidate.rank,
                "name": {"id": product.names.id, "en": product.names.en},
                "tagline": None,
                "stay_policy": {
                    "stay": product.stay_policy.model_dump(mode="json"),
                    "extension": product.extension_policy.model_dump(mode="json"),
                },
                "documentation": {
                    "status": "UNKNOWN",
                    "reason_code": "DOCUMENTATION_CATALOG_NOT_VERIFIED",
                    "observed_at": decision.observed_at.isoformat(),
                    "requirements": [],
                    "checklist": [],
                },
                "processing_timeline": {
                    "status": "UNKNOWN",
                    "reason_code": "PROCESSING_TIMELINE_NOT_VERIFIED",
                    "observed_at": decision.observed_at.isoformat(),
                    "anchor_date": None,
                    "estimated_completion_from": None,
                    "estimated_completion_to": None,
                },
                "availability": {
                    "legal_eligibility": "SUPPORTED",
                    "operational_availability": {
                        "status": "UNKNOWN",
                        "reason_code": "OPERATIONAL_AVAILABILITY_NOT_EVALUATED",
                        "observed_at": decision.observed_at.isoformat(),
                        "source_refs": [],
                    },
                    "bali_zero_service_availability": {
                        "status": "UNKNOWN",
                        "reason_code": "BALI_ZERO_SERVICE_AVAILABILITY_NOT_EVALUATED",
                        "observed_at": decision.observed_at.isoformat(),
                        "source_refs": [],
                    },
                },
                "pricing": pricing.as_json(),
            }
        )
    if unresolved:
        logger.warning(
            "evaluate path: %d candidate(s) with no product in pack (trace=%s)",
            unresolved,
            request_trace,
        )
    return {"candidates": entries}


def _attach_price_quotes(
    decision: Decision,
    compiled: CompiledRulePack,
    *,
    pricing_catalog: ExactPricingCatalog,
) -> Decision:
    """Attach exact-key PricingTool quotes before decision sealing/persistence."""

    if decision.state is not DecisionState.SUPPORTED_CANDIDATES:
        return decision
    if decision.decision_id is None:  # pragma: no cover - evaluated-state invariant
        return decision
    products = {
        product.product_version_id: product for product in compiled.source_pack.payload.products
    }
    quotes = []
    for candidate in decision.candidates:
        product = products.get(candidate.product_version_id)
        if product is None:
            continue
        resolution = resolve_candidate_pricing(
            product,
            pricing_catalog=pricing_catalog,
            evaluated_at=decision.evaluated_at,
        )
        quote = build_price_quote(product, resolution, decision_id=decision.decision_id)
        if quote is not None:
            quotes.append(quote)
    payload = decision.model_dump(mode="python")
    payload["quotes"] = tuple(quotes)
    return Decision.model_validate(payload)


_DISCLOSED_REVIEW_REASON_CODES: MappingProxyType[DisclosedReviewFlag, str] = MappingProxyType(
    {
        DisclosedReviewFlag.CRIMINAL_RECORD: "DISCLOSED_CRIMINAL_RECORD_REVIEW",
        DisclosedReviewFlag.HEALTH_CONCERN: "DISCLOSED_HEALTH_CONCERN_REVIEW",
        DisclosedReviewFlag.PRIOR_VISA_REFUSAL: "DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW",
        DisclosedReviewFlag.NOT_CERTAIN: "DISCLOSED_UNCERTAINTY_REVIEW",
        DisclosedReviewFlag.PEP_OR_SANCTIONS: "DISCLOSED_PEP_OR_SANCTIONS_REVIEW",
        DisclosedReviewFlag.SOURCE_OF_FUNDS_UNCLEAR: "DISCLOSED_SOURCE_OF_FUNDS_REVIEW",
        DisclosedReviewFlag.DIPLOMATIC_PASSPORT: "DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW",
        DisclosedReviewFlag.AMBIGUOUS_SPONSOR: "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW",
        DisclosedReviewFlag.ACTIVITY_BOUNDARY: "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW",
        DisclosedReviewFlag.MULTI_PURPOSE_TRIP: "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW",
        DisclosedReviewFlag.CONFLICTING_IMMIGRATION_STATUS: (
            "CONFLICTING_IMMIGRATION_STATUS_REVIEW"
        ),
    }
)


def _apply_minor_privacy_hold(decision: Decision, facts: ApplicantFacts) -> Decision:
    """Apply Privacy Policy V1's non-eligibility guardian safety boundary.

    The public evaluation contract has no guardian-identity/consent fact, so a
    known minor can never prove that an automated supported outcome is safe.
    This deterministic adapter may only abstain: it cannot create, retain or
    reorder a candidate. Empty citations are intentional because this is a
    product/privacy workflow control, not a claim of legal visa ineligibility.
    """

    if decision.state is DecisionState.TEMPORARILY_UNAVAILABLE:
        return decision
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=decision.effective_at)
    minor_fact = snapshot.values[FactPath.DERIVED_IS_MINOR]
    if isinstance(minor_fact, UnknownFact):
        if decision.state is DecisionState.HUMAN_REVIEW_REQUIRED:
            return decision
        missing = tuple(
            sorted(
                {*decision.missing_facts, FactPath.PERSON_BIRTH_DATE},
                key=lambda path: path.value,
            )
        )
        payload = decision.model_dump(mode="python")
        payload.update(
            {
                "state": "NEEDS_INPUT",
                "candidates": (),
                "missing_facts": missing,
                "review_reasons": (),
                "no_path_reasons": (),
                "outage": None,
                "quotes": (),
                "decision_integrity": None,
            }
        )
        return Decision.model_validate(payload)
    if minor_fact.value is not True:
        return decision

    reason = Reason(
        code="MINOR_GUARDIAN_PRIVACY_REVIEW",
        rule_ids=("system.privacy.minor-guardian-review",),
        source_refs=(),
    )
    existing_reasons = (
        decision.review_reasons if decision.state is DecisionState.HUMAN_REVIEW_REQUIRED else ()
    )
    payload = decision.model_dump(mode="python")
    payload.update(
        {
            "state": "HUMAN_REVIEW_REQUIRED",
            "candidates": (),
            "missing_facts": (),
            "review_reasons": (*existing_reasons, reason),
            "no_path_reasons": (),
            "outage": None,
            "quotes": (),
            "decision_integrity": None,
        }
    )
    return Decision.model_validate(payload)


def _apply_decisive_source_authority_hold(
    decision: Decision,
    compiled: CompiledRulePack,
) -> Decision:
    """Abstain unless every decisive citation is authoritative at both clocks.

    This runs after deterministic evaluation but before sealing/persistence.
    It is deliberately independent of ``Rule.safety_critical``: no supported
    candidate or definitive no-path result may rely on a secondary, revoked,
    superseded, unavailable, legally inapplicable, system-time-inapplicable,
    or non-current source.
    """

    if decision.state not in (
        DecisionState.SUPPORTED_CANDIDATES,
        DecisionState.NO_SUPPORTED_PATH,
    ):
        return decision

    rule_ids: set[str] = set()
    decisive_refs: set[uuid.UUID] = set()
    if decision.state is DecisionState.SUPPORTED_CANDIDATES:
        for candidate in decision.candidates:
            rule_ids.update(candidate.support_rule_ids)
            decisive_refs.update(candidate.source_refs)
    else:
        for reason in decision.no_path_reasons:
            rule_ids.update(reason.rule_ids)
            decisive_refs.update(reason.source_refs)

    source_index = {
        source.source_record_id: source for source in compiled.source_pack.payload.source_records
    }
    invalid_refs: set[uuid.UUID] = set()
    freshness_stale_refs: set[uuid.UUID] = set()
    freshness_unknown_refs: set[uuid.UUID] = set()
    for source_ref in decisive_refs:
        source = source_index.get(source_ref)
        if source is None:
            invalid_refs.add(source_ref)
            continue
        if not _source_is_authoritative_and_applicable(
            source,
            decision=decision,
            compiled=compiled,
        ):
            invalid_refs.add(source_ref)
            continue

        freshness = _evaluate_source_freshness(
            source,
            evaluated_at=decision.observed_at,
        )
        if freshness.status is SourceFreshnessStatus.STALE:
            freshness_stale_refs.add(source_ref)
        elif freshness.status is not SourceFreshnessStatus.CURRENT:
            freshness_unknown_refs.add(source_ref)

    reasons: list[Reason] = []
    stable_rule_ids = tuple(sorted(rule_ids)) or ("system.decisive-source-gate",)
    if not decisive_refs or invalid_refs:
        reasons.append(
            Reason(
                code="DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(invalid_refs, key=str)),
            )
        )
    if freshness_unknown_refs:
        reasons.append(
            Reason(
                code="DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(freshness_unknown_refs, key=str)),
            )
        )
    if freshness_stale_refs:
        reasons.append(
            Reason(
                code="DECISIVE_SOURCE_STALE",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(freshness_stale_refs, key=str)),
            )
        )
    if not reasons:
        return decision

    payload = decision.model_dump(mode="python")
    payload.update(
        {
            "state": "HUMAN_REVIEW_REQUIRED",
            "candidates": (),
            "missing_facts": (),
            "review_reasons": tuple(reasons),
            "no_path_reasons": (),
            "outage": None,
            "quotes": (),
            "trace_sha256": decision.trace_sha256,
            "decision_integrity": None,
        }
    )
    return Decision.model_validate(payload)


def _apply_safety_critical_source_hold(
    decision: Decision,
    compiled: CompiledRulePack,
) -> Decision:
    """Abstain unless every active safety-critical source is CURRENT.

    The hold is global for an otherwise conclusive decision. This also covers
    authoritative-list omissions that the rule condition itself cannot detect
    (for example, a country missing from a stale list).
    """

    # Freshness cannot outrank an infrastructure outage, cannot consume facts
    # that the evaluator still needs, and must not replace a more specific
    # review already raised by the signed rules. It is an abstention adapter
    # only for otherwise conclusive legal outcomes.
    if decision.state not in (
        DecisionState.SUPPORTED_CANDIDATES,
        DecisionState.NO_SUPPORTED_PATH,
    ):
        return decision

    rule_ids: list[str] = []
    source_refs: set[uuid.UUID] = set()
    for rule in compiled.active_rules(effective_at=decision.effective_at):
        if not rule.source_rule.safety_critical:
            continue
        rule_ids.append(rule.rule_id)
        source_refs.update(rule.source_rule.source_refs)
    if not source_refs:
        return decision

    source_index = {
        source.source_record_id: source for source in compiled.source_pack.payload.source_records
    }
    invalid_refs: set[uuid.UUID] = set()
    stale_refs: set[uuid.UUID] = set()
    unknown_refs: set[uuid.UUID] = set()
    for source_ref in source_refs:
        source = source_index.get(source_ref)
        if source is None:
            invalid_refs.add(source_ref)
            continue
        if not _source_is_authoritative_and_applicable(
            source,
            decision=decision,
            compiled=compiled,
        ):
            invalid_refs.add(source_ref)
            continue
        freshness = _evaluate_source_freshness(
            source,
            evaluated_at=decision.observed_at,
        )
        if freshness.status is SourceFreshnessStatus.STALE:
            stale_refs.add(source_ref)
        elif freshness.status is not SourceFreshnessStatus.CURRENT:
            unknown_refs.add(source_ref)
    if not invalid_refs and not stale_refs and not unknown_refs:
        return decision

    stable_rule_ids = tuple(sorted(set(rule_ids)))
    reasons: list[Reason] = []
    if invalid_refs:
        reasons.append(
            Reason(
                code="SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(invalid_refs, key=str)),
            )
        )
    if unknown_refs:
        reasons.append(
            Reason(
                code="SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(unknown_refs, key=str)),
            )
        )
    if stale_refs:
        reasons.append(
            Reason(
                code="SAFETY_CRITICAL_SOURCE_STALE",
                rule_ids=stable_rule_ids,
                source_refs=tuple(sorted(stale_refs, key=str)),
            )
        )
    payload = decision.model_dump(mode="python")
    payload.update(
        {
            "state": "HUMAN_REVIEW_REQUIRED",
            "candidates": (),
            "missing_facts": (),
            "review_reasons": tuple(reasons),
            "no_path_reasons": (),
            "outage": None,
            "quotes": (),
            "trace_sha256": decision.trace_sha256,
            "decision_integrity": None,
        }
    )
    return Decision.model_validate(payload)


def _apply_disclosed_review_flags(
    decision: Decision,
    flags: tuple[DisclosedReviewFlag, ...],
) -> Decision:
    """Monotone abstention adapter for review disclosures outside the pack.

    This adapter cannot CREATE a candidate — it only ever lowers a legal
    outcome to ``HUMAN_REVIEW_REQUIRED``.  It does, however, **retain** the
    candidates the engine had already computed (owner ruling #5, 2026-08-25,
    ``docs/plans/2026-08-24-visa-oracle-live/OWNER-RULINGS-2026-08-25.md``
    §5: *"zero-risultati è vietato come schermata — ogni vicolo cieco diventa
    un candidato onesto + una mano tesa"*).

    Erasing them here was the ruling applied to one branch out of two: the
    in-pack review branch in ``evaluator.py`` was updated, this adapter —
    which predates the ruling and runs on EVERY public evaluation — was not,
    and it is the one that actually fires (measured 2026-08-25: every ``work``
    and every ``business`` applicant raises ``ACTIVITY_BOUNDARY`` through
    ``fact-mapper.ts``'s always-asked ``work_role``/``business_activity``,
    so no applicant in those categories could ever be shown a candidate).
    See ``RULING5-HALF-APPLIED.md`` in that same directory.

    Monotonicity is unchanged and is what the retention rests on: the
    candidate list is copied verbatim, never extended or re-ranked, and
    ``quotes`` stays ``()`` — contract C1 (a candidate without a resolved
    quote cannot exhibit a price) is what blocks a purchase button here, not
    the emptiness of ``candidates``.  A retained candidate is therefore
    priceless and unbuyable by construction, exactly as ruling #5 intends.

    Retention is self-scoping: ``_check_state_conditionals`` already forces
    ``candidates == ()`` on ``NEEDS_INPUT``/``NO_SUPPORTED_PATH``, so only a
    ``SUPPORTED_CANDIDATES`` or ``HUMAN_REVIEW_REQUIRED`` baseline has
    anything to carry.

    Empty ``source_refs`` is intentional: these codes describe an applicant
    disclosure requiring a human workflow, not a legal eligibility claim.
    They must not borrow a regulatory citation that the signed RulePack did
    not declare.
    """

    if not flags:
        return decision
    if decision.decision_id is None or decision.public_id is None:
        return decision

    flag_seed = ",".join(flag.value for flag in flags)
    decision_id = uuid.uuid5(decision.decision_id, flag_seed)
    public_id = hashlib.sha256(f"{decision.public_id}:{flag_seed}".encode()).hexdigest()[:20]
    disclosed_reasons = tuple(
        Reason(
            code=_DISCLOSED_REVIEW_REASON_CODES[flag],
            rule_ids=(f"system.disclosed-review.{flag.value.lower().replace('_', '-')}",),
            source_refs=(),
        )
        for flag in flags
    )
    existing_reasons = (
        decision.review_reasons if decision.state.value == "HUMAN_REVIEW_REQUIRED" else ()
    )
    payload = decision.model_dump(mode="python")
    payload.update(
        {
            "decision_id": decision_id,
            "public_id": public_id,
            "state": "HUMAN_REVIEW_REQUIRED",
            # Owner ruling #5: the candidates ride along, verbatim from the
            # underlying decision. `payload` already carries them, and this
            # adapter deliberately does NOT overwrite the key — which is how
            # "cannot create a candidate" and "does retain one" are both true
            # at once. `quotes` is still forced to () below.
            "missing_facts": (),
            "review_reasons": (*existing_reasons, *disclosed_reasons),
            "no_path_reasons": (),
            "outage": None,
            "quotes": (),
            "trace_sha256": decision.trace_sha256,
            "decision_integrity": None,
        }
    )
    return Decision.model_validate(payload)


_PublicPolicyAdapter: TypeAlias = Callable[
    [Decision, ApplicantFacts, CompiledRulePack, tuple[DisclosedReviewFlag, ...]],
    Decision,
]


def _minor_privacy_policy_adapter(
    decision: Decision,
    facts: ApplicantFacts,
    _compiled: CompiledRulePack,
    _disclosed_review_flags: tuple[DisclosedReviewFlag, ...],
) -> Decision:
    return _apply_minor_privacy_hold(decision, facts)


def _decisive_source_policy_adapter(
    decision: Decision,
    _facts: ApplicantFacts,
    compiled: CompiledRulePack,
    _disclosed_review_flags: tuple[DisclosedReviewFlag, ...],
) -> Decision:
    return _apply_decisive_source_authority_hold(decision, compiled)


def _safety_critical_source_policy_adapter(
    decision: Decision,
    _facts: ApplicantFacts,
    compiled: CompiledRulePack,
    _disclosed_review_flags: tuple[DisclosedReviewFlag, ...],
) -> Decision:
    return _apply_safety_critical_source_hold(decision, compiled)


def _disclosed_review_policy_adapter(
    decision: Decision,
    _facts: ApplicantFacts,
    _compiled: CompiledRulePack,
    disclosed_review_flags: tuple[DisclosedReviewFlag, ...],
) -> Decision:
    return _apply_disclosed_review_flags(decision, disclosed_review_flags)


# This ordered registry is both the executable chain and report provenance.
# Adding, removing, or reordering a public adapter therefore changes behavior
# and the offline evidence manifest in the same diff.
_PUBLIC_POLICY_ADAPTERS: tuple[tuple[str, _PublicPolicyAdapter], ...] = (
    ("_apply_minor_privacy_hold", _minor_privacy_policy_adapter),
    ("_apply_decisive_source_authority_hold", _decisive_source_policy_adapter),
    ("_apply_safety_critical_source_hold", _safety_critical_source_policy_adapter),
    ("_apply_disclosed_review_flags", _disclosed_review_policy_adapter),
)
PUBLIC_POLICY_ADAPTER_NAMES: tuple[str, ...] = tuple(
    name for name, _adapter in _PUBLIC_POLICY_ADAPTERS
)


def apply_public_policy_adapters(
    decision: Decision,
    facts: ApplicantFacts,
    compiled: CompiledRulePack,
    *,
    disclosed_review_flags: tuple[DisclosedReviewFlag, ...] = (),
) -> Decision:
    """Apply every deterministic abstention adapter used by the public path.

    Keeping the ordering in one pure helper prevents offline evidence tools
    from silently drifting away from the endpoint. Runtime-only operations
    such as binding resolution, retention, pricing, sealing, and persistence
    remain outside this helper.
    """

    for _name, adapter in _PUBLIC_POLICY_ADAPTERS:
        decision = adapter(decision, facts, compiled, disclosed_review_flags)
    return decision


async def _save_evaluate_decision(
    db_pool: asyncpg.Pool,
    *,
    decision: Decision,
    rule_pack_db_id: uuid.UUID,
    ruleset_activation_id: uuid.UUID,
    environment: str,
    engine_mode: EngineMode,
    request_fingerprint: bytes,
    request_category: str,
    traffic_source: str,
) -> None:
    """INSERT one ``visa_decisions`` row for an evaluate-path ``Decision``.

    A documented mirror of ``shadow._save_shadow_decision`` with RECOMMEND
    surface metadata. A decision-id collision is accepted only when its
    immutable replay identity matches; otherwise persistence fails closed.

    - ``engine_surface`` is ``RECOMMEND`` (this module's surface), never
      ``MATCH`` — an audit row must never claim a surface it did not serve;
    - ``request_category`` is a plain validated ``str`` (migration 257's
      10-value space — ``shadow.py``'s own writer is typed to the 8-value
      ``Purpose`` enum and cannot express ``business``/``diaspora``);
    - ``traffic_source`` (migration 256) is always set explicitly — this
      endpoint is the first writer of the column (256's own header:
      "labeling lands with ... the read-path wiring in later PRs").
    """

    rule_pack_sha256 = (
        bytes.fromhex(decision.rule_pack.payload_sha256) if decision.rule_pack is not None else None
    )
    if decision.trace_sha256 is None or decision.decision_integrity is None:
        raise ValueError(
            "evaluated decisions must be trace-bound and authenticated before persistence"
        )
    trace_sha256 = bytes.fromhex(decision.trace_sha256)
    decision_hmac = bytes.fromhex(decision.decision_integrity.digest)
    decision_hmac_key_id = decision.decision_integrity.key_id
    candidate_summary = _build_candidate_summary(decision)
    grounding_summary = _build_grounding_summary(decision)
    citations = _collect_citations(grounding_summary)

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            inserted = await conn.fetchrow(
                """
            INSERT INTO visa_decisions (
                decision_id, environment, engine_surface, engine_mode,
                rule_pack_id, ruleset_activation_id, rule_pack_sha256, verdict,
                citations, engine_version, effective_at, observed_at, evaluated_at,
                request_fingerprint, request_category, candidate_summary,
                grounding_summary, traffic_source, trace_sha256,
                decision_hmac, decision_hmac_key_id
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9::text::jsonb, $10, $11, $12, $13,
                $14, $15, $16::text::jsonb, $17::text::jsonb, $18, $19, $20, $21
            )
            ON CONFLICT (decision_id) DO NOTHING
            RETURNING decision_id
            """,
                decision.decision_id,
                environment,
                _SURFACE.value,
                engine_mode.value,
                rule_pack_db_id,
                ruleset_activation_id,
                rule_pack_sha256,
                decision.state.value,
                json.dumps(citations),
                ENGINE_VERSION,
                decision.effective_at,
                decision.observed_at,
                decision.evaluated_at,
                request_fingerprint,
                request_category,
                json.dumps(candidate_summary),
                json.dumps(grounding_summary),
                traffic_source,
                trace_sha256,
                decision_hmac,
                decision_hmac_key_id,
            )
            if inserted is not None:
                return
            existing = await conn.fetchrow(
                """
                SELECT request_fingerprint, rule_pack_sha256, verdict,
                       effective_at, engine_mode, trace_sha256,
                       decision_hmac, decision_hmac_key_id
                FROM visa_decisions
                WHERE decision_id = $1
                """,
                decision.decision_id,
            )
            if existing is None:  # pragma: no cover - ON CONFLICT visibility invariant
                raise RuntimeError("conflicting decision row disappeared")
            expected = (
                request_fingerprint,
                rule_pack_sha256,
                decision.state.value,
                decision.effective_at,
                engine_mode.value,
                trace_sha256,
                decision_hmac,
                decision_hmac_key_id,
            )
            actual = (
                bytes(existing["request_fingerprint"]),
                (
                    None
                    if existing["rule_pack_sha256"] is None
                    else bytes(existing["rule_pack_sha256"])
                ),
                str(existing["verdict"]),
                existing["effective_at"],
                str(existing["engine_mode"]),
                (None if existing["trace_sha256"] is None else bytes(existing["trace_sha256"])),
                (None if existing["decision_hmac"] is None else bytes(existing["decision_hmac"])),
                (
                    None
                    if existing["decision_hmac_key_id"] is None
                    else str(existing["decision_hmac_key_id"])
                ),
            )
            if actual != expected:
                raise RuntimeError(
                    "existing decision row is incompatible with deterministic replay"
                )


async def run_evaluation(
    db_pool: asyncpg.Pool,
    *,
    facts: ApplicantFacts,
    traffic_source: str,
    request_category_hint: str | None,
    request_trace: str,
    disclosed_review_flags: tuple[DisclosedReviewFlag, ...] = (),
    evaluation_time: datetime | None = None,
) -> dict[str, JsonValue]:
    """Run one evaluate-path evaluation and build the B.2 envelope body.

    Pack and engine failures degrade to TEMPORARILY_UNAVAILABLE. Persistence
    is best-effort in SHADOW mode because the visible response stays CURATED;
    ENFORCE fails closed to TEMPORARILY_UNAVAILABLE when durable persistence
    cannot be proven. ``traffic_source`` MUST already be allowlist-checked by the
    router (this function trusts it; the synthetic-class gate is the
    router's job, one layer up, next to the other request validations).

    NEVER logs applicant facts — every log line carries only the caller-
    supplied ``request_trace`` (a random, PII-independent identifier), the
    resolved environment, the verdict, and counts.
    """

    now = evaluation_time or datetime.now(timezone.utc)
    engine_mode = resolve_evaluate_mode()

    if engine_mode is EngineMode.OFF:
        return build_temp_unavailable_body(
            now=now,
            code="EVALUATE_SURFACE_DISABLED",
            mode=engine_mode,
        )

    environment = _resolve_evaluate_environment()

    if not await _retention_gate_allows_persistence(
        db_pool,
        environment=environment,
        evaluated_at=now,
        request_trace=request_trace,
    ):
        return build_temp_unavailable_body(
            now=now,
            code="RETENTION_POLICY_UNAVAILABLE",
            mode=engine_mode,
        )

    try:
        binding = await _resolve_active_pack_binding(
            db_pool,
            environment=environment,
            effective_at=now,
            observed_at=now,
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError):
        logger.warning(
            "evaluate path: pack binding query failed (trace=%s)", request_trace, exc_info=True
        )
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE", mode=engine_mode)
    if binding is None:
        logger.info(
            "evaluate path: no active rule pack for environment=%s, unavailable (trace=%s)",
            environment,
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE", mode=engine_mode)

    try:
        verified = verify_rule_pack(
            binding.raw_envelope,
            trust_store=StaticTrustStore.from_env(),
            observed_at=now,
        )
    except RulePackVerificationError as exc:
        logger.warning("evaluate path: rule pack verification failed: %s", exc)
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE", mode=engine_mode)

    try:
        compiled = build_compiled_pack(verified.pack)
    except RulePackCompilationError as exc:
        logger.warning("evaluate path: rule pack compilation failed: %s", exc)
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE", mode=engine_mode)

    try:
        pricing_catalog: ExactPricingCatalog = await asyncio.to_thread(get_pricing_service)
    except Exception as exc:
        # Pricing availability cannot overwrite a legal decision. Log only the
        # exception class; adapter exceptions may include catalog payloads or paths.
        logger.warning(
            "evaluate path: pricing catalog acquisition failed: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        pricing_catalog = UnavailablePricingCatalog()

    try:
        identity_provider = resolve_identity_provider()
        evaluation = evaluate_with_trace(
            facts,
            compiled,
            effective_at=now,
            observed_at=now,
            identity_provider=identity_provider,
        )
        decision = apply_public_policy_adapters(
            evaluation.decision,
            facts,
            compiled,
            disclosed_review_flags=disclosed_review_flags,
        )
        try:
            decision = _attach_price_quotes(
                decision,
                compiled,
                pricing_catalog=pricing_catalog,
            )
        except Exception as exc:
            logger.warning(
                "evaluate path: price quote projection failed: %s (trace=%s)",
                type(exc).__name__,
                request_trace,
            )
            pricing_catalog = UnavailablePricingCatalog()
        keyring = resolve_engine_hmac_keyring(compiled.environment, now)
        decision = seal_decision(
            decision,
            key=keyring.minting_key,
            trace=evaluation.trace,
        )
    except (PlaceholderIdentityNotAllowedError, FactsFingerprintKeyUnavailableError):
        logger.warning(
            "evaluate path: active pack environment=%s needs a real crypto "
            "identity_provider (STEP-6d) / a provisioned facts-fingerprint "
            "key, unavailable (trace=%s)",
            environment,
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE", mode=engine_mode)
    except FactsFingerprintKeyError:
        logger.warning(
            "evaluate path: malformed facts-fingerprint key config "
            "(VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON), unavailable (trace=%s)",
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE", mode=engine_mode)
    except Exception as exc:  # defense-in-depth — evaluate() is documented pure/total
        # Log the exception TYPE only, never str(exc): evaluate() runs over
        # ApplicantFacts, and a stray ValidationError/KeyError message could
        # echo a raw fact value — this module must never log facts (Law 2).
        logger.warning("evaluate path: evaluate() failed: %s", type(exc).__name__)
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE", mode=engine_mode)

    request_category = derive_request_category(facts, request_category_hint)
    # The request correlator IS the STEP-6d facts fingerprint (see module
    # docstring): keyed HMAC, non-reversible, exactly the G-a "distinct
    # requests" granularity.
    if decision.facts_fingerprint is None:  # pragma: no cover - evaluated-state invariant
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE", mode=engine_mode)
    request_fingerprint = bytes.fromhex(decision.facts_fingerprint.digest)

    try:
        await _save_evaluate_decision(
            db_pool,
            decision=decision,
            rule_pack_db_id=binding.rule_pack_id,
            ruleset_activation_id=binding.ruleset_activation_id,
            environment=environment,
            engine_mode=engine_mode,
            request_fingerprint=request_fingerprint,
            request_category=request_category,
            traffic_source=traffic_source,
        )
    except Exception as exc:
        # The audit trail must never break the product response: the caller's
        # decision is already computed and valid. Logged loudly (type only,
        # never the exception text — a driver error could embed statement
        # parameters) for the ops channel; the G-a collector sees the gap.
        logger.warning(
            "evaluate path: decision persistence failed: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
            exc_info=True,
        )
        if engine_mode is EngineMode.ENFORCE:
            return build_temp_unavailable_body(
                now=now,
                code="DECISION_PERSISTENCE_UNAVAILABLE",
                mode=engine_mode,
            )

    try:
        envelope = {
            "mode": resolve_response_mode(engine_mode),
            "decision": decision.model_dump(mode="json"),
        }
        envelope["sources"] = _build_sources_dto(
            decision,
            compiled,
            request_trace=request_trace,
        )
        envelope["display"] = _build_display(
            decision,
            compiled,
            request_trace=request_trace,
            pricing_catalog=pricing_catalog,
        )
        validated = VisaOracleEvaluateResponse.model_validate(envelope)
    except Exception as exc:
        # Projection defects (unresolved source/product, malformed quote, or
        # response-contract drift) must never escape as a 500 or a partial,
        # fabricated result. Log type and trace only; never the payload/error
        # text because validation messages can include applicant-derived data.
        logger.error(
            "evaluate path: public projection failed: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        return build_temp_unavailable_body(
            now=now,
            code="PUBLIC_PROJECTION_UNAVAILABLE",
            mode=engine_mode,
        )

    logger.info(
        "evaluate path decision ready: trace=%s verdict=%s candidates=%d",
        request_trace,
        decision.state.value,
        len(decision.candidates),
    )
    return validated.model_dump(mode="json")


async def run_public_evaluation(
    db_pool: asyncpg.Pool,
    *,
    request: VisaOracleEvaluateRequest,
    traffic_source: str,
    request_category_hint: str | None,
    request_trace: str,
    canonical_request: bytes,
    idempotency_key: str | None,
) -> VisaOracleEvaluateResponse:
    """Run the typed public contract, optionally with durable replay.

    A supplied idempotency key is never best-effort: inability to reserve or
    complete its durable record returns TEMPORARILY_UNAVAILABLE instead of a
    non-replayable successful decision.
    """

    facts = request.applicant_facts()
    entry_mode = resolve_evaluate_mode()
    if idempotency_key is not None and entry_mode is EngineMode.OFF:
        return _replay_rejection_response(mode=entry_mode, now=datetime.now(timezone.utc))
    if idempotency_key is None:
        try:
            body = await run_evaluation(
                db_pool,
                facts=facts,
                traffic_source=traffic_source,
                request_category_hint=request_category_hint,
                request_trace=request_trace,
                disclosed_review_flags=request.effective_review_flags(),
            )
            return VisaOracleEvaluateResponse.model_validate(body)
        except Exception as exc:
            logger.error(
                "evaluate path: public response validation failed: %s (trace=%s)",
                type(exc).__name__,
                request_trace,
            )
            return VisaOracleEvaluateResponse.model_validate(
                build_temp_unavailable_body(
                    now=datetime.now(timezone.utc),
                    code="PUBLIC_PROJECTION_UNAVAILABLE",
                )
            )

    entry_environment = _resolve_evaluate_environment()
    retention_moment = datetime.now(timezone.utc)
    if not await _retention_gate_allows_persistence(
        db_pool,
        environment=entry_environment,
        evaluated_at=retention_moment,
        request_trace=request_trace,
    ):
        return VisaOracleEvaluateResponse.model_validate(
            build_temp_unavailable_body(
                now=retention_moment,
                code="RETENTION_POLICY_UNAVAILABLE",
                mode=entry_mode,
            )
        )

    key_sha256 = hash_idempotency_key(idempotency_key)
    key_moment = datetime.now(timezone.utc)
    try:
        environment = Environment(_resolve_evaluate_environment())
        keyring = resolve_engine_hmac_keyring(environment, key_moment)
    except (ValueError, FactsFingerprintKeyError, FactsFingerprintKeyUnavailableError):
        logger.warning("evaluate path: idempotency HMAC unavailable (trace=%s)", request_trace)
        return VisaOracleEvaluateResponse.model_validate(
            build_temp_unavailable_body(now=key_moment, code="IDEMPOTENCY_UNAVAILABLE")
        )
    mode_before_reserve = resolve_evaluate_mode()
    if mode_before_reserve is EngineMode.OFF:
        return _replay_rejection_response(mode=mode_before_reserve, now=datetime.now(timezone.utc))
    try:
        reservation = await reserve_idempotency(
            db_pool,
            key_sha256=key_sha256,
            canonical_request=canonical_request,
            environment=environment.value,
            minting_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
    except IdempotencyConflictError:
        raise
    except Exception as exc:
        logger.warning(
            "evaluate path: idempotency reservation unavailable: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        return VisaOracleEvaluateResponse.model_validate(
            build_temp_unavailable_body(
                now=datetime.now(timezone.utc), code="IDEMPOTENCY_UNAVAILABLE"
            )
        )
    if reservation.response is not None:
        replay_allowed, current_mode = await _replay_authority_matches(
            db_pool,
            response=reservation.response,
            expected_environment=environment.value,
            request_trace=request_trace,
        )
        if not replay_allowed:
            return _replay_rejection_response(
                mode=current_mode,
                now=datetime.now(timezone.utc),
            )
        return reservation.response

    try:
        body = await run_evaluation(
            db_pool,
            facts=facts,
            traffic_source=traffic_source,
            request_category_hint=request_category_hint,
            request_trace=request_trace,
            disclosed_review_flags=request.effective_review_flags(),
            evaluation_time=reservation.reserved_at,
        )
        response = VisaOracleEvaluateResponse.model_validate(body)
    except Exception as exc:
        logger.error(
            "evaluate path: idempotent response validation failed: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        response = VisaOracleEvaluateResponse.model_validate(
            build_temp_unavailable_body(
                now=reservation.reserved_at,
                code="PUBLIC_PROJECTION_UNAVAILABLE",
            )
        )
    # A reserved row intentionally remains incomplete when the surface or its
    # signed authority changes while the evaluator is running.  This is a
    # fail-closed tombstone until its Zero-approved policy deadline reclaims it; it
    # contains no response body or authentication material.  Configuration is
    # process-local rather than DB-transactional, so this double snapshot
    # narrows (but cannot make atomic) the final completion boundary.
    if (
        response.decision.state is DecisionState.TEMPORARILY_UNAVAILABLE
        and response.decision.outage is not None
        and response.decision.outage.code == "EVALUATE_SURFACE_DISABLED"
    ):
        return response
    completion_allowed, current_mode = await _replay_authority_matches(
        db_pool,
        response=response,
        expected_environment=environment.value,
        request_trace=request_trace,
    )
    if not completion_allowed:
        return _replay_rejection_response(
            mode=current_mode,
            now=datetime.now(timezone.utc),
        )
    try:
        completed = await complete_idempotency(
            db_pool,
            reservation=reservation,
            response=response,
            response_signing_key=keyring.minting_key,
            verification_keys=keyring.verification_keys,
        )
        replay_allowed, current_mode = await _replay_authority_matches(
            db_pool,
            response=completed,
            expected_environment=environment.value,
            request_trace=request_trace,
        )
        if not replay_allowed:
            return _replay_rejection_response(
                mode=current_mode,
                now=datetime.now(timezone.utc),
            )
        return completed
    except Exception as exc:
        logger.warning(
            "evaluate path: idempotency completion unavailable: %s (trace=%s)",
            type(exc).__name__,
            request_trace,
        )
        return VisaOracleEvaluateResponse.model_validate(
            build_temp_unavailable_body(now=reservation.reserved_at, code="IDEMPOTENCY_UNAVAILABLE")
        )


__all__ = [
    "ALLOW_SYNTHETIC_SOURCES_ENV",
    "DRIVER_TOKEN_ENV",
    "EVALUATE_ENVIRONMENT_ENV",
    "EVALUATE_MODE_ENV",
    "PUBLIC_POLICY_ADAPTER_NAMES",
    "apply_public_policy_adapters",
    "build_temp_unavailable_body",
    "derive_request_category",
    "resolve_allowed_synthetic_sources",
    "resolve_evaluate_mode",
    "resolve_evaluate_shadow_enabled",
    "resolve_response_mode",
    "run_evaluation",
    "run_public_evaluation",
    "verify_driver_token",
]
