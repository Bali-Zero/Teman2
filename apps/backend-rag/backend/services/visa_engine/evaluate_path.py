"""W1 — the Visa Oracle v2 evaluate read-path (RECOMMEND surface, SHADOW era).

Backing service for the public ``POST /api/visa-oracle/evaluate`` endpoint
(``app/routers/visa_oracle_evaluate.py``): canonical ``ApplicantFacts`` in,
the Kimi-spec B.2 envelope out — ``{mode, decision, sources, display}``
(``research/visa/2026-07-19-kimi-uiux-adaptation-spec.md`` §A.4.1/B.2) —
and exactly one full-fact SHADOW ``visa_decisions`` audit row persisted per
evaluation (migrations 252/255/256/257).

Spec: ``research/visa/2026-07-23-w1-evidence-machinery-brief.md`` Item 2.

Relationship to ``shadow.py`` (STEP-6c/6d): same fail-closed pack binding,
same crypto posture, same PII boundary — different surface. ``shadow.py``
is the fire-and-forget MATCH-surface audit twin whose response is never
rendered; THIS module is the RECOMMEND-surface read-path whose response IS
the product (the v2 UI renders it in ``mode="CURATED"`` form). The private
helpers are IMPORTED from ``shadow.py`` read-only — the file itself is not
touched — rather than triplicated: the pack-binding SQL and the 255
candidate/grounding/citation writers have exactly one home each
(``shadow.py``), the same single-home trade-off ``shadow.py`` itself
documented when it mirrored ``repository.py``.

Mode discipline (mirrors ``shadow.resolve_match_shadow_enabled``):

- ``VISA_ENGINE_EVALUATE_MODE`` — OFF (default) | SHADOW | ENFORCE. OFF is
  a disabled surface: the endpoint responds with the TEMPORARILY_UNAVAILABLE
  shape (``retryable=true``, HTTP 200) and persists NOTHING. SHADOW runs the
  evaluation and persists the audit row. ENFORCE is accepted (evaluation
  still runs, SHADOW semantics) but logs a one-time warning that the
  response-flip is not implemented — and the response ``mode`` STAYS
  ``"CURATED"`` (``resolve_response_mode`` can never return ``"ENGINE"`` in
  this lane; the ENFORCE flip is a separately-gated task).
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

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from types import MappingProxyType
from typing import TypeAlias

import asyncpg

from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.crypto import resolve_identity_provider
from backend.services.visa_engine.enums import (
    EngineMode,
    EngineSurface,
    VisaPurpose,
)
from backend.services.visa_engine.errors import (
    FactsFingerprintKeyError,
    FactsFingerprintKeyUnavailableError,
    PlaceholderIdentityNotAllowedError,
    RulePackCompilationError,
    RulePackVerificationError,
)
from backend.services.visa_engine.evaluator import evaluate
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
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

_enforce_not_implemented_warned = False


def _warn_enforce_not_implemented_once() -> None:
    global _enforce_not_implemented_warned
    if _enforce_not_implemented_warned:
        return
    logger.warning(
        "%s=ENFORCE requested but enforcement is not implemented yet; running SHADOW-only",
        EVALUATE_MODE_ENV,
    )
    _enforce_not_implemented_warned = True


def resolve_evaluate_shadow_enabled() -> bool:
    """Re-read ``EVALUATE_MODE_ENV`` fresh on every call.

    True iff the (stripped, upper-cased) value is ``SHADOW`` or ``ENFORCE``;
    anything else (missing, ``OFF``, or any invalid string) resolves to
    ``False``. ``ENFORCE`` is accepted (returns ``True`` — the evaluation
    still runs with SHADOW semantics) but logs a one-time warning that the
    response-flip is not implemented yet — a deliberate mirror of
    ``shadow.resolve_match_shadow_enabled``'s discipline.
    """

    raw = os.environ.get(EVALUATE_MODE_ENV, EngineMode.OFF.value).strip().upper()
    if raw == EngineMode.ENFORCE.value:
        _warn_enforce_not_implemented_once()
        return True
    return raw == EngineMode.SHADOW.value


def resolve_response_mode() -> str:
    """The B.2 envelope ``mode`` — always ``"CURATED"`` in this lane.

    ``"ENGINE"`` is the ENFORCE-era value (the engine verdict becomes the
    authoritative render source, Kimi spec §B.2/B.3). The flip is driven by
    a DB lever that does not exist yet and is gated separately (ENFORCE-
    GATE); this resolver is the single place that will read it. It
    deliberately CANNOT return ``"ENGINE"`` today — even under
    ``VISA_ENGINE_EVALUATE_MODE=ENFORCE`` the response keeps saying
    ``CURATED``, so a premature flag flip can never silently promote the
    engine verdict to authoritative in the UI (the same fail-closed posture
    as ``resolve_evaluate_shadow_enabled``'s warn-and-stay-SHADOW rule).
    """

    return "CURATED"


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


def build_temp_unavailable_body(*, now: datetime, code: str) -> dict[str, JsonValue]:
    """The TEMPORARILY_UNAVAILABLE-shaped envelope body (HTTP 200).

    Returned — with NOTHING persisted — whenever the evaluation cannot run:
    surface disabled (OFF), no active pack, pack verification/compilation
    failure, or the crypto/evaluation layer fail-closing. ``mode`` is still
    ``resolve_response_mode()``: the UI's ``resolveVerdict`` reads
    ``decision.state``/``outage.retryable`` on this path, and the curated
    labeling invariant (Kimi spec §B.4) must keep holding.

    The ``decision`` object mirrors the ``Decision`` wire shape but is NOT a
    validated ``models.Decision`` instance: ``facts_fingerprint`` is
    ``null`` because no evaluation happened, and fabricating an HMAC tag
    over facts that were never evaluated would be a dishonest integrity
    claim (the model's own invariant requires the field non-null, which is
    exactly why this is a documented wire shape, not a ``Decision``).
    """

    iso_now = now.astimezone(timezone.utc).isoformat()
    return {
        "mode": resolve_response_mode(),
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
        dtos.append(
            {
                "source_record_id": str(source.source_record_id),
                "source_key": source.source_key,
                "title": source.title,
                "publisher": source.publisher,
                "authority_type": source.authority_type.value,
                "status": source.status.value,
                "document_number": source.document_number,
                "canonical_url": source.canonical_url,
                "locators": [
                    {"kind": locator.kind.value, "value": locator.value}
                    for locator in source.locators
                ],
                "legal_period_from": source.legal_period.from_.isoformat(),
                "verified_at": source.verified_at.isoformat(),
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
) -> dict[str, JsonValue]:
    """The B.2 ``display`` block — pack-backed candidate display data.

    Field set is PINNED here (W1 brief Item 2, design-seat P2-2; Track C 4a
    consumes this contract): ``name`` / ``tagline`` / ``timeline`` /
    ``requirements`` / ``checklist`` per candidate. Only ``name`` (pack
    ``VisaProductVersion.names``) and ``timeline`` (pack
    ``stay_policy``/``extension_policy``) exist in rule-pack schema 1.0.0 —
    ``tagline``/``requirements``/``checklist`` are pinned as ``null``/empty
    placeholders rather than fabricated, and the pack-schema lane that
    introduces them populates them here.
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
        entries.append(
            {
                "product_code": str(candidate.product_code),
                "product_version_id": str(candidate.product_version_id),
                "rank": candidate.rank,
                "name": {"id": product.names.id, "en": product.names.en},
                "tagline": None,
                "timeline": {
                    "stay": product.stay_policy.model_dump(mode="json"),
                    "extension": product.extension_policy.model_dump(mode="json"),
                },
                "requirements": [],
                "checklist": [],
            }
        )
    if unresolved:
        logger.warning(
            "evaluate path: %d candidate(s) with no product in pack (trace=%s)",
            unresolved,
            request_trace,
        )
    return {"candidates": entries}


async def _save_evaluate_decision(
    db_pool: asyncpg.Pool,
    *,
    decision: Decision,
    rule_pack_db_id: uuid.UUID,
    ruleset_activation_id: uuid.UUID,
    environment: str,
    request_fingerprint: bytes,
    request_category: str,
    traffic_source: str,
) -> None:
    """INSERT one ``visa_decisions`` row for an evaluate-path ``Decision``.

    A DOCUMENTED MIRROR of ``shadow._save_shadow_decision`` (same INSERT,
    same column set, same ``ON CONFLICT (decision_id) DO NOTHING``
    semantics) with exactly three deliberate deltas:

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
    candidate_summary = _build_candidate_summary(decision)
    grounding_summary = _build_grounding_summary(decision)
    citations = _collect_citations(grounding_summary)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO visa_decisions (
                decision_id, environment, engine_surface, engine_mode,
                rule_pack_id, ruleset_activation_id, rule_pack_sha256, verdict,
                citations, engine_version, effective_at, observed_at, evaluated_at,
                request_fingerprint, request_category, candidate_summary,
                grounding_summary, traffic_source
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9::text::jsonb, $10, $11, $12, $13,
                $14, $15, $16::text::jsonb, $17::text::jsonb, $18
            )
            ON CONFLICT (decision_id) DO NOTHING
            """,
            decision.decision_id,
            environment,
            _SURFACE.value,
            EngineMode.SHADOW.value,
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
        )


