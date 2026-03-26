"""
Federation Router
Inter-node message bus for Super OpenClaw Federation.
Nodes: pro, air, krisna, damar (extensible)

Auth: JWT (same as CRM — each node uses its own token)
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_current_user_email, get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/federation", tags=["federation"])

VALID_NODES = {"pro", "air", "krisna", "damar", "all"}


# =============================================================================
# Models
# =============================================================================

class SendMessageRequest(BaseModel):
    to_node: str
    body: str
    subject: str | None = None
    message_type: Literal["message", "task", "escalation", "ack"] = "message"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class FederationMessage(BaseModel):
    id: UUID
    from_node: str
    to_node: str
    subject: str | None
    body: str
    message_type: str
    priority: str
    read_at: datetime | None
    created_at: datetime


# =============================================================================
# Helpers
# =============================================================================

def _email_to_node(email: str) -> str:
    """Map user email to federation node ID."""
    mapping = {
        "krisna@balizero.com": "krisna",
        "damar@balizero.com": "damar",
        "zero@balizero.com": "pro",
        "antonellosiano@balizero.com": "air",
        "asya@balizero.com": "asya",
    }
    return mapping.get(email, email.split("@")[0])


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/send", response_model=FederationMessage)
async def send_message(
    req: SendMessageRequest,
    db: asyncpg.Pool = Depends(get_database_pool),
    email: str = Depends(get_current_user_email),
) -> FederationMessage:
    """Send a message from this node to another node (or broadcast to 'all')."""
    if req.to_node not in VALID_NODES:
        raise HTTPException(status_code=400, detail=f"Unknown node: {req.to_node}. Valid: {VALID_NODES}")

    from_node = _email_to_node(email)

    row = await db.fetchrow(
        """
        INSERT INTO federation_messages (from_node, to_node, subject, body, message_type, priority)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, from_node, to_node, subject, body, message_type, priority, read_at, created_at
        """,
        from_node, req.to_node, req.subject, req.body, req.message_type, req.priority,
    )
    logger.info(f"[federation] {from_node} → {req.to_node} ({req.message_type}): {req.subject or req.body[:60]}")
    return FederationMessage(**dict(row))


@router.get("/inbox", response_model=list[FederationMessage])
async def get_inbox(
    unread_only: bool = Query(True),
    limit: int = Query(20, le=100),
    db: asyncpg.Pool = Depends(get_database_pool),
    email: str = Depends(get_current_user_email),
) -> list[FederationMessage]:
    """Get messages for this node (inbox). Includes broadcast messages."""
    node = _email_to_node(email)

    query = """
        SELECT id, from_node, to_node, subject, body, message_type, priority, read_at, created_at
        FROM federation_messages
        WHERE (to_node = $1 OR to_node = 'all')
        {unread_filter}
        ORDER BY created_at DESC
        LIMIT $2
    """
    unread_filter = "AND read_at IS NULL" if unread_only else ""
    rows = await db.fetch(query.format(unread_filter=unread_filter), node, limit)
    return [FederationMessage(**dict(r)) for r in rows]


@router.post("/inbox/read/{message_id}")
async def mark_read(
    message_id: UUID,
    db: asyncpg.Pool = Depends(get_database_pool),
    email: str = Depends(get_current_user_email),
) -> dict:
    """Mark a message as read."""
    node = _email_to_node(email)
    result = await db.execute(
        """
        UPDATE federation_messages
        SET read_at = NOW()
        WHERE id = $1 AND (to_node = $2 OR to_node = 'all') AND read_at IS NULL
        """,
        message_id, node,
    )
    return {"ok": result == "UPDATE 1"}


@router.get("/outbox", response_model=list[FederationMessage])
async def get_outbox(
    limit: int = Query(20, le=100),
    db: asyncpg.Pool = Depends(get_database_pool),
    email: str = Depends(get_current_user_email),
) -> list[FederationMessage]:
    """Get messages sent by this node."""
    node = _email_to_node(email)
    rows = await db.fetch(
        """
        SELECT id, from_node, to_node, subject, body, message_type, priority, read_at, created_at
        FROM federation_messages
        WHERE from_node = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        node, limit,
    )
    return [FederationMessage(**dict(r)) for r in rows]


@router.get("/status")
async def federation_status(
    db: asyncpg.Pool = Depends(get_database_pool),
    _user: dict = Depends(get_current_user),
) -> dict:
    """Get federation overview — unread counts per node."""
    rows = await db.fetch(
        """
        SELECT to_node, COUNT(*) as unread
        FROM federation_messages
        WHERE read_at IS NULL AND to_node != 'all'
        GROUP BY to_node
        """
    )
    broadcast = await db.fetchval(
        "SELECT COUNT(*) FROM federation_messages WHERE to_node = 'all' AND read_at IS NULL"
    )
    return {
        "nodes": {r["to_node"]: r["unread"] for r in rows},
        "broadcast_unread": broadcast,
    }
