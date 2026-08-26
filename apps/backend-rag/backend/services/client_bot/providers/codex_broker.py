"""CodexBrokerClientBrainProvider — the F3 codex-broker leg of the
client-bot ``ClientBrainProviderRouter`` (research capture Sol §1.5/§2,
MANDATE.md F3, lane B2).

Ships DARK: nothing in this repo instantiates this class yet, and
``client_bot_codex_broker_enabled`` defaults to ``False`` — the ONLY thing
that flag controls is ``ClientBrainProviderRouter._is_eligible()``
(``provider_router.py``), which never even calls ``generate()`` on a
provider named ``"codex_broker"`` while it is off. This class therefore
does NOT re-check the flag itself (F1.5 routing rule 1: "This is the only
[the router's] component that reads provider-selection configuration" —
an adapter re-reading the same env var would be a second source of truth
for the same gate, and CLAUDE.md §5's "adapters never import provider
environment variables" applies here word for word).

Job-queue, not a synchronous call (F3: "reuses the existing dark
implementation ... queue depth 1, lease 20s, breaker 3-fail/5-min"). This
adapter runs where ``ClientBotEngine`` runs (the Fly RAG process) and never
executes ``codex exec`` itself — that subprocess boundary belongs to the
Mac-side daemon (``wa_codex_daemon.py``, which imports
``backend.llm.codex_exec_client`` directly). This adapter's whole job is:
build a hash-sealed wire envelope from the frozen ``BrainRequest``, OFFER
it onto ``broker_jobs`` (``wa_broker.offer_client_job``, migration 290,
``job_kind='client_answer_v1'``), WAIT for a completion
(``wa_broker.wait_for_job`` — already job_kind-agnostic, unchanged), CONSUME
the result exactly once (``wa_broker.consume_result`` — likewise
unchanged), and parse it into the ONE type a provider may ever return,
``BrainCandidate`` (``contracts.py``). Every step maps its failure onto the
closed ``ProviderFailureKind`` vocabulary (``providers/base.py``) so
``ClientBrainProviderRouter.route()`` has one failure shape to catch
regardless of where in the pipeline this leg broke.

Established from the code and the spec, not assumed (per this lane's
mandate):

- ``wa_broker.claim_job``/``complete_job`` (the daemon-facing HTTP
  endpoints, ``app/routers/wa_broker.py``) are ALREADY job_kind-agnostic —
  neither touches ``wa_outbox`` at all, verified by reading both. The only
  wa_outbox-COUPLED function in the whole transport is ``offer_job``
  itself (its fenced ``UPDATE wa_outbox SET generation_route`` + the
  ``generation_route`` marker exist ONLY to protect the WA outbox WORKER's
  own retry ladder across crashes — see ``offer_client_job``'s own
  docstring in ``wa_broker.py`` for why a client-bot request has no
  equivalent ladder to protect). ``offer_client_job`` (migration 290) is
  therefore the one new piece of transport this leg needed, added directly
  to ``wa_broker.py`` rather than a second module, per F1 ("do not create
  a second jobs table") and per ``kill_switches.py``'s own verify_command
  for ``CLIENT_BOT_CODEX_BROKER_ENABLED`` ("grep ... in wa_broker job
  offer logic").
- The daemon (``wa_codex_daemon.py``) still posts the LEGACY
  ``wa_broker.ALLOWED_ERROR_CLASSES`` vocabulary today (``exec_timeout``/
  ``cli_failure``/...), NOT F3's closed 7-member set (``AUTH_DEAD``/
  ``QUOTA``/...) — verified by reading its import list and every
  ``error_class=`` call site. Migrating the daemon to emit F3's
  vocabulary (splitting the ``cli_failure`` bucket that collapses auth and
  quota today, per F3's own "auth and quota MUST be distinct" framing) is
  daemon-side work this unit does not do — ``_error_class_to_kind`` below
  is deliberately built to classify BOTH vocabularies correctly, so this
  adapter needs no further change once that daemon migration lands.

Author: Claude Opus 5 (lane B2 — codex broker provider leg).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import asyncpg
from pydantic import ValidationError

from backend.services.client_bot.contracts import BrainCandidate, BrainRequest
from backend.services.client_bot.providers.base import (
    ProviderFailure,
    ProviderFailureKind,
    ProviderHealth,
)
from backend.services.integrations import wa_broker

logger = logging.getLogger("zantara.backend")

__all__ = ["CodexBrokerClientBrainProvider"]

# Matches provider_router.py's private _CODEX_BROKER_NAME literal and
# config.py's CLIENT_BOT_PRIMARY_PROVIDER/CLIENT_BOT_SHADOW_PROVIDER
# description ("gemini|codex_broker|future_metered") — not imported (that
# constant is intentionally private to the router, F1.5 rule 1) but must
# stay byte-identical; test_codex_broker.py asserts this against the
# router's own eligibility gate.
PROVIDER_NAME = "codex_broker"

# The wire envelope's own format version — independent of BrainCandidate's
# schema_version (the OUTPUT shape) and of migration 290's
# output_schema_version column (which names the OUTPUT contract, i.e.
# client_brain_candidate_v1.json's version, passed straight through here).
_WIRE_ENVELOPE_VERSION = "1.0"

_DEFAULT_OUTPUT_SCHEMA_VERSION = "1.0"

# F3's closed wire-error vocabulary (codex_broker_wire.py's BrokerErrorClass,
# restated as string literals here rather than imported: that module maps
# backend.llm.codex_exec_client exceptions -> BrokerErrorClass for the
# DAEMON side; this adapter never sees a codex_exec_client exception at
# all, only whatever string the daemon posted as broker_jobs.error_class,
# so importing that module here would suggest a coupling that does not
# exist). Every value maps 1:1 onto ProviderFailureKind by name.
_F3_ERROR_CLASS_TO_KIND: dict[str, ProviderFailureKind] = {
    "AUTH_DEAD": ProviderFailureKind.AUTH_DEAD,
    "QUOTA": ProviderFailureKind.QUOTA,
    "TIMEOUT": ProviderFailureKind.TIMEOUT,
    "HOST_OFFLINE": ProviderFailureKind.HOST_OFFLINE,
    "OUTPUT_INVALID": ProviderFailureKind.OUTPUT_INVALID,
    "POLICY_BLOCKED": ProviderFailureKind.POLICY_BLOCKED,
    "INTERNAL": ProviderFailureKind.INTERNAL,
}

# The LEGACY vocabulary wa_codex_daemon.py actually emits TODAY
# (wa_broker.ALLOWED_ERROR_CLASSES) — see module docstring. auth and quota
# collapse into "cli_failure" here; that collapse is the exact F3 arming
# condition ("split before arming") this table cannot fix from the
# adapter side, so both map to INTERNAL rather than a guessed AUTH_DEAD or
# QUOTA (SPEC-codex-error-classification.md's own P5 discipline — "unknown
# stays unknown" — applied here to a daemon-side ambiguity this module did
# not create and cannot resolve by guessing).
_LEGACY_ERROR_CLASS_TO_KIND: dict[str, ProviderFailureKind] = {
    "exec_timeout": ProviderFailureKind.TIMEOUT,
    "cli_failure": ProviderFailureKind.INTERNAL,
    "cli_version_mismatch": ProviderFailureKind.INTERNAL,
    "spawn_failure": ProviderFailureKind.HOST_OFFLINE,
    "oversized_output": ProviderFailureKind.OUTPUT_INVALID,
    "empty_output": ProviderFailureKind.OUTPUT_INVALID,
    "policy_refusal": ProviderFailureKind.POLICY_BLOCKED,
}

# wa_broker.OfferOutcome values this leg can actually observe.
# ALREADY_SPENT/FENCE_LOST belong to offer_job's wa_outbox fencing, never
# raised by offer_client_job (no fencing on this leg — see its docstring)
# — mapped defensively to INTERNAL so an exhaustive lookup never KeyErrors
# if OfferOutcome ever grows a member this path can reach.
_OFFER_OUTCOME_TO_KIND: dict[wa_broker.OfferOutcome, ProviderFailureKind] = {
    wa_broker.OfferOutcome.BROKER_ABSENT: ProviderFailureKind.HOST_OFFLINE,
    wa_broker.OfferOutcome.BREAKER_OPEN: ProviderFailureKind.HOST_OFFLINE,
    # research capture §2.5: "codex_broker_queue_depth >= 1 waiting job ->
    # Bypass Codex for subsequent messages; do not grow the queue." TIMEOUT
    # carries exactly the router's fallback semantics this calls for — the
    # request cannot be served within budget, try the next provider.
    wa_broker.OfferOutcome.QUEUE_FULL: ProviderFailureKind.TIMEOUT,
    wa_broker.OfferOutcome.ALREADY_SPENT: ProviderFailureKind.INTERNAL,
    wa_broker.OfferOutcome.FENCE_LOST: ProviderFailureKind.INTERNAL,
}


def _error_class_to_kind(error_class: str | None) -> ProviderFailureKind:
    """Classify a ``broker_jobs.error_class`` string against BOTH the F3
    vocabulary and the legacy one the daemon emits today — see module
    docstring. An unrecognized non-``None`` value (a future daemon
    vocabulary this adapter has not been taught yet) falls back to
    ``INTERNAL`` rather than raising: an adapter that crashes on an
    unfamiliar-but-valid wire value would take the WHOLE client-bot
    provider chain down with it, which is a worse failure than reporting
    one generic bucket for one unclassified case.
    """
    if error_class is None:
        return ProviderFailureKind.INTERNAL
    if error_class in _F3_ERROR_CLASS_TO_KIND:
        return _F3_ERROR_CLASS_TO_KIND[error_class]
    if error_class in _LEGACY_ERROR_CLASS_TO_KIND:
        return _LEGACY_ERROR_CLASS_TO_KIND[error_class]
    logger.warning(
        "codex_broker provider: unrecognized broker error_class %r — "
        "mapping to INTERNAL (neither the F3 nor the legacy vocabulary "
        "names it; extend this module's tables when the daemon adds a "
        "new value)",
        error_class,
    )
    return ProviderFailureKind.INTERNAL


def _build_wire_package(request: BrainRequest, *, output_schema_version: str) -> tuple[str, str]:
    """Build the hash-sealed wire envelope sent to the codex broker's
    stdin (via the daemon; this adapter only builds the bytes and computes
    their integrity hash — the ``package_hash`` ``offer_client_job``
    stores for the daemon's own "verify package SHA-256" step, research
    capture §2.2).

    Deliberately serializes the FULL ``GroundingBundle``
    (``request.grounding.model_dump(mode="json")``) rather than a
    hand-picked subset: Gemini and Codex must see IDENTICAL evidence
    (F1.5 routing rule 2), and hand-picking fields here would silently
    drop a future ``GroundingBundle`` field from the codex leg only,
    reintroducing exactly the two-loaders-drift class this codebase
    documents as W114 elsewhere. ``request.message`` (the raw
    ``CanonicalMessage``) is deliberately NOT forwarded — the effective
    question already lives in ``grounding.query`` (built upstream by the
    out-of-scope ``GroundingBundleBuilder``), and forwarding the message
    envelope too would duplicate transport-adjacent identifiers
    (``event_id``/``trace_id``/``conversation_id``/``session_id``) into a
    cloud-bound prompt for no generation benefit.

    ``surface_constraints`` IS a curated subset of ``request.profile`` —
    the inverse call: ``SurfaceProfile`` also carries ``renderer_name``/
    ``handoff_queue``/i18n copy-keys that steer DOWNSTREAM rendering and
    the gate, not generation; forwarding them would leak irrelevant
    plumbing into the model's context without helping it answer.

    The ``instructions`` field is MECHANICAL wire-protocol guidance only
    (output shape, the ``package_sha256`` echo requirement, length/
    citation constraints derived from the profile) — it deliberately does
    NOT contain persona/voice prose (F1: "Prompt/persona rules continue to
    come from ``backend/prompts/zantara_core.py``. Do not create a second
    prompt-policy source under ``client_bot/``."). How
    ``zantara_core.py``'s persona content reaches the codex leg is NOT
    resolved by this module — declared as an open integration question for
    whichever lane builds the shared prompt-assembly step both the Gemini
    and Codex providers will need before B2 arms live traffic, not
    silently assumed solved here.

    Returns:
        ``(package_json, package_hash)`` — ``package_json`` is what
        ``offer_client_job`` stores verbatim in ``broker_jobs.package``;
        ``package_hash`` is its sha256 hex digest.
    """
    profile = request.profile
    envelope = {
        "wire_version": _WIRE_ENVELOPE_VERSION,
        "output_schema_version": output_schema_version,
        "request_id": str(request.request_id),
        "grounding": request.grounding.model_dump(mode="json"),
        "surface_constraints": {
            "surface": profile.surface.value,
            "max_words": profile.max_words,
            "soft_max_chars": profile.soft_max_chars,
            "hard_max_chars": profile.hard_max_chars,
            "max_paragraphs": profile.max_paragraphs,
            "max_bullets": profile.max_bullets,
            "allow_markdown": profile.allow_markdown,
            "allow_emoji": profile.allow_emoji,
            "citation_policy": profile.citation_policy.value,
            "citation_style": profile.citation_style.value,
        },
        "instructions": (
            "Respond with EXACTLY ONE JSON object matching the "
            "client_brain_candidate_v1 schema (schema_version, "
            "disposition, answer, claims, cited_evidence_ids, "
            "handoff_reason_code, provider_name, model_name, "
            "package_sha256). Copy the 'package_sha256' value from "
            "grounding.package_sha256 in this envelope VERBATIM into your "
            "own output's package_sha256 field — do not recompute it. "
            "Use ONLY the evidence and pricing items given in "
            "'grounding' — never invent a source, a citation id, a "
            "regulation, or a price. Every 'price' claim must name the "
            "exact price_service_key from the pricing snapshot; never a "
            "bare number. If the given evidence does not support a "
            "confident, fully-cited answer, set disposition='abstain' "
            "and leave answer empty. If this requires a human decision "
            "rather than information, set disposition='handoff' with a "
            "handoff_reason_code and leave answer empty. Respect "
            "surface_constraints' length/citation/formatting limits."
        ),
    }
    package = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
    package_hash = hashlib.sha256(package.encode("utf-8")).hexdigest()
    return package, package_hash


def _effective_deadline_s(request: BrainRequest, configured_deadline_s: int | None) -> int:
    """The smaller of the broker's own configured budget
    (``wa_broker.deadline_seconds()`` unless overridden) and however much
    time is actually left before ``request.deadline_at`` — a provider must
    never wait longer for a broker round-trip than the request itself has
    left to live. Floors at 1 second (never 0/negative) so a request whose
    deadline has already passed still fails FAST through the real
    offer/wait path (and gets classified as TIMEOUT/DEADLINE like any
    other budget exhaustion) rather than being rejected before ever
    reaching the broker with a value SQL would reject outright.
    """
    configured = (
        configured_deadline_s if configured_deadline_s is not None else wa_broker.deadline_seconds()
    )
    remaining_s = (request.deadline_at - datetime.now(timezone.utc)).total_seconds()
    if remaining_s <= 0:
        return 1
    return max(1, min(configured, int(remaining_s)))


class CodexBrokerClientBrainProvider:
    """``ClientBrainProvider`` implementation for the F3 codex-broker leg.

    Constructed with an injected ``asyncpg.Pool`` (Golden Rule #10 spirit:
    the pool's lifecycle belongs to app wiring/``lifespan``, never created
    per-call here) rather than reading one from a global — the same
    dependency-injection shape ``ClientBrainProviderRouter`` itself uses
    for its `providers` mapping.
    """

    name: str = PROVIDER_NAME

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        output_schema_version: str = _DEFAULT_OUTPUT_SCHEMA_VERSION,
        deadline_s: int | None = None,
    ) -> None:
        """
        Args:
            pool: shared asyncpg connection pool (app-wide, not owned here).
            output_schema_version: the ``client_brain_candidate_v1.json``
                contract version the daemon's ``codex exec --output-schema``
                is expected to target. Stored verbatim in the wire envelope
                and in ``broker_jobs.output_schema_version`` (migration
                290) so a future promotion ladder can distinguish jobs by
                the schema version they were offered under.
            deadline_s: override for the broker-side budget
                (``wa_broker.deadline_seconds()`` default, 15s). Always
                further bounded per-call by ``request.deadline_at`` — see
                ``_effective_deadline_s``.
        """
        self._pool = pool
        self._output_schema_version = output_schema_version
        self._deadline_s = deadline_s

    async def generate(self, request: BrainRequest) -> BrainCandidate:
        """Offer, wait, consume, parse — see module docstring for the full
        job-queue shape. Never returns anything but a valid
        ``BrainCandidate``; every other outcome is a typed
        ``ProviderFailure`` (base.py's contract: "Failure is a typed
        exception, not a return-type union").
        """
        package, package_hash = _build_wire_package(
            request, output_schema_version=self._output_schema_version
        )
        deadline_s = _effective_deadline_s(request, self._deadline_s)
        surface = request.message.surface.value

        try:
            async with self._pool.acquire() as conn:
                offer = await wa_broker.offer_client_job(
                    conn,
                    request_id=request.request_id,
                    surface=surface,
                    package=package,
                    package_hash=package_hash,
                    output_schema_version=self._output_schema_version,
                    deadline_s=deadline_s,
                )
        except Exception as exc:
            logger.warning(
                "codex_broker provider: offer failed (request=%s): %s",
                request.request_id,
                type(exc).__name__,
            )
            raise ProviderFailure(
                self.name, ProviderFailureKind.INTERNAL, f"offer_error:{type(exc).__name__}"
            ) from exc

        if offer.outcome is not wa_broker.OfferOutcome.OFFERED or offer.job_id is None:
            raise ProviderFailure(
                self.name,
                _OFFER_OUTCOME_TO_KIND.get(offer.outcome, ProviderFailureKind.INTERNAL),
                f"offer:{offer.outcome.value}",
            )

        try:
            wait = await wa_broker.wait_for_job(self._pool, offer.job_id)
        except Exception as exc:
            logger.warning(
                "codex_broker provider: wait failed (request=%s job=%s): %s",
                request.request_id,
                offer.job_id,
                type(exc).__name__,
            )
            raise ProviderFailure(
                self.name, ProviderFailureKind.INTERNAL, f"wait_error:{type(exc).__name__}"
            ) from exc

        if wait.outcome is wa_broker.WaitOutcome.DEADLINE:
            raise ProviderFailure(self.name, ProviderFailureKind.TIMEOUT, "deadline")
        if wait.outcome is wa_broker.WaitOutcome.FAILED:
            raise ProviderFailure(
                self.name,
                _error_class_to_kind(wait.error_class),
                f"error_class:{wait.error_class or 'unknown'}",
            )
        # wait.outcome is COMPLETED past this point.

        try:
            async with self._pool.acquire() as conn:
                result_text = await wa_broker.consume_result(conn, offer.job_id)
        except Exception as exc:
            logger.warning(
                "codex_broker provider: consume failed (request=%s job=%s): %s",
                request.request_id,
                offer.job_id,
                type(exc).__name__,
            )
            raise ProviderFailure(
                self.name, ProviderFailureKind.INTERNAL, f"consume_error:{type(exc).__name__}"
            ) from exc

        if result_text is None or not result_text.strip():
            # Lost a race with the reaper's dead-consumer grace, or a
            # completion no owner may fold twice — see wa_codex_leg.py's
            # identical "consume_lost" reasoning. Not this leg's failure to
            # diagnose further; the router's fallback attempt (or the next
            # request) gets a fresh offer.
            raise ProviderFailure(self.name, ProviderFailureKind.TIMEOUT, "consume_lost")

        try:
            return BrainCandidate.model_validate_json(result_text)
        except (ValidationError, ValueError) as exc:
            # Never logs result_text itself (PII/CLAUDE.md §14 discipline —
            # this is exactly the kind of content the daemon's own
            # "package/result bodies are never logged" rule protects).
            logger.warning(
                "codex_broker provider: candidate failed schema validation "
                "(request=%s job=%s)",
                request.request_id,
                offer.job_id,
            )
            raise ProviderFailure(
                self.name, ProviderFailureKind.OUTPUT_INVALID, "schema_validation_failed"
            ) from exc

    async def health(self) -> ProviderHealth:
        """Best-effort liveness snapshot from ``wa_broker_gauge`` — never
        raises (base.py's ``ProviderHealth`` contract: "never authoritative
        on its own"; a query failure here reports unhealthy rather than
        propagating, since a health check that can crash its own caller is
        worse than a health check that is occasionally wrong).
        """
        now = datetime.now(timezone.utc)
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT breaker_state,
                           broker_last_seen_at
                               >= now() - ($1 * INTERVAL '1 second')
                               AS broker_alive
                    FROM wa_broker_gauge WHERE id = 1
                    """,
                    wa_broker.absent_after_seconds(),
                )
        except Exception as exc:
            return ProviderHealth(
                healthy=False, detail=f"gauge_query_error:{type(exc).__name__}", checked_at=now
            )

        if row is None:
            return ProviderHealth(healthy=False, detail="gauge_unseeded", checked_at=now)
        if not row["broker_alive"]:
            return ProviderHealth(healthy=False, detail="host_offline", checked_at=now)
        if row["breaker_state"] == "open":
            return ProviderHealth(healthy=False, detail="breaker_open", checked_at=now)
        return ProviderHealth(healthy=True, detail=f"breaker_{row['breaker_state']}", checked_at=now)
