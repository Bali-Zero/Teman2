"""STEP-6c — SHADOW wiring: fire-and-forget audit evaluation for real
POST /api/visa/match traffic.

Design: ``research/visa/2026-07-20-step6c-shadow-wiring-design.md``.

Scope (per the design doc's own §1): flag-gated (default OFF), fire-and-
forget re-evaluation of a live Visa Match submission through the real
visa_engine (``evaluator.evaluate``) against whatever rule pack is active
for the resolved environment, writing exactly one ``visa_decisions`` row
(migration 252's SHADOW-minimal write substrate). NEVER rendered to the
caller, NEVER able to raise into the request/response path, NEVER logs raw
applicant facts (nationality/purpose/duration) or the public ``match_hash``
token — only a truncated SHA-256 trace, verdict, and candidate counts
(SYMBIOSIS Law 2 / UU PDP PII boundary).

PROD remains a no-op until all runtime prerequisites are present together:
an active signed PRODUCTION pack, trust-store keys, a PRODUCTION facts-
fingerprint key, and ``VISA_ENGINE_MATCH_MODE=SHADOW``. Missing identity
material fail-closes through ``PlaceholderIdentityNotAllowedError`` /
``FactsFingerprintKeyUnavailableError``. The plumbing is exercised end-to-
end by this module's own tests without arming any production flag.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import TypeAlias

import asyncpg

from backend.services.common.background import spawn
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.crypto import resolve_identity_provider
from backend.services.visa_engine.enums import (
    APPLICANT_FACT_PATHS,
    EngineMode,
    EngineSurface,
    FactPath,
    UnknownReason,
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
    KnownCountrySet,
    KnownNonNegativeInteger,
    KnownPurposeSet,
    UnknownFact,
)

logger = logging.getLogger(__name__)

#: A raw, JSON-safe value. Defined locally — no importable shared home in
#: this package (see ``bundle.py``'s/``repository.py``'s module docstrings,
#: PR2b adaptation note — every module here duplicates this alias rather
#: than inventing a shared one).
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

#: Match-surface engine mode gate (OFF|SHADOW|ENFORCE; any other/missing
#: value resolves to OFF). Re-read fresh on every call — never cached at
#: import time — so a live config flip (or ``monkeypatch.setenv`` in tests)
#: takes effect immediately, matching ``bundle.resolve_allow_unsigned_default``'s
#: own "never cache at import time" contract.
MATCH_MODE_ENV = "VISA_ENGINE_MATCH_MODE"

#: Which rule-pack environment SHADOW resolves against for the Match
#: surface. Defaults to PRODUCTION — SHADOW's whole point is auditing real
#: production traffic against what the engine *would* have said, even
#: though (see module docstring) no PRODUCTION pack is activated yet.
MATCH_ENVIRONMENT_ENV = "VISA_ENGINE_MATCH_ENVIRONMENT"
_DEFAULT_MATCH_ENVIRONMENT = "PRODUCTION"

#: The running engine build/release identity persisted on every SHADOW row
#: (``visa_decisions.engine_version`` — migration 252's own column,
#: distinct from a rule pack's own ``engine_contract_version``/
#: ``engine_min_version``/``engine_max_version``). SSOT for this string —
#: grep confirms zero other literal occurrences in the package.
ENGINE_VERSION = "visa-engine/0.1.0"

#: Fixed namespace UUID for deriving a SHADOW ``ApplicantFacts.assessment_id``
#: deterministically from a Match submission's own ``match_hash`` (so two
#: shadow evaluations of the same persisted match row always carry the same
#: assessment identity). Minted once via ``uuid5(NAMESPACE_URL, ...)`` — a
#: fixed, arbitrary 128-bit constant, not itself sensitive.
_SHADOW_ASSESSMENT_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://balizero.com/visa-engine/shadow-assessment"
)

#: ``visa_check.match_tree.Purpose`` (the Match wizard's 8-value funnel
#: vocabulary) -> ``visa_engine.enums.VisaPurpose`` (the engine's closed
#: purpose vocabulary). Every Purpose member is mapped — see
#: ``test_shadow_match.py``'s parametrized remap test for the exhaustiveness
#: proof.
_PURPOSE_REMAP: MappingProxyType[Purpose, VisaPurpose] = MappingProxyType(
    {
        Purpose.WORK_REMOTE: VisaPurpose.REMOTE_WORK,
        Purpose.INVESTOR: VisaPurpose.INVESTMENT,
        Purpose.WORK_EMPLOYEE: VisaPurpose.EMPLOYMENT,
        Purpose.FAMILY: VisaPurpose.FAMILY,
        Purpose.LONG_TOURISM: VisaPurpose.TOURISM,
        Purpose.RETIREMENT: VisaPurpose.RETIREMENT,
        Purpose.STUDENT: VisaPurpose.STUDY,
        Purpose.OTHER: VisaPurpose.OTHER,
    }
)

#: Best-effort, deliberately NON-EXHAUSTIVE ISO 3166-1 alpha-3 -> alpha-2
#: table for ``build_shadow_facts``'s nationality fact. ``MatchRequest.
#: nationality`` (``app/routers/visa_check.py``) accepts 2-3 chars; a 2-char
#: value is used directly (already the engine's own ``CountryCode``
#: pattern), a 3-char value is looked up here. An unmapped/unrecognised
#: alpha-3 code (or any other malformed input) degrades to
#: ``UnknownFact(reason=NOT_PROVIDED)`` — never a hard failure — this is
#: audit-only SHADOW plumbing, not a legal eligibility gate.
_ALPHA3_TO_ALPHA2: MappingProxyType[str, str] = MappingProxyType(
    {
        "AFG": "AF", "ALB": "AL", "DZA": "DZ", "AND": "AD", "AGO": "AO",
        "ARG": "AR", "ARM": "AM", "AUS": "AU", "AUT": "AT", "AZE": "AZ",
        "BHS": "BS", "BHR": "BH", "BGD": "BD", "BRB": "BB", "BLR": "BY",
        "BEL": "BE", "BLZ": "BZ", "BEN": "BJ", "BTN": "BT", "BOL": "BO",
        "BIH": "BA", "BWA": "BW", "BRA": "BR", "BRN": "BN", "BGR": "BG",
        "BFA": "BF", "BDI": "BI", "KHM": "KH", "CMR": "CM", "CAN": "CA",
        "CPV": "CV", "CAF": "CF", "TCD": "TD", "CHL": "CL", "CHN": "CN",
        "COL": "CO", "COM": "KM", "COG": "CG", "COD": "CD", "CRI": "CR",
        "CIV": "CI", "HRV": "HR", "CUB": "CU", "CYP": "CY", "CZE": "CZ",
        "DNK": "DK", "DJI": "DJ", "DMA": "DM", "DOM": "DO", "ECU": "EC",
        "EGY": "EG", "SLV": "SV", "GNQ": "GQ", "ERI": "ER", "EST": "EE",
        "SWZ": "SZ", "ETH": "ET", "FJI": "FJ", "FIN": "FI", "FRA": "FR",
        "GAB": "GA", "GMB": "GM", "GEO": "GE", "DEU": "DE", "GHA": "GH",
        "GRC": "GR", "GRD": "GD", "GTM": "GT", "GIN": "GN", "GNB": "GW",
        "GUY": "GY", "HTI": "HT", "HND": "HN", "HKG": "HK", "HUN": "HU",
        "ISL": "IS", "IND": "IN", "IDN": "ID", "IRN": "IR", "IRQ": "IQ",
        "IRL": "IE", "ISR": "IL", "ITA": "IT", "JAM": "JM", "JPN": "JP",
        "JOR": "JO", "KAZ": "KZ", "KEN": "KE", "KIR": "KI", "PRK": "KP",
        "KOR": "KR", "KWT": "KW", "KGZ": "KG", "LAO": "LA", "LVA": "LV",
        "LBN": "LB", "LSO": "LS", "LBR": "LR", "LBY": "LY", "LIE": "LI",
        "LTU": "LT", "LUX": "LU", "MAC": "MO", "MDG": "MG", "MWI": "MW",
        "MYS": "MY", "MDV": "MV", "MLI": "ML", "MLT": "MT", "MHL": "MH",
        "MRT": "MR", "MUS": "MU", "MEX": "MX", "FSM": "FM", "MDA": "MD",
        "MCO": "MC", "MNG": "MN", "MNE": "ME", "MAR": "MA", "MOZ": "MZ",
        "MMR": "MM", "NAM": "NA", "NRU": "NR", "NPL": "NP", "NLD": "NL",
        "NZL": "NZ", "NIC": "NI", "NER": "NE", "NGA": "NG", "NOR": "NO",
        "OMN": "OM", "PAK": "PK", "PLW": "PW", "PAN": "PA", "PNG": "PG",
        "PRY": "PY", "PER": "PE", "PHL": "PH", "POL": "PL", "PRT": "PT",
        "QAT": "QA", "ROU": "RO", "RUS": "RU", "RWA": "RW", "WSM": "WS",
        "SMR": "SM", "SAU": "SA", "SEN": "SN", "SRB": "RS", "SYC": "SC",
        "SLE": "SL", "SGP": "SG", "SVK": "SK", "SVN": "SI", "SLB": "SB",
        "SOM": "SO", "ZAF": "ZA", "SSD": "SS", "ESP": "ES", "LKA": "LK",
        "SDN": "SD", "SUR": "SR", "SWE": "SE", "CHE": "CH", "SYR": "SY",
        "TWN": "TW", "TJK": "TJ", "TZA": "TZ", "THA": "TH", "TLS": "TL",
        "TGO": "TG", "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR",
        "TKM": "TM", "TUV": "TV", "UGA": "UG", "UKR": "UA", "ARE": "AE",
        "GBR": "GB", "USA": "US", "URY": "UY", "UZB": "UZ", "VUT": "VU",
        "VAT": "VA", "VEN": "VE", "VNM": "VN", "YEM": "YE", "ZMB": "ZM",
        "ZWE": "ZW", "PSE": "PS",
    }
)

#: Mirrors ``repository.py``'s own module-level scoping constants — every
#: row this package writes/reads is constitutionally ``ID``/
#: ``IMMIGRATION_VISA`` today (both tables' CHECK constraints pin it).
_JURISDICTION = "ID"
_DECISION_DOMAIN = "IMMIGRATION_VISA"

_enforce_not_implemented_warned = False


def _warn_enforce_not_implemented_once() -> None:
    global _enforce_not_implemented_warned
    if _enforce_not_implemented_warned:
        return
    logger.warning(
        "%s=ENFORCE requested but enforcement is not implemented yet; running SHADOW-only",
        MATCH_MODE_ENV,
    )
    _enforce_not_implemented_warned = True


def resolve_match_shadow_enabled() -> bool:
    """Re-read ``MATCH_MODE_ENV`` fresh on every call.

    True iff the (stripped, upper-cased) value is ``SHADOW`` or ``ENFORCE``;
    anything else (missing, ``OFF``, or any invalid string) resolves to
    ``False``. ``ENFORCE`` is accepted (returns ``True`` — SHADOW-mode
    evaluation still runs) but logs a one-time warning that enforcement
    itself is not implemented yet (STEP-6c ships SHADOW-only; the ENFORCE
    response-flip is a later, separately-gated PENDING-ARMS task).
    """

    raw = os.environ.get(MATCH_MODE_ENV, EngineMode.OFF.value).strip().upper()
    if raw == EngineMode.ENFORCE.value:
        _warn_enforce_not_implemented_once()
        return True
    return raw == EngineMode.SHADOW.value


def _resolve_match_environment() -> str:
    raw = os.environ.get(MATCH_ENVIRONMENT_ENV, _DEFAULT_MATCH_ENVIRONMENT).strip()
    return raw or _DEFAULT_MATCH_ENVIRONMENT


def _resolve_nationality_alpha2(nationality: str) -> str | None:
    """Best-effort alpha-2 resolution. See ``_ALPHA3_TO_ALPHA2``'s docstring."""

    code = nationality.strip().upper()
    if len(code) == 2 and code.isalpha():
        return code
    if len(code) == 3:
        return _ALPHA3_TO_ALPHA2.get(code)
    return None


