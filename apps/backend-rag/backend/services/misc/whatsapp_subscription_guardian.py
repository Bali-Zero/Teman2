"""WhatsApp WABA webhook-subscription guardian.

Born 2026-07-14 after the channel went DEAF for 8 days (2026-07-05 → 07-13):
the WABA webhook subscription silently dropped Meta-side, every green health
check kept lying (our webhook endpoint answered, Meta just stopped calling it),
and inbound customer messages were lost until a manual
``POST /{WABA_ID}/subscribed_apps`` re-armed it.

Design constraints learned from that incident:

- The subscription state is NOT READABLE with our token: ``GET subscribed_apps``
  fails with Meta "unknown error code=1" (missing ``whatsapp_business_management``
  read permission). The POST, however, works and is idempotent.
  → The guardian does not probe-then-fix; it **re-arms unconditionally** every
  cycle. Healing by construction, not by detection (scar family #2).
- Belt + braces: a **deafness receptor** compares the newest whatsapp row in
  ``inbound_webhooks`` against a threshold. It cannot distinguish a quiet
  business day from a broken webhook, so it only WARNS (the re-arm above is
  the actual cure) and de-duplicates its own alerts.

Runs inside the AutonomousScheduler (Redis leader lock across api/rag workers,
6h interval, first run within ~1 minute of boot). Manual one-shot for prod
verification:

    PYTHONPATH=. python -m backend.services.misc.whatsapp_subscription_guardian --once
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"
REARM_ATTEMPTS = 3
REARM_BACKOFF_SECONDS = 5.0
DEFAULT_DEAFNESS_ALERT_HOURS = 72
# While deaf, re-alert at most once per this window (the 6h cycle would
# otherwise spam one warning per tick for the whole quiet period).
DEAFNESS_REALERT_HOURS = 24

_DEAFNESS_SQL = """
SELECT max(received_at) AS last_inbound
  FROM inbound_webhooks
 WHERE channel = 'whatsapp'
