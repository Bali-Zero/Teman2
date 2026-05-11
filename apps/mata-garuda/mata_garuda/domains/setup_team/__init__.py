"""Setup Team domain (B1) — per-domain layer for immigration / company KBLI / property / labor.

Source spec: docs/superpowers/specs/2026-05-08-domain-mesh-autonomic-design.md §2 B1
Source plan: docs/superpowers/plans/2026-05-08-domain-mesh-phase1-setup-team.md

Sub-modules (lazy via PEP 562 __getattr__, mirroring foundations/__init__.py):

- types: lightweight dataclasses (Regulation, Obligation, Client, Match, PromotionEntry)
- feeders.nb_intel_regulation: NB-INTEL-Regulation feeder
- feeders.nb_intel_immigration: NB-INTEL-Immigration feeder
- feeders.nb_intel_regulation_bali: NB-INTEL-Regulation-Bali sub-stream (4 portals)
- obligation_engine: AscentAI bottom-up obligation extraction (claude --print subprocess)
- promotion_gate: human-approved INTEL→AUTHORITY promotion with timeboxed SLA
- client_match: KBLI overlap matching
- scheduler: Bali calendar guard (skip Galungan/Kuningan windows)

Wave 2 lesson (foundations): heavy modules (httpx async fetchers, NER, claude --print
subprocess, sqlite3) load only when callers explicitly access them. Importing
`mata_garuda.domains.setup_team` alone must NOT pull transformers/torch/sklearn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Eager: pure stdlib types only. No httpx, no transformers, no sqlite cursor open.
from mata_garuda.domains.setup_team.types import (
    Client,
    Match,
    Obligation,
    PromotionEntry,
    Regulation,
)

# Lazy: anything that touches httpx, sqlite, claude subprocess, NER pipeline.
_LAZY_EXPORTS = {
    "fetch_recent_regulations": (
        "mata_garuda.domains.setup_team.feeders.nb_intel_regulation",
        "fetch_recent_regulations",
    ),
    "fetch_recent_immigration": (
        "mata_garuda.domains.setup_team.feeders.nb_intel_immigration",
        "fetch_recent_immigration",
    ),
    "fetch_recent_regulation_bali": (
        "mata_garuda.domains.setup_team.feeders.nb_intel_regulation_bali",
        "fetch_recent_regulation_bali",
    ),
    "extract_obligations": (
        "mata_garuda.domains.setup_team.obligation_engine",
        "extract_obligations",
    ),
    "propose_promotion": (
        "mata_garuda.domains.setup_team.promotion_gate",
        "propose_promotion",
    ),
    "check_sla_and_alert": (
        "mata_garuda.domains.setup_team.promotion_gate",
        "check_sla_and_alert",
    ),
    "auto_approve_tier1_after_sla": (
        "mata_garuda.domains.setup_team.promotion_gate",
        "auto_approve_tier1_after_sla",
    ),
    "match_obligations_to_clients": (
        "mata_garuda.domains.setup_team.client_match",
        "match_obligations_to_clients",
    ),
    "should_skip_today": (
        "mata_garuda.domains.setup_team.scheduler",
        "should_skip_today",
    ),
}

if TYPE_CHECKING:  # pragma: no cover
    from mata_garuda.domains.setup_team.client_match import (
        match_obligations_to_clients,
    )
    from mata_garuda.domains.setup_team.feeders.nb_intel_immigration import (
        fetch_recent_immigration,
    )
    from mata_garuda.domains.setup_team.feeders.nb_intel_regulation import (
        fetch_recent_regulations,
    )
    from mata_garuda.domains.setup_team.feeders.nb_intel_regulation_bali import (
        fetch_recent_regulation_bali,
    )
    from mata_garuda.domains.setup_team.obligation_engine import extract_obligations
    from mata_garuda.domains.setup_team.promotion_gate import (
        auto_approve_tier1_after_sla,
        check_sla_and_alert,
        propose_promotion,
    )
    from mata_garuda.domains.setup_team.scheduler import should_skip_today


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module_name, attr_name = _LAZY_EXPORTS[name]
        import importlib

        module = importlib.import_module(module_name)
        attr = getattr(module, attr_name)
        globals()[name] = attr  # cache for subsequent accesses
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Client",
    "Match",
    "Obligation",
    "PromotionEntry",
    "Regulation",
    "auto_approve_tier1_after_sla",
    "check_sla_and_alert",
    "extract_obligations",
    "fetch_recent_immigration",
    "fetch_recent_regulation_bali",
    "fetch_recent_regulations",
    "match_obligations_to_clients",
    "propose_promotion",
    "should_skip_today",
]