def _default_unknown_facts() -> dict[str, UnknownFact]:
    """The 40 applicant-collected fact paths, each defaulted to
    ``UnknownFact(reason=NOT_ASKED)`` — a Match wizard submission never
    asked the other 37 facts a full visa_oracle interview would. Sharing one
    frozen ``UnknownFact`` instance across every key is safe (immutable
    model, no per-key state).
    """

    default = UnknownFact(status="UNKNOWN", reason=UnknownReason.NOT_ASKED)
    return {path.value: default for path in APPLICANT_FACT_PATHS}


def build_shadow_facts(
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    match_hash: str,
) -> ApplicantFacts | None:
    """Adapt a 4-field Match submission into a full 40-key ``ApplicantFacts``.

    Every one of the 40 fields is built defensively: the 3 KNOWN-able ones
    (``person.nationalities``/``intent.purposes``/``intent.stay_days``) are
    each attempted in their own ``try/except`` — a failure on any single
    field degrades ONLY that field to its ``UnknownFact`` default, never
    aborts the whole build. The remaining 37 stay ``UNKNOWN(NOT_ASKED)``.
    Returns ``None`` only if the ``ApplicantFacts`` construction fails
    entirely (e.g. the facts dict itself is somehow malformed) — the whole
    SHADOW evaluation aborts silently in that case (caller logs and returns).
    """

    try:
        facts_wire: dict[str, object] = _default_unknown_facts()

        try:
            alpha2 = _resolve_nationality_alpha2(nationality)
            if alpha2 is not None:
                facts_wire[FactPath.PERSON_NATIONALITIES.value] = KnownCountrySet(
                    status="KNOWN", value=(alpha2,)
                )
            else:
                facts_wire[FactPath.PERSON_NATIONALITIES.value] = UnknownFact(
                    status="UNKNOWN", reason=UnknownReason.NOT_PROVIDED
                )
        except Exception:
            logger.debug("shadow: nationality fact build failed, leaving UNKNOWN", exc_info=True)

        try:
            mapped_purpose = _PURPOSE_REMAP.get(purpose)
            if mapped_purpose is not None:
                facts_wire[FactPath.INTENT_PURPOSES.value] = KnownPurposeSet(
                    status="KNOWN", value=(mapped_purpose.value,)
                )
        except Exception:
            logger.debug("shadow: purpose fact build failed, leaving UNKNOWN", exc_info=True)

        try:
            stay_days = duration_months * 30
            facts_wire[FactPath.INTENT_STAY_DAYS.value] = KnownNonNegativeInteger(
                status="KNOWN", value=stay_days
            )
        except Exception:
            logger.debug("shadow: stay_days fact build failed, leaving UNKNOWN", exc_info=True)

        return ApplicantFacts(
            schema_version="1.0.0",
            assessment_id=uuid.uuid5(_SHADOW_ASSESSMENT_NAMESPACE, match_hash),
            collected_at=datetime.now(timezone.utc),
            facts=facts_wire,
        )
    except Exception:
        logger.warning("shadow: build_shadow_facts failed entirely, aborting shadow eval")
        return None


