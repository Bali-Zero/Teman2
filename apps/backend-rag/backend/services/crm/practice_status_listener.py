"""
Practice Status Listener
========================
Asyncio-based PostgreSQL LISTEN handler for the 'practice_changed' channel.

Fired by the pg_notify trigger in migration_075 whenever:
  - practices.status changes          → M5: status milestone emails
  - practices.payment_status changes  → M4: payment confirmation emails

Design:
  - Uses a *dedicated* asyncpg connection (not from the pool) so LISTEN
    never competes with regular queries.
  - Runs as a background asyncio task; auto-reconnects on dropped connections.
  - Dispatches to ProcessAutomationService for email logic already in place.
"""

import asyncio
import json
import os
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.crm.automation import ProcessAutomationService

logger = get_logger(__name__)

_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")

# Status transitions that warrant a client-facing email.
# Maps new_status → human label used in logs (actual email copy lives in ProcessAutomationService).
_CLIENT_NOTIFY_STATUSES: set[str] = {
    "on_process",    # M4 + M5: payment confirmed, work started
    "submitted",     # M5: docs submitted to authority
    "approved",      # M5: practice approved
    "completed",     # M5: documents delivered
}

_RECONNECT_DELAY_S = 5  # seconds to wait before reconnecting after error


class PracticeStatusListener:
    """
    Manages a persistent asyncpg LISTEN connection and dispatches
    notifications to ProcessAutomationService.
    """

    def __init__(self, db_dsn: str, db_pool: asyncpg.Pool) -> None:
        self._db_dsn = db_dsn
        self._db_pool = db_pool
        self._conn: asyncpg.Connection | None = None
        self._running = False
        self._task: asyncio.Task | None = None
        self._process_svc = ProcessAutomationService(db_pool)

    # ── Public lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background listener task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="practice_status_listener")
        logger.info("✅ PracticeStatusListener started")

    async def stop(self) -> None:
        """Stop the listener and close the dedicated connection."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("practice_status_listener task cancelled during stop() — expected")
        await self._close_conn()
        logger.info("✅ PracticeStatusListener stopped")

    # ── Internal loop ─────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Outer retry loop — re-connects on errors."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                logger.debug("practice_status_listener retry loop cancelled — exiting cleanly")
                break
            except Exception as exc:
                logger.error(f"PracticeStatusListener error, reconnecting in {_RECONNECT_DELAY_S}s: {exc}", exc_info=True)
                await self._close_conn()
                if self._running:
                    await asyncio.sleep(_RECONNECT_DELAY_S)

    async def _connect_and_listen(self) -> None:
        """Open a dedicated connection, LISTEN, and block until cancelled."""
        self._conn = await asyncpg.connect(self._db_dsn)
        await self._conn.add_listener("practice_changed", self._on_notification)
        logger.info("📡 Listening on PostgreSQL channel 'practice_changed'")

        # Keep the connection alive; the callback handles all work.
        while self._running:
            await asyncio.sleep(30)
            # Lightweight ping to detect dropped connections
            try:
                await self._conn.execute("SELECT 1")
            except Exception:
                raise  # triggers reconnect in _run_loop

    async def _close_conn(self) -> None:
        if self._conn and not self._conn.is_closed():
            try:
                await self._conn.remove_listener("practice_changed", self._on_notification)
                await self._conn.close()
            except Exception as exc:
                # UU PDP audit: cleanup failure must be visible so orphaned
                # PG listener connections can be correlated with retries.
                logger.warning(
                    "practice_status_listener.close_failed",
                    extra={"error_type": type(exc).__name__, "error": str(exc)[:120]},
                )
        self._conn = None

    # ── Notification callback ─────────────────────────────────────────────

    def _on_notification(
        self,
        connection: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """
        asyncpg calls this synchronously on the event loop; dispatch async work
        via asyncio.ensure_future so we never block the LISTEN connection.
        """
        asyncio.ensure_future(self._handle_notification(payload))

    async def _handle_notification(self, payload: str) -> None:
        """Parse payload and dispatch to the right handler."""
        try:
            data: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning(f"practice_changed: invalid JSON payload: {payload!r}")
            return

        practice_id: int = data.get("practice_id")
        old_status: str | None = data.get("old_status")
        new_status: str | None = data.get("new_status")
        old_payment: str | None = data.get("old_payment")
        new_payment: str | None = data.get("new_payment")

        logger.info(
            f"practice_changed: practice={practice_id} "
            f"status={old_status}→{new_status} "
            f"payment={old_payment}→{new_payment}",
        )

        # ── M4: payment_status → 'paid' ───────────────────────────────────
        # Asya changes payment_status to 'paid' (and separately moves status
        # to 'on_process'). We fire on the payment transition specifically so
        # the payment-confirmation email is decoupled from the process-start email.
        if old_payment != "paid" and new_payment == "paid":
            await self._on_payment_received(practice_id, data)

        # ── M5: status milestone transitions ─────────────────────────────
        if old_status != new_status and new_status in _CLIENT_NOTIFY_STATUSES:
            await self._on_status_changed(practice_id, new_status, data)

    # ── M4 handler ────────────────────────────────────────────────────────

    async def _on_payment_received(self, practice_id: int, data: dict) -> None:
        """
        M4 — Payment confirmed by Asya.

        Sends:
          1. Client: payment receipt + "we're starting soon"
          2. Team member (assigned_to): payment in, start working
        """
        assigned_to = data.get("assigned_to") or "asya@balizero.com"
        try:
            await self._send_payment_emails(practice_id, triggered_by=assigned_to)
        except (httpx.HTTPError, asyncpg.PostgresError, ValueError) as exc:
            logger.error(f"M4 payment email failed for practice {practice_id}: {exc}", exc_info=True)
        except Exception as exc:  # noqa: BLE001 — EventBus callback must never crash listener loop
            logger.error(
                f"M4 payment email unexpected error for practice {practice_id}: {exc}",
                exc_info=True,
            )

    async def _send_payment_emails(self, practice_id: int, triggered_by: str) -> None:
        """Fetch practice + client data, send payment confirmation emails."""
        practice_data = await self._process_svc._fetch_practice_data(practice_id)
        if not practice_data:
            logger.error(f"M4: practice {practice_id} not found", exc_info=True)
            return

        client_data = await self._process_svc._fetch_client_data(practice_data["client_id"])
        if not client_data:
            logger.error(f"M4: client {practice_data['client_id']} not found")
            return

        practice_type = practice_data.get("practice_type_name", "Immigration Service")
        client_name = client_data["full_name"]
        client_email = client_data.get("email")
        team_member_email = practice_data.get("assigned_to")

        # ── Email 1: Client — payment received ──────────────────────────
        if client_email:
            subject = f"✅ Payment Received — Your {practice_type} is Now in Motion!"
            body = f"""Hi {client_name},

