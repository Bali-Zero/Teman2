"""crm-cell — light cell wrapping for the existing CRM modules.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/crm-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md
  docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md (TICKET A.1)

The CRM modules (engine, practice_status_listener, welcome_practice_service,
drive_poll_service, etc.) are wrapped — NOT rewritten. This package adds 3
lateral concerns around the existing logic:

* :class:`CrmScarRecorder` (:mod:`scar_recorder`) — recurring failure
  patterns (welcome partial-failure, enrichment circuit-breaker open,
  drive_poll page_token reset) land in ``packages/cell-core`` Genome as
  scars so future runs can back off and the supervisor can surface
  persistent degradation.

* :class:`CrmHGTBridge` (:mod:`hgt_publisher`) — high-confidence STRUCTURAL
  discoveries (e.g. "Brevo template ID X reliably bounces for
  client_segment Y") are broadcast to sibling cells via the cell-core HGT
  stream. Client PII stays scoped to UU PDP (never published — only
  structural patterns with confidence ≥ 0.7). Async API only; the Sprint 3
  W2 sync stub ``CrmHGTPublisher`` was REMOVED in Phase 3 TICKET A.1.

* :class:`CrmEventBridge` (:mod:`event_bridge`) — every welcome run
  records a durable audit row via the existing ``crm_welcome_runs``
  trigger (migration 153, mig 144 + 146 outbox pattern).

W2 status: ``CrmScarRecorder`` + ``CrmEventBridge`` ship as STUBS that
accept the canonical inputs and log the would-run operation; wiring into
``welcome_practice_service``, ``crm_automation_engine``, and
``drive_poll_service`` lands in Sprint 4. ``CrmHGTBridge`` (post Phase 3
TICKET A.1) is production-ready async; the production caller lands in
TICKET A.2 (operator-gated).

The cell IS the existing FastAPI request cycle (``runtime: fastapi-inproc``
per cell.yaml Q1 decision) — there's no new daemon. The classes here
are imported and instantiated INSIDE the existing CRM services.
"""
from __future__ import annotations

from .event_bridge import CrmEventBridge, WelcomeRunResult
from .hgt_publisher import CrmHGTBridge, StructuralPattern
from .scar_recorder import CrmScar, CrmScarRecorder, FailureKind

CELL_NAME = "crm-cell"
CELL_VERSION = "0.2.0"

__all__ = [
    "CELL_NAME",
    "CELL_VERSION",
    "CrmEventBridge",
    "CrmHGTBridge",
    "CrmScar",
    "CrmScarRecorder",
    "FailureKind",
    "StructuralPattern",
    "WelcomeRunResult",
]