def _jsonb_to_dict(value: object) -> dict[str, JsonValue]:
    """Normalise a JSONB column read-back to a plain ``dict`` — duplicated
    from ``repository.py``'s identical helper (see this module's/that
    module's docstrings on why the SQL here is a documented mirror, not an
    import, of ``load_active_rule_pack``: keeps the most-tested file
    untouched)."""

    if isinstance(value, str):
        return json.loads(value)
    return value


def _b64url_nopad_encode(raw: bytes) -> str:
    """Duplicated from ``repository.py``'s identical helper — see
    ``_jsonb_to_dict``'s docstring."""

    import base64

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class _PackBinding:
    """The selected pack/activation identities and signed wire envelope."""

    rule_pack_id: uuid.UUID
    ruleset_activation_id: uuid.UUID
    environment: str
    raw_envelope: dict[str, JsonValue]


async def _resolve_active_pack_binding(
    db_pool: asyncpg.Pool,
    *,
    environment: str,
    effective_at: datetime,
    observed_at: datetime,
) -> _PackBinding | None:
    """Shadow-local SQL — a DOCUMENTED MIRROR of
    ``repository.VisaEngineRepository.load_active_rule_pack`` PLUS the
    pack's own DB primary key (``p.id``) and ``p.environment``, which that
    method deliberately does not return (its contract is "the raw wire
    envelope only", the shape ``bundle.verify_rule_pack`` expects).

    Kept HERE, not folded into ``repository.py``, so that most-tested file
    stays untouched by this PR — the duplication is intentional and
    documented, not an oversight (see this module's own docstring and the
    design doc §2).
    """

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                p.id AS rule_pack_id,
                a.id AS ruleset_activation_id,
                p.environment,
                p.protected_header,
                p.payload,
                p.payload_sha256,
                p.signature
            FROM visa_ruleset_activations a
            JOIN visa_rule_packs p ON p.id = a.rule_pack_id
            WHERE a.environment = $1
              AND a.jurisdiction = $2
              AND a.decision_domain = $3
              AND a.legal_period @> $4::timestamptz
              AND a.system_period @> $5::timestamptz
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            environment,
            _JURISDICTION,
            _DECISION_DOMAIN,
            effective_at,
            observed_at,
        )
    if row is None:
        return None

    return _PackBinding(
        rule_pack_id=row["rule_pack_id"],
        ruleset_activation_id=row["ruleset_activation_id"],
        environment=row["environment"],
        raw_envelope={
            "canonicalization": "RFC8785",
            "protected": _jsonb_to_dict(row["protected_header"]),
            "payload": _jsonb_to_dict(row["payload"]),
            "payload_sha256": row["payload_sha256"].hex(),
            "signature": _b64url_nopad_encode(row["signature"]),
        },
    )