Great news — we've received your payment! 🎉

Your {practice_type} is now officially confirmed and our team is getting ready to start.

What happens next:
• You'll receive a separate email once we officially kick off the process
• You can track your progress anytime at https://my.balizero.com
• Your advisor ({team_member_email or "our team"}) will reach out on WhatsApp shortly

Thank you for your trust — we'll take it from here!

Warmly,
The Bali Zero Team

---
Questions? Reply to this email or reach us on WhatsApp.
"""
            try:
                await self._send_via_internal_api(client_email, subject, body)
                logger.info(f"M4: payment confirmation sent to client {client_email}")
            except httpx.HTTPError as exc:
                logger.error(f"M4: failed to email client {client_email}: {exc}", exc_info=True)
            except Exception as exc:  # noqa: BLE001 — must continue to the team email below
                logger.error(
                    f"M4: unexpected error emailing client {client_email}: {exc}",
                    exc_info=True,
                )

        # ── Email 2: Team member — with Asya in CC ───────────────────────
        if team_member_email:
            subject = f"[PAYMENT IN] ✅ {client_name} — {practice_type} — Proceed Now"
            body = f"""Hi,

Payment has been confirmed for the following practice — you're clear to start!

Client:       {client_name}
Service:      {practice_type}
Practice ID:  #{practice_id}
Amount:       {practice_data.get("quoted_price", "see CRM")}

Next steps:
1. Review documents in CRM: https://kita.balizero.com/process/{practice_id}
2. Contact the client on WhatsApp to introduce yourself
3. Begin application preparation

Asya has verified the payment. Any billing questions → asya@balizero.com

Go!

