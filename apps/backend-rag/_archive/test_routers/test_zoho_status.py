"""Check Zoho OAuth status."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/zoho-status")
async def test_zoho_status():
    """Check Zoho OAuth tokens status."""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        # Check zoho_email_tokens
        rows = await pool.fetch("""
            SELECT user_id, account_id, email_address, token_expires_at
            FROM zoho_email_tokens
            ORDER BY token_expires_at DESC
            LIMIT 10
        """)

        # Check which Zoho tables exist
        tables = await pool.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%zoho%'
        """)

        await pool.close()

        return {
            "zoho_tables_found": [r["table_name"] for r in tables],
            "zoho_email_tokens": [dict(r) for r in rows] if rows else [],
            "count_email_tokens": len(rows) if rows else 0,
        }
    except Exception as e:
        return {"error": str(e)}