def _request_fingerprint(match_hash: str) -> bytes:
    """Return a non-reversible request correlator; never persist the token."""

    return hashlib.sha256(match_hash.encode("utf-8")).digest()


def _request_trace(match_hash: str) -> str:
    """Short, non-reversible correlation value safe for operational logs."""

    return _request_fingerprint(match_hash).hex()[:12]


def _build_candidate_summary(decision: Decision) -> list[dict[str, JsonValue]]:
    """Build the PII-free product breadth projection used by gate G-a."""

    return [
        {
            "rank": candidate.rank,
            "product_version_id": str(candidate.product_version_id),
            "product_code": str(candidate.product_code),
            "support_rule_ids": [str(rule_id) for rule_id in candidate.support_rule_ids],
            "source_record_ids": [str(ref) for ref in candidate.source_refs],
            "reason_codes": [str(code) for code in candidate.reason_codes],
        }
        for candidate in decision.candidates
    ]


def _build_grounding_summary(decision: Decision) -> list[dict[str, JsonValue]]:
    """Map every persisted verdict/claim to source-record identifiers.

    The top-level VERDICT claim is deliberate: a NEEDS_INPUT/abstention row
    with no grounded reason remains visible as a G-c failure instead of being
    silently treated as "no claims".
    """

    claims: list[dict[str, JsonValue]] = []
    verdict_refs: list[uuid.UUID] = []
    seen_verdict_refs: set[uuid.UUID] = set()

    def add_claim(kind: str, code: str, refs: tuple[uuid.UUID, ...]) -> None:
        for ref in refs:
            if ref not in seen_verdict_refs:
                seen_verdict_refs.add(ref)
                verdict_refs.append(ref)
        claims.append(
            {
                "claim_kind": kind,
                "claim_code": code,
                "source_record_ids": [str(ref) for ref in refs],
            }
        )

    for candidate in decision.candidates:
        add_claim("CANDIDATE", str(candidate.product_code), candidate.source_refs)
    for reason in decision.review_reasons:
        add_claim("REVIEW_REASON", str(reason.code), reason.source_refs)
    for reason in decision.no_path_reasons:
        add_claim("NO_PATH_REASON", str(reason.code), reason.source_refs)
    for notice in decision.notices:
        add_claim("NOTICE", str(notice.code), notice.source_refs)

    return [
        {
            "claim_kind": "VERDICT",
            "claim_code": decision.state.value,
            "source_record_ids": [str(ref) for ref in verdict_refs],
        },
        *claims,
    ]


