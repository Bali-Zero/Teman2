"""
ZANTARA CRM - Auto-Population Service
Automatically creates/updates clients and practices from chat conversations

REFACTORED 2025-12-07:
- Migrated from psycopg2 to asyncpg with connection pooling
- Uses centralized database pool from app.state (dependency injection)
- Batched queries to reduce N+1 problem
- Improved error handling

REFACTORED 2025-12-07 (Phase 2):
- Removed own connection pool creation
- Uses centralized pool from get_database_pool() dependency
- Better integration with FastAPI dependency injection
"""

import logging
from datetime import datetime

import asyncpg

from app.core.constants import CRMConstants
from services.ai_crm_extractor import get_extractor

logger = logging.getLogger(__name__)


class AutoCRMService:
    """
    Automatically populate CRM from conversations using AI extraction

    Uses centralized asyncpg connection pool via dependency injection.
    No longer creates its own pool - uses app.state.db_pool.
    """

    # Constants (from centralized constants)
    CLIENT_CONFIDENCE_THRESHOLD_CREATE = CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_CREATE
    CLIENT_CONFIDENCE_THRESHOLD_UPDATE = CRMConstants.CLIENT_CONFIDENCE_THRESHOLD_UPDATE
    SUMMARY_MAX_LENGTH = CRMConstants.SUMMARY_MAX_LENGTH

    def __init__(self, ai_client=None, db_pool: asyncpg.Pool | None = None):
        """
        Initialize service

        Args:
            ai_client: Optional AI client for extraction
            db_pool: Optional database pool (if None, will use dependency injection in methods)
        """
        self.extractor = get_extractor(ai_client=ai_client)
        self.pool: asyncpg.Pool | None = db_pool

    async def connect(self):
        """
        Initialize service (no-op for pool, but kept for backward compatibility).

        The pool is now provided via dependency injection or __init__.
        This method is kept for backward compatibility with existing initialization code.
        """
        if self.pool:
            logger.info("✅ AutoCRMService: Using provided database pool")
        else:
            logger.info("✅ AutoCRMService: Will use dependency injection for database pool")

    async def close(self):
        """
        Close service (no-op for pool cleanup).

        The pool is managed by app.state and should not be closed here.
        This method is kept for backward compatibility.
        """
        # Don't close pool - it's managed centrally
        logger.debug("AutoCRMService: close() called (pool managed centrally)")

    async def process_conversation(
        self,
        conversation_id: int,
        messages: list[dict],
        user_email: str | None = None,
        team_member: str = "system",
        db_pool: asyncpg.Pool | None = None,
    ) -> dict:
        """
        Process a conversation and auto-populate CRM

        REFACTORED: Uses centralized asyncpg pool via dependency injection.
        Batched queries to reduce N+1 problem.

        Args:
            conversation_id: ID from conversations table
            messages: List of {role, content} messages
            user_email: Optional known user email
            team_member: Team member who handled conversation
            db_pool: Optional database pool (uses self.pool if not provided)

        Returns:
            {
                "success": bool,
                "client_id": int or None,
                "client_created": bool,
                "client_updated": bool,
                "practice_id": int or None,
                "practice_created": bool,
                "interaction_id": int,
                "extracted_data": dict
            }
        """
        # Use provided pool or instance pool
        pool = db_pool or self.pool

        if not pool:
            logger.error("❌ AutoCRMService: Database pool not available")
            return {
                "success": False,
                "error": "Database pool not available",
                "client_id": None,
                "client_created": False,
                "client_updated": False,
                "practice_id": None,
                "practice_created": False,
                "interaction_id": None,
                "extracted_data": None,
            }

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Step 1: Batch query - Check client and get practice type in parallel
                    # Use extracted email if not provided (will be set after extraction)
                    check_email = user_email

                    # Step 2: Extract data using AI
                    logger.info(f"🧠 Extracting CRM data from conversation {conversation_id}...")

                    # First check if client exists (if email provided)
                    existing_client = None
                    if check_email:
                        existing_client = await conn.fetchrow(
                            "SELECT * FROM clients WHERE email = $1", check_email
                        )

                    extracted = await self.extractor.extract_from_conversation(
                        messages=messages,
                        existing_client_data=dict(existing_client) if existing_client else None,
                    )

                    logger.info(
                        f"📊 Extraction result: client_confidence={extracted['client']['confidence']:.2f}, practice_detected={extracted['practice_intent']['detected']}"
                    )

                    # Use extracted email if not provided
                    if not check_email and extracted["client"]["email"]:
                        check_email = extracted["client"]["email"]

                    # Re-check with extracted email if needed
                    if check_email and not existing_client:
                        existing_client = await conn.fetchrow(
                            "SELECT * FROM clients WHERE email = $1", check_email
                        )

                    # Step 3: Create or update client
                    client_id = None
                    client_created = False
                    client_updated = False

                    if existing_client:
                        # Update existing client if extraction confidence is good
                        client_id = existing_client["id"]

                        if (
                            extracted["client"]["confidence"]
                            >= self.CLIENT_CONFIDENCE_THRESHOLD_UPDATE
                        ):
                            # Build update query dynamically
                            update_fields = []
                            update_values = []

                            for field in ["full_name", "phone", "whatsapp", "nationality"]:
                                extracted_value = extracted["client"].get(field)
                                if extracted_value and not existing_client.get(field):
                                    update_fields.append(f"{field} = ${len(update_values) + 1}")
                                    update_values.append(extracted_value)

                            if update_fields:
                                update_values.append(client_id)
                                # Fields are from hardcoded list, values are parameterized
                                # nosemgrep: sqlalchemy-execute-raw-query
                                update_query = f"""
                                    UPDATE clients
                                    SET {", ".join(update_fields)}, updated_at = NOW()
                                    WHERE id = ${len(update_values)}
                                """
                                await conn.execute(update_query, *update_values)  # nosemgrep
                                client_updated = True
                                logger.info(f"✅ Updated client {client_id} with extracted data")

                    else:
                        # Create new client if we have minimum data
                        if extracted["client"][
                            "confidence"
                        ] >= self.CLIENT_CONFIDENCE_THRESHOLD_CREATE and (
                            extracted["client"]["email"]
                            or extracted["client"]["phone"]
                            or check_email
                        ):
                            client_id = await conn.fetchval(
                                """
                                INSERT INTO clients (
                                    full_name, email, phone, whatsapp, nationality,
                                    status, first_contact_date, created_by, last_interaction_date
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                                RETURNING id
                            """,
                                extracted["client"]["full_name"]
                                or (check_email.split("@")[0] if check_email else "Unknown"),
                                extracted["client"]["email"] or check_email,
                                extracted["client"]["phone"],
                                extracted["client"]["whatsapp"],
                                extracted["client"]["nationality"],
                                "prospect",
                                datetime.now(),
                                team_member,
                                datetime.now(),
                            )
                            client_created = True
                            logger.info(f"✅ Created new client {client_id} from conversation")

                    # Step 4: Create practice if intent detected
                    practice_id = None
                    practice_created = False

                    if client_id and await self.extractor.should_create_practice(extracted):
                        practice_intent = extracted["practice_intent"]

                        # Batch query: Get practice type and check existing practice
                        practice_type = await conn.fetchrow(
                            "SELECT id, base_price FROM practice_types WHERE code = $1",
                            practice_intent["practice_type_code"],
                        )

                        if practice_type:
                            practice_type_id = practice_type["id"]
                            # Convert Decimal to float if needed (asyncpg returns Decimal)
                            base_price = (
                                float(practice_type["base_price"])
                                if practice_type["base_price"]
                                else None
                            )

                            # Check if similar practice already exists (avoid duplicates)
                            existing_practice = await conn.fetchrow(
                                """
                                SELECT id FROM practices
                                WHERE client_id = $1
                                AND practice_type_id = $2
                                AND status IN ('inquiry', 'quotation_sent', 'payment_pending', 'in_progress')
                                AND created_at >= NOW() - INTERVAL '7 days'
                            """,
                                client_id,
                                practice_type_id,
                            )

                            if not existing_practice:
                                # Create new practice
                                practice_id = await conn.fetchval(
                                    """
                                    INSERT INTO practices (
                                        client_id, practice_type_id, status, priority,
                                        quoted_price, notes, inquiry_date, created_by
                                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                                    RETURNING id
                                """,
                                    client_id,
                                    practice_type_id,
                                    "inquiry",
                                    "high" if extracted.get("urgency") == "urgent" else "normal",
                                    base_price,
                                    practice_intent.get("details"),
                                    datetime.now(),
                                    team_member,
                                )
                                practice_created = True
                                logger.info(
                                    f"✅ Created practice {practice_id} ({practice_intent['practice_type_code']})"
                                )
                            else:
                                practice_id = existing_practice["id"]
                                logger.info(f"ℹ️  Practice already exists: {practice_id}")

                    # Step 5: Log interaction and update client in single transaction
                    conversation_summary = extracted.get("summary") or "Chat conversation"
                    full_content = "\n\n".join(
                        [f"{msg['role'].upper()}: {msg['content']}" for msg in messages]
                    )

                    # Insert interaction
                    interaction_id = await conn.fetchval(
                        """
                        INSERT INTO interactions (
                            client_id, practice_id,
                            interaction_type, channel, summary, full_content,
                            sentiment, team_member, direction,
                            extracted_entities, action_items, interaction_date
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        RETURNING id
                    """,
                        client_id,
                        practice_id,
                        "chat",
                        "web_chat",
                        conversation_summary[: self.SUMMARY_MAX_LENGTH],
                        full_content,
                        extracted.get("sentiment"),
                        team_member,
                        "inbound",
                        extracted.get("extracted_entities", {}),
                        extracted.get("action_items", []),
                        datetime.now(),
                    )

                    # Update client last interaction if client exists
                    if client_id:
                        await conn.execute(
                            "UPDATE clients SET last_interaction_date = NOW() WHERE id = $1",
                            client_id,
                        )

                    result = {
                        "success": True,
                        "client_id": client_id,
                        "client_created": client_created,
                        "client_updated": client_updated,
                        "practice_id": practice_id,
                        "practice_created": practice_created,
                        "interaction_id": interaction_id,
                        "extracted_data": extracted,
                    }

                    logger.info(
                        f"✅ Auto-CRM complete: client_id={client_id}, practice_id={practice_id}"
                    )

                    return result

        except Exception as e:
            logger.error(f"❌ Auto-CRM processing failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "client_id": None,
                "client_created": False,
                "client_updated": False,
                "practice_id": None,
                "practice_created": False,
                "interaction_id": None,
                "extracted_data": None,
            }

    async def process_email_interaction(
        self,
        email_data: dict,
        team_member: str = "system",
        db_pool: asyncpg.Pool | None = None,
    ) -> dict:
        """
        Process an incoming email and auto-populate CRM

        REFACTORED: Uses centralized asyncpg pool via dependency injection.

        Args:
            email_data: {subject, sender, body, date, id}
            team_member: Team member handling (system default)
            db_pool: Optional database pool (uses self.pool if not provided)
        """
        # Use provided pool or instance pool
        pool = db_pool or self.pool

        if not pool:
            logger.error("❌ AutoCRMService: Database pool not available")
            return {"success": False, "error": "Database pool not available"}

        # Convert email to message format for extractor
        messages = [
            {"role": "user", "content": f"Subject: {email_data['subject']}\n\n{email_data['body']}"}
        ]

        # Extract sender email from "Name <email@domain.com>" format
        sender_email = email_data["sender"]
        if "<" in sender_email and ">" in sender_email:
            sender_email = sender_email.split("<")[1].split(">")[0]

        try:
            async with pool.acquire() as conn:
                # Create a conversation record for this email thread
                conversation_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, title, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    RETURNING id
                    """,
                    sender_email,
                    f"Email: {email_data['subject']}",
                )

            logger.info(
                f"📧 Processing email from {sender_email} as conversation {conversation_id}"
            )

            return await self.process_conversation(
                conversation_id=conversation_id,
                messages=messages,
                user_email=sender_email,
                team_member=team_member,
                db_pool=pool,
            )

        except Exception as e:
            logger.error(f"❌ Email processing failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# Singleton instance
_auto_crm_instance: AutoCRMService | None = None


def get_auto_crm_service(ai_client=None, db_pool: asyncpg.Pool | None = None) -> AutoCRMService:
    """
    Get or create singleton auto-CRM service instance

    REFACTORED: Now uses centralized database pool via dependency injection.

    Args:
        ai_client: Optional AI client for extraction
        db_pool: Optional database pool (if None, will use dependency injection in methods)

    Returns:
        AutoCRMService instance
    """
    global _auto_crm_instance

    if _auto_crm_instance is None:
        try:
            _auto_crm_instance = AutoCRMService(ai_client=ai_client, db_pool=db_pool)
            logger.info("✅ Auto-CRM Service initialized")
        except Exception as e:
            logger.warning(f"⚠️  Auto-CRM Service not available: {e}")
            raise

    return _auto_crm_instance
