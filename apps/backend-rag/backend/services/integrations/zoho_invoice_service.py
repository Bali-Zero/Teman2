"""
Zoho Invoice API Integration Service.

Handles:
- OAuth authentication
- Contact/Customer management
- Invoice creation and management
- Email sending through Zoho Invoice
"""

from datetime import datetime
from typing import Any

import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.zoho_oauth_service import ZohoOAuthService

logger = get_logger(__name__)


class ZohoInvoiceService:
    """Service for interacting with Zoho Invoice API."""

    def __init__(self, db_pool: Any) -> None:
        self.db_pool = db_pool
        self.api_domain = "https://invoice.zoho.com"
        self.oauth_service = ZohoOAuthService(db_pool)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        await self.oauth_service.close()

    async def _make_api_request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
        accept_json: bool = True,
    ) -> Any:
        """
        Make authenticated request to Zoho Invoice API.

        Args:
            user_id: User ID for OAuth
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data
            headers: Additional headers
            accept_json: Whether to expect JSON response

        Returns:
            Response data (JSON or bytes)
        """
        # Get valid OAuth token
        access_token = await self.oauth_service.get_valid_token(user_id)
        if not access_token:
            raise ValueError(f"No valid Zoho OAuth token for user {user_id}")

        # Get organization ID from environment or config
        import os

        organization_id = os.environ.get("ZOHO_INVOICE_ORG_ID", "")

        if not organization_id:
            logger.error("ZOHO_INVOICE_ORG_ID not configured")
            raise ValueError("Zoho organization ID not configured")

        # Build request headers
        request_headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "X-com-zoho-invoice-organizationid": organization_id,
        }
        if accept_json:
            request_headers["Accept"] = "application/json"
        if headers:
            request_headers.update(headers)

        url = f"{self.api_domain}/api/v3{endpoint}"

        client = self._get_client()
        response = await client.request(
            method=method,
            url=url,
            headers=request_headers,
            params=params,
            json=json_data,
        )

        # Check for token expiration
        if response.status_code == 401:
            logger.error("Zoho token expired - manual reconnect required")
            raise ValueError(
                "Zoho OAuth token expired - please reconnect at /api/integrations/zoho/auth"
            )

        response.raise_for_status()

        if accept_json:
            return response.json()
        return response.content

    async def get_or_create_customer(
        self,
        user_id: str,
        client_data: dict,
    ) -> dict[str, Any]:
        """
        Get existing customer or create new one in Zoho Invoice.

        Args:
            user_id: User ID for OAuth
            client_data: Client data with email, full_name, etc.

        Returns:
            Customer data from Zoho
        """
        email = client_data.get("email")
        if not email:
            raise ValueError("Client email required for Zoho Invoice")

        # Search for existing contact by email
        try:
            search_result = await self._make_api_request(
                user_id,
                "GET",
                "/contacts",
                params={"email": email},
            )

            if search_result.get("contacts"):
                customer = search_result["contacts"][0]
                logger.info(f"Found existing Zoho customer: {customer['contact_id']}")
                return customer
        except Exception as e:
            logger.warning(f"Error searching for customer: {e}")

        # Create new contact
        contact_data = {
            "contact_name": client_data["full_name"],
            "contact_type": "customer",
            "contact_persons": [
                {
                    "first_name": client_data["full_name"].split()[0]
                    if client_data["full_name"]
                    else "Client",
                    "last_name": " ".join(client_data["full_name"].split()[1:])
                    if len(client_data["full_name"].split()) > 1
                    else "",
                    "email": email,
                    "phone": client_data.get("phone", ""),
                }
            ],
            "billing_address": {
                "address": client_data.get("address", ""),
                "country": "Indonesia",
            },
            "shipping_address": {
                "address": client_data.get("address", ""),
                "country": "Indonesia",
            },
        }

        response = await self._make_api_request(
            user_id,
            "POST",
            "/contacts",
            json_data=contact_data,
        )

        customer = response["contact"]
        logger.info(f"Created new Zoho customer: {customer['contact_id']}")
        return customer

    async def create_invoice(
        self,
        user_id: str,
        customer_id: str,
        practice_data: dict,
        client_data: dict,
    ) -> dict[str, Any]:
        """
        Create a draft invoice in Zoho Invoice.

        Args:
            user_id: User ID for OAuth
            customer_id: Zoho customer/contact ID
            practice_data: Practice data
            client_data: Client data

        Returns:
            Created invoice data
        """
        # Build invoice line items
        line_items = []

        # Main service line item
        service_name = practice_data.get("practice_type_name", "Immigration Service")
        quoted_price = float(practice_data.get("quoted_price", 0))

        line_items.append(
            {
                "name": service_name,
                "description": practice_data.get(
                    "notes", f"Service for {client_data['full_name']}"
                ),
                "rate": quoted_price,
                "quantity": 1,
                "item_total": quoted_price,
            }
        )

        # Calculate due date (7 days from now)
        due_date = (datetime.now(tz=timezone.utc)).strftime("%Y-%m-%d")
        due_date_obj = datetime.now(tz=timezone.utc)
        due_date = due_date_obj.strftime("%Y-%m-%d")

        invoice_data = {
            "customer_id": customer_id,
            "line_items": line_items,
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "due_date": due_date,
            "reference_number": str(practice_data.get("id", "")),
            "notes": "Thank you for choosing Zantara Indonesia. Payment is due within 7 days.",
            "terms": "Payment terms: Net 7 days. Please contact us for any questions.",
        }

        response = await self._make_api_request(
            user_id,
            "POST",
            "/invoices",
            json_data=invoice_data,
        )

        invoice = response["invoice"]
        logger.info(f"Created Zoho Invoice: {invoice['invoice_id']} - {invoice['invoice_number']}")

        return invoice

    async def send_invoice_email(
        self,
        user_id: str,
        invoice_id: str,
        to_email: str,
        cc_email: str | None = None,
    ) -> bool:
        """
        Send invoice via email from Zoho Invoice.

        Args:
            user_id: User ID for OAuth
            invoice_id: Zoho Invoice ID
            to_email: Recipient email
            cc_email: CC email (optional)

        Returns:
            True if sent successfully
        """
        email_data = {
            "to_mail_ids": [to_email],
            "subject": "Invoice from Zantara Indonesia",
            "body": """Dear Client,

Please find your invoice attached.

Thank you for choosing Zantara Indonesia for your immigration services.

Payment is due within 7 days from the invoice date.

If you have any questions, please don't hesitate to contact us.

Best regards,
Zantara Indonesia Team
""",
        }

        if cc_email:
            email_data["cc_mail_ids"] = [cc_email]

        try:
            await self._make_api_request(
                user_id,
                "POST",
                f"/invoices/{invoice_id}/email",
                json_data=email_data,
            )
            logger.info(f"Invoice {invoice_id} email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}")
            return False

    async def get_invoice_pdf(
        self,
        user_id: str,
        invoice_id: str,
    ) -> bytes:
        """
        Download invoice PDF from Zoho Invoice.

        Args:
            user_id: User ID for OAuth
            invoice_id: Zoho Invoice ID

        Returns:
            PDF file as bytes
        """
        pdf_bytes = await self._make_api_request(
            user_id,
            "GET",
            f"/invoices/{invoice_id}",
            params={"accept": "pdf"},
            accept_json=False,
        )

        logger.info(f"Downloaded PDF for invoice {invoice_id}")
        return pdf_bytes

    async def create_and_send_invoice(
        self,
        user_id: str,
        practice_data: dict,
        client_data: dict,
    ) -> dict[str, Any]:
        """
        Complete workflow: Create invoice and send email.

        Args:
            user_id: User ID for OAuth (should be admin/system user)
            practice_data: Practice data
            client_data: Client data

        Returns:
            Result with invoice_id, invoice_number, email_sent
        """
        try:
            # Step 1: Get or create customer
            customer = await self.get_or_create_customer(user_id, client_data)

            # Step 2: Create invoice
            invoice = await self.create_invoice(
                user_id,
                customer["contact_id"],
                practice_data,
                client_data,
            )

            # Step 3: Send email if client has email
            email_sent = False
            if client_data.get("email"):
                email_sent = await self.send_invoice_email(
                    user_id,
                    invoice["invoice_id"],
                    client_data["email"],
                )

            return {
                "success": True,
                "invoice_id": invoice["invoice_id"],
                "invoice_number": invoice["invoice_number"],
                "customer_id": customer["contact_id"],
                "email_sent": email_sent,
                "view_url": invoice.get("invoice_url", ""),
                "zoho_invoice_data": invoice,
            }

        except Exception as e:
            logger.error(f"Failed to create/send Zoho Invoice: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }
