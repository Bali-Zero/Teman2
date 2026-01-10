"""
ZANTARA CRM - Interactions Tracking Router
Endpoints for logging and retrieving team-client interactions

Refactored: Migrated to asyncpg with connection pooling (2025-12-07)
"""

from datetime import datetime
from typing import Any

import asyncpg
from core.cache import cached
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, field_validator

from app.dependencies import get_current_user, get_database_pool
from app.utils.crm_utils import is_crm_admin
from app.utils.error_handlers import handle_database_error
from app.utils.logging_utils import get_logger, log_database_operation, log_success

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm/interactions", tags=["crm-interactions"])

# Constants
MAX_LIMIT = 200
DEFAULT_LIMIT = 50
CACHE_TTL_STATS_SECONDS = 300  # 5 minutes
INTERACTION_TYPES = {"chat", "email", "whatsapp", "call", "meeting", "note"}
SENTIMENT_VALUES = {"positive", "neutral", "negative", "urgent"}
DEFAULT_RECENT_DAYS = 7  # Default days for "recent" queries
MAX_RECENT_DAYS = 30  # Maximum days for "recent" queries
SUMMARY_MAX_LENGTH = 200  # Max length for auto-generated summaries


# ================================================
# PYDANTIC MODELS
# ================================================


class InteractionCreate(BaseModel):
    client_id: int | None = None
    practice_id: int | None = None
    conversation_id: int | None = None
    interaction_type: str  # 'chat', 'email', 'whatsapp', 'call', 'meeting', 'note'
    channel: str | None = None  # 'web_chat', 'gmail', 'whatsapp', 'phone', 'in_person'
    subject: str | None = None
    summary: str | None = None  # AI-generated or manual
    full_content: str | None = None
    sentiment: str | None = None  # 'positive', 'neutral', 'negative', 'urgent'
    team_member: str  # who handled this
    direction: str = "inbound"  # 'inbound' or 'outbound'
    duration_minutes: int | None = None
    extracted_entities: dict = {}
    action_items: list[dict] = []

    @field_validator("interaction_type")
    @classmethod
    def validate_interaction_type(cls, v: str) -> str:
        """Validate interaction_type is one of allowed values"""
        if v not in INTERACTION_TYPES:
            raise ValueError(f"interaction_type must be one of {INTERACTION_TYPES}, got '{v}'")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str | None) -> str | None:
        """Validate channel if provided"""
        if v is not None:
            allowed_channels = {"web_chat", "gmail", "whatsapp", "phone", "in_person"}
            if v not in allowed_channels:
                raise ValueError(f"channel must be one of {allowed_channels}, got '{v}'")
        return v

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str | None) -> str | None:
        """Validate sentiment is one of allowed values"""
        if v is not None and v not in SENTIMENT_VALUES:
            raise ValueError(f"sentiment must be one of {SENTIMENT_VALUES}, got '{v}'")
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        """Validate direction is inbound or outbound"""
        allowed_directions = {"inbound", "outbound"}
        if v not in allowed_directions:
            raise ValueError(f"direction must be one of {allowed_directions}, got '{v}'")
        return v

    @field_validator("team_member")
    @classmethod
    def validate_team_member(cls, v: str) -> str:
        """Validate team_member is not empty"""
        if not v or not v.strip():
            raise ValueError("team_member cannot be empty")
        return v.strip()

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int | None) -> int | None:
        """Validate duration_minutes is non-negative"""
        if v is not None and v < 0:
            raise ValueError("duration_minutes must be non-negative")
        return v


class InteractionResponse(BaseModel):
    id: int
    client_id: int | None
    practice_id: int | None
    interaction_type: str
    channel: str | None
    subject: str | None
    summary: str | None
    team_member: str
    direction: str
    sentiment: str | None
    interaction_date: datetime
    created_at: datetime


# ================================================
# ENDPOINTS
# ================================================


