"""crm-cell — light cell wrapping for the existing CRM modules.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/crm-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md

The CRM modules (engine, practice_status_listener, welcome_practice_service,
drive_poll_service, etc.) are wrapped — NOT rewritten. This package adds 3
lateral concerns around the existing logic:

* :class:`CrmGenome` — recurring failure patterns (welcome partial-failure,
  enrichment circuit-breaker open, drive_poll page_token reset) land in
  ``packages/cell-core`` Genome as scars so future runs can back off and
  the supervisor can surface persistent degradation.
* :class:`CrmHGTPublisher` — high-confidence STRUCTURAL discoveries (e.g.
  "Brevo template ID X reliably bounces for client_segment Y") are
  broadcast to sibling cells via the cell-core HGT stream. Client PII
  stays scoped to UU PDP (never published — only structural patterns
  with confidence ≥0.7).
* :class:`CrmEventBridge` — every welcome run emits one durable row via
  the existing ``crm_welcome_runs`` trigger (migration 153, mig 144 +
  146 outbox pattern); the bridge wraps the INSERT call so the cell
  records both the audit row AND a cell-level pulse.

The full :class:`CrmCellRunner` is intentionally NOT a separate daemon:
crm-cell is ``runtime: fastapi-inproc`` (cell.yaml Q1 decision). The
runner methods are called from inside the existing FastAPI services
(``welcome_practice_service``, ``crm_automation_engine``,
``drive_poll_service``) — no new process is spawned.
"""
from __future__ import annotations

CELL_NAME = "crm-cell"
CELL_VERSION = "0.1.0"

__all__ = [
    "CELL_NAME",
    "CELL_VERSION",
]
