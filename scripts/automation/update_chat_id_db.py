#!/usr/bin/env python3
"""
Script per aggiornare il Telegram chat ID nel database PostgreSQL
Da: 8032150393
A: 1125336968
"""

import os
import asyncio
import asyncpg
import sys

async def update_chat_id():
    """Aggiorna il chat ID nel database"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL non trovato nelle variabili d'ambiente")
        print("💡 Esegui questo script sulla macchina Fly.io dove DATABASE_URL è disponibile")
        return False
    
    try:
        conn = await asyncpg.connect(db_url)
        try:
            # Aggiorna il chat ID
            result = await conn.execute("""
                UPDATE messaging_users 
                SET telegram_chat_id = 1125336968,
                    updated_at = NOW()
                WHERE telegram_chat_id = 8032150393
            """)
            
            print(f"✅ Aggiornati record: {result}")
            
            # Verifica i risultati
            rows = await conn.fetch("""
                SELECT 
                    telegram_chat_id,
                    user_id,
                    display_name,
                    verified,
                    created_at
                FROM messaging_users
                WHERE telegram_chat_id IN (8032150393, 1125336968)
                ORDER BY created_at DESC
            """)
            
            if rows:
                print("\n📊 Record trovati:")
                for row in rows:
                    print(f"   Chat ID: {row['telegram_chat_id']}, User: {row['user_id']}, Name: {row['display_name']}")
            else:
                print("\nℹ️  Nessun record trovato con questi chat ID nel database")
            
            return True
                
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(update_chat_id())
    sys.exit(0 if success else 1)
