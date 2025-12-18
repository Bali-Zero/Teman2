"""
DEBUG endpoint per verificare PostgreSQL
"""
from fastapi import APIRouter, Depends
from app.services.api_key_auth import APIKeyAuth
import asyncpg
from app.core.config import settings

router = APIRouter()
api_key_service = APIKeyAuth()


async def get_current_user(api_key: str):
    """Validate API key"""
    user = api_key_service.validate_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


@router.get("/debug/parent-documents/{document_id}")
async def get_parent_documents(document_id: str):
    """Get parent documents (BAB) from PostgreSQL"""
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        # Query parent_documents table
        rows = await conn.fetch(
            """
            SELECT id, document_id, type, title,
                   char_count, pasal_count,
                   created_at
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
            """,
            document_id
        )

        await conn.close()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "document_id": row["document_id"],
                "type": row["type"],
                "title": row["title"],
                "char_count": row["char_count"],
                "pasal_count": row["pasal_count"],
                "created_at": str(row["created_at"]),
            })

        return {
            "success": True,
            "document_id": document_id,
            "total_bab": len(results),
            "bab_list": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/debug/parent-documents/{document_id}/{bab_id}")
async def get_bab_full_text(document_id: str, bab_id: str):
    """Get full text of a BAB"""
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        row = await conn.fetchrow(
            """
            SELECT id, title, full_text,
                   char_count, pasal_count
            FROM parent_documents
            WHERE document_id = $1 AND id = $2
            """,
            document_id, bab_id
        )

        await conn.close()

        if not row:
            return {"success": False, "error": "BAB not found"}

        return {
            "success": True,
            "id": row["id"],
            "title": row["title"],
            "char_count": row["char_count"],
            "pasal_count": row["pasal_count"],
            "full_text": row["full_text"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
