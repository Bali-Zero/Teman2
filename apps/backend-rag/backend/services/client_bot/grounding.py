"""GroundingBundleBuilder — the ONE frozen evidence/pricing/history package
every provider sees identically (research capture Sol §1.1/§1.5 routing
rule 2: "GroundingBundleBuilder runs before provider selection. Gemini and
Codex receive the same evidence and PricingTool snapshot").

Two collaborators, two different maturity levels — both deliberate, both
reported to the team lead before this lane built outward on them:

- ``PricingSnapshot`` construction is wired to the REAL, live PricingTool
  (``services/pricing/pricing_service.py::get_pricing_service()``) —
  Golden Rule 11 ("PricingTool Only") makes this the highest-risk path in
  the whole client-bot engine, so it gets a real integration, not a stub.
- Evidence (KB/Qdrant) retrieval is an injectable ``EvidenceRetriever``
  protocol with a safe empty default. The existing agentic RAG retrieval
  stack (``services/rag/agentic/orchestrator_core.py`` and its siblings)
  is a large, multi-file subsystem this lane does not own and has not
  wired — reaching into it correctly is a real integration project of its
  own, not something to rush during a dark-ship pass. An empty evidence
  tuple is SAFE here (never a false ALLOW): every FinalPolicyGate check
  that depends on evidence (6/8/9) fails closed — ABSTAIN or HANDOFF —

  **But safe is not the same as measured (team lead, 2026-08-25).** With
  no retriever wired, this builder returns an empty ``evidence`` tuple on
  EVERY query, which makes checks 6/8/9 abstain/handoff on EVERY claim
  that needs evidence — a well-formed, 100%-handoff result that LOOKS
  exactly like "the gates are working" and is INDISTINGUISHABLE from it in
  the output alone. It is not a measurement of retrieval quality, answer
  quality, or anything else — it is a stub returning its one possible
  answer. ``evidence_retrieval_is_stubbed`` below exists so no caller can
  produce a shadow/quality number from this builder without knowing that.
  **No shadow number from a stubbed builder measures answer quality —
  only that no evidence was ever offered to the gate.**

``domain`` classification (which of "immigration"/"company"/"tax"/
"property"/"kbli" a query belongs to) is likewise NOT this builder's job —
it is an input the caller (``engine.py``, or a future domain-classifier
lane) supplies, defaulting to the profile's sole allowed domain for
single-domain profiles (KBLI widget) and left unresolved (raises) for
multi-domain profiles without an explicit domain — see ``build()``.

``package_sha256`` is computed over every OTHER field before the bundle is
constructed (the bundle cannot hash itself) — the exact same canonical
serialization ``BrainCandidate.package_sha256`` must echo back verbatim
for check 2 (``final_gate.py``) to pass.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from backend.channels.profiles import SurfaceProfile
from backend.services.client_bot.contracts import (
    EvidenceItem,
    GroundingBundle,
    HistoryTurn,
    PricingSnapshot,
)
from backend.services.pricing.pricing_service import get_pricing_service

logger = logging.getLogger("zantara.backend")

__all__ = ["DomainNotSpecifiedError", "EvidenceRetriever", "GroundingBundleBuilder"]

# Logged once per stubbed build() call — deliberately WARNING, not INFO:
# this is a standing condition worth an operator's attention every time it
# fires, not routine progress. Never includes `query` (client text — PII
# boundary, CLAUDE.md §14); `domain` is a closed, small vocabulary string.
_STUBBED_EVIDENCE_WARNING = (
    "grounding: evidence retrieval is STUBBED (no EvidenceRetriever wired) for "
    "domain=%r — this bundle carries zero evidence by construction. Every "
    "FinalPolicyGate check that depends on evidence (6/8/9) will fail closed "
    "(ABSTAIN/HANDOFF), which is SAFE, but NO shadow/containment/abstain-rate "
    "number computed against this call measures retrieval or answer quality — "
    "see GroundingBundleBuilder.evidence_retrieval_is_stubbed."
)

_PRICING_TOOL_VERSION = "pricing-service-2026"


class DomainNotSpecifiedError(ValueError):
    """Raised when ``build()`` is called with no explicit ``domain`` for a
    profile whose ``allowed_domains`` has more than one member — silently
    guessing a domain for a multi-domain surface is exactly the kind of
    unverified assumption CLAUDE.md §6 forbids.
    """


class EvidenceRetriever(Protocol):
    """A future lane's real KB/Qdrant retrieval. See module docstring for
    why no lane has wired this yet.
    """

    async def retrieve(self, query: str, domain: str) -> tuple[EvidenceItem, ...]: ...


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_package_sha256(
    *,
    query: str,
    domain: str,
    evidence: tuple[EvidenceItem, ...],
    pricing: PricingSnapshot | None,
    history: tuple[HistoryTurn, ...],
    persona_digest: str,
) -> str:
    payload = {
        "query": query,
        "domain": domain,
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "pricing": pricing.model_dump(mode="json") if pricing is not None else None,
        "history": [h.model_dump(mode="json") for h in history],
        "persona_digest": persona_digest,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class GroundingBundleBuilder:
    def __init__(
        self,
        *,
        evidence_retriever: EvidenceRetriever | None = None,
        persona_digest: str = "zantara-persona-v1",
    ) -> None:
        self._evidence_retriever = evidence_retriever
        self._persona_digest = persona_digest

    @property
    def evidence_retrieval_is_stubbed(self) -> bool:
        """``True`` when this builder was constructed with no real
        ``EvidenceRetriever`` — every bundle it builds carries an empty
        ``evidence`` tuple regardless of the query. See the module
        docstring's "safe is not the same as measured" note. Check this
        BEFORE trusting any shadow/quality number produced from this
        builder's output — `ClientBotEngine` exposes the same signal.
        """
        return self._evidence_retriever is None

    async def build(
        self,
        *,
        query: str,
        profile: SurfaceProfile,
        domain: str | None = None,
        history: tuple[HistoryTurn, ...] = (),
    ) -> GroundingBundle:
        resolved_domain = self._resolve_domain(profile, domain)

        evidence: tuple[EvidenceItem, ...] = ()
        if self._evidence_retriever is not None:
            evidence = await self._evidence_retriever.retrieve(query, resolved_domain)
        else:
            logger.warning(_STUBBED_EVIDENCE_WARNING, resolved_domain)

        pricing = self._build_pricing_snapshot() if resolved_domain != "kbli" else None

        package_sha256 = _compute_package_sha256(
            query=query,
            domain=resolved_domain,
            evidence=evidence,
            pricing=pricing,
            history=history,
            persona_digest=self._persona_digest,
        )

        return GroundingBundle(
            bundle_id=uuid.uuid4(),
            query=query,
            domain=resolved_domain,
            evidence=evidence,
            pricing=pricing,
            history=history,
            persona_digest=self._persona_digest,
            package_sha256=package_sha256,
        )

    @staticmethod
    def _resolve_domain(profile: SurfaceProfile, domain: str | None) -> str:
        if domain is not None:
            if domain not in profile.allowed_domains:
                logger.warning(
                    "grounding: explicit domain=%r not in profile %s's allowed_domains — "
                    "FinalPolicyGate check 5 will abstain, this is not silently corrected here",
                    domain,
                    profile.profile_id,
                )
            return domain
        if len(profile.allowed_domains) == 1:
            return next(iter(profile.allowed_domains))
        raise DomainNotSpecifiedError(
            f"{profile.profile_id} allows {sorted(profile.allowed_domains)!r} — "
            "an explicit domain is required, none was inferred"
        )

    def _build_pricing_snapshot(self) -> PricingSnapshot | None:
        """Real PricingTool integration (Golden Rule 11) — never a
        hardcoded price. ``get_pricing_service()`` returns the same
        process-wide singleton ``PricingTool`` (services/rag/agentic/
        tools.py) already uses, so this builder and the existing RAG path
        can never disagree about what "the frozen pricing snapshot" means.
        """
        service = get_pricing_service()
        if not getattr(service, "loaded", False):
            logger.warning("grounding: PricingService not loaded — no PricingSnapshot built")
            return None
        raw = service.get_pricing("all")
        if not isinstance(raw, dict) or raw.get("error"):
            logger.warning("grounding: PricingService.get_pricing('all') returned an error payload")
            return None
        snapshot_sha256 = hashlib.sha256(_canonical_json(raw).encode("utf-8")).hexdigest()
        return PricingSnapshot(
            snapshot_id=uuid.uuid4(),
            pricing_tool_version=_PRICING_TOOL_VERSION,
            generated_at=datetime.now(timezone.utc),
            items=(raw,),
            snapshot_sha256=snapshot_sha256,
        )
