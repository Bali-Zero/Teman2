"""
AlertDispatcher — routes compliance alerts to team + client channels (decision #11).

Team channels (code-gated, unconditional):
  critical → [telegram_owner, inapp_team]
  urgent   → [telegram_team, inapp_team]
  warning  → [inapp_team]
  info     → [inapp_team]

Client channels (notification_prefs m110, severity >= warning only):
  email_client  — gated by prefs.email_enabled (default TRUE)
  wa_client     — gated by prefs.wa_enabled    (default FALSE)

Dedup via notification_log m111: ref = f"compliance_alert:{alert_id}:{channel}".
24h rolling window enforced via timestamp filter.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import asyncpg

from backend.services.compliance.alert_repository import AlertRow

logger = logging.getLogger(__name__)


# Constant UUID for team-only notification rows (where there's no portal user).
SYSTEM_TEAM_UUID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")

_TEAM_CHANNELS_BY_SEVERITY: dict[str, list[str]] = {
    "critical": ["telegram_owner", "inapp_team"],
    "urgent":   ["telegram_team",  "inapp_team"],
    "warning":  ["inapp_team"],
    "info":     ["inapp_team"],
}

_CLIENT_SEVERITIES = {"warning", "urgent", "critical"}


@dataclass
class _Prefs:
    email_enabled: bool
    wa_enabled: bool


class AlertDispatcher:
    """
    Fan-out compliance alerts to configured channels.

    Channel services have narrow async APIs:
      email_service.send(from_: str, to: str, subject: str, body: str) → dict
      telegram_service.send_message(chat: str | int, text: str) → dict
      inapp_service.emit(user_id: str, payload: dict) → None
      wa_service.send(to: str, body: str) → dict
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool | None,
        *,
        email_service: Any,
        telegram_service: Any,
        inapp_service: Any,
        wa_service: Any,
        connection: asyncpg.Connection | None = None,
        _resolve_portal_user_id: Callable[[int], str | None] | None = None,
    ) -> None:
        self._pool = db_pool
        self._conn = connection
        self._email = email_service
        self._telegram = telegram_service
        self._inapp = inapp_service
        self._wa = wa_service
        self._resolve_portal_user = _resolve_portal_user_id

    @classmethod
    def with_connection(
        cls,
        conn: asyncpg.Connection,
        **svc: Any,
    ) -> "AlertDispatcher":
        """Bind the dispatcher to a single pre-acquired connection (tests / TXN scope)."""
        return cls(db_pool=None, connection=conn, **svc)

    # ── Public ──────────────────────────────────────────────────────────────────

    async def dispatch(self, alert: AlertRow) -> None:
        """Fan-out to team + client channels, respecting notification_prefs
        and deduping via notification_log."""
        team_channels = _TEAM_CHANNELS_BY_SEVERITY.get(alert.severity)
        if team_channels is None:
            logger.warning(
                "unrecognized severity %r for alert %s; no team channels will fire",
                alert.severity, alert.alert_id,
            )
            team_channels = []
        client_channels: list[str] = []

        portal_user_id = await self._lookup_portal_user_id(alert.client_id)
        if portal_user_id and alert.severity in _CLIENT_SEVERITIES:
            prefs = await self._load_prefs(portal_user_id)
            if prefs.email_enabled:
                client_channels.append("email_client")
            if prefs.wa_enabled:
                client_channels.append("wa_client")

        any_success = False
        for channel in team_channels + client_channels:
            ref = f"compliance_alert:{alert.alert_id}:{channel}"
            user_id = portal_user_id or str(SYSTEM_TEAM_UUID)

            if await self._already_sent(user_id, channel, ref):
                logger.debug("dedup: skipping %s (already sent within 24h)", ref)
                continue

            try:
                await self._send_one(channel, alert, portal_user_id)
            except Exception as exc:  # noqa: BLE001  -- per-channel isolation (decision #11)
                logger.warning(
                    "channel %s failed for alert %s: %s",
                    channel, alert.alert_id, exc,
                )
                continue

            # Send succeeded — record delivery. Log failure is LOUD but does not
            # retract the send.
            try:
                await self._log_sent(user_id, channel, ref)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "notification_log insert failed for %s (send already completed): %s",
                    ref, exc,
                )
            any_success = True

        if not any_success:
            logger.warning("no channel succeeded for alert %s", alert.alert_id)

    # ── Channel senders ─────────────────────────────────────────────────────────

    async def _send_one(
        self,
        channel: str,
        alert: AlertRow,
        portal_user_id: str | None,
    ) -> None:
        if channel == "telegram_owner":
            await self._telegram.send_message(
                chat="owner",
                text=self._telegram_text(alert),
            )
        elif channel == "telegram_team":
            await self._telegram.send_message(
                chat="team",
                text=self._telegram_text(alert),
            )
        elif channel == "inapp_team":
            await self._inapp.emit(
                user_id=portal_user_id or str(SYSTEM_TEAM_UUID),
                payload={
                    "type": "compliance_alert",
                    "alert_id": alert.alert_id,
                    "severity": alert.severity,
                    "category": alert.category,
                },
            )
        elif channel == "email_client":
            subject = f"[Bali Zero] {alert.category.replace('_', ' ').title()}"
            await self._email.send(
                from_="zantara@balizero.com",
                to=await self._lookup_client_email(alert.client_id),
                subject=subject,
                body=alert.message_en or alert.message_it or "",
            )
        elif channel == "wa_client":
            await self._wa.send(
                to=await self._lookup_client_wa(alert.client_id),
                body=alert.message_en or alert.message_it or "",
            )
        else:
            raise ValueError(f"unknown channel: {channel}")

    def _telegram_text(self, alert: AlertRow) -> str:
        return (
            f"\U0001f514 {alert.severity.upper()} \u00b7 {alert.category} \u00b7 "
            f"client={alert.client_id} \u00b7 due {alert.deadline.isoformat()}"
        )

    # ── DB helpers ───────────────────────────────────────────────────────────────

    async def _conn_execute(self, fn: str, query: str, *args: Any) -> Any:
        if self._conn is not None:
            return await getattr(self._conn, fn)(query, *args)
        async with self._pool.acquire() as c:
            return await getattr(c, fn)(query, *args)

    async def _lookup_portal_user_id(self, client_id: int) -> str | None:
        """Return portal_user_id for the client, or None if not found / column absent.

        Uses a savepoint when operating inside a transaction so that an
        UndefinedColumnError (column missing in this schema version) does not
        poison the outer transaction.
        """
        if self._resolve_portal_user is not None:
            return self._resolve_portal_user(client_id)

        # When bound to a single connection (tests / TXN scope), protect the
        # outer transaction via a savepoint so a column-missing error doesn't
        # abort it.
        if self._conn is not None:
            try:
                async with self._conn.transaction():  # savepoint — isolation inherited from outer TX
                    return await self._conn.fetchval(
                        "SELECT portal_user_id::text FROM clients WHERE id = $1",
                        client_id,
                    )
            except asyncpg.UndefinedColumnError:
                logger.info(
                    "clients.portal_user_id column not present; skipping client "
                    "channels for client_id=%s",
                    client_id,
                )
                return None

        # Pool path — each acquire is its own connection / transaction scope.
        try:
            async with self._pool.acquire() as c:
                return await c.fetchval(
                    "SELECT portal_user_id::text FROM clients WHERE id = $1",
                    client_id,
                )
        except asyncpg.UndefinedColumnError:
            logger.info(
                "clients.portal_user_id column not present; skipping client "
                "channels for client_id=%s",
                client_id,
            )
            return None

    async def _lookup_client_email(self, client_id: int) -> str:
        email = await self._conn_execute(
            "fetchval",
            "SELECT email FROM clients WHERE id = $1",
            client_id,
        )
        return email or "unknown@balizero.com"

    async def _lookup_client_wa(self, client_id: int) -> str:
        phone = await self._conn_execute(
            "fetchval",
            "SELECT phone FROM clients WHERE id = $1",
            client_id,
        )
        return phone or ""

    async def _load_prefs(self, portal_user_id: str) -> _Prefs:
        row = await self._conn_execute(
            "fetchrow",
            "SELECT email_enabled, wa_enabled FROM notification_prefs "
            "WHERE user_id = $1::uuid",
            portal_user_id,
        )
        if row is None:
            return _Prefs(email_enabled=True, wa_enabled=False)  # defaults per spec
        return _Prefs(email_enabled=row["email_enabled"], wa_enabled=row["wa_enabled"])

    async def _already_sent(self, user_id: str, channel: str, ref: str) -> bool:
        """Return True if a notification_log row matches (user_id, channel, ref)
        within the last 24 hours."""
        sent_at = await self._conn_execute(
            "fetchval",
            """
            SELECT sent_at FROM notification_log
             WHERE user_id = $1::uuid
               AND channel = $2
               AND ref     = $3
               AND sent_at > NOW() - INTERVAL '24 hours'
             ORDER BY sent_at DESC
             LIMIT 1
            """,
            user_id,
            channel,
            ref,
        )
        return sent_at is not None

    async def _log_sent(self, user_id: str, channel: str, ref: str) -> None:
        await self._conn_execute(
            "execute",
            "INSERT INTO notification_log (user_id, channel, ref) "
            "VALUES ($1::uuid, $2, $3)",
            user_id,
            channel,
            ref,
        )


__all__ = ["AlertDispatcher", "SYSTEM_TEAM_UUID"]
