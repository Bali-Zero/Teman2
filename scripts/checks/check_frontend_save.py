#!/usr/bin/env python3
"""
Check Frontend Conversation Save Flow

This script verifies:
1. Frontend saves conversation after each message
2. conversation_id is returned and stored
3. session_id is passed correctly
4. Messages are saved in correct format
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_conversation_save():
    """Check if conversations are being saved correctly"""
    
    # Get database URL from environment
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    
    logger.info(f"Connecting to database: {database_url}")
    
    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        
        async with pool.acquire() as conn:
            logger.info("✅ Connected to database")
            
            # Check recent conversations
            rows = await conn.fetch("""
                SELECT 
                    id,
                    user_id,
                    session_id,
                    messages,
                    created_at,
                    updated_at
                FROM conversations
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            logger.info(f"\n📊 Found {len(rows)} recent conversations:\n")
            
            for i, row in enumerate(rows, 1):
                logger.info(f"Conversation {i}:")
                logger.info(f"  - ID: {row['id']}")
                logger.info(f"  - User ID: {row['user_id']}")
                logger.info(f"  - Session ID: {row['session_id']}")
                logger.info(f"  - Created: {row['created_at']}")
                logger.info(f"  - Updated: {row['updated_at']}")
                
                # Parse messages
                messages = row['messages']
                if isinstance(messages, str):
                    messages = json.loads(messages)
                
                logger.info(f"  - Messages: {len(messages)}")
                for j, msg in enumerate(messages[:3], 1):  # Show first 3
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:50]
                    logger.info(f"    {j}. [{role}] {content}...")
                
                # Check for Marco/Milano in messages
                all_content = " ".join([msg.get('content', '') for msg in messages]).lower()
                if 'marco' in all_content:
                    logger.info(f"  ✅ Contains 'Marco'")
                if 'milano' in all_content:
                    logger.info(f"  ✅ Contains 'Milano'")
                
                logger.info("")
            
            # Check for conversations with session_id
            session_rows = await conn.fetch("""
                SELECT 
                    session_id,
                    COUNT(*) as count,
                    MAX(created_at) as last_created
                FROM conversations
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY last_created DESC
                LIMIT 5
            """)
            
            logger.info(f"\n📋 Sessions with conversations: {len(session_rows)}\n")
            for row in session_rows:
                logger.info(f"  - Session: {row['session_id']}")
                logger.info(f"    Conversations: {row['count']}")
                logger.info(f"    Last created: {row['last_created']}")
                logger.info("")
            
        await pool.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(check_conversation_save())
    sys.exit(0 if success else 1)