def _collect_citations(
    grounding_summary: list[dict[str, JsonValue]],
) -> list[dict[str, str]]:
    """Flatten every claim's sources into migration 252's citation shape."""

    seen: set[str] = set()
    citations: list[dict[str, str]] = []
    for claim in grounding_summary:
        refs = claim.get("source_record_ids", [])
        if not isinstance(refs, list):
            continue
        for ref_value in refs:
            ref = str(ref_value)
            if ref in seen:
                continue
            seen.add(ref)
            citations.append({"source_record_id": ref})
    return citations


async def _save_shadow_decision(
    db_pool: asyncpg.Pool,
    *,
    decision: Decision,
    rule_pack_db_id: uuid.UUID,
    ruleset_activation_id: uuid.UUID,
    environment: str,
    request_fingerprint: bytes,
    request_category: Purpose,
) -> None:
    """INSERT one ``visa_decisions`` row for a SHADOW ``Decision``.

    ``rule_pack_id`` is ALWAYS the caller-resolved DB primary key
    (``rule_pack_db_id``, from ``_resolve_active_pack_binding``) — never
    ``decision.rule_pack.rule_pack_id`` (the engine's OWN payload identity).
    ``repository.py``'s own docstring calls this out explicitly: the two are
    not schema-enforced to be equal, so the writer must resolve the DB PK
    itself rather than trust the Decision's self-reported one.

    ``ruleset_activation_id`` is the exact activation selected alongside the
    pack, so migration 252's trigger re-proves both bitemporal containment
    checks at INSERT time. ``engine_mode`` is always ``'SHADOW'`` — this
    writer never produces an ENFORCE row.

    ``ON CONFLICT (decision_id) DO NOTHING`` guards ONLY against an exact
    double-insert of the SAME decision (same ``decision_id``) — e.g. a
    re-spawned/retried identical coroutine. It is NOT a cross-time
    idempotency guarantee: ``decision_id`` is ``uuid5(assessment_id,
    rule_pack_id, sequence, facts_digest, effective_at)`` (evaluator
    ``_deterministic_ids``) and ``effective_at`` is wall-clock ``now()`` per
    evaluation, so re-evaluating the same ``match_hash`` at a LATER time
    yields a DISTINCT ``decision_id`` and a NEW audit row. That is expected
    and harmless (migration 252's own header: a duplicate SHADOW row is a
    harmless audit-log duplicate, not a user-visible defect; SHADOW carries
    no caller-facing retry contract).
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
                grounding_summary
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9::text::jsonb, $10, $11, $12, $13,
                $14, $15, $16::text::jsonb, $17::text::jsonb
            )
            ON CONFLICT (decision_id) DO NOTHING
            """,
            decision.decision_id,
            environment,
            EngineSurface.MATCH.value,
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
            request_category.value,
            json.dumps(candidate_summary),
            json.dumps(grounding_summary),
        )


