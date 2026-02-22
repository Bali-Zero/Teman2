"""List practices for testing."""
from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/test/list-practices")
async def test_list_practices():
    """List recent practices with client info."""
    import asyncpg
    
    db_url = os.environ.get("DATABASE_URL")
    
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
        
        rows = await pool.fetch("""
            SELECT p.id, p.status, p.quoted_price, c.id as client_id, c.full_name as client_name, c.email as client_email
            FROM practices p
            JOIN clients c ON p.client_id = c.id
            ORDER BY p.id DESC
            LIMIT 10
        """)
        
        await pool.close()
        
        return {
            "practices": [dict(r) for r in rows]
        }
    except Exception as e:
        return {"error": str(e)}