async def run_evaluation(
    db_pool: asyncpg.Pool,
    *,
    facts: ApplicantFacts,
    traffic_source: str,
    request_category_hint: str | None,
    request_trace: str,
) -> dict[str, JsonValue]:
    """Run one evaluate-path evaluation and build the B.2 envelope body.

    Never raises for pack/engine/persistence failures — every failure mode
    degrades to the TEMPORARILY_UNAVAILABLE-shaped body (HTTP 200,
    ``retryable=true``, NOTHING persisted), the same fail-closed philosophy
    as ``shadow._shadow_evaluate_match``'s silent skips, but rendered
    because this surface's caller is the UI, not a fire-and-forget audit
    spawn. ``traffic_source`` MUST already be allowlist-checked by the
    router (this function trusts it; the synthetic-class gate is the
    router's job, one layer up, next to the other request validations).

    NEVER logs applicant facts — every log line carries only the caller-
    supplied ``request_trace`` (a truncated SHA-256 of the raw request
    body), the resolved environment, the verdict, and counts.
    """

    now = datetime.now(timezone.utc)

    if not resolve_evaluate_shadow_enabled():
        return build_temp_unavailable_body(now=now, code="EVALUATE_SURFACE_DISABLED")

    environment = _resolve_evaluate_environment()

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
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")
    if binding is None:
        logger.info(
            "evaluate path: no active rule pack for environment=%s, unavailable (trace=%s)",
            environment,
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")

    try:
        verified = verify_rule_pack(
            binding.raw_envelope,
            trust_store=StaticTrustStore.from_env(),
            observed_at=now,
        )
    except RulePackVerificationError as exc:
        logger.warning("evaluate path: rule pack verification failed: %s", exc)
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")

    try:
        compiled = build_compiled_pack(verified.pack)
    except RulePackCompilationError as exc:
        logger.warning("evaluate path: rule pack compilation failed: %s", exc)
        return build_temp_unavailable_body(now=now, code="RULE_PACK_UNAVAILABLE")

    try:
        identity_provider = resolve_identity_provider()
        decision = evaluate(
            facts,
            compiled,
            effective_at=now,
            observed_at=now,
            identity_provider=identity_provider,
        )
    except (PlaceholderIdentityNotAllowedError, FactsFingerprintKeyUnavailableError):
        logger.warning(
            "evaluate path: active pack environment=%s needs a real crypto "
            "identity_provider (STEP-6d) / a provisioned facts-fingerprint "
            "key, unavailable (trace=%s)",
            environment,
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE")
    except FactsFingerprintKeyError:
        logger.warning(
            "evaluate path: malformed facts-fingerprint key config "
            "(VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON), unavailable (trace=%s)",
            request_trace,
        )
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE")
    except Exception as exc:  # defense-in-depth — evaluate() is documented pure/total
        # Log the exception TYPE only, never str(exc): evaluate() runs over
        # ApplicantFacts, and a stray ValidationError/KeyError message could
        # echo a raw fact value — this module must never log facts (Law 2).
        logger.warning("evaluate path: evaluate() failed: %s", type(exc).__name__)
        return build_temp_unavailable_body(now=now, code="EVALUATION_UNAVAILABLE")

    request_category = derive_request_category(facts, request_category_hint)
    # The request correlator IS the STEP-6d facts fingerprint (see module
    # docstring): keyed HMAC, non-reversible, exactly the G-a "distinct
    # requests" granularity.
    request_fingerprint = bytes.fromhex(decision.facts_fingerprint.digest)

    try:
        await _save_evaluate_decision(
            db_pool,
            decision=decision,
            rule_pack_db_id=binding.rule_pack_id,
            ruleset_activation_id=binding.ruleset_activation_id,
            environment=environment,
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

    logger.info(
        "evaluate path decision written: trace=%s verdict=%s candidates=%d",
        request_trace,
        decision.state.value,
        len(decision.candidates),
    )
    return {
        "mode": resolve_response_mode(),
        "decision": decision.model_dump(mode="json"),
        "sources": _build_sources_dto(decision, compiled, request_trace=request_trace),
        "display": _build_display(decision, compiled, request_trace=request_trace),
    }


__all__ = [
    "ALLOW_SYNTHETIC_SOURCES_ENV",
    "DRIVER_TOKEN_ENV",
    "EVALUATE_ENVIRONMENT_ENV",
    "EVALUATE_MODE_ENV",
    "build_temp_unavailable_body",
    "derive_request_category",
    "resolve_allowed_synthetic_sources",
    "resolve_evaluate_shadow_enabled",
    "resolve_response_mode",
    "run_evaluation",
    "verify_driver_token",
]
