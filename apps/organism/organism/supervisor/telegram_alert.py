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
from typing import Any, Awaitable, Callable, Mapping

from organism.schemas import ActionDecision


log = logging.getLogger(__name__)


_MAX_TELEGRAM_BODY = 3500  # Telegram caps at 4096 chars; leave headroom


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
