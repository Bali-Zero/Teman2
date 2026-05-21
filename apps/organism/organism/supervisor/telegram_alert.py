"""Telegram alerter — best-effort `on_dispatched` callback for Dispatcher.

Builds a callable that the daemon passes to `Dispatcher(on_dispatched=...)`.
The callback formats one short Telegram message per DISPATCHED outcome and
delegates to the `notify_telegram` actuator already in the registry, so we
reuse its httpx client + bot credentials without duplicating env-var logic.

Best-effort by design: any exception from NotifyTelegram is logged and
swallowed. The dispatcher already wraps the callback in its own try/except,
this layer adds a second guard so a failing telegram API call cannot lock
out the supervise loop.

Self-recursion guard: when the dispatched actuator is itself
`notify_telegram` we do NOT alert — that would loop on every alert sent.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Mapping

from organism.schemas import ActionDecision


log = logging.getLogger(__name__)


_MAX_TELEGRAM_BODY = 3500  # Telegram caps at 4096 chars; leave headroom


def _telegram_alerts_enabled() -> bool:
    """Autonomic-mode gate (2026-05-22).

    The Cell/Organism/Genoma triad operates in closed-loop by default:
    Cell detects incident → publishes event → Organism dispatches recovery
    actuator (restart, scale, cleanup, propose_yaml_rule). Telegram-to-Zero
    is opt-in via ORGANISM_TELEGRAM_DISPATCH_ALERTS=true.

    This module remains importable and tested; only the side-effect (sending
    Telegram) is gated. Future re-enable: flip env var, no code change.
    """
    return os.environ.get("ORGANISM_TELEGRAM_DISPATCH_ALERTS", "").lower() == "true"


def _format_message(
    *,
    decision: ActionDecision,
    target: str,
    correlation_id: str,
    result: Mapping[str, Any],
) -> str:
    success = bool(result.get("success", False))
    icon = "✅" if success else "❌"
    header = f"{icon} Supervisor W2 dispatch — {decision.actuator}"
    lines = [
        header,
        f"target: {target}",
        f"corr:   {correlation_id[:32]}",
        f"tier:   {decision.tier} (conf={decision.confidence:.2f})",
        f"status: {'success' if success else 'FAILED'}",
    ]
    if not success:
        err = str(result.get("error", "(no error message)"))
        lines.append(f"error:  {err[:300]}")
    body = "\n".join(lines)
    return body[:_MAX_TELEGRAM_BODY]


def build_dispatch_alerter(
    actuator_registry: Mapping[str, Any],
) -> Callable[..., Awaitable[None]]:
    """Return an async on_dispatched callback bound to the registry.

    The returned callable matches Dispatcher's contract:
        async def(*, decision, target, correlation_id, result) -> None
    """
    notifier = actuator_registry.get("notify_telegram")

    async def on_dispatched(
        *,
        decision: ActionDecision,
        target: str,
        correlation_id: str,
        result: Mapping[str, Any],
    ) -> None:
        if decision.actuator == "notify_telegram":
            # Avoid feedback loop: NotifyTelegram dispatched → don't alert about it.
            return
        if not _telegram_alerts_enabled():
            # Autonomic mode (default 2026-05-22): no human-in-the-loop.
            # Dispatch outcomes are logged to PG events_outbox + organism
            # internal tables. The Reflexion loop reviews them weekly.
            log.debug(
                "telegram_alert: autonomic-mode skip "
                "(ORGANISM_TELEGRAM_DISPATCH_ALERTS not true) "
                "actuator=%s target=%s corr=%s success=%s",
                decision.actuator,
                target,
                correlation_id[:32],
                bool(result.get("success", False)),
            )
            return
        if notifier is None:
            log.debug(
                "telegram_alert: notify_telegram missing from registry — skip",
            )
            return
        try:
            await notifier.run(
                params={
                    "message": _format_message(
                        decision=decision,
                        target=target,
                        correlation_id=correlation_id,
                        result=result,
                    ),
                },
                correlation_id=correlation_id,
                dry_run=False,
            )
        except Exception:
            log.exception("telegram_alert: notifier.run raised (non-fatal)")

    return on_dispatched
