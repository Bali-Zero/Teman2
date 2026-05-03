"""Invoicing Tools - 3 tools for invoice generation and management."""

from typing import Optional

from nuzantara_mcp.auth import require_role


def register(mcp, _call, _call_safe):
    @mcp.tool()
    @require_role("admin")
    async def regenerate_invoice(practice_id: int) -> dict:
        """
        Regenerate and resend invoice for a practice.

        Triggers the full invoice workflow: generates PDF, uploads to
        Google Drive, sends via email and WhatsApp.

        Use when: client lost invoice, amount corrected, automation failed,
        or invoice generation was skipped during practice creation.

        Args:
            practice_id: Practice ID (must be in quotation_sent status)

        Returns:
            Invoice details: invoice_number, drive_file_id, drive_link,
            email_sent status, whatsapp_sent status.
        """
        return await _call(
            f"/api/crm/practices/{practice_id}/regenerate-invoice",
            method="POST",
        )

    @mcp.tool()
    @require_role("tax_consultant", "admin")
    async def get_practice_invoice(practice_id: int) -> dict:
        """
        Get invoice details for a practice.

        Retrieves the current invoice information including PDF link,
        payment status, and delivery confirmation.

        Args:
            practice_id: Practice ID

        Returns:
            Invoice metadata: number, amount, currency, status, drive_link.
        """
        return await _call(f"/api/crm/practices/{practice_id}/invoice")

    @mcp.tool()
    @require_role("tax_consultant", "admin")
    async def list_pending_invoices(
        status: str = "unpaid",
        limit: int = 50,
    ) -> dict:
        """
        List invoices filtered by payment status.

        Args:
            status: Filter by status: "unpaid", "paid", "overdue", "all"
            limit: Max results to return

        Returns:
            List of invoices with practice_id, client, amount, due_date.
        """
        return await _call(
            "/api/crm/invoices",
            params={"status": status, "limit": limit},
        )
