#!/bin/bash
# Script per aggiornare il Telegram chat ID nel database PostgreSQL
# Da: 8032150393
# A: 1125336968

echo "🔄 Aggiornamento Telegram Chat ID nel database"
echo "=============================================="
echo ""

# Ottieni DATABASE_URL da Fly.io secrets
echo "📋 Recupero DATABASE_URL da Fly.io..."
DB_URL=$(fly secrets list --app nuzantara-rag | grep DATABASE_URL | awk '{print $1}')

if [ -z "$DB_URL" ]; then
    echo "⚠️  DATABASE_URL non trovato nei secrets"
    echo "💡 Esegui manualmente lo script SQL:"
    echo "   psql \$DATABASE_URL -f scripts/automation/update_telegram_chat_id.sql"
    exit 1
fi

echo "✅ DATABASE_URL trovato"
echo ""

# Esegui lo script SQL
echo "🔄 Esecuzione aggiornamento nel database..."
fly ssh console --app nuzantara-rag -C "python3 << 'PYTHON'
import os
import asyncio
import asyncpg

async def update_chat_id():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print('❌ DATABASE_URL non trovato')
        return
    
    conn = await asyncpg.connect(db_url)
    try:
        # Aggiorna il chat ID
        result = await conn.execute('''
            UPDATE messaging_users 
            SET telegram_chat_id = 1125336968,
                updated_at = NOW()
            WHERE telegram_chat_id = 8032150393
        ''')
        
        print(f'✅ Aggiornati record: {result}')
        
        # Verifica i risultati
        rows = await conn.fetch('''
            SELECT 
                telegram_chat_id,
                user_id,
                display_name,
                verified,
                created_at
            FROM messaging_users
            WHERE telegram_chat_id IN (8032150393, 1125336968)
            ORDER BY created_at DESC
        ''')
        
        if rows:
            print('\\n📊 Record trovati:')
            for row in rows:
                print(f'   Chat ID: {row[\"telegram_chat_id\"]}, User: {row[\"user_id\"]}, Name: {row[\"display_name\"]}')
        else:
            print('\\nℹ️  Nessun record trovato con questi chat ID')
            
    finally:
        await conn.close()

asyncio.run(update_chat_id())
PYTHON
"

echo ""
echo "✅ Aggiornamento completato!"
