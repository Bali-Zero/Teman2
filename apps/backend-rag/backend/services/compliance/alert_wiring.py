"""
Alert Wiring — production adapters connecting AlertsEngine/AlertDispatcher's
abstract service interfaces to the REAL concrete services this codebase
already ships (TelegramBotService, WhatsAppService, PricingService, the
internal Brevo-backed email endpoint).

Why this file exists (2026-07-17 arming)
-----------------------------------------
AlertsEngine (`alerts_engine.py`) and AlertDispatcher (`alert_dispatcher.py`)
were built with abstract ``Any``-typed constructor params and a *documented*
interface contract:

  - ``alert_dispatcher.py`` docstring: ``telegram_service.send_message(chat, text)``
  - ``alerts_engine.py``    docstring: ``PricingTool.get_price`` (lookup-based)

...but nothing in the app ever constructed either class in production
(0 callers — confirmed by grepping ``AlertDispatcher(``/``AlertsEngine(``
outside tests). The concrete services that already exist do NOT match those
documented contracts verbatim:

  - ``TelegramBotService.send_message(chat_id, text, ...)`` takes a real
    numeric/string ``chat_id`` — never the literal aliases ``"owner"``/
    ``"team"`` AlertDispatcher passes, AND the parameter is named
    ``chat_id``, not ``chat`` (a plain ``send_message(chat="owner", ...)``
    call against the real service raises ``TypeError`` on the parameter
    name alone, before the alias problem even matters).
  - ``PricingService`` exposes ``get_pricing("all") -> dict``, not a
    ``get_price(key) -> int | None`` lookup.

So the wiring was never a one-line ``AlertDispatcher(..., telegram_service=
telegram_bot)`` — it needed these adapters first. This module is that
missing piece. ``alert_dispatcher.py``/``alerts_engine.py`` themselves are
deliberately left untouched (their own unit tests assert the ``chat="owner"``
call shape verbatim — see ``tests/services/compliance/test_alert_dispatcher.py
::test_critical_alert_hits_telegram_owner``), so the fix lives entirely on
the "real service" side of the boundary.

``inapp_service`` has no real backing anywhere in the codebase today —
``PortalNotificationService`` is client-facing only (tied to document/
practice/profile change events, backed by the ``portal_messages`` table —
a different shape entirely). ``LoggingInAppAdapter`` is an honest stand-in:
it logs the alert (so it is at least observable) and then RAISES
``InAppChannelUnavailableError`` so ``AlertDispatcher`` records a channel
FAILURE — never a delivery that did not happen. ``notification_log`` is the
delivery audit trail of a compliance organ; a "sent" row with no real
delivery would be a false truth in an audit table (superscar family #2:
green ≠ working). The alert data itself is never lost regardless of what
this channel does — AlertsEngine persists every alert to
``compliance_alerts`` (m114) *before* dispatch is even attempted.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg

from backend.services.compliance.alert_dispatcher import AlertDispatcher
from backend.services.compliance.alerts_engine import AlertsEngine
from backend.services.compliance.revenue_estimator import estimate_renewal_revenue
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.integrations.whatsapp_service import whatsapp_service
from backend.services.notifications.email_http import get_email_client
from backend.services.pricing.pricing_service import PricingService

logger = logging.getLogger(__name__)

# Owner chat is the one real, already-provisioned destination (GitHub Secret
# + Fly secret per CLAUDE.md §13 — Zero's chat with @Balizerobot).
_TELEGRAM_OWNER_ENV = "TELEGRAM_OWNER_CHAT_ID"
# Team chat has no dedicated destination configured anywhere in this codebase
# today (grepped clean — no TELEGRAM_TEAM_CHAT_ID anywhere in prod code, CI
# secrets, or docs). The env var is read defensively so a future dedicated
# team chat "just works" the day ops configures it; until then, "team"
# alerts fall back to the owner chat rather than being silently dropped.
_TELEGRAM_TEAM_ENV = "TELEGRAM_TEAM_CHAT_ID"

# Same internal-Brevo-endpoint pattern already used by
# ``auth.py::_send_magic_link_email`` and
# ``lkpm_deadline_notifier.py::_post_email`` — reused verbatim, not reinvented.
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY_ENV = "NUZANTARA_API_KEY"


class TelegramAliasAdapter:
    """Adapts a ``TelegramBotService``-shaped client
    (``send_message(chat_id, text, ...)``) to the
    ``send_message(chat: str | int, text: str)`` interface AlertDispatcher's
    docstring documents, resolving the ``"owner"``/``"team"`` channel
    aliases to real numeric Telegram chat IDs read from env at call time
    (never cached at import/construction time, so tests can monkeypatch
    per-case and a live secret rotation takes effect on next call).

    Anything that isn't exactly ``"owner"``/``"team"`` is passed through
    unchanged (forward-compatible with a future direct-numeric chat id).
    """

    def __init__(self, bot: Any | None = None) -> None:
        self._bot = bot if bot is not None else telegram_bot
        self._warned_team_fallback = False

    def _resolve(self, chat: str | int) -> str | int:
        if chat == "owner":
            raw = os.environ.get(_TELEGRAM_OWNER_ENV)
            if not raw:
                raise ValueError(
                    f"{_TELEGRAM_OWNER_ENV} not configured; cannot resolve "
                    "'owner' Telegram chat alias"
                )
            return raw
        if chat == "team":
            raw = os.environ.get(_TELEGRAM_TEAM_ENV)
            if raw:
                return raw
            fallback = os.environ.get(_TELEGRAM_OWNER_ENV)
            if not fallback:
                raise ValueError(
                    f"neither {_TELEGRAM_TEAM_ENV} nor {_TELEGRAM_OWNER_ENV} "
                    "configured; cannot resolve 'team' Telegram chat alias"
                )
            if not self._warned_team_fallback:
                logger.warning(
                    "%s not configured; routing 'telegram_team' compliance "
                    "alerts to the owner chat instead",
                    _TELEGRAM_TEAM_ENV,
                )
                self._warned_team_fallback = True
            return fallback
        return chat  # already a literal chat id — pass through

    async def send_message(self, chat: str | int, text: str) -> Any:
        resolved = self._resolve(chat)
        return await self._bot.send_message(chat_id=resolved, text=text)


class _KeyOnlyRule:
    """Minimal shim satisfying the 2 attributes `estimate_renewal_revenue`
    reads off a `RenewalRule` (`renewal_pricing_key`, `rule_id` for logging),
    without needing a full RenewalRule (which carries visa-pattern-matching
    fields irrelevant to a bare key lookup)."""

    __slots__ = ("renewal_pricing_key", "rule_id")

    def __init__(self, renewal_pricing_key: str) -> None:
        self.renewal_pricing_key = renewal_pricing_key
        self.rule_id = f"adhoc:{renewal_pricing_key}"


class PricingToolAdapter:
    """Adapts ``PricingService.get_pricing("all")`` to the
    ``.get_price(key) -> int | None`` contract ``AlertsEngine`` expects.

    Reuses the SAME nested-dict scan ``PredictiveComplianceEngine`` already
    uses for ``estimated_revenue_idr`` (``revenue_estimator.
    estimate_renewal_revenue``) — no new pricing-lookup logic invented here
    (Golden Rule #11: prices ONLY from PricingTool, never hardcoded).
    """

    def __init__(self, pricing_service: PricingService) -> None:
        self._pricing_service = pricing_service

    def get_price(self, key: str | None) -> int | None:
        if not key:
            return None
        all_prices = self._pricing_service.get_pricing("all")
        return estimate_renewal_revenue(_KeyOnlyRule(key), all_prices)


class HttpEmailServiceAdapter:
    """``.send(from_, to, subject, body)`` over the internal Brevo-backed
    endpoint — same ``INTERNAL_EMAIL_API_URL``/``NUZANTARA_API_KEY`` pattern
    already used by ``auth.py::_send_magic_link_email`` and
    ``lkpm_deadline_notifier.py::_post_email``. Uses the shared persistent
    httpx client (``email_http.get_email_client``) per Golden Rule #10."""

    async def send(self, *, from_: str, to: str, subject: str, body: str) -> dict[str, Any]:
        api_key = os.environ.get(_EMAIL_API_KEY_ENV, "")
        client = await get_email_client()
        response = await client.post(
            _EMAIL_API_URL,
            json={"to": to, "subject": subject, "body": body, "from": from_},
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


class WhatsAppServiceAdapter:
    """``.send(to, body)`` over the existing, fully-built
    ``WhatsAppService.send_message(phone, text)`` (Meta WhatsApp Business
    Cloud API) — parameter-name adaptation only, no new transport."""

    def __init__(self, wa: Any | None = None) -> None:
        self._wa = wa if wa is not None else whatsapp_service

    async def send(self, to: str, body: str) -> dict[str, Any]:
        return await self._wa.send_message(phone=to, text=body)


class InAppChannelUnavailableError(RuntimeError):
    """Raised by ``LoggingInAppAdapter.emit()`` after logging — BY DESIGN.

    No real team in-app notification center exists anywhere in this codebase
    yet, so the ``inapp_team`` channel must NOT be recorded as delivered in
    ``notification_log`` — that table is the delivery audit trail of the
    compliance organ, and its whole purpose is proving deadlines were
    actually notified. A "sent" row backed by nothing but a log line would
    be a false truth in an audit table (superscar family #2: green ≠
    working) that accumulates silently once the kill switch is flipped on.

    ``AlertDispatcher.dispatch()`` catches per-channel exceptions (warning +
    continue) and skips ``_log_sent`` for the failed channel — exactly the
    honest outcome: observable log line, no phantom audit row, all other
    channels unaffected. The resulting warning noise ("channel inapp_team
    failed", at most once per alert per 24h dedup window) is accepted until
    a real channel exists.
    """


class LoggingInAppAdapter:
    """Stand-in for a real team in-app/notification-center channel, which
    does not exist yet anywhere in this codebase (``PortalNotificationService``
    is client-facing only — a different shape, tied to ``portal_messages``).

    Logs the alert with full structured context (observability preserved),
    then ALWAYS raises ``InAppChannelUnavailableError`` so the dispatcher
    records a channel failure instead of a phantom delivery in
    ``notification_log`` (see the exception's docstring for the full
    rationale). The alert itself is never lost regardless — AlertsEngine
    persists it to ``compliance_alerts`` before dispatch is attempted, so the
    team can always see it via the CRM/DB directly. Building a real team
    notification center is future work, tracked separately from this PR.
    """

    async def emit(self, *, user_id: str, payload: dict[str, Any]) -> None:
        logger.info("compliance alert (in-app, team) user=%s payload=%s", user_id, payload)
        raise InAppChannelUnavailableError(
            "no real team in-app notification channel exists; refusing to report "
            "a phantom delivery (alert logged above and already persisted in "
            "compliance_alerts)"
        )


def build_alerts_engine(
    db_pool: asyncpg.Pool,
    *,
    pricing_service: PricingService,
) -> AlertsEngine:
    """Construct a fully-wired, production-real AlertsEngine.

    ``pricing_service`` is accepted (not looked up internally) so callers
    that already loaded one for the same request (e.g.
    ``cron_notifiers.run_compliance_forecast``) don't pay for a second
    lookup — ``get_pricing_service()`` is a cached singleton either way, so
    this is a minor efficiency, not a correctness requirement.
    """
    dispatcher = AlertDispatcher(
        db_pool,
        email_service=HttpEmailServiceAdapter(),
        telegram_service=TelegramAliasAdapter(),
        inapp_service=LoggingInAppAdapter(),
        wa_service=WhatsAppServiceAdapter(),
    )
    pricing_adapter = PricingToolAdapter(pricing_service)
    return AlertsEngine(db_pool, pricing=pricing_adapter, dispatcher=dispatcher)


__all__ = [
    "HttpEmailServiceAdapter",
    "InAppChannelUnavailableError",
    "LoggingInAppAdapter",
    "PricingToolAdapter",
    "TelegramAliasAdapter",
    "WhatsAppServiceAdapter",
    "build_alerts_engine",
]
