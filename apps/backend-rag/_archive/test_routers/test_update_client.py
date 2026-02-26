"""Update client email for testing."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/update-client-email")
async def test_update_client_email(client_id: int = 1, email: str = "test@balizero.com"):
    """Update client email for testing."""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

        await pool.execute(
            "UPDATE clients SET email = $1, updated_at = NOW() WHERE id = $2", email, client_id
        )

        # Get client info
        row = await pool.fetchrow(
            "SELECT id, full_name, email FROM clients WHERE id = $1", client_id
        )

        await pool.close()

        return {"success": True, "client": dict(row) if row else None}
    except Exception as e:
        return {"success": False, "error": str(e)}
