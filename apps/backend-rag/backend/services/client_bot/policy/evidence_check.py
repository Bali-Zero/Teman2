"""Checks 6, 8, 9 — claim inventory completeness, evidence support, and
citation integrity (research capture Sol §1.6). The "claim/citation
support" module Sol's own layout names.

Check 6 (claim inventory completeness) is DELIBERATELY split into two
different detection strategies, not one, because the two halves of its
own spec sentence are not the same kind of problem:

- "currency amounts... dates, deadlines, percentages" are a BOUNDED
  syntactic class — the same kind of thing ``pricing_check.py``'s currency
  regex already detects reliably. ``UNINVENTORIED_NUMERIC_STATEMENT``
  checks these against the claims the model actually inventoried.
- "eligibility statements, and regulatory assertions" in general natural
  language IS the unbounded-phrasing trap the team lead's brief warned
  against (the team-bot's 16-false-ALLOW lesson: enumerating suspicious
  phrasings is unbounded). This module does NOT attempt that. It checks
  ``UNINVENTORIED_REGULATED_STATEMENT`` only against a narrow, genuinely
  bounded lexical class instead — Indonesian legal-citation SHAPES
  ("UU No. 6 Tahun 2011", "Pasal 48", "PP No. 31 Tahun 2013",
  "Permenkumham No. X"), which are a closed naming convention, not open
  natural language. A regulatory assertion with no legal-citation shape at
  all is NOT caught by this check — that residual gap is real and is
  covered by check 8 (every regulatory/eligibility/deadline claim still
  needs an evidence_id) and check 9 (citation integrity) as a second,
  independent layer, not by trying to make check 6 catch everything.

Check 8's "semantic support verification" is an injectable
``SemanticVerifier`` — no real semantic verifier is wired by this lane
(that is a future integration, likely an embedding-similarity or LLM-judge
call this lane does not own). The default behaves exactly as Sol's own
spec requires for this exact situation: "verifier outage or uncertainty
becomes abstention" — with no verifier registered, every claim that would
need semantic backing reports ``EVIDENCE_VERIFIER_OUTAGE``, never a false
ALLOW.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from backend.services.client_bot.contracts import (
    BrainCandidate,
    Claim,
    EvidenceItem,
    GroundingBundle,
)
from backend.services.client_bot.policy.check_result import CheckOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict

__all__ = [
    "SemanticVerifier",
    "check_citation_integrity",
    "check_claim_inventory",
    "check_evidence_support",
]

# Claim kinds that assert something a client could act on wrongly if
# unsupported — the kinds check 8 requires evidence for under the default
# REGULATORY_AND_NUMERIC citation policy (ALL_FACTUAL widens this to every
# claim — see check_evidence_support / check_citation_integrity).
# "price" is NOT in this set: pricing_check.py's check 7 is the dedicated,
# stricter enforcement for it (verbatim match against PricingSnapshot, not
# a KB evidence_id) — B6b's own golden fixture "client.pricing-correct"
# constructs a valid price claim with evidence_ids=() (verified empirically:
# requiring evidence here would reject that fixture's own ALLOW case).
_EVIDENCE_REQUIRED_KINDS = frozenset({"regulatory", "eligibility", "deadline"})

# Bounded numeric-statement shape (check 6, numeric half): currency only.
# Kept separate from pricing_check.py's identical-shaped regex deliberately
# — this module checks claim COVERAGE, not price CORRECTNESS, and importing
# pricing_check's private regex would couple two independent checks'
# internals for no benefit. Percentages and date/duration idioms were
# tried and DROPPED (B1b review): the B6b goldens' own ALLOW fixtures
# ("client.regulation-supported-correct-citation",
# "client.provider-timeout-then-fallback") both contain a bare duration
# mention ("5-7 hari kerja", "30 hari") with NO dedicated numeric claim,
# verified empirically to be legal — Indonesian regulatory prose is full
# of duration idioms and dates-with-month-names that a bounded regex
# cannot distinguish from a genuinely unsupported invented figure without
# false-positiving on exactly the goldens' own correct answers.
_CURRENCY_RE = re.compile(r"\b(?:Rp\.?|IDR|USD|\$)[ \t]*\d(?:[\d.,]*\d)?", re.IGNORECASE)

# Indonesian legal-citation SHAPES — a closed naming convention (law type +
# number + "Tahun"/year), not open natural language. Deliberately narrow:
# catches "UU No. 6 Tahun 2011", "PP 31/2013", "Permenkumham No. 11 Tahun
# 2023", "Pasal 48 ayat (1)" — misses a regulatory assertion phrased with
# no citation shape at all, which is an accepted residual per the module
# docstring (checks 8/9 are the second layer for that gap, not this check).
_LEGAL_CITATION_RE = re.compile(
    r"\b(?:UU|PP|Perpres|Permenkumham|Permenaker|Permenkes|PMK|Perka|Pasal|Ayat)"
    r"[.\s]*(?:No\.?\s*)?\d+"
    r"(?:[/\s]*(?:Tahun\s*)?\d{2,4})?",
    re.IGNORECASE,
)


def check_claim_inventory(candidate: BrainCandidate) -> CheckOutcome | None:
    """None means pass. Only runs meaningfully on disposition="answer" —
    abstain/handoff candidates carry no answer text to scan (contracts.py's
    own disposition-coupling validator already guarantees this).
    """
    if not candidate.answer:
        return None

    has_price_claim = any(c.kind == "price" for c in candidate.claims)
    if not has_price_claim and _CURRENCY_RE.search(candidate.answer):
        return CheckOutcome(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.UNINVENTORIED_NUMERIC_STATEMENT,
            reason_detail="answer carries a currency-shaped statement not represented by any price claim",
        )

    has_regulatory_claim = any(c.kind == "regulatory" for c in candidate.claims)
    if not has_regulatory_claim and _LEGAL_CITATION_RE.search(candidate.answer):
        return CheckOutcome(
            verdict=GateVerdict.ABSTAIN,
            reason=GateReason.UNINVENTORIED_REGULATED_STATEMENT,
            reason_detail="answer carries a legal-citation-shaped statement not represented "
            "by any regulatory claim",
        )

    return None


# A semantic verifier scores how well `evidence` supports `claim`, in
# [0.0, 1.0], or returns None to mean "outage/uncertain" (Sol's own
# required fail-safe reading — see module docstring). ASYNC (Golden Rule 4
# — a real verifier will call an embedding/LLM service over I/O).
SemanticVerifier = Callable[[Claim, tuple[EvidenceItem, ...]], Awaitable[float | None]]

# Not one number (CLAUDE.md §9's own "evidence scoring is NOT one number,
# 5 named gates" invariant applies here too): this is a NEW, distinct gate
# for the client-bot semantic-support check specifically, not a reuse of
# _abstain_policy.py's generation/label/confidence/context_quality gates,
# which score a DIFFERENT thing (RAG generation confidence, not a client-
# bot claim's evidence support). 0.6 is a documented invention pending a
# real verifier + measured calibration — deliberately conservative given
# this is the anti-hallucination gate CLAUDE.md §6 names as load-bearing.
_SEMANTIC_SUPPORT_THRESHOLD = 0.6


async def check_evidence_support(
    candidate: BrainCandidate,
    grounding: GroundingBundle,
    *,
    citation_policy_all_factual: bool,
    semantic_verifier: SemanticVerifier | None = None,
) -> CheckOutcome | None:
    """None means pass. ``citation_policy_all_factual`` is the caller's
    ``SurfaceProfile.citation_policy == CitationPolicy.ALL_FACTUAL`` (KBLI
    widget) — widens the evidence-required kind set to every claim, not
    just regulatory/eligibility/deadline/price.
    """
    evidence_by_id = {e.evidence_id: e for e in grounding.evidence}

    for claim in candidate.claims:
        needs_evidence = citation_policy_all_factual or claim.kind in _EVIDENCE_REQUIRED_KINDS
        if not needs_evidence:
            continue
        if not claim.evidence_ids:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.CLAIM_MISSING_EVIDENCE_ID,
                reason_detail=f"{claim.claim_id} ({claim.kind}) carries no evidence_id",
            )

        cited_evidence = tuple(evidence_by_id[eid] for eid in claim.evidence_ids if eid in evidence_by_id)
        if not cited_evidence:
            # Every evidence_id the claim names is absent from the bundle —
            # a deterministic, structural failure (not a semantic one).
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.EVIDENCE_DETERMINISTIC_CHECK_FAILED,
                reason_detail=f"{claim.claim_id}: none of its evidence_ids exist in the bundle",
            )

        # ABSTAIN, not HANDOFF, for both branches below — Sol §1.6 states
        # this verbatim ("verifier outage or uncertainty becomes
        # abstention"), and it is verified against the B6b golden fixture
        # "client.deadline-date-mismatch" (a real, non-outage semantic
        # miss — the cited evidence exists but does not support the
        # claim's specific date — still resolves to ABSTAIN, not HANDOFF).
        if semantic_verifier is None:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.EVIDENCE_VERIFIER_OUTAGE,
                reason_detail="no semantic verifier registered — fail-safe per Sol §1.6",
            )
        score = await semantic_verifier(claim, cited_evidence)
        if score is None:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.EVIDENCE_VERIFIER_OUTAGE,
                reason_detail=f"{claim.claim_id}: verifier reported outage/uncertain",
            )
        if score < _SEMANTIC_SUPPORT_THRESHOLD:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD,
                reason_detail=f"{claim.claim_id}: score {score:.2f} < {_SEMANTIC_SUPPORT_THRESHOLD}",
            )

    return None


def check_citation_integrity(
    candidate: BrainCandidate,
    grounding: GroundingBundle,
    *,
    citation_policy_all_factual: bool,
) -> CheckOutcome | None:
    """None means pass."""
    bundle_ids = {e.evidence_id for e in grounding.evidence}

    for cid in candidate.cited_evidence_ids:
        if cid not in bundle_ids:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.CITATION_ID_NOT_IN_BUNDLE,
                reason_detail=f"{cid} not present in the frozen GroundingBundle",
            )

    claim_evidence_ids = {eid for claim in candidate.claims for eid in claim.evidence_ids}
    for cid in candidate.cited_evidence_ids:
        if cid not in claim_evidence_ids:
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.CITATION_TO_UNUSED_EVIDENCE,
                reason_detail=f"{cid} is displayed but backs no claim",
            )

    for claim in candidate.claims:
        needs_evidence = citation_policy_all_factual or claim.kind in _EVIDENCE_REQUIRED_KINDS
        if not needs_evidence or not claim.evidence_ids:
            continue
        if not any(eid in candidate.cited_evidence_ids for eid in claim.evidence_ids):
            if citation_policy_all_factual:
                return CheckOutcome(
                    verdict=GateVerdict.ABSTAIN,
                    reason=GateReason.KBLI_CLASSIFICATION_MISSING_ALL_FACTUAL_CITATION,
                    reason_detail=f"{claim.claim_id}: no evidence_id displayed under ALL_FACTUAL policy",
                )
            return CheckOutcome(
                verdict=GateVerdict.ABSTAIN,
                reason=GateReason.CLAIM_MISSING_DISPLAYED_CITATION,
                reason_detail=f"{claim.claim_id}: cites evidence internally but none is displayed",
            )

    return None