async def _shadow_evaluate_match(
    db_pool: asyncpg.Pool,
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    match_hash: str,
) -> None:
    """Run one full SHADOW evaluation for a persisted Match submission.

    WHOLE-BODY try/except (mirrors
    ``app/routers/visa_oracle.py::_persist_session_create``'s "non-fatal,
    failures are logged, not raised" contract): nothing in here may ever
    propagate into the caller (``maybe_spawn_shadow_match`` already runs
    this fire-and-forget via ``spawn()``, but this function must also stay
    safe if ever awaited directly, e.g. by a test).

    NEVER logs ``nationality``/``purpose``/``duration_months``/facts or the
    public ``match_hash`` — every log line below carries only a hash trace,
    the resolved environment, the verdict, and/or a candidate count.
    """

    try:
        now = datetime.now(timezone.utc)
        environment = _resolve_match_environment()
        request_trace = _request_trace(match_hash)

        binding = await _resolve_active_pack_binding(
            db_pool,
            environment=environment,
            effective_at=now,
            observed_at=now,
        )
        if binding is None:
            logger.debug(
                "shadow match: no active rule pack for environment=%s, skipping (trace=%s)",
                environment,
                request_trace,
            )
            return

        facts = build_shadow_facts(
            nationality=nationality,
            purpose=purpose,
            duration_months=duration_months,
            match_hash=match_hash,
        )
        if facts is None:
            logger.warning(
                "shadow match: could not build applicant facts, skipping (trace=%s)",
                request_trace,
            )
            return

        try:
            verified = verify_rule_pack(
                binding.raw_envelope,
                trust_store=StaticTrustStore.from_env(),
                observed_at=now,
            )
        except RulePackVerificationError as exc:
            logger.warning("shadow match: rule pack verification failed: %s", exc)
            return

        try:
            compiled = build_compiled_pack(verified.pack)
        except RulePackCompilationError as exc:
            logger.warning("shadow match: rule pack compilation failed: %s", exc)
            return

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
                "shadow match: active pack environment=%s needs a real crypto "
                "identity_provider (STEP-6d) / a provisioned facts-fingerprint "
                "key, skipping (trace=%s)",
                environment,
                request_trace,
            )
            return
        except FactsFingerprintKeyError:
            logger.warning(
                "shadow match: malformed facts-fingerprint key config "
                "(VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON), skipping (trace=%s)",
                request_trace,
            )
            return
        except Exception as exc:  # defense-in-depth — evaluate() is documented pure/total
            # Log the exception TYPE only, never str(exc): evaluate() runs over
            # ApplicantFacts, and a stray ValidationError/KeyError message could
            # echo a raw fact value — this module must never log facts (Law 2).
            logger.warning("shadow match: evaluate() failed: %s", type(exc).__name__)
            return

        await _save_shadow_decision(
            db_pool,
            decision=decision,
            rule_pack_db_id=binding.rule_pack_id,
            ruleset_activation_id=binding.ruleset_activation_id,
            environment=environment,
            request_fingerprint=_request_fingerprint(match_hash),
            request_category=purpose,
        )
        logger.info(
            "shadow match decision written: trace=%s verdict=%s candidates=%d",
            request_trace,
            decision.state.value,
            len(decision.candidates),
        )
    except Exception:
        logger.warning(
            "shadow match evaluation failed (trace=%s)",
            _request_trace(match_hash),
            exc_info=True,
        )


