"""
Unpaid Invoice Notifier Service.

Detects practices stuck in `sending_invoice` status for 7+ days
(invoice sent but no payment received) and sends a summary reminder
email to Asya (accounting) listing all overdue invoices.
"""

import os
from datetime import date
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Accounting contact
ACCOUNTING_EMAIL: str = "asya@balizero.com"

# How many days before an invoice is considered overdue
OVERDUE_DAYS: int = 7

# Internal Brevo email endpoint (from=zantara@balizero.com)
_EMAIL_API_URL: str = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY: str = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")


class UnpaidInvoiceNotifier:
    """
    Scans practices in `sending_invoice` status for 7+ days and
    notifies Asya (accounting) with a single summary email.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_notify(self) -> dict[str, Any]:
        """
        Find all practices in sending_invoice status for 7+ days.
        Send one summary email to Asya listing all unpaid invoices.

        Returns:
            dict with keys:
                - overdue_count (int): number of overdue invoices found
                - notified (bool): whether the email was sent
                - skipped (bool): True when no overdue invoices exist
        """
        logger.info(
            "[UnpaidInvoiceNotifier] Starting overdue invoice check "
            f"(threshold: {OVERDUE_DAYS} days)"
        )

        try:
            invoices = await self._get_overdue_invoices()
        except Exception as exc:
            logger.error(
                "[UnpaidInvoiceNotifier] Failed to query overdue invoices",
                exc_info=True,
            )
            return {"overdue_count": 0, "notified": False, "skipped": False, "error": str(exc)}

        if not invoices:
            logger.info("[UnpaidInvoiceNotifier] No overdue invoices found — skipping notification")
            return {"overdue_count": 0, "notified": False, "skipped": True}

        logger.info(f"[UnpaidInvoiceNotifier] Found {len(invoices)} overdue invoice(s)")

        try:
            await self._send_asya_reminder(invoices)
            logger.info(
                f"[UnpaidInvoiceNotifier] Reminder sent to {ACCOUNTING_EMAIL} "
                f"for {len(invoices)} invoice(s)"
            )
            return {"overdue_count": len(invoices), "notified": True, "skipped": False}
        except Exception as exc:
            logger.error(
                "[UnpaidInvoiceNotifier] Failed to send reminder email",
                exc_info=True,
            )
            return {
                "overdue_count": len(invoices),
                "notified": False,
                "skipped": False,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Private: database query
    # ------------------------------------------------------------------

    async def _get_overdue_invoices(self) -> list[dict[str, Any]]:
        """
        Query practices in `sending_invoice` status whose `updated_at`
        is older than OVERDUE_DAYS days.

        Returns:
            List of dicts with keys:
                id, client_name, client_email, client_phone,
                practice_type_name, quoted_price, days_overdue,
                invoice_number (from documents->'invoice'->>'invoice_number',
                may be None)
        """
        # NOTE: INTERVAL cannot take a $1 placeholder directly in asyncpg;
        # multiply a plain INTERVAL '1 day' by the integer parameter instead.
        query = """
            SELECT
                p.id,
                c.full_name                                          AS client_name,
                c.email                                              AS client_email,
                c.phone                                              AS client_phone,
                pt.name                                              AS practice_type_name,
                p.quoted_price,
                EXTRACT(DAY FROM NOW() - p.updated_at)::int         AS days_overdue,
                p.documents -> 'invoice' ->> 'invoice_number'       AS invoice_number
            FROM practices p
            JOIN clients c      ON c.id = p.client_id
            LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE p.status = 'sending_invoice'
              AND p.updated_at < NOW() - ($1 * INTERVAL '1 day')
            ORDER BY p.updated_at ASC
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, OVERDUE_DAYS)

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Private: email
    # ------------------------------------------------------------------

    async def _send_asya_reminder(self, invoices: list[dict[str, Any]]) -> None:
        """
        Send a friendly reminder email to Asya (accounting) listing all
        overdue invoices as an HTML table.

        Args:
            invoices: list of invoice dicts from _get_overdue_invoices()
        """
        n = len(invoices)
        today_str = date.today().strftime("%d %B %Y")
        subject = f"\U0001f4b0 {n} fatture in attesa di pagamento \u2014 {today_str}"

        # Build HTML table rows
        table_rows: list[str] = []
        for inv in invoices:
            invoice_number: str = inv.get("invoice_number") or "—"
            client_name: str = inv.get("client_name") or "—"
            phone: str = inv.get("client_phone") or "—"
            quoted_price: float = float(inv.get("quoted_price") or 0)
            days_overdue: int = int(inv.get("days_overdue") or OVERDUE_DAYS)

            # Format IDR with thousand separators (no decimals)
            amount_formatted = f"Rp {quoted_price:,.0f}".replace(",", ".")

            # Highlight rows that are very overdue (≥14 days) in light red
            row_style = ' style="background:#fff0f0;"' if days_overdue >= 14 else ""

            table_rows.append(
                f"<tr{row_style}>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{invoice_number}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{client_name}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{phone}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right;'>"
                f"{amount_formatted}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center;'>"
                f"<strong>{days_overdue}</strong></td>"
                "</tr>"
            )

        table_html = "\n".join(table_rows)

        html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:720px;margin:0 auto;color:#333;">

  <h2 style="color:#d4845a;">💰 Fatture in attesa di pagamento</h2>

  <p>Ciao Asya! ☺️</p>

  <p>
    Spero tu stia passando una bella giornata!
    Ti scrivo perché ci sono <strong>{n} fattura/e</strong> inviate più di
    {OVERDUE_DAYS} giorni fa che risultano ancora senza pagamento ricevuto.
  </p>

  <table style="width:100%;border-collapse:collapse;margin-top:16px;margin-bottom:24px;
                font-size:14px;">
    <thead>
      <tr style="background:#0c0c0e;color:#fff;">
        <th style="padding:10px 12px;text-align:left;">Fattura #</th>
        <th style="padding:10px 12px;text-align:left;">Cliente</th>
        <th style="padding:10px 12px;text-align:left;">Telefono</th>
        <th style="padding:10px 12px;text-align:right;">Importo (IDR)</th>
        <th style="padding:10px 12px;text-align:center;">Giorni in attesa</th>
      </tr>
    </thead>
    <tbody>
      {table_html}
    </tbody>
  </table>

  <p><strong>✨ Per ciascun cliente, ti chiediamo di:</strong></p>
  <ol style="line-height:1.9;">
    <li>Contattarli via WhatsApp e ricordare gentilmente il pagamento</li>
    <li>Verificare se il pagamento è già arrivato in banca</li>
    <li>Se pagato, aggiornare lo status su <strong>ON PROCESS</strong> nel CRM</li>
  </ol>

  <p style="color:#888;font-size:13px;margin-top:32px;">
    Come sempre, sei la migliore — grazie per tenere tutto sotto controllo! 🙏<br><br>
    Con affetto,<br>
    <em>Zantara CRM Assistant 🤖</em><br><br>
    <em>P.S. Questo è un promemoria automatico, ma il grazie è assolutamente sincero! 😊</em>
  </p>

</div>
""".strip()

        logger.info(
            f"[UnpaidInvoiceNotifier] Sending reminder to {ACCOUNTING_EMAIL} "
            f"via Brevo ({n} invoice(s))"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={
                    "to": ACCOUNTING_EMAIL,
                    "subject": subject,
                    "body": html_body,
                },
            )
            response.raise_for_status()

        logger.info(
            f"[UnpaidInvoiceNotifier] Brevo accepted reminder email (status {response.status_code})"
        )
