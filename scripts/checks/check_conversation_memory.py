#!/usr/bin/env python3
"""
Script per verificare direttamente nel database se le conversazioni vengono salvate
e se la conversation history viene recuperata correttamente.

Usage:
    python apps/backend-rag/scripts/check_conversation_memory.py --email zero@balizero.com
    python apps/backend-rag/scripts/check_conversation_memory.py --email zero@balizero.com --session-id session-123
    python apps/backend-rag/scripts/check_conversation_memory.py --email zero@balizero.com --limit 10
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import asyncpg

# Try to import settings - handle different path structures
try:
    from backend.app.core.config import settings
except ImportError:
    try:
        from app.core.config import settings
    except ImportError:
        # Fallback: use environment variables directly
        import os
        from pydantic_settings import BaseSettings
        
        class Settings(BaseSettings):
            DATABASE_URL: str = os.getenv("DATABASE_URL", "")
            
        settings = Settings()


async def check_conversations(email: str, session_id: str | None = None, limit: int = 5):
    """Check conversations in database"""
    print(f"\n{'='*80}")
    print(f"🔍 Checking conversations for: {email}")
    if session_id:
        print(f"   Session ID: {session_id}")
    print(f"{'='*80}\n")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.DATABASE_URL)
        print(f"✅ Connected to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}\n")
        
        # Query conversations
        if session_id:
            query = """
                SELECT id, user_id, session_id, messages, created_at, updated_at, metadata
                FROM conversations
                WHERE user_id = $1 AND session_id = $2
                ORDER BY created_at DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, email, session_id, limit)
        else:
            query = """
                SELECT id, user_id, session_id, messages, created_at, updated_at, metadata
                FROM conversations
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            rows = await conn.fetch(query, email, limit)
        
        if not rows:
            print(f"⚠️  No conversations found for {email}")
            if session_id:
                print(f"   (with session_id: {session_id})")
            return
        
        print(f"📚 Found {len(rows)} conversation(s):\n")
        
        for i, row in enumerate(rows, 1):
            print(f"{'─'*80}")
            print(f"Conversation #{i}")
            print(f"{'─'*80}")
            print(f"ID: {row['id']}")
            print(f"User ID: {row['user_id']}")
            print(f"Session ID: {row['session_id']}")
            print(f"Created: {row['created_at']}")
            print(f"Updated: {row.get('updated_at', 'N/A')}")
            print(f"Messages: {len(row['messages']) if row['messages'] else 0}")
            
            if row['messages']:
                print(f"\n📝 Messages:")
                for j, msg in enumerate(row['messages'], 1):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    print(f"   [{j}] {role.upper()}: {content[:100]}{'...' if len(content) > 100 else ''}")
                
                # Extract entities
                print(f"\n🔍 Extracted Entities:")
                entities = extract_entities_from_messages(row['messages'])
                print(f"   Name: {entities.get('name', 'None')}")
                print(f"   City: {entities.get('city', 'None')}")
                print(f"   Budget: {entities.get('budget', 'None')}")
                print(f"   Preferences: {entities.get('preferences', [])}")
            
            if row.get('metadata'):
                print(f"\n📋 Metadata: {json.dumps(row['metadata'], indent=2)}")
            
            print()
        
        await conn.close()
        print(f"✅ Database check completed\n")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()


async def check_recent_conversations(limit: int = 10):
    """Check most recent conversations across all users"""
    print(f"\n{'='*80}")
    print(f"🔍 Checking most recent conversations (limit: {limit})")
    print(f"{'='*80}\n")
    
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        print(f"✅ Connected to database\n")
        
        query = """
            SELECT id, user_id, session_id, 
                   jsonb_array_length(messages) as message_count,
                   created_at
            FROM conversations
            ORDER BY created_at DESC
            LIMIT $1
        """
        rows = await conn.fetch(query, limit)
        
        if not rows:
            print("⚠️  No conversations found in database")
            return
        
        print(f"📚 Most recent {len(rows)} conversations:\n")
        print(f"{'ID':<8} {'User':<30} {'Session ID':<25} {'Messages':<10} {'Created':<20}")
        print(f"{'─'*100}")
        
        for row in rows:
            session_id = row['session_id'] or 'N/A'
            if len(session_id) > 23:
                session_id = session_id[:20] + '...'
            print(f"{row['id']:<8} {row['user_id']:<30} {session_id:<25} {row['message_count']:<10} {row['created_at']}")
        
        await conn.close()
        print(f"\n✅ Check completed\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def extract_entities_from_messages(messages: list[dict]) -> dict:
    """Extract entities from messages (simplified version for script)"""
    import re
    entities = {
        "name": None,
        "city": None,
        "budget": None,
        "preferences": [],
    }
    
    if not messages:
        return entities
    
    # Combine all user messages
    user_messages = " ".join([
        msg.get("content", "") for msg in messages
        if msg.get("role") == "user"
    ]).lower()
    
    # Extract name
    name_patterns = [
        r"mi chiamo\s+(\w+)",
        r"sono\s+(\w+)",
        r"il mio nome è\s+(\w+)",
        r"my name is\s+(\w+)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_messages, re.IGNORECASE)
        if match:
            name = match.group(1)
            skip_words = ["di", "da", "a", "in", "un", "una", "uno", "the", "a", "an"]
            if name.lower() not in skip_words:
                entities["name"] = name.capitalize()
                break
    
    # Extract city
    city_patterns = [
        r"sono di\s+(\w+)",
        r"vivo a\s+(\w+)",
        r"vengo da\s+(\w+)",
        r"i'm from\s+(\w+)",
    ]
    italian_cities = ["milano", "roma", "napoli", "torino", "firenze", "bologna", "venezia", "genova", "bali", "jakarta"]
    for pattern in city_patterns:
        match = re.search(pattern, user_messages, re.IGNORECASE)
        if match:
            city = match.group(1).lower()
            skip_words = ["un", "una", "uno", "the", "a", "an", "e", "ed", "o", "ma"]
            if city not in skip_words:
                if city in italian_cities:
                    entities["city"] = city.capitalize()
                else:
                    entities["city"] = city.capitalize()
                break
    
    # Extract budget
    budget_patterns = [
        r"budget\s+di\s+([0-9,\.]+)",
        r"budget\s+([0-9,\.]+)",
        r"ho\s+([0-9,\.]+)\s+euro",
        r"€\s*([0-9,\.]+)",
    ]
    for pattern in budget_patterns:
        match = re.search(pattern, user_messages, re.IGNORECASE)
        if match:
            budget_str = match.group(1).replace(",", "").replace(".", "")
            try:
                entities["budget"] = str(int(budget_str))
            except ValueError:
                pass
            break
    
    return entities


async def test_entity_extraction():
    """Test entity extraction with sample messages"""
    print(f"\n{'='*80}")
    print(f"🧪 Testing Entity Extraction")
    print(f"{'='*80}\n")
    
    test_cases = [
        {
            "name": "Name and City",
            "messages": [
                {"role": "user", "content": "Mi chiamo Marco e sono di Milano"},
                {"role": "assistant", "content": "Ciao Marco!"}
            ]
        },
        {
            "name": "Name only",
            "messages": [
                {"role": "user", "content": "Mi chiamo Marco"},
                {"role": "assistant", "content": "Ciao!"}
            ]
        },
        {
            "name": "City only",
            "messages": [
                {"role": "user", "content": "Sono di Milano"},
                {"role": "assistant", "content": "Ok"}
            ]
        },
        {
            "name": "Budget",
            "messages": [
                {"role": "user", "content": "Il mio budget è di 50 milioni di rupie"},
                {"role": "assistant", "content": "Capito"}
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        entities = extract_entities_from_messages(test_case['messages'])
        print(f"  Name: {entities.get('name', 'None')}")
        print(f"  City: {entities.get('city', 'None')}")
        print(f"  Budget: {entities.get('budget', 'None')}")
        print(f"  Preferences: {entities.get('preferences', [])}")
        print()


async def main():
    parser = argparse.ArgumentParser(description="Check conversation memory in database")
    parser.add_argument("--email", help="User email to check")
    parser.add_argument("--session-id", help="Session ID to filter")
    parser.add_argument("--limit", type=int, default=5, help="Limit results")
    parser.add_argument("--recent", action="store_true", help="Show recent conversations")
    parser.add_argument("--test-extraction", action="store_true", help="Test entity extraction")
    
    args = parser.parse_args()
    
    if args.test_extraction:
        await test_entity_extraction()
    elif args.recent:
        await check_recent_conversations(args.limit)
    elif args.email:
        await check_conversations(args.email, args.session_id, args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

