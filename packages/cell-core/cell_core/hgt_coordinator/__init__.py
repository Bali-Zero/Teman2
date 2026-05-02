"""HGT Coordinator — propose-only cross-cell skill transfer layer.

Sits ON TOP of ``cell_core.hgt`` (publisher/consumer/feedback). The
in-cell-core HGT layer is **automatic**: when a cell's skill reaches
confidence>=0.7 + scope=Project, it is broadcast on Redis Stream
``cell:skills`` and sibling cells in matching domains integrate it with a
0.9× decay. That layer is autonomous by design.

The coordinator is a **second layer** that observes the same stream over a
window (default 7d), aggregates per-skill statistics across cells, and
PROPOSES new transfers when a high-confidence pattern emerges. Proposals
land in a SQLite audit log for **human review only** — no auto-merge.

Threshold (per 4-LLM brainstorm round 2 § "Q3 disagreement DeepSeek vs
Codex/Gemini"): ≥10 uses + average confidence > 0.7. Codex/Gemini argued
≥10+0.7; DeepSeek pushed for ≥5+0.6 (more proposals, less signal). Final
pick: ≥10+0.7 — Sprint 1 W2 prioritises signal over volume.

Quarantine guarantees:
    1. NO direct merge to consumer cells (the existing automatic HGT
       consumer keeps its own ≥0.7 + matching-domain gate; this layer only
       writes to SQLite).
    2. The audit log is the source of truth — operators resolve proposals
       manually via ``mark_resolved``.
    3. Recovery: if the OpenClaw agent (Kimi K2.6) misbehaves, set
       ``agents.list[*].id == hgt-coordinator`` to ``"sandbox": {"mode":
       "off-disabled"}`` in ``~/.openclaw/openclaw.json`` (or remove the
       entry entirely) and the propose-only python coordinator continues
       to populate the audit log without LLM reasoning. The audit log is
       canonical; the LLM ranking is decorative.

Out of scope:
    - Auto-merge — explicit cicatrix-pattern (NO automation closes the
      loop). Human review is the final instance.
    - Bypass of the existing HGT consumer's domain filter — coordinator
      proposes target cells already in the same domain.
    - PostgreSQL — audit log is SQLite-local per ADR doctrine
      "JSONL canonical / SQLite per-machine".
"""
from __future__ import annotations

from cell_core.hgt_coordinator.audit_log import (
    DEFAULT_AUDIT_LOG_PATH,
    audit_log_path,
    init_db,
    list_pending,
    mark_resolved,
    record_proposal,
)
from cell_core.hgt_coordinator.coordinator import HGTCoordinator
from cell_core.hgt_coordinator.proposal import Proposal

__all__ = [
    "DEFAULT_AUDIT_LOG_PATH",
    "HGTCoordinator",
    "Proposal",
    "audit_log_path",
    "init_db",
    "list_pending",
    "mark_resolved",
    "record_proposal",
]
