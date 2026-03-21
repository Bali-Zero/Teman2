"""
Omnichannel Workflow Router - Business Intelligence & Actions
"""

import logging

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])

# --- SCHEMAS ---


class AssignmentRequest(BaseModel):
    assigned_to: str  # Email or ID


class StatusRequest(BaseModel):
    status: str  # open, pending, closed


class NoteRequest(BaseModel):
    content: str
    author_id: str
    author_name: str | None = "Team Member"


# --- UTILS ---


async def ensure_schema(db: Pool):
    """Ensure workflow columns and tables exist (Self-healing schema)"""
    try:
        async with db.acquire() as conn:
            # Check conversations columns
            await conn.execute("""
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'open';
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'medium';
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255);
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE conversations ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0;

                CREATE TABLE IF NOT EXISTS conversation_notes (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                    author_id VARCHAR(255),
                    author_name VARCHAR(255),
                    content TEXT NOT NULL,
                    is_system_note BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
    except Exception as e:
        logger.error(f"Schema update failed: {e}")


# --- ENDPOINTS ---


@router.get("/conversations/{id}/enrichment")
async def get_conversation_enrichment(id: int, db: Pool = Depends(get_database)):
    """
    Looks up the lead in the CRM and returns business intelligence.
    """
    await ensure_schema(db)
    async with db.acquire() as conn:
        # 1. Get conversation phone
        conv = await conn.fetchrow(
            "SELECT session_id, user_id FROM conversations WHERE id = $1", id
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Extract phone from session_id (wa_session_62xxx) or user_id
        session_id = conv["session_id"] or ""
        phone = (
            session_id.replace("wa_session_", "")
            .replace("tg_session_", "")
            .replace("ig_session_", "")
        )

        # 2. Lookup in CRM
        # We try to match by phone or whatsapp
        client = await conn.fetchrow(
            "SELECT full_name, email, status, client_type, nationality, notes, tags, last_interaction_date "
            "FROM clients "
            "WHERE phone LIKE $1 OR whatsapp LIKE $1 OR phone LIKE $2 OR whatsapp LIKE $2 LIMIT 1",
            f"%{phone}%",
            phone[-8:],  # Match last 8 digits for flexibility
        )

        # 3. Lookup Practice/Deal info
        practices = []
        if client:
            client_id = await conn.fetchval(
                "SELECT id FROM clients WHERE email = $1 OR phone = $2", client["email"], phone
            )
            practices_rows = await conn.fetch(
                "SELECT p.status, p.quoted_price, pt.name as practice_name "
                "FROM practices p JOIN practice_types pt ON p.practice_type_id = pt.id "
                "WHERE p.client_id = $1 LIMIT 5",
                client_id,
            )
            practices = [dict(r) for r in practices_rows]

        return {
            "exists_in_crm": bool(client),
            "profile": dict(client) if client else None,
            "practices": practices,
            "suggested_actions": ["Create Deal", "Assign to Sales"]
            if not client
            else ["Follow up on Practice"],
        }


@router.patch("/conversations/{id}/assign")
async def assign_conversation(id: int, req: AssignmentRequest, db: Pool = Depends(get_database)):
    await ensure_schema(db)
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET assigned_to = $1, status = 'open' WHERE id = $2",
            req.assigned_to,
            id,
        )
        # Add a system note
        await conn.execute(
            "INSERT INTO conversation_notes (conversation_id, content, is_system_note) VALUES ($1, $2, TRUE)",
            id,
            f"Conversation assigned to {req.assigned_to}",
        )
        return {"status": "success"}


@router.patch("/conversations/{id}/status")
async def update_conversation_status(id: int, req: StatusRequest, db: Pool = Depends(get_database)):
    await ensure_schema(db)
    async with db.acquire() as conn:
        await conn.execute("UPDATE conversations SET status = $1 WHERE id = $2", req.status, id)
        return {"status": "success"}


@router.get("/conversations/{id}/notes")
async def get_conversation_notes(id: int, db: Pool = Depends(get_database)):
    await ensure_schema(db)
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM conversation_notes WHERE conversation_id = $1 ORDER BY created_at DESC",
            id,
        )
        return [dict(r) for r in rows]


@router.post("/conversations/{id}/notes")
async def add_conversation_note(id: int, req: NoteRequest, db: Pool = Depends(get_database)):
    await ensure_schema(db)
    async with db.acquire() as conn:
        await conn.execute(
            "INSERT INTO conversation_notes (conversation_id, author_id, author_name, content) VALUES ($1, $2, $3, $4)",
            id,
            req.author_id,
            req.author_name,
            req.content,
        )
        return {"status": "success"}