def maybe_spawn_shadow_match(
    db_pool: asyncpg.Pool,
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    match_hash: str,
) -> None:
    """Router entry point — call AFTER ``save_match`` succeeds.

    WHOLE-BODY try/except: this must never break the request even if
    ``resolve_match_shadow_enabled()`` or ``spawn()`` itself misbehaves.
    When enabled, schedules ``_shadow_evaluate_match`` as a genuine
    fire-and-forget background task (``spawn()`` — strong-ref + error
    surfacing, never awaited here).
    """

    try:
        if resolve_match_shadow_enabled():
            request_trace = _request_trace(match_hash)
            spawn(
                _shadow_evaluate_match(
                    db_pool,
                    nationality=nationality,
                    purpose=purpose,
                    duration_months=duration_months,
                    match_hash=match_hash,
                ),
                name=f"shadow-match-{request_trace}",
            )
    except Exception:
        logger.warning(
            "maybe_spawn_shadow_match: failed to schedule shadow evaluation (trace=%s)",
            _request_trace(match_hash),
            exc_info=True,
        )


__all__ = [
    "ENGINE_VERSION",
    "MATCH_ENVIRONMENT_ENV",
    "MATCH_MODE_ENV",
    "build_shadow_facts",
    "maybe_spawn_shadow_match",
    "resolve_match_shadow_enabled",
]
