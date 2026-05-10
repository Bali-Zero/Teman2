"""
Portal dashboard / visa / companies / tax / timeline mixin.

These are read-only view endpoints: they assemble client-scoped data
(visa practice, companies, tax deadlines, activity timeline) for the
client portal frontend. No Drive / OCR / billing side-effects live here.
"""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger
from backend.services.common.cache import cache_invalidating
from backend.services.portal._rbac import ClientContext, require_client_access

logger = get_logger(__name__)


class PortalDashboardMixin:
    """Read-only dashboard views and activity timeline."""

    pool: asyncpg.Pool

    # _is_undefined_column_error / _is_undefined_table_error are provided by
    # PortalService in portal_service.py and resolved via MRO at runtime.
    # They are not re-declared here to avoid shadowing the real implementation.

    # ================================================
    # DASHBOARD
    # ================================================

    @require_client_access
    async def get_dashboard(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Get client dashboard overview.

        Returns format expected by frontend PortalDashboard type:
            - visa: status, type, expiryDate, daysRemaining
            - company: status, primaryCompanyName, totalCompanies
            - taxes: status, nextDeadline, daysToDeadline
            - documents: total, pending
            - messages: unread
            - actions: list of PortalAction
        """
        async with self.pool.acquire() as conn:
            # Get client info
            client = await conn.fetchrow(
                "SELECT id, full_name, email FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get visa status (most recent KITAS/KITAP practice)
            # Use try-except to handle missing tables gracefully
            visa_practice = None
            try:
                visa_practice = await conn.fetchrow(
                    """
                    SELECT p.id, p.status, p.expiry_date, pt.code, pt.name
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status NOT IN ('cancelled', 'rejected')
                    ORDER BY p.expiry_date DESC NULLS LAST
                    LIMIT 1
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch visa practice: {e}")

            # Get companies
            companies = []
            try:
                companies = await conn.fetch(
                    """
                    SELECT ccl.id, ccl.role, ccl.is_primary, c.company_name, c.company_type
                    FROM client_company_links ccl
                    JOIN companies c ON c.id = ccl.company_id
                    WHERE ccl.client_id = $1
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch companies: {e}")

            # Get primary company name
            primary_company = next(
                (c for c in companies if c["is_primary"]), companies[0] if companies else None,
            )

            # Get upcoming tax deadlines (next 30 days)
            today = datetime.now(timezone.utc)
            tax_deadlines = self._get_standard_tax_deadlines(today)
            next_deadline = tax_deadlines[0] if tax_deadlines else None

            # Get action items (practices with required documents)
            action_items = []
            try:
                action_items = await conn.fetch(
                    """
                    SELECT p.id, pt.name as practice_name, p.missing_documents, p.status
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status IN ('inquiry', 'in_progress', 'waiting_documents')
                    ORDER BY p.created_at DESC
                    LIMIT 5
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch action items: {e}")

            # Get unread messages count
            unread_count = 0
            try:
                unread_count = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM portal_messages
                    WHERE client_id = $1
                    AND direction = 'team_to_client'
                    AND read_at IS NULL
                    """,
                        client_id,
                    )
                    or 0
                )
            except Exception as e:
                logger.warning(f"Could not fetch unread messages count: {e}")

            # Get document counts
            doc_counts = None
            try:
                doc_counts = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'pending') as pending
                    FROM documents
                    WHERE client_id = $1
                    AND client_visible = true
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch document counts: {e}")

            # Build visa response
            visa_data = self._build_visa_dashboard_data(visa_practice)

            # Build company response
            company_data = {
                "status": "active" if companies else "none",
                "primaryCompanyName": primary_company["company_name"] if primary_company else None,
                "totalCompanies": len(companies),
            }

            # Build tax response
            tax_data = {
                "status": self._get_tax_status(next_deadline),
                "nextDeadline": next_deadline["due_date"][:10] if next_deadline else None,
                "daysToDeadline": next_deadline["days_until"] if next_deadline else None,
            }

            # Build actions response
            actions = self._build_action_items(action_items, visa_data)

            return {
                "visa": visa_data,
                "company": company_data,
                "taxes": tax_data,
                "documents": {
                    "total": doc_counts["total"] if doc_counts else 0,
                    "pending": doc_counts["pending"] if doc_counts else 0,
                },
                "messages": {
                    "unread": unread_count,
                },
                "actions": actions,
            }

    def _build_visa_dashboard_data(self, visa_practice) -> dict[str, Any]:
        """Build visa data in frontend expected format."""
        if not visa_practice:
            return {
                "status": "none",
                "type": None,
                "expiryDate": None,
                "daysRemaining": None,
            }

        today = datetime.now(timezone.utc).date()
        expiry = visa_practice["expiry_date"].date() if visa_practice["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        # Determine status based on practice status and expiry
        if visa_practice["status"] == "completed":
            if days_left is not None:
                if days_left <= 0:
                    status = "expired"
                elif days_left <= 90:
                    status = "warning"
                else:
                    status = "active"
            else:
                status = "active"
        elif visa_practice["status"] in ("inquiry", "in_progress", "waiting_documents"):
            status = "pending"
        else:
            status = "pending"

        return {
            "status": status,
            "type": f"{visa_practice['code']} - {visa_practice['name']}"
            if visa_practice["code"]
            else visa_practice["name"],
            "expiryDate": visa_practice["expiry_date"].isoformat()[:10]
            if visa_practice["expiry_date"]
            else None,
            "daysRemaining": days_left,
        }

    def _get_tax_status(self, next_deadline) -> str:
        """Determine tax compliance status."""
        if not next_deadline:
            return "compliant"
        days = next_deadline["days_until"]
        if days < 0:
            return "overdue"
        if days <= 14:
            return "attention"
        return "compliant"

    def _build_action_items(self, action_items, visa_data) -> list[dict[str, Any]]:
        """Build action items for dashboard."""
        actions = []
        action_id = 1

        # Add visa warning if expiring soon
        if visa_data["status"] == "warning" and visa_data["daysRemaining"]:
            actions.append(
                {
                    "id": f"visa-{action_id}",
                    "title": "Visa Expiring Soon",
                    "description": f"Your visa expires in {visa_data['daysRemaining']} days. Start renewal process.",
                    "priority": "high" if visa_data["daysRemaining"] <= 30 else "medium",
                    "type": "visa_renewal",
                    "href": "/portal/visa",
                },
            )
            action_id += 1

        # Add missing documents actions
        for item in action_items:
            missing_docs = item["missing_documents"] or []
            if missing_docs:
                actions.append(
                    {
                        "id": f"docs-{item['id']}",
                        "title": f"Documents Required: {item['practice_name']}",
                        "description": f"Please upload: {', '.join(missing_docs[:3])}{'...' if len(missing_docs) > 3 else ''}",
                        "priority": "high" if item["status"] == "waiting_documents" else "medium",
                        "type": "missing_documents",
                        "href": "/portal/documents",
                    },
                )
                action_id += 1
                if action_id > 5:  # Max 5 actions
                    break

        return actions

    # ================================================
    # VISA & IMMIGRATION
    # ================================================

    @require_client_access
    async def get_visa_status(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Get detailed visa and immigration status.

        Returns format expected by frontend VisaInfo type:
            - current: { type, status, issueDate, expiryDate, daysRemaining, permitNumber, sponsor }
            - history: [{ id, type, period, status }]
            - documents: [{ id, name, type, category, status, uploadDate, expiryDate, size, downloadUrl }]
        """
        async with self.pool.acquire() as conn:
            # Verify client exists
            client = await conn.fetchrow(
                "SELECT id FROM clients WHERE id = $1 AND deleted_at IS NULL",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get current visa practice (completed, not expired)
            try:
                current_visa = await conn.fetchrow(
                    """
                    SELECT p.id, p.status, p.start_date, p.completion_date, p.expiry_date,
                           p.notes, pt.code, pt.name as type_name
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    AND p.status = 'completed'
                    AND (p.expiry_date IS NULL OR p.expiry_date > NOW())
                    ORDER BY p.expiry_date DESC NULLS LAST
                    LIMIT 1
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    current_visa = await conn.fetchrow(
                        """
                        SELECT p.id, p.status, p.start_date, p.completion_date, p.expiry_date,
                               p.notes, pt.code, pt.name as type_name
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'visa'
                        AND p.status = 'completed'
                        AND (p.expiry_date IS NULL OR p.expiry_date > NOW())
                        ORDER BY p.expiry_date DESC NULLS LAST
                        LIMIT 1
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get visa history (all visa practices)
            try:
                visa_history = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.start_date, p.completion_date,
                           p.expiry_date, p.status
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'visa'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.start_date DESC
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    visa_history = await conn.fetch(
                        """
                        SELECT p.id, pt.code, pt.name, p.start_date, p.completion_date,
                               p.expiry_date, p.status
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'visa'
                        ORDER BY p.start_date DESC
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get immigration documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_id, d.file_size_kb, d.created_at
                FROM documents d
                WHERE d.client_id = $1
                AND d.client_visible = true
                AND d.document_type IN (
                    'passport', 'photo', 'cv', 'sponsor_letter',
                    'sktt', 'stm', 'kitas_card', 'merp', 'visa'
                )
                ORDER BY d.created_at DESC
                """,
                client_id,
            )

            # Build current visa response (matching frontend VisaInfo.current)
            current = None
            if current_visa:
                today = datetime.now(timezone.utc).date()
                expiry = current_visa["expiry_date"].date() if current_visa["expiry_date"] else None
                days_left = (expiry - today).days if expiry else 0

                # Determine status
                if days_left <= 0:
                    status = "expired"
                elif current_visa["status"] == "completed":
                    status = "active"
                else:
                    status = "pending"

                visa_type = (
                    f"{current_visa['code']} - {current_visa['type_name']}"
                    if current_visa["code"]
                    else current_visa["type_name"]
                )

                current = {
                    "type": visa_type,
                    "status": status,
                    "issueDate": current_visa["completion_date"].strftime("%d %b %Y")
                    if current_visa["completion_date"]
                    else "-",
                    "expiryDate": current_visa["expiry_date"].strftime("%d %b %Y")
                    if current_visa["expiry_date"]
                    else "-",
                    "daysRemaining": max(0, days_left),
                    "permitNumber": f"KITAS-{current_visa['id']:06d}",  # Generated permit number
                    "sponsor": "Bali Zero Indonesia",  # Default sponsor
                }

            # Build history response (matching frontend VisaHistoryItem)
            history = []
            for v in visa_history:
                # Determine period string
                start = v["start_date"].strftime("%b %Y") if v["start_date"] else ""
                end = (
                    v["expiry_date"].strftime("%b %Y")
                    if v["expiry_date"]
                    else v["completion_date"].strftime("%b %Y")
                    if v["completion_date"]
                    else ""
                )
                period = f"{start} - {end}" if start and end else start or end or "-"

                # Map status to frontend expected values
                hist_status = "completed" if v["status"] == "completed" else "expired"

                history.append(
                    {
                        "id": str(v["id"]),
                        "type": f"{v['code']} - {v['name']}" if v["code"] else v["name"],
                        "period": period,
                        "status": hist_status,
                    },
                )

            # Build documents response (matching frontend PortalDocument)
            doc_list = []
            for d in documents:
                # Map document type to category
                category_map = {
                    "passport": "Identity",
                    "photo": "Identity",
                    "cv": "Supporting",
                    "sponsor_letter": "Sponsorship",
                    "sktt": "Immigration",
                    "stm": "Immigration",
                    "kitas_card": "Immigration",
                    "merp": "Immigration",
                    "visa": "Immigration",
                }

                # Map status
                status_map = {
                    "verified": "verified",
                    "issued": "verified",
                    "pending": "pending",
                    "rejected": "expired",
                    "expired": "expired",
                }

                doc_list.append(
                    {
                        "id": str(d["id"]),
                        "name": d["file_name"],
                        "type": d["document_type"],
                        "category": category_map.get(d["document_type"], "Other"),
                        "status": status_map.get(d["status"], "pending"),
                        "uploadDate": d["created_at"].strftime("%d %b %Y")
                        if d["created_at"]
                        else "-",
                        "expiryDate": d["expiry_date"].strftime("%d %b %Y")
                        if d["expiry_date"]
                        else None,
                        "size": f"{d['file_size_kb']} KB" if d["file_size_kb"] else "-",
                        "downloadUrl": f"/api/portal/documents/{d['id']}/download"
                        if d["file_url"] or d["file_id"]
                        else None,
                    },
                )

            return {
                "current": current,
                "history": history,
                "documents": doc_list,
            }

    # ================================================
    # COMPANIES
    # ================================================

    @require_client_access
    async def get_companies(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> list[dict[str, Any]]:
        """Get all companies associated with client."""
        async with self.pool.acquire() as conn:
            companies = await conn.fetch(
                """
                SELECT ccl.id, ccl.role, ccl.is_primary, ccl.created_at,
                       ccl.ownership_percentage, ccl.status as link_status,
                       c.id as company_id, c.company_name, c.company_type,
                       c.nib, c.npwp_company, c.kbli_code, c.status as company_status
                FROM client_company_links ccl
                JOIN companies c ON c.id = ccl.company_id
                WHERE ccl.client_id = $1
                ORDER BY ccl.is_primary DESC, ccl.created_at
                """,
                client_id,
            )

            return [
                {
                    "id": c["id"],
                    "company_id": c["company_id"],
                    "name": c["company_name"],
                    "type": c["company_type"],
                    "role": c["role"],
                    "isPrimary": c["is_primary"],
                    "ownership_pct": float(c["ownership_percentage"])
                    if c["ownership_percentage"]
                    else None,
                    "nib": c["nib"],
                    "npwp": c["npwp_company"],
                    "kbli": c["kbli_code"],
                    "status": c["company_status"],
                    "link_status": c["link_status"],
                }
                for c in companies
            ]

    @require_client_access
    async def get_company_detail(
        self,
        client_id: int,
        company_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Get detailed company information."""
        async with self.pool.acquire() as conn:
            # Verify client owns this company
            ownership = await conn.fetchrow(
                """
                SELECT ccl.role, ccl.is_primary, ccl.ownership_percentage
                FROM client_company_links ccl
                WHERE ccl.client_id = $1 AND ccl.company_id = $2
                """,
                client_id,
                company_id,
            )
            if not ownership:
                raise ValueError("Company not found or not accessible")

            # Get company profile
            company = await conn.fetchrow(
                """
                SELECT * FROM companies WHERE id = $1
                """,
                company_id,
            )

            # Get company practices (licenses, registrations)
            try:
                practices = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.status, p.expiry_date,
                           p.completion_date
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'company'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.expiry_date ASC NULLS LAST
                    """,
                    client_id,
                )
            except Exception as e:
                if self._is_undefined_column_error(e):
                    practices = await conn.fetch(
                        """
                        SELECT p.id, pt.code, pt.name, p.status, p.expiry_date,
                               p.completion_date
                        FROM practices p
                        JOIN practice_types pt ON pt.id = p.practice_type_id
                        WHERE p.client_id = $1
                        AND pt.category = 'company'
                        ORDER BY p.expiry_date ASC NULLS LAST
                        """,
                        client_id,
                    )
                else:
                    raise

            # Get company documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status, d.file_url, d.file_id
                FROM documents d
                JOIN practices p ON p.id = d.practice_id
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                AND pt.category = 'company'
                AND d.client_visible = true
                ORDER BY d.created_at DESC
                """,
                client_id,
            )

            # Get all directors/shareholders linked to this company
            directors = await conn.fetch(
                """
                SELECT cl.full_name, ccl.role, ccl.ownership_percentage
                FROM client_company_links ccl
                JOIN clients cl ON cl.id = ccl.client_id
                WHERE ccl.company_id = $1
                ORDER BY ccl.is_primary DESC, ccl.role, cl.full_name
                """,
                company_id,
            )

            # Parse custom_fields safely
            custom = company["custom_fields"] or {}
            if isinstance(custom, str):
                try:
                    custom = json.loads(custom)
                except Exception:
                    custom = {}
            if not isinstance(custom, dict):
                custom = {}

            return {
                "id": company["id"],
                "name": company["company_name"],
                "type": company["company_type"],
                "nib": company["nib"],
                "npwp": company["npwp_company"],
                "kbli": company["kbli_code"],
                "status": company["status"],
                "address": company["registered_address"],
                "email": company["company_email"],
                "phone": company["company_phone"],
                "akta_no": company["akta_pendirian_no"],
                "akta_date": company["akta_pendirian_date"].isoformat()
                if company["akta_pendirian_date"]
                else None,
                "sk_number": company["sk_menhumkam_no"],
                "tax_office": custom.get("tax_office"),
                "company_status": custom.get("company_status"),
                "investment_type": custom.get("investment_type"),
                "authorized_capital": custom.get("authorized_capital"),
                "ownership": {
                    "role": ownership["role"],
                    "is_primary": ownership["is_primary"],
                    "pct": float(ownership["ownership_percentage"])
                    if ownership["ownership_percentage"]
                    else None,
                },
                "licenses": [
                    {
                        "id": p["id"],
                        "code": p["code"],
                        "name": p["name"],
                        "status": p["status"],
                        "expiry_date": p["expiry_date"].isoformat() if p["expiry_date"] else None,
                    }
                    for p in practices
                ],
                "documents": [
                    {
                        "id": d["id"],
                        "type": d["document_type"],
                        "name": d["file_name"],
                        "downloadable": d["file_url"] is not None
                        or d["file_id"] is not None,
                    }
                    for d in documents
                ],
                "directors": [
                    d["full_name"]
                    for d in directors
                    if d["role"] in ("director", "commissioner", "president_director")
                ],
                "shareholders": [
                    {
                        "name": d["full_name"],
                        "pct": float(d["ownership_percentage"])
                        if d["ownership_percentage"]
                        else None,
                    }
                    for d in directors
                ],
            }

    @cache_invalidating([
        lambda _self, client_id, *_a, **_k: f"zantara:portal_dashboard:{client_id}:*",
        lambda _self, client_id, *_a, **_k: f"zantara:crm_client:{client_id}:*",
    ])
    @require_client_access
    async def set_primary_company(
        self,
        client_id: int,
        company_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """Set a company as primary for the client."""
        async with self.pool.acquire() as conn, conn.transaction():
            # Clear previous primary
            await conn.execute(
                """
                    UPDATE client_company_links
                    SET is_primary = false
                    WHERE client_id = $1
                    """,
                client_id,
            )

            # Set new primary
            result = await conn.execute(
                """
                    UPDATE client_company_links
                    SET is_primary = true
                    WHERE client_id = $1 AND company_id = $2
                    """,
                client_id,
                company_id,
            )

            if result == "UPDATE 0":
                raise ValueError("Company not found or not accessible")

            return {"success": True, "primary_company_id": company_id}

    # ================================================
    # TAXES
    # ================================================

    @require_client_access
    async def get_tax_overview(
        self,
        client_id: int,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Get tax overview and upcoming deadlines.

        Returns format expected by frontend TaxOverview:
        - summary: { status, totalDue, nextDeadline, daysToDeadline }
        - obligations: list of TaxObligation
        - history: list of TaxHistoryItem
        """
        async with self.pool.acquire() as conn:
            # Get tax-related practices (for obligations)
            tax_practices = []
            try:
                tax_practices = await conn.fetch(
                    """
                    SELECT p.id, pt.code, pt.name, p.status, p.expiry_date, p.created_at
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND pt.category = 'tax'
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.expiry_date ASC NULLS LAST
                    """,
                    client_id,
                )
            except Exception as e:
                logger.warning(f"Could not fetch tax practices: {e}")

            # Generate standard tax deadlines
            today = datetime.now(timezone.utc)
            deadlines = self._get_standard_tax_deadlines(today)

            # Build obligations from deadlines (upcoming tax filings)
            obligations = []
            for i, d in enumerate(deadlines):
                obligations.append(
                    {
                        "id": f"deadline-{i}",
                        "name": d["type"],
                        "type": "Monthly Filing",
                        "period": d["period"],
                        "dueDate": d["due_date"],
                        "status": "overdue" if d["days_until"] < 0 else "pending",
                        "amount": None,
                    },
                )

            # Build history from completed tax practices
            history = []
            for p in tax_practices:
                if p["status"] in ("completed", "filed"):
                    history.append(
                        {
                            "id": str(p["id"]),
                            "name": p["name"],
                            "period": p["created_at"].strftime("%b %Y")
                            if p["created_at"]
                            else "N/A",
                            "filedDate": p["created_at"].isoformat() if p["created_at"] else None,
                            "amount": 0,  # No amount stored in practices
                        },
                    )

            # Calculate summary
            next_deadline = None
            days_to_deadline = None
            if deadlines:
                next_deadline = deadlines[0]["due_date"]
                days_to_deadline = deadlines[0]["days_until"]

            # Determine status based on deadlines
            status = "compliant"
            if days_to_deadline is not None:
                if days_to_deadline < 0:
                    status = "overdue"
                elif days_to_deadline <= 14:
                    status = "attention"

            return {
                "summary": {
                    "status": status,
                    "totalDue": 0,  # No payment tracking yet
                    "nextDeadline": next_deadline,
                    "daysToDeadline": days_to_deadline,
                },
                "obligations": obligations,
                "history": history,
            }
    # ================================================
    # TIMELINE
    # ================================================

    @require_client_access
    async def get_timeline(
        self,
        client_id: int,
        limit: int = 50,
        *,
        current_user: ClientContext,
    ) -> dict[str, Any]:
        """
        Get client activity timeline.

        Combines:
        - Messages (sent and received)
        - Document uploads
        - Practice status changes
        - Upcoming deadlines

        Returns format expected by frontend TimelineResponse:
            - scope: 'portal'
            - entries: list of TimelineEntry
            - lastUpdated: timestamp
        """

        entries = []

        async with self.pool.acquire() as conn:
            # Persisted portal timeline events (preferred when available)
            try:
                timeline_events = await conn.fetch(
                    """
                    SELECT id, practice_id, event_type, title, description, event_date
                    FROM timeline_events
                    WHERE client_id = $1
                      AND client_visible = true
                    ORDER BY event_date DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit,
                )

                now = datetime.now(timezone.utc)
                for ev in timeline_events:
                    event_type = ev["event_type"]
                    # Map event types to the frontend-supported TimelineEntryType union.
                    if event_type in ("document_request", "document_received"):
                        entry_type = "document"
                    elif event_type in ("deadline", "payment_due", "appointment", "reminder"):
                        entry_type = "deadline"
                    else:
                        entry_type = "practice"

                    occurred_at = ev["event_date"]
                    is_future = bool(occurred_at and occurred_at > now)

                    entries.append(
                        {
                            "id": f"event-{ev['id']}",
                            "type": entry_type,
                            "occurredAt": occurred_at.isoformat()
                            if occurred_at
                            else now.isoformat(),
                            "title": ev["title"],
                            "description": ev["description"],
                            "status": event_type,
                            "unread": False,
                            "isFuture": is_future,
                            "entity": {"practiceId": ev["practice_id"]}
                            if ev["practice_id"]
                            else {},
                        },
                    )
            except Exception as e:
                if not self._is_undefined_table_error(e):
                    logger.warning(f"Could not fetch timeline_events: {e}")

            # Get recent messages
            try:
                messages = await conn.fetch(
                    """
                    SELECT id, subject, content, direction, created_at, read_at
                    FROM portal_messages
                    WHERE client_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,  # Allocate 1/3 of limit to messages
                )
                for msg in messages:
                    entries.append(
                        {
                            "id": f"msg-{msg['id']}",
                            "type": "message",
                            "occurredAt": msg["created_at"].isoformat(),
                            "title": msg["subject"] or "New Message",
                            "description": msg["content"][:100]
                            + ("..." if len(msg["content"]) > 100 else ""),
                            "status": "sent"
                            if msg["direction"] == "client_to_team"
                            else "received",
                            "unread": msg["direction"] == "team_to_client"
                            and msg["read_at"] is None,
                            "isFuture": False,
                            "entity": {"messageId": str(msg["id"])},
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch messages for timeline: {e}")

            # Get recent documents
            try:
                documents = await conn.fetch(
                    """
                    SELECT id, document_type, file_name, status, created_at
                    FROM documents
                    WHERE client_id = $1 AND client_visible = true
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,
                )
                for doc in documents:
                    entries.append(
                        {
                            "id": f"doc-{doc['id']}",
                            "type": "document",
                            "occurredAt": doc["created_at"].isoformat(),
                            "title": f"Document: {doc['file_name']}",
                            "description": f"Type: {doc['document_type']}",
                            "status": doc["status"],
                            "unread": False,
                            "isFuture": False,
                            "entity": {"documentId": str(doc["id"])},
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch documents for timeline: {e}")

            # Get recent practice updates
            try:
                practices = await conn.fetch(
                    """
                    SELECT p.id, pt.name, pt.category, p.status, p.updated_at
                    FROM practices p
                    JOIN practice_types pt ON pt.id = p.practice_type_id
                    WHERE p.client_id = $1
                    AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
                    ORDER BY p.updated_at DESC
                    LIMIT $2
                    """,
                    client_id,
                    limit // 3,
                )
                for p in practices:
                    entries.append(
                        {
                            "id": f"practice-{p['id']}",
                            "type": "practice",
                            "occurredAt": p["updated_at"].isoformat()
                            if p["updated_at"]
                            else datetime.now(timezone.utc).isoformat(),
                            "title": f"{p['name']} Update",
                            "description": f"Status: {p['status']}",
                            "status": p["status"],
                            "unread": False,
                            "isFuture": False,
                            "entity": {
                                "practiceId": p["id"],
                                "practiceCategory": p["category"],
                            },
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not fetch practices for timeline: {e}")

            # Add upcoming deadlines (future events)
            today = datetime.now(timezone.utc)
            deadlines = self._get_standard_tax_deadlines(today)
            for deadline in deadlines[:3]:  # Max 3 deadlines
                entries.append(
                    {
                        "id": f"deadline-{deadline['type'].lower().replace(' ', '-')}",
                        "type": "deadline",
                        "occurredAt": deadline["due_date"],
                        "title": f"Tax Deadline: {deadline['type']}",
                        "description": f"Due in {deadline['days_until']} days",
                        "status": deadline["urgency"],
                        "unread": False,
                        "isFuture": True,
                    },
                )

        # Sort by date descending
        entries.sort(key=lambda x: x["occurredAt"], reverse=True)

        return {
            "scope": "portal",
            "entries": entries[:limit],
            "lastUpdated": int(time.time() * 1000),
        }

    # ================================================
    # HELPER METHODS
    # ================================================

    def _get_standard_tax_deadlines(self, today: datetime) -> list[dict[str, Any]]:
        """Generate standard Indonesian tax deadlines."""
        year = today.year
        month = today.month

        deadlines = []

        # PPh 21/23/4(2) - 10th of following month
        pph_date = datetime(year, month, 10, tzinfo=timezone.utc)
        if pph_date <= today:
            pph_date = datetime(
                year if month < 12 else year + 1,
                month + 1 if month < 12 else 1,
                10,
                tzinfo=timezone.utc,
            )
        days_until = (pph_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "PPh 21/23/4(2)",
                "period": f"{pph_date.strftime('%b %Y')}",
                "due_date": pph_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # PPN (VAT) - End of following month
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        # Last day of next month
        if next_month == 12:
            ppn_date = datetime(next_year, 12, 31, tzinfo=timezone.utc)
        else:
            ppn_date = datetime(next_year, next_month + 1, 1, tzinfo=timezone.utc) - timedelta(
                days=1,
            )

        days_until = (ppn_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "PPN (VAT)",
                "period": f"{ppn_date.strftime('%b %Y')}",
                "due_date": ppn_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # Annual SPT - March 31
        spt_date = datetime(year, 3, 31, tzinfo=timezone.utc)
        if spt_date <= today:
            spt_date = datetime(year + 1, 3, 31, tzinfo=timezone.utc)
        days_until = (spt_date.date() - today.date()).days
        deadlines.append(
            {
                "type": "Annual SPT",
                "period": str(spt_date.year - 1),
                "due_date": spt_date.isoformat(),
                "days_until": days_until,
                "urgency": "urgent"
                if days_until <= 14
                else "warning"
                if days_until <= 30
                else "normal",
            },
        )

        # Sort by days_until
        deadlines.sort(key=lambda x: x["days_until"])

        return deadlines


__all__ = ["PortalDashboardMixin"]