"""


class WhatsAppSubscriptionGuardian:
    """Re-arms the WABA webhook subscription and watches for inbound silence."""

    def __init__(
        self,
        db_pool: Any = None,
        alert_service: Any = None,
        waba_id: str | None = None,
        access_token: str | None = None,
        deafness_alert_hours: float | None = None,
    ) -> None:
        self.db_pool = db_pool
        self.alert_service = alert_service
        self.waba_id = waba_id or os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID")
        self.access_token = access_token or os.environ.get("WHATSAPP_ACCESS_TOKEN")
        self.deafness_alert_hours = (
            deafness_alert_hours
            if deafness_alert_hours is not None
            else float(os.environ.get("WA_DEAFNESS_ALERT_HOURS", DEFAULT_DEAFNESS_ALERT_HOURS))
        )
        self._client: httpx.AsyncClient | None = None
        self._last_deafness_alert: datetime | None = None
        self._config_alert_sent = False

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def rearm(self) -> dict[str, Any]:
        """Idempotently re-subscribe the app to the WABA webhook.

        Returns ``{"ok": bool, "attempts": int, "detail": str}``. Never raises:
        the scheduler loop must survive Meta outages (scar family #8).
        """
        if not self.waba_id or not self.access_token:
            return {"ok": False, "attempts": 0, "detail": "config_missing"}

        url = f"{GRAPH_BASE}/{self.waba_id}/subscribed_apps"
        last_detail = "unknown"
        for attempt in range(1, REARM_ATTEMPTS + 1):
            try:
                resp = await self._get_client().post(
                    url,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )
                body: dict[str, Any] = {}
                try:
                    body = resp.json()
                except json.JSONDecodeError:
                    pass
                if resp.status_code == 200 and body.get("success") is True:
                    logger.info(
                        "[wa-sub-guardian] subscription re-armed (attempt %d)", attempt
                    )
                    return {"ok": True, "attempts": attempt, "detail": "success"}
                # Non-200 or success!=true: token/permission problem, not transient.
                err = body.get("error", {})
                last_detail = (
                    f"http={resp.status_code} code={err.get('code')} "
                    f"type={err.get('type')} msg={str(err.get('message', ''))[:120]}"
                )
                logger.error("[wa-sub-guardian] rearm rejected: %s", last_detail)
                break
            except httpx.HTTPError as e:
                last_detail = f"network: {type(e).__name__}: {e}"
                logger.warning(
                    "[wa-sub-guardian] rearm attempt %d/%d failed: %s",
                    attempt,
                    REARM_ATTEMPTS,
                    last_detail,
                )
                if attempt < REARM_ATTEMPTS:
                    await asyncio.sleep(REARM_BACKOFF_SECONDS * attempt)
        return {"ok": False, "attempts": attempt, "detail": last_detail}

    async def check_deafness(self) -> dict[str, Any]:
        """Warn-only receptor: newest whatsapp inbound vs threshold."""
        if self.db_pool is None:
            return {"deaf": False, "detail": "no_db_pool"}
        try:
            row = await self.db_pool.fetchrow(_DEAFNESS_SQL)
        except Exception as e:  # receptor must never kill the cycle
            logger.warning("[wa-sub-guardian] deafness query failed: %s", e)
            return {"deaf": False, "detail": f"query_failed: {type(e).__name__}"}
        last_inbound = row["last_inbound"] if row else None
        if last_inbound is None:
            return {"deaf": False, "detail": "no_rows"}
        age = datetime.now(tz=timezone.utc) - last_inbound
        deaf = age > timedelta(hours=self.deafness_alert_hours)
        return {
            "deaf": deaf,
            "detail": f"last_inbound={last_inbound.isoformat()} age_hours={age.total_seconds() / 3600:.1f}",
        }

    def _should_alert_deafness(self, now: datetime) -> bool:
        if self._last_deafness_alert is None:
            return True
        return now - self._last_deafness_alert > timedelta(hours=DEAFNESS_REALERT_HOURS)

    async def _alert(self, title: str, message: str, level: str) -> None:
        if self.alert_service is None:
            logger.error("[wa-sub-guardian] ALERT (no alert_service): %s — %s", title, message)
            return
        try:
            from backend.services.monitoring.alert_service import AlertLevel

            await self.alert_service.send_alert(
                title=title,
                message=message,
                level=AlertLevel(level),
                metadata={"source": "whatsapp_subscription_guardian"},
            )
        except Exception as e:  # alerting must never kill the cycle
            logger.error("[wa-sub-guardian] alert delivery failed: %s", e)

    async def run_cycle(self) -> dict[str, Any]:
        """One guardian cycle: unconditional re-arm + deafness receptor."""
        rearm = await self.rearm()
        if not rearm["ok"]:
            if rearm["detail"] == "config_missing":
                # Alert once per process lifetime — a missing WABA/token env is
                # a broken arm, but repeating it every 6h is noise.
                if not self._config_alert_sent:
                    self._config_alert_sent = True
                    await self._alert(
                        "WhatsApp subscription guardian misconfigured",
                        "WHATSAPP_BUSINESS_ACCOUNT_ID / WHATSAPP_ACCESS_TOKEN missing — "
                        "the WABA webhook subscription is NOT being re-armed.",
                        "critical",
                    )
            else:
                await self._alert(
                    "WhatsApp WABA re-subscribe FAILED",
                    f"POST subscribed_apps failed after {rearm['attempts']} attempt(s): "
                    f"{rearm['detail']}. If Meta dropped the subscription, the customer "
                    "channel is deaf until this succeeds.",
                    "critical",
                )

        deafness = await self.check_deafness()
        now = datetime.now(tz=timezone.utc)
        if deafness["deaf"]:
            if self._should_alert_deafness(now):
                self._last_deafness_alert = now
                await self._alert(
                    "WhatsApp inbound silence",
                    f"No whatsapp row in inbound_webhooks for over "
                    f"{self.deafness_alert_hours:.0f}h ({deafness['detail']}). "
                    "Subscription was re-armed this cycle; if silence persists, "
                    "check the Meta app dashboard (token validity, webhook callback).",
                    "warning",
                )
        else:
            self._last_deafness_alert = None

        result = {"rearm": rearm, "deafness": deafness, "ran_at": now.isoformat()}
        logger.info("[wa-sub-guardian] cycle done: %s", json.dumps(result))
        await self._persist_state(result)
        return result

    async def _persist_state(self, result: dict[str, Any]) -> None:
        """Durable receptor (economia-notifiche): Telegram is a best-effort VIEW
        nobody may be reading — the verdict must also live as disk-state. One
        row in ``system_settings`` keyed ``wa_subscription_guardian_last``, so
        any session/monitor can read the last cycle with one SELECT.
        """
        if self.db_pool is None:
            return
        try:
            await self.db_pool.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES ('wa_subscription_guardian_last', $1, now())
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now()
                """,
                json.dumps(result),
            )
        except Exception as e:  # persistence must never kill the cycle
            logger.warning("[wa-sub-guardian] state persist failed: %s", e)


async def _guardian_loop(
    guardian: WhatsAppSubscriptionGuardian, interval_seconds: int
) -> None:
    """Standalone loop for the LIVE init path (the AutonomousScheduler is
    disabled in prod — service_initializer §10, "omnichannel stabilization" —
    so registering there alone would be an unarmed arm, scar W81).

    Leader election reuses the scheduler's own Redis lock key, so if the
    scheduler is ever re-enabled the two paths dedupe instead of double-running.
    """
    from backend.services.misc.autonomous_scheduler import _acquire_task_lock

    await asyncio.sleep(30)  # let the app finish booting
    while True:
        try:
            if await _acquire_task_lock("wa_subscription_guardian", interval_seconds):
                await guardian.run_cycle()
            else:
                logger.debug("[wa-sub-guardian] another worker holds the lock")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the loop must survive anything
            logger.error("[wa-sub-guardian] cycle crashed: %s", e)
        await asyncio.sleep(interval_seconds)


def start_whatsapp_subscription_guardian_task(
    db_pool: Any = None,
    alert_service: Any = None,
    interval_seconds: int = 21600,
) -> asyncio.Task | None:
    """Spawn the guardian loop on the running event loop (kill-switch aware)."""
    if os.environ.get("WA_SUBSCRIPTION_GUARDIAN_ENABLED", "true").lower() in {
        "false",
        "0",
        "no",
    }:
        logger.info("[wa-sub-guardian] disabled via WA_SUBSCRIPTION_GUARDIAN_ENABLED")
        return None
    guardian = WhatsAppSubscriptionGuardian(db_pool=db_pool, alert_service=alert_service)
    task = asyncio.get_event_loop().create_task(
        _guardian_loop(guardian, interval_seconds), name="wa_subscription_guardian"
    )
    logger.info(
        "✅ WhatsApp subscription guardian loop started (%dh interval)",
        interval_seconds // 3600,
    )
    return task


def register_whatsapp_subscription_guardian(
    scheduler: Any,
    db_pool: Any = None,
    alert_service: Any = None,
    interval_seconds: int = 21600,
) -> WhatsAppSubscriptionGuardian | None:
    """Register the guardian on the AutonomousScheduler (kill-switch aware)."""
    if os.environ.get("WA_SUBSCRIPTION_GUARDIAN_ENABLED", "true").lower() in {
        "false",
        "0",
        "no",
    }:
        logger.info("[wa-sub-guardian] disabled via WA_SUBSCRIPTION_GUARDIAN_ENABLED")
        return None

    guardian = WhatsAppSubscriptionGuardian(db_pool=db_pool, alert_service=alert_service)

    async def run_wa_subscription_guardian() -> None:
        await guardian.run_cycle()

    scheduler.register_task(
        name="wa_subscription_guardian",
        task_func=run_wa_subscription_guardian,
        interval_seconds=interval_seconds,
        enabled=True,
    )
    logger.info(
        "✅ WhatsApp subscription guardian registered (%dh interval)",
        interval_seconds // 3600,
    )
    return guardian


async def _main_once(skip_alerts: bool) -> int:
    """CLI one-shot for live verification (fly ssh)."""
    alert_service = None
    if not skip_alerts:
        try:
            from backend.services.monitoring.alert_service import AlertService

            alert_service = AlertService()
        except Exception as e:
            logger.warning("[wa-sub-guardian] AlertService unavailable in CLI: %s", e)

    db_pool = None
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        try:
            import asyncpg

            db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1)
        except Exception as e:
            logger.warning("[wa-sub-guardian] no db pool in CLI: %s", e)

    guardian = WhatsAppSubscriptionGuardian(db_pool=db_pool, alert_service=alert_service)
    try:
        result = await guardian.run_cycle()
    finally:
        await guardian.close()
        if db_pool is not None:
            await db_pool.close()
    # run_cycle already logs the full JSON result; the exit code is the verdict
    # (house pattern: ig_token_watchdog — logger only, stdout stays clean).
    return 0 if result["rearm"]["ok"] else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WhatsApp WABA subscription guardian")
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    parser.add_argument(
        "--skip-alerts", action="store_true", help="do not send Telegram alerts"
    )
    args = parser.parse_args()
    if not args.once:
        parser.error("only --once mode is supported from the CLI")
    raise SystemExit(asyncio.run(_main_once(skip_alerts=args.skip_alerts)))
