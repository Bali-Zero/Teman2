"""Federation Alert Dispatcher (FAD).

Standalone daemon that turns Telegram alerts into proposed remediation
actions through multi-LLM consensus + sandbox-tested patches + Telegram
approval gate.

Spec: docs/superpowers/specs/2026-04-30-federation-alert-dispatcher.md

This package is the SOURCE-CONTROLLED implementation. The actual daemon
runs as a LaunchAgent on Pro (see infra/launchd/ in PR #2).

Layout (when complete):
    models.py       — Pydantic types for proposals, payloads, modes
    repository.py   — async asyncpg CRUD against federation_alert_proposals
    daemon.py       — main loop (LISTEN federation_alert, mode SM)
    dispatcher.py   — subprocess wrapper around scripts/ai-dispatch.sh
    config.py       — env + DB-backed mode flag
    actions/        — whitelist V1 (cleanup_log, ack_outbox_event,
                       quarantine_alert, prune_consumed_outbox)
    providers/      — Telegram, PostgreSQL, LocalShell abstractions
    approval.py     — fad:* callback token + HMAC verify

PR #1 (this) ships only models + repository + EventBus channel registration.
"""
from __future__ import annotations

__all__: list[str] = [
    "FederationAlertMode",
    "ProposalStatus",
    "AlertSeverity",
    "RiskLevel",
    "RequestedAction",
    "ProposalRow",
    "AlertInput",
    "FederationAlertRepo",
]

from backend.services.federation_alerts.models import (
    AlertInput,
    AlertSeverity,
    FederationAlertMode,
    ProposalRow,
    ProposalStatus,
    RequestedAction,
    RiskLevel,
)
from backend.services.federation_alerts.repository import FederationAlertRepo