@router.post("/", response_model=InteractionResponse)
async def create_interaction(
    interaction: InteractionCreate,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Log a new interaction

    **Types:**
    - chat: Web chat conversation
    - email: Email exchange
    - whatsapp: WhatsApp message
    - call: Phone call
    - meeting: In-person or video meeting
    - note: Internal note/comment

    **Channels:**
    - web_chat: ZANTARA chat widget
    - gmail: Gmail integration
    - whatsapp: WhatsApp Business
    - phone: Phone call
    - in_person: Face-to-face meeting
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    # RBAC: If client_id provided, check access
    if interaction.client_id:
        async with db_pool.acquire() as conn:
            check = await conn.fetchrow(
                "SELECT assigned_to FROM clients WHERE id = $1", interaction.client_id
            )
            if not check:
                raise HTTPException(status_code=404, detail="Client not found")
            if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
                raise HTTPException(status_code=403, detail="You don't have access to this client")
    try:
        async with db_pool.acquire() as conn:
            # Insert interaction
            # Note: 'type' and 'content' are legacy NOT NULL columns that must be populated
            content_value = interaction.summary or interaction.subject or "Interaction"
            row = await conn.fetchrow(
                """
                INSERT INTO interactions (
                    client_id, practice_id, conversation_id,
                    type, interaction_type, channel,
                    content, subject, summary, full_content,
                    sentiment, team_member, direction,
                    duration_minutes, extracted_entities, action_items, interaction_date
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
                )
                RETURNING *
                """,
                interaction.client_id,
                interaction.practice_id,
                interaction.conversation_id,
                interaction.interaction_type,  # type (legacy NOT NULL column)
                interaction.interaction_type,
                interaction.channel,
                content_value,  # content (legacy NOT NULL column)
                interaction.subject,
                interaction.summary,
                interaction.full_content,
                interaction.sentiment,
                interaction.team_member,
                interaction.direction,
                interaction.duration_minutes,
                interaction.extracted_entities,
                interaction.action_items,
                datetime.now(),
            )

            if not row:
                raise HTTPException(status_code=500, detail="Failed to create interaction")

            new_interaction = dict(row)

            # Update client's last_interaction_date if client_id provided
            if interaction.client_id:
                await conn.execute(
                    """
                    UPDATE clients
                    SET last_interaction_date = NOW()
                    WHERE id = $1
                    """,
                    interaction.client_id,
                )

            log_success(
                logger,
                f"Logged {interaction.interaction_type} interaction",
                interaction_id=new_interaction["id"],
                team_member=interaction.team_member,
            )
            log_database_operation(
                logger, "CREATE", "interactions", record_id=new_interaction["id"]
            )

            return InteractionResponse(**new_interaction)

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/", response_model=list[dict])
async def list_interactions(
    client_id: int | None = Query(None, description="Filter by client"),
    practice_id: int | None = Query(None, description="Filter by practice"),
    team_member: str | None = Query(None, description="Filter by team member"),
    interaction_type: str | None = Query(None, description="Filter by type"),
    sentiment: str | None = Query(None, description="Filter by sentiment"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    # Support for direct calls from dashboard_summary.py
    user_id: str | None = None,
    pool: Any | None = None,
):
    """
    List interactions with optional filtering
    """
    # Use provided pool if called directly
    if pool:
        db_pool = pool

    # If called directly, we might not have current_user, but we have user_id
    if user_id and not current_user:
        user_email = user_id.lower()
        user_is_admin = user_email in ["zero@balizero.com", "admin@zantara.io"]
    else:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)
    try:
        async with db_pool.acquire() as conn:
            # Build query dynamically with explicit columns
            query_parts = [
                """SELECT i.id, i.client_id, i.practice_id, i.conversation_id, i.interaction_type, i.channel,
                   i.subject, i.summary, i.full_content, i.sentiment, i.team_member, i.direction,
                   i.duration_minutes, i.extracted_entities, i.action_items, i.interaction_date, i.created_at
                   FROM interactions i
                   LEFT JOIN clients c ON i.client_id = c.id
                   WHERE 1=1"""
            ]
            params: list[Any] = []
            param_index = 1

            # RBAC: Non-admins can only see interactions for their assigned clients or their own interactions
            if not user_is_admin:
                query_parts.append(
                    f" AND (LOWER(c.assigned_to) = ${param_index} OR LOWER(i.team_member) = ${param_index})"
                )
                params.append(user_email)
                param_index += 1

            if client_id:
                query_parts.append(f" AND client_id = ${param_index}")
                params.append(client_id)
                param_index += 1

            if practice_id:
                query_parts.append(f" AND practice_id = ${param_index}")
                params.append(practice_id)
                param_index += 1

            if team_member:
                query_parts.append(f" AND team_member = ${param_index}")
                params.append(team_member)
                param_index += 1

            if interaction_type:
                query_parts.append(f" AND interaction_type = ${param_index}")
                params.append(interaction_type)
                param_index += 1

            if sentiment:
                query_parts.append(f" AND sentiment = ${param_index}")
                params.append(sentiment)
                param_index += 1

            query_parts.append(
                f" ORDER BY interaction_date DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
            )
            params.extend([limit, offset])

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            return [dict(row) for row in rows]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/{interaction_id}")
async def get_interaction(
    interaction_id: int = Path(..., gt=0, description="Interaction ID"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get full interaction details by ID"""
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    i.*,
                    c.full_name as client_name,
                    c.email as client_email
                FROM interactions i
                LEFT JOIN clients c ON i.client_id = c.id
                WHERE i.id = $1
                """,
                interaction_id,
            )

            if not row:
                raise HTTPException(status_code=404, detail="Interaction not found")

            # RBAC check
            if not user_is_admin:
                if (row["assigned_to"] or "").lower() != user_email and (
                    row["team_member"] or ""
                ).lower() != user_email:
                    raise HTTPException(
                        status_code=403, detail="You don't have access to this interaction"
                    )

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/client/{client_id}/timeline")
async def get_client_timeline(
    client_id: int = Path(..., gt=0, description="Client ID"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get complete interaction timeline for a client
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    try:
        async with db_pool.acquire() as conn:
            # Check access to client
            check = await conn.fetchrow("SELECT assigned_to FROM clients WHERE id = $1", client_id)
            if not check:
                raise HTTPException(status_code=404, detail="Client not found")

            if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
                raise HTTPException(
                    status_code=403, detail="You don't have access to this client's timeline"
                )

            rows = await conn.fetch(
                """
                SELECT
                    i.*,
                    p.id as practice_id,
                    pt.name as practice_type_name,
                    pt.code as practice_type_code
                FROM interactions i
                LEFT JOIN practices p ON i.practice_id = p.id
                LEFT JOIN practice_types pt ON p.practice_type_id = pt.id
                WHERE i.client_id = $1
                ORDER BY i.interaction_date DESC
                LIMIT $2
                """,
                client_id,
                limit,
            )

            return {
                "client_id": client_id,
                "total_interactions": len(rows),
                "timeline": [dict(row) for row in rows],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/practice/{practice_id}/history")
async def get_practice_history(
    practice_id: int = Path(..., gt=0, description="Practice ID"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Get all interactions related to a specific practice
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    try:
        async with db_pool.acquire() as conn:
            # Check access to practice via client
            check = await conn.fetchrow(
                """
                SELECT c.assigned_to 
                FROM practices p 
                JOIN clients c ON p.client_id = c.id 
                WHERE p.id = $1
            """,
                practice_id,
            )

            if not check:
                raise HTTPException(status_code=404, detail="Practice not found")

            if not user_is_admin and (check["assigned_to"] or "").lower() != user_email:
                raise HTTPException(
                    status_code=403, detail="You don't have access to this practice history"
                )

            rows = await conn.fetch(
                """
                SELECT id, client_id, practice_id, conversation_id, interaction_type, channel,
                       subject, summary, full_content, sentiment, team_member, direction,
                       duration_minutes, extracted_entities, action_items, interaction_date, created_at
                FROM interactions
                WHERE practice_id = $1
                ORDER BY interaction_date DESC
                """,
                practice_id,
            )

            return {
                "practice_id": practice_id,
                "total_interactions": len(rows),
                "history": [dict(row) for row in rows],
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.get("/stats/overview")
@cached(ttl=CACHE_TTL_STATS_SECONDS, prefix="crm_interactions_stats")
async def get_interactions_stats(
    team_member: str | None = Query(None, description="Stats for specific team member"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    # Support for direct calls from dashboard_summary.py
    user_id: str | None = None,
    pool: Any | None = None,
):
    """
    Get interaction statistics

    - Total interactions
    - By type (chat, email, call, etc.)
    - By sentiment
    - By team member

    Performance: Cached for 5 minutes to reduce database load.
    """
    # Use provided pool if called directly
    if pool:
        db_pool = pool

    # If called directly from dashboard_summary, user_id is passed as the first positional arg (team_member)
    # or as a keyword arg. We prioritize it if provided.
    if user_id and not team_member:
        team_member = user_id

    # If called directly, current_user might be None
    if not current_user and team_member:
        # Construct a minimal current_user for is_crm_admin check
        current_user = {"email": team_member}

    # Extract user info for RBAC
    if current_user:
        user_email = current_user.get("email", "").lower()
        user_is_admin = is_crm_admin(current_user)
    else:
        user_email = ""
        user_is_admin = False
    try:
        async with db_pool.acquire() as conn:
            # Build base conditions
            base_where = "WHERE 1=1"
            params: list[Any] = []
            param_index = 1

            # RBAC: Non-admins only see their own interactions or those for their assigned clients
            # This requires a JOIN or a subquery. For stats, let's keep it simple: just their own team_member or assigned clients
            if not user_is_admin:
                base_where += f" AND (LOWER(team_member) = ${param_index} OR client_id IN (SELECT id FROM clients WHERE LOWER(assigned_to) = ${param_index}))"
                params.append(user_email)
                param_index += 1

            if team_member:
                # If non-admin tries to see someone else's stats, limit to what they can see
                if not user_is_admin and team_member.lower() != user_email:
                    base_where += (
                        f" AND LOWER(team_member) = ${param_index} AND FALSE"  # Effectively denied
                    )
                else:
                    base_where += f" AND LOWER(team_member) = ${param_index}"
                params.append(team_member.lower())
                param_index += 1

            # By type - base_where is built internally, values are parameterized
            # nosemgrep: sqlalchemy-execute-raw-query
            type_query = f"""
                SELECT interaction_type, COUNT(*) as count
                FROM interactions
                {base_where}
                GROUP BY interaction_type
            """
            by_type_rows = await conn.fetch(type_query, *params)  # nosemgrep

            # By sentiment - where clause built internally, values parameterized
            sentiment_where = (
                base_where + (" AND" if base_where else "WHERE") + " sentiment IS NOT NULL"
            )
            # nosemgrep: sqlalchemy-execute-raw-query
            sentiment_query = f"""
                SELECT sentiment, COUNT(*) as count
                FROM interactions
                {sentiment_where}
                GROUP BY sentiment
            """
            by_sentiment_rows = await conn.fetch(sentiment_query, *params)  # nosemgrep

            # By team member (if not filtered)
            if not team_member:
                by_team_member_rows = await conn.fetch(
                    """
                    SELECT team_member, COUNT(*) as count
                    FROM interactions
                    GROUP BY team_member
                    ORDER BY count DESC
                    """
                )
            else:
                by_team_member_rows = []

            # Recent activity (last N days) - DEFAULT_RECENT_DAYS is a constant (7)
            recent_where = (
                base_where
                + (" AND" if base_where else "WHERE")
                + f" interaction_date >= NOW() - INTERVAL '1 day' * {DEFAULT_RECENT_DAYS}"
            )
            # nosemgrep: sqlalchemy-execute-raw-query
            recent_query = f"""
                SELECT COUNT(*) as count
                FROM interactions
                {recent_where}
            """
            recent_row = await conn.fetchrow(recent_query, *params)  # nosemgrep

            by_type = {row["interaction_type"]: row["count"] for row in by_type_rows}
            by_sentiment = {row["sentiment"]: row["count"] for row in by_sentiment_rows}
            recent_count = recent_row["count"] if recent_row else 0

            return {
                "total_interactions": sum(by_type.values()),
                "last_7_days": recent_count,
                "by_type": by_type,
                "by_sentiment": by_sentiment,
                "by_team_member": [dict(row) for row in by_team_member_rows]
                if not team_member
                else [],
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


@router.post("/from-conversation")
async def create_interaction_from_conversation(
    conversation_id: int = Query(..., gt=0),
    client_email: str = Query(...),
    team_member: str = Query(...),
    summary: str | None = Query(None, description="AI-generated summary"),
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
):
    """
    Auto-create interaction record from a chat conversation

    This is called automatically when a chat session ends or at intervals
    """
    user_email_from_token = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)

    # RBAC: Only allow if team_member matches current_user or is admin
    if not user_is_admin and team_member.lower() != user_email_from_token:
        raise HTTPException(status_code=403, detail="You can only create interactions for yourself")
    try:
        async with db_pool.acquire() as conn:
            # Get or create client by email
            client_row = await conn.fetchrow(
                "SELECT id FROM clients WHERE email = $1", client_email
            )

            if not client_row:
                # Create new client (prospect)
                new_client_row = await conn.fetchrow(
                    """
                    INSERT INTO clients (full_name, email, status, first_contact_date, created_by)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    client_email.split("@")[0],  # Use email prefix as temp name
                    client_email,
                    "prospect",
                    datetime.now(),
                    team_member,
                )
                if new_client_row:
                    client_row = new_client_row
                    log_success(logger, "Auto-created prospect client", client_email=client_email)

            if not client_row:
                raise HTTPException(status_code=500, detail="Failed to create client")

            client_id = client_row["id"]

            # Get conversation from conversations table
            conv_row = await conn.fetchrow(
                "SELECT messages FROM conversations WHERE id = $1",
                conversation_id,
            )

            full_content = ""
            if conv_row and conv_row.get("messages"):
                # Format messages into readable text
                messages = conv_row["messages"]
                full_content = "\n\n".join(
                    [
                        f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}"
                        for msg in messages
                    ]
                )

            # Auto-generate summary if not provided (take first user message)
            if not summary and conv_row and conv_row.get("messages"):
                first_user_msg = next(
                    (m for m in conv_row["messages"] if m.get("role") == "user"), None
                )
                if first_user_msg:
                    summary = first_user_msg.get("content", "")[:SUMMARY_MAX_LENGTH]

            # Create interaction
            interaction_row = await conn.fetchrow(
                """
                INSERT INTO interactions (
                    client_id, conversation_id, interaction_type, channel,
                    summary, full_content, team_member, direction, interaction_date
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                )
                RETURNING *
                """,
                client_id,
                conversation_id,
                "chat",
                "web_chat",
                summary,
                full_content,
                team_member,
                "inbound",
                datetime.now(),
            )

            if not interaction_row:
                raise HTTPException(status_code=500, detail="Failed to create interaction")

            # Update client last interaction
            await conn.execute(
                """
                UPDATE clients
                SET last_interaction_date = NOW()
                WHERE id = $1
                """,
                client_id,
            )

            log_success(
                logger,
                "Created interaction from conversation",
                conversation_id=conversation_id,
                client_id=client_id,
            )

            return {
                "success": True,
                "interaction_id": interaction_row["id"],
                "client_id": client_id,
                "was_new_client": client_row is not None,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)


# NOTE: Gmail sync endpoint removed - will be replaced by MCP integration


@router.delete("/{interaction_id}")
async def delete_interaction(
    interaction_id: int,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_database_pool),
):
    """
    Delete an interaction (soft delete - marks as archived).
    User must be admin or the creator of the interaction.
    """
    user_email = current_user.get("email", "").lower()
    user_is_admin = is_crm_admin(current_user)
    try:
        async with pool.acquire() as conn:
            # Check if interaction exists and get creator
            existing = await conn.fetchrow(
                "SELECT id, interaction_type, created_by FROM interactions WHERE id = $1",
                interaction_id,
            )
            if not existing:
                raise HTTPException(status_code=404, detail="Interaction not found")

            # RBAC: Non-admins can only delete their own interactions
            if not user_is_admin:
                created_by = (existing.get("created_by") or "").lower()
                if created_by != user_email:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only delete interactions you created"
                    )

            # Delete the interaction
            await conn.execute(
                "DELETE FROM interactions WHERE id = $1",
                interaction_id,
            )

            logger.info(f"Interaction {interaction_id} deleted by {user_email}")

            return {
                "success": True,
                "interaction_id": interaction_id,
                "deleted_by": user_email,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise handle_database_error(e)