Zantara CRM 🤖
"""
            try:
                # Use internal /send-email endpoint: handles Zoho/Brevo routing + CC support
                await self._send_via_internal_api(
                    to_email=team_member_email,
                    subject=subject,
                    body=body,
                    cc="asya@balizero.com",
                )
                logger.info(f"M4: team notification sent to {team_member_email} (CC: asya)")
            except httpx.HTTPError as exc:
                logger.error(f"M4: failed to email team member {team_member_email}: {exc}", exc_info=True)
            except Exception as exc:  # noqa: BLE001 — notification failure never blocks the listener
                logger.error(
                    f"M4: unexpected error emailing team member {team_member_email}: {exc}",
                    exc_info=True,
                )

    # ── M5 handler ────────────────────────────────────────────────────────

    async def _on_status_changed(
        self, practice_id: int, new_status: str, data: dict,
    ) -> None:
        """
        M5 — Practice status milestone reached.

        Routes to the correct ProcessAutomationService method based on new_status.
        'on_process' reuses the existing trigger_on_process_start() — no duplication.
        """
        assigned_to = data.get("assigned_to") or "system"
        try:
            if new_status == "on_process":
                # Existing method already handles client + team emails for this milestone
                await self._process_svc.trigger_on_process_start(
                    practice_id=practice_id,
                    triggered_by=assigned_to,
                )
            else:
                # Other milestones: submitted, approved, completed
                await self._send_milestone_email(practice_id, new_status, assigned_to)
        except (httpx.HTTPError, asyncpg.PostgresError, ValueError) as exc:
            logger.error(
                f"M5: status milestone handler failed for practice {practice_id} "
                f"new_status={new_status}: {exc}",
                exc_info=True,
            )
        except Exception as exc:  # noqa: BLE001 — EventBus callback must never crash listener loop
            logger.error(
                f"M5: status milestone handler unexpected error for practice {practice_id} "
                f"new_status={new_status}: {exc}",
                exc_info=True,
            )

    async def _send_milestone_email(
        self, practice_id: int, status: str, triggered_by: str,
    ) -> None:
        """Send client-facing milestone update for submitted/approved/completed."""
        practice_data = await self._process_svc._fetch_practice_data(practice_id)
        if not practice_data:
            return

        client_data = await self._process_svc._fetch_client_data(practice_data["client_id"])
        if not client_data or not client_data.get("email"):
            return

        client_name = client_data["full_name"]
        client_email = client_data["email"]
        practice_type = practice_data.get("practice_type_name", "your application")

        subject, body = _milestone_content(client_name, practice_type, practice_id, status)

        try:
            await self._send_via_internal_api(client_email, subject, body)
            logger.info(f"M5: milestone '{status}' email sent to {client_email} (practice {practice_id})")
        except httpx.HTTPError as exc:
            logger.error(f"M5: milestone email failed for {client_email}: {exc}", exc_info=True)
        except Exception as exc:  # noqa: BLE001 — milestone notification failure never propagates
            logger.error(
                f"M5: milestone email unexpected error for {client_email}: {exc}",
                exc_info=True,
            )

    async def _send_via_internal_api(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> None:
        """
        Send email via the internal /api/notifications/send-email endpoint.

        This endpoint handles Zoho SMTP vs Brevo routing automatically
        (intra-domain @balizero.com → Zoho, external → Brevo) and supports CC/BCC.
        """
        html_body = body.replace("\n", "<br>")
        payload: dict[str, Any] = {
            "to": to_email,
            "subject": subject,
            "body": html_body,
        }
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json=payload,
            )
            response.raise_for_status()


# ── Email copy for status milestones ──────────────────────────────────────────

def _milestone_content(
    client_name: str,
    practice_type: str,
    practice_id: int,
    status: str,
) -> tuple[str, str]:
    """Return (subject, plain-text body) for a given status milestone."""

    portal_url = "https://my.balizero.com"

    if status == "submitted":
        subject = f"📤 Update: Your {practice_type} Has Been Submitted!"
        body = f"""Hi {client_name},

Exciting update — we've officially submitted your {practice_type} application to the relevant authorities! 🎉

What to expect now:
• The government will review your application (timing varies by service type)
• We'll monitor progress daily and follow up proactively
• You'll hear from us the moment there's any news

You can check your case status anytime:
{portal_url}

Hang tight — we're on it!

Warmly,
The Bali Zero Team
"""

    elif status == "approved":
        subject = f"🎉 APPROVED! Your {practice_type} is Ready!"
        body = f"""Hi {client_name},

WE DID IT! 🎊

Your {practice_type} has been APPROVED by the authorities!

Next steps:
• Our team will prepare your documents for delivery
• You'll receive your documents shortly (we'll confirm the handover details separately)
• If applicable, we'll also update your records in our system

View your case: {portal_url}

Thank you for choosing Bali Zero. Congratulations! 🥂

Warmly,
The Bali Zero Team
"""

    elif status == "completed":
        subject = f"✅ Completed: Your {practice_type} Documents Are Ready"
        body = f"""Hi {client_name},

Your {practice_type} process is now fully complete — your documents are ready! ✅

Your advisor will be in touch shortly to arrange the handover.

For your records, you can always access your case history at:
{portal_url}

It's been a pleasure working with you. If you ever need anything else — visas, company setup, tax assistance — we're always here.

Thank you for trusting Bali Zero!

Warmly,
The Bali Zero Team

P.S. We'd love to hear about your experience — feel free to leave us a review! ⭐
"""

    else:
        subject = f"Update on Your {practice_type} (Practice #{practice_id})"
        body = f"""Hi {client_name},

There's been an update on your {practice_type} — status is now: {status}.

Check your portal for details: {portal_url}

The Bali Zero Team
"""

    return subject, body
