"""
Client Portal Service

Provides client-scoped data access for:
- Dashboard overview
- Visa & immigration status
- Company & licenses
- Tax deadlines
- Documents
- Messages
- Preferences
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from app.utils.logging_utils import get_logger

logger = get_logger(__name__)


class PortalService:
    """Service for client portal data access."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ================================================
    # DASHBOARD
    # ================================================

    async def get_dashboard(self, client_id: int) -> dict[str, Any]:
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
                "SELECT id, full_name, email FROM clients WHERE id = $1",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get visa status (most recent KITAS/KITAP practice)
            visa_practice = await conn.fetchrow(
                """
                SELECT p.id, p.status, p.expiry_date, pt.code, pt.name
                FROM practices p
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                AND pt.category = 'visa'
                AND p.status NOT IN ('cancelled', 'rejected')
                ORDER BY p.expiry_date DESC NULLS LAST
                LIMIT 1
                """,
                client_id,
            )

            # Get companies
            companies = await conn.fetch(
                """
                SELECT cc.id, cc.role, cc.is_primary, cp.company_name, cp.entity_type
                FROM client_companies cc
                JOIN company_profiles cp ON cp.id = cc.company_id
                WHERE cc.client_id = $1
                """,
                client_id,
            )

            # Get primary company name
            primary_company = next(
                (c for c in companies if c["is_primary"]),
                companies[0] if companies else None
            )

            # Get upcoming tax deadlines (next 30 days)
            today = datetime.now(timezone.utc)
            tax_deadlines = self._get_standard_tax_deadlines(today)
            next_deadline = tax_deadlines[0] if tax_deadlines else None

            # Get action items (practices with required documents)
            action_items = await conn.fetch(
                """
                SELECT p.id, pt.name as practice_name, p.missing_documents, p.status
                FROM practices p
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                AND p.status IN ('inquiry', 'in_progress', 'waiting_documents')
                ORDER BY p.created_at DESC
                LIMIT 5
                """,
                client_id,
            )

            # Get unread messages count
            unread_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM portal_messages
                WHERE client_id = $1
                AND direction = 'team_to_client'
                AND read_at IS NULL
                """,
                client_id,
            ) or 0

            # Get document counts
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
            "type": f"{visa_practice['code']} - {visa_practice['name']}" if visa_practice["code"] else visa_practice["name"],
            "expiryDate": visa_practice["expiry_date"].isoformat()[:10] if visa_practice["expiry_date"] else None,
            "daysRemaining": days_left,
        }

    def _get_tax_status(self, next_deadline) -> str:
        """Determine tax compliance status."""
        if not next_deadline:
            return "compliant"
        days = next_deadline["days_until"]
        if days < 0:
            return "overdue"
        elif days <= 14:
            return "attention"
        return "compliant"

    def _build_action_items(self, action_items, visa_data) -> list[dict[str, Any]]:
        """Build action items for dashboard."""
        actions = []
        action_id = 1

        # Add visa warning if expiring soon
        if visa_data["status"] == "warning" and visa_data["daysRemaining"]:
            actions.append({
                "id": f"visa-{action_id}",
                "title": "Visa Expiring Soon",
                "description": f"Your visa expires in {visa_data['daysRemaining']} days. Start renewal process.",
                "priority": "high" if visa_data["daysRemaining"] <= 30 else "medium",
                "type": "visa_renewal",
                "href": "/portal/visa",
            })
            action_id += 1

        # Add missing documents actions
        for item in action_items:
            missing_docs = item["missing_documents"] or []
            if missing_docs:
                actions.append({
                    "id": f"docs-{item['id']}",
                    "title": f"Documents Required: {item['practice_name']}",
                    "description": f"Please upload: {', '.join(missing_docs[:3])}{'...' if len(missing_docs) > 3 else ''}",
                    "priority": "high" if item["status"] == "waiting_documents" else "medium",
                    "type": "missing_documents",
                    "href": "/portal/documents",
                })
                action_id += 1
                if action_id > 5:  # Max 5 actions
                    break

        return actions

    # ================================================
    # VISA & IMMIGRATION
    # ================================================

    async def get_visa_status(self, client_id: int) -> dict[str, Any]:
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
                "SELECT id FROM clients WHERE id = $1",
                client_id,
            )
            if not client:
                raise ValueError(f"Client {client_id} not found")

            # Get current visa practice (completed, not expired)
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

            # Get visa history (all visa practices)
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

            # Get immigration documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_size_kb, d.created_at
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

                visa_type = f"{current_visa['code']} - {current_visa['type_name']}" if current_visa["code"] else current_visa["type_name"]

                current = {
                    "type": visa_type,
                    "status": status,
                    "issueDate": current_visa["completion_date"].strftime("%d %b %Y") if current_visa["completion_date"] else "-",
                    "expiryDate": current_visa["expiry_date"].strftime("%d %b %Y") if current_visa["expiry_date"] else "-",
                    "daysRemaining": max(0, days_left),
                    "permitNumber": f"KITAS-{current_visa['id']:06d}",  # Generated permit number
                    "sponsor": "Bali Zero Indonesia",  # Default sponsor
                }

            # Build history response (matching frontend VisaHistoryItem)
            history = []
            for v in visa_history:
                # Determine period string
                start = v["start_date"].strftime("%b %Y") if v["start_date"] else ""
                end = v["expiry_date"].strftime("%b %Y") if v["expiry_date"] else v["completion_date"].strftime("%b %Y") if v["completion_date"] else ""
                period = f"{start} - {end}" if start and end else start or end or "-"

                # Map status to frontend expected values
                if v["status"] == "completed":
                    hist_status = "completed"
                else:
                    hist_status = "expired"

                history.append({
                    "id": str(v["id"]),
                    "type": f"{v['code']} - {v['name']}" if v["code"] else v["name"],
                    "period": period,
                    "status": hist_status,
                })

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

                doc_list.append({
                    "id": str(d["id"]),
                    "name": d["file_name"],
                    "type": d["document_type"],
                    "category": category_map.get(d["document_type"], "Other"),
                    "status": status_map.get(d["status"], "pending"),
                    "uploadDate": d["created_at"].strftime("%d %b %Y") if d["created_at"] else "-",
                    "expiryDate": d["expiry_date"].strftime("%d %b %Y") if d["expiry_date"] else None,
                    "size": f"{d['file_size_kb']} KB" if d["file_size_kb"] else "-",
                    "downloadUrl": d["file_url"] if d["status"] in ("verified", "issued") else None,
                })

            return {
                "current": current,
                "history": history,
                "documents": doc_list,
            }

    # ================================================
    # COMPANIES
    # ================================================

    async def get_companies(self, client_id: int) -> list[dict[str, Any]]:
        """Get all companies associated with client."""
        async with self.pool.acquire() as conn:
            companies = await conn.fetch(
                """
                SELECT cc.id, cc.role, cc.is_primary, cc.created_at,
                       cp.id as company_id, cp.company_name, cp.entity_type,
                       cp.industry, cp.annual_revenue
                FROM client_companies cc
                JOIN company_profiles cp ON cp.id = cc.company_id
                WHERE cc.client_id = $1
                ORDER BY cc.is_primary DESC, cc.created_at
                """,
                client_id,
            )

            return [
                {
                    "id": c["id"],
                    "company_id": c["company_id"],
                    "name": c["company_name"],
                    "type": c["entity_type"],
                    "industry": c["industry"],
                    "role": c["role"],
                    "is_primary": c["is_primary"],
                }
                for c in companies
            ]

    async def get_company_detail(
        self, client_id: int, company_id: int
    ) -> dict[str, Any]:
        """Get detailed company information."""
        async with self.pool.acquire() as conn:
            # Verify client owns this company
            ownership = await conn.fetchrow(
                """
                SELECT cc.role, cc.is_primary
                FROM client_companies cc
                WHERE cc.client_id = $1 AND cc.company_id = $2
                """,
                client_id,
                company_id,
            )
            if not ownership:
                raise ValueError("Company not found or not accessible")

            # Get company profile
            company = await conn.fetchrow(
                """
                SELECT * FROM company_profiles WHERE id = $1
                """,
                company_id,
            )

            # Get company practices (licenses, registrations)
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

            # Get company documents
            documents = await conn.fetch(
                """
                SELECT d.id, d.document_type, d.file_name, d.status, d.file_url
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

            return {
                "id": company["id"],
                "name": company["company_name"],
                "type": company["entity_type"],
                "industry": company["industry"],
                "ownership": {
                    "role": ownership["role"],
                    "is_primary": ownership["is_primary"],
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
                        "downloadable": d["status"] in ("verified", "issued") and d["file_url"] is not None,
                    }
                    for d in documents
                ],
            }

    async def set_primary_company(
        self, client_id: int, company_id: int
    ) -> dict[str, Any]:
        """Set a company as primary for the client."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Clear previous primary
                await conn.execute(
                    """
                    UPDATE client_companies
                    SET is_primary = false
                    WHERE client_id = $1
                    """,
                    client_id,
                )

                # Set new primary
                result = await conn.execute(
                    """
                    UPDATE client_companies
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

    async def get_tax_overview(self, client_id: int) -> dict[str, Any]:
        """Get tax overview and upcoming deadlines."""
        async with self.pool.acquire() as conn:
            # Get client's companies for tax context
            companies = await conn.fetch(
                """
                SELECT cp.id, cp.company_name, cp.entity_type
                FROM client_companies cc
                JOIN company_profiles cp ON cp.id = cc.company_id
                WHERE cc.client_id = $1
                """,
                client_id,
            )

            # Get tax-related practices
            tax_practices = await conn.fetch(
                """
                SELECT p.id, pt.code, pt.name, p.status, p.expiry_date
                FROM practices p
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE p.client_id = $1
                AND pt.category = 'tax'
                ORDER BY p.expiry_date ASC NULLS LAST
                """,
                client_id,
            )

            # Generate tax deadlines
            today = datetime.now(timezone.utc)
            deadlines = self._get_standard_tax_deadlines(today)

            return {
                "companies": [
                    {
                        "id": c["id"],
                        "name": c["company_name"],
                        "type": c["entity_type"],
                    }
                    for c in companies
                ],
                "deadlines": deadlines,
                "services": [
                    {
                        "id": p["id"],
                        "code": p["code"],
                        "name": p["name"],
                        "status": p["status"],
                    }
                    for p in tax_practices
                ],
            }

    # ================================================
    # DOCUMENTS
    # ================================================

    async def get_documents(
        self, client_id: int, document_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all client-visible documents."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT d.id, d.document_type, d.file_name, d.status,
                       d.expiry_date, d.file_url, d.file_size_kb, d.created_at,
                       p.id as practice_id, pt.name as practice_name
                FROM documents d
                LEFT JOIN practices p ON p.id = d.practice_id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE d.client_id = $1
                AND d.client_visible = true
            """
            params = [client_id]

            if document_type:
                query += " AND d.document_type = $2"
                params.append(document_type)

            query += " ORDER BY d.created_at DESC"

            documents = await conn.fetch(query, *params)

            return [
                {
                    "id": d["id"],
                    "type": d["document_type"],
                    "name": d["file_name"],
                    "status": d["status"],
                    "expiry_date": d["expiry_date"].isoformat() if d["expiry_date"] else None,
                    "size_kb": d["file_size_kb"],
                    "practice_id": d["practice_id"],
                    "practice_name": d["practice_name"],
                    "downloadable": d["status"] in ("verified", "issued") and d["file_url"] is not None,
                    "created_at": d["created_at"].isoformat(),
                }
                for d in documents
            ]

    async def upload_document(
        self,
        client_id: int,
        file_content: bytes,
        file_name: str,
        document_type: str,
        mime_type: str | None = None,
        practice_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Upload a document for a client.

        For MVP, stores metadata in DB. File storage can be enhanced later
        to use Google Drive or S3.
        """
        async with self.pool.acquire() as conn:
            # Calculate file size
            file_size_kb = len(file_content) // 1024

            # Verify practice belongs to client if provided
            if practice_id:
                practice = await conn.fetchrow(
                    "SELECT id FROM practices WHERE id = $1 AND client_id = $2",
                    practice_id,
                    client_id,
                )
                if not practice:
                    raise ValueError("Practice not found or not accessible")

            # Get client email for uploaded_by
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1",
                client_id,
            )

            # Insert document record
            doc = await conn.fetchrow(
                """
                INSERT INTO documents (
                    client_id, practice_id, document_type, file_name,
                    status, uploaded_by, file_size_kb, mime_type,
                    storage_type, client_visible
                )
                VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7, 'pending', true)
                RETURNING id, document_type, file_name, status, created_at
                """,
                client_id,
                practice_id,
                document_type,
                file_name,
                client["email"],
                file_size_kb,
                mime_type,
            )

            logger.info(
                f"Document uploaded: {file_name} for client {client_id}, "
                f"size: {file_size_kb}KB, type: {document_type}"
            )

            # TODO: Store file content to Google Drive or S3
            # For now, just record the metadata

            return {
                "id": doc["id"],
                "type": doc["document_type"],
                "name": doc["file_name"],
                "status": doc["status"],
                "size_kb": file_size_kb,
                "created_at": doc["created_at"].isoformat(),
            }

    # ================================================
    # MESSAGES
    # ================================================

    async def get_messages(
        self,
        client_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get message threads for client."""
        async with self.pool.acquire() as conn:
            messages = await conn.fetch(
                """
                SELECT m.id, m.subject, m.content, m.direction, m.sent_by,
                       m.read_at, m.created_at, m.practice_id,
                       p.id as practice_id, pt.name as practice_name
                FROM portal_messages m
                LEFT JOIN practices p ON p.id = m.practice_id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE m.client_id = $1
                ORDER BY m.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                client_id,
                limit,
                offset,
            )

            total = await conn.fetchval(
                "SELECT COUNT(*) FROM portal_messages WHERE client_id = $1",
                client_id,
            )

            unread = await conn.fetchval(
                """
                SELECT COUNT(*) FROM portal_messages
                WHERE client_id = $1
                AND direction = 'team_to_client'
                AND read_at IS NULL
                """,
                client_id,
            )

            return {
                "messages": [
                    {
                        "id": m["id"],
                        "subject": m["subject"],
                        "content": m["content"],
                        "from_team": m["direction"] == "team_to_client",
                        "sent_by": m["sent_by"],
                        "is_read": m["read_at"] is not None,
                        "practice_id": m["practice_id"],
                        "practice_name": m["practice_name"],
                        "created_at": m["created_at"].isoformat(),
                    }
                    for m in messages
                ],
                "total": total,
                "unread_count": unread,
            }

    async def send_message(
        self,
        client_id: int,
        content: str,
        subject: str | None = None,
        practice_id: int | None = None,
    ) -> dict[str, Any]:
        """Send a message from client to team."""
        async with self.pool.acquire() as conn:
            # Get client email for sent_by
            client = await conn.fetchrow(
                "SELECT email FROM clients WHERE id = $1",
                client_id,
            )

            message = await conn.fetchrow(
                """
                INSERT INTO portal_messages (
                    client_id, practice_id, subject, direction, content, sent_by
                )
                VALUES ($1, $2, $3, 'client_to_team', $4, $5)
                RETURNING id, created_at
                """,
                client_id,
                practice_id,
                subject,
                content,
                client["email"],
            )

            return {
                "id": message["id"],
                "created_at": message["created_at"].isoformat(),
            }

    async def mark_message_read(
        self, client_id: int, message_id: int
    ) -> dict[str, Any]:
        """Mark a message as read."""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE portal_messages
                SET read_at = NOW()
                WHERE id = $1 AND client_id = $2 AND read_at IS NULL
                """,
                message_id,
                client_id,
            )

            return {"success": result != "UPDATE 0"}

    # ================================================
    # PREFERENCES
    # ================================================

    async def get_preferences(self, client_id: int) -> dict[str, Any]:
        """Get client preferences."""
        async with self.pool.acquire() as conn:
            prefs = await conn.fetchrow(
                """
                SELECT email_notifications, whatsapp_notifications,
                       language, timezone
                FROM client_preferences
                WHERE client_id = $1
                """,
                client_id,
            )

            if not prefs:
                # Return defaults
                return {
                    "email_notifications": True,
                    "whatsapp_notifications": True,
                    "language": "en",
                    "timezone": "Asia/Jakarta",
                }

            return {
                "email_notifications": prefs["email_notifications"],
                "whatsapp_notifications": prefs["whatsapp_notifications"],
                "language": prefs["language"],
                "timezone": prefs["timezone"],
            }

    async def update_preferences(
        self,
        client_id: int,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        """Update client preferences."""
        async with self.pool.acquire() as conn:
            # Build dynamic update
            updates = []
            params = [client_id]
            param_idx = 2

            allowed_fields = {
                "email_notifications": bool,
                "whatsapp_notifications": bool,
                "language": str,
                "timezone": str,
            }

            for field, field_type in allowed_fields.items():
                if field in preferences:
                    updates.append(f"{field} = ${param_idx}")
                    params.append(preferences[field])
                    param_idx += 1

            if not updates:
                return await self.get_preferences(client_id)

            # Upsert preferences
            await conn.execute(
                f"""
                INSERT INTO client_preferences (client_id, {', '.join(allowed_fields.keys())})
                VALUES ($1, true, true, 'en', 'Asia/Jakarta')
                ON CONFLICT (client_id) DO UPDATE
                SET {', '.join(updates)}
                """,
                *params,
            )

            return await self.get_preferences(client_id)

    # ================================================
    # HELPER METHODS
    # ================================================

    def _format_visa_summary(self, visa: asyncpg.Record) -> dict[str, Any]:
        """Format visa practice as summary."""
        today = datetime.now(timezone.utc).date()
        expiry = visa["expiry_date"].date() if visa["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        return {
            "type": visa["code"],
            "name": visa["name"],
            "status": visa["status"],
            "expiry_date": visa["expiry_date"].isoformat() if visa["expiry_date"] else None,
            "days_remaining": days_left,
            "is_expiring_soon": days_left is not None and days_left <= 90,
        }

    def _format_visa_detail(self, visa: asyncpg.Record) -> dict[str, Any]:
        """Format visa practice as detailed view."""
        today = datetime.now(timezone.utc).date()
        expiry = visa["expiry_date"].date() if visa["expiry_date"] else None
        days_left = (expiry - today).days if expiry else None

        return {
            "id": visa["id"],
            "type": visa["code"],
            "name": visa["type_name"],
            "status": visa["status"],
            "start_date": visa["start_date"].isoformat() if visa["start_date"] else None,
            "expiry_date": visa["expiry_date"].isoformat() if visa["expiry_date"] else None,
            "days_remaining": days_left,
        }

    def _format_visa_case(self, case: asyncpg.Record) -> dict[str, Any]:
        """Format active visa case."""
        return {
            "id": case["id"],
            "name": case["name"],
            "status": case["status"],
            "start_date": case["start_date"].isoformat() if case["start_date"] else None,
            "progress": self._status_to_progress(case["status"]),
        }

    def _format_case_progress(self, case: asyncpg.Record) -> dict[str, Any]:
        """Format case with progress percentage."""
        return {
            "id": case["id"],
            "name": case["name"],
            "status": case["status"],
            "progress": self._status_to_progress(case["status"]),
            "payment_status": case["payment_status"],
        }

    def _status_to_progress(self, status: str) -> int:
        """Convert status to progress percentage."""
        progress_map = {
            "inquiry": 10,
            "quotation_sent": 20,
            "payment_pending": 30,
            "in_progress": 50,
            "waiting_documents": 40,
            "submitted_to_gov": 70,
            "approved": 90,
            "completed": 100,
        }
        return progress_map.get(status, 0)

    def _get_standard_tax_deadlines(
        self, today: datetime
    ) -> list[dict[str, Any]]:
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
        deadlines.append({
            "type": "PPh 21/23/4(2)",
            "period": f"{pph_date.strftime('%b %Y')}",
            "due_date": pph_date.isoformat(),
            "days_until": days_until,
            "urgency": "urgent" if days_until <= 14 else "warning" if days_until <= 30 else "normal",
        })

        # PPN (VAT) - End of following month
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        # Last day of next month
        if next_month == 12:
            ppn_date = datetime(next_year, 12, 31, tzinfo=timezone.utc)
        else:
            ppn_date = datetime(next_year, next_month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)

        days_until = (ppn_date.date() - today.date()).days
        deadlines.append({
            "type": "PPN (VAT)",
            "period": f"{ppn_date.strftime('%b %Y')}",
            "due_date": ppn_date.isoformat(),
            "days_until": days_until,
            "urgency": "urgent" if days_until <= 14 else "warning" if days_until <= 30 else "normal",
        })

        # Annual SPT - March 31
        spt_date = datetime(year, 3, 31, tzinfo=timezone.utc)
        if spt_date <= today:
            spt_date = datetime(year + 1, 3, 31, tzinfo=timezone.utc)
        days_until = (spt_date.date() - today.date()).days
        deadlines.append({
            "type": "Annual SPT",
            "period": str(spt_date.year - 1),
            "due_date": spt_date.isoformat(),
            "days_until": days_until,
            "urgency": "urgent" if days_until <= 14 else "warning" if days_until <= 30 else "normal",
        })

        # Sort by days_until
        deadlines.sort(key=lambda x: x["days_until"])

        return deadlines
