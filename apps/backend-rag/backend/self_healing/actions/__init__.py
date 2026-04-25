"""
Remediation actions — each targets a specific failure mode surfaced by
one or more checks.

Actions must be idempotent: the orchestrator may invoke them repeatedly
while a breaker is HALF_OPEN probing recovery.
"""

from backend.self_healing.actions.base import ActionResult, RemediationAction
from backend.self_healing.actions.gc import GCAction
from backend.self_healing.actions.reconnect_cache import ReconnectCacheAction
from backend.self_healing.actions.restart_service import RestartServiceAction

__all__ = [
    "ActionResult",
    "GCAction",
    "ReconnectCacheAction",
    "RemediationAction",
    "RestartServiceAction",
]
