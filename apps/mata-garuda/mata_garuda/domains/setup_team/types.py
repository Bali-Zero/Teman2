"""Setup Team domain types (B1).

Single source of truth for the dataclasses passed between feeders, the
obligation engine, the promotion gate, and the client matcher. Pure stdlib
— no httpx, no pydantic, no sqlite. Importing this module is safe in any
context (sub-100ms cold-start cron, wave-1 worker, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, Optional

# Tier scheme (per spec §2 B1):
#   1 = gov direct (peraturan.bpk.go.id, setkab.go.id, jdih.*) — auto-approve after SLA
#   2 = gov press signal (Tempo, Hukumonline, Detik tag) — escalate after SLA
#   3 = community/blog (deferred Phase 2)
RegulationTier = Literal[1, 2, 3]

# Domain bucket — matches the 4 NB-INTEL streams Phase 1 covers.
RegulationDomain = Literal[
    "regulation",       # NB-INTEL-Regulation (national, all sectors)
    "immigration",      # NB-INTEL-Immigration (KITAS/VITAS/visa/RPTKA)
    "regulation_bali",  # NB-INTEL-Regulation-Bali (4 jdih portals)
]

ObligationType = Literal[
    "filing",         # SPT, NPWP report, LKPM
    "reporting",      # quarterly/annual disclosure
    "payment",        # tax, royalty, sanction
    "operational",    # PBG, SLF, IUMK
    "registration",   # KBLI, NIB, OSS
]

PromotionDecision = Literal[
    "pending",        # in queue, SLA not reached
    "approved",       # human or auto-approve
    "rejected",       # human reject
    "escalated",      # SLA passed, tier 2 → manual review escalated
]


@dataclass(frozen=True)
class Regulation:
    """One regulatory artifact harvested by a feeder.

    `source_id` is the feeder-specific ID (e.g. pasal.id law id, jdih portal
    record id, or hash of URL+title for ad-hoc scrapers). Globally unique
    when prefixed by `domain`.
    """

    source_id: str
    domain: RegulationDomain
    tier: RegulationTier
    title: str
    url: str
    published_at: Optional[date] = None
    body_excerpt: str = ""
    # Free-form tags for downstream scorer-fastpath filtering. Examples:
    # ["regex_match:PMK 81/2024"], ["bali_tourism", "property"].
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Obligation:
    """One atomic obligation extracted from a regulation article.

    Bottom-up AscentAI pattern: each `Pasal X ayat Y` may yield 0..N
    obligations. The `id` is assigned by SQLite (autoincrement); when
    extracted in-memory it is `None` until persisted.
    """

    text: str
    obligation_type: ObligationType
    article_ref: str  # e.g. "Pasal 4 ayat (2)"
    deadline_pattern: str  # verbatim: "30 hari setelah …" / "tahunan ke-N"
    sanction_if_missed: str
    effective_date: Optional[date]
    kbli_codes_affected: tuple[str, ...]  # e.g. ("63122", "62019")
    regulation_source_id: str  # FK back to Regulation.source_id
    id: Optional[int] = None
    human_validated: bool = False


@dataclass(frozen=True)
class Client:
    """Active Bali Zero client. Used by client_match for KBLI overlap.

    `kbli_codes` is a tuple of KBLI strings (5-digit codes, e.g. "63122").
    Empty tuple means "no KBLI assigned yet" — match_obligations skips them.
    """

    id: int
    name: str
    kbli_codes: tuple[str, ...]
    active: bool = True
    contact: str = ""  # email or phone, optional


@dataclass(frozen=True)
class PromotionEntry:
    """Row in `promotion_queue` — INTEL→AUTHORITY promotion proposal."""

    intel_source_id: str  # FK to Regulation.source_id
    target_authority_nb: str  # e.g. "NB-AUTHORITY-Regulation"
    proposed_at: datetime
    sla_deadline: datetime
    owner: str  # "Adit" | "Veronika" | "Krisna" | "Surya" | etc.
    decision: PromotionDecision = "pending"
    queue_id: Optional[int] = None
    decided_at: Optional[datetime] = None


@dataclass(frozen=True)
class Match:
    """Result row of client_match — one obligation matched to one client."""

    obligation_id: int
    client_id: int
    matched_kbli: tuple[str, ...]  # intersection of obligation × client KBLI
    alert_payload: dict = field(default_factory=dict)


__all__ = [
    "Client",
    "Match",
    "Obligation",
    "ObligationType",
    "PromotionDecision",
    "PromotionEntry",
    "Regulation",
    "RegulationDomain",
    "RegulationTier",
]
