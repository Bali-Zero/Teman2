#!/usr/bin/env python3
"""
Script per esportare tabelle PostgreSQL in file Excel.

Richiede: pandas, openpyxl, asyncpg
Connessione: via fly proxy (tunnel locale)

USO:
  1. Avvia proxy in un altro terminale:
     fly proxy 15432:5432 -a nuzantara-rag

  2. Esegui script:
     python3 update_excel.py

CRON (ogni giorno alle 6:00):
  0 6 * * * cd /Users/antonellosiano/Desktop/nuzantara/POSTGRESQL && ./update_with_proxy.sh
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import asyncpg
import pandas as pd

# Directory output
OUTPUT_DIR = Path(__file__).parent

# Database URL (fly proxy su porta 15432)
# Ottieni password da: fly postgres connect -a nuzantara-postgres
# Oppure imposta DATABASE_URL come variabile ambiente
import os
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable"
)

# Configurazione file Excel per categoria semantica
EXCEL_FILES = {
    "01_CRM.xlsx": [
        ("clients", "SELECT id, uuid, full_name, email, phone, whatsapp, nationality, status, client_type, assigned_to, created_at FROM clients ORDER BY id"),
        ("practices", "SELECT id, uuid, client_id, practice_type_code, title, status, priority, quoted_price, assigned_to, start_date, expiry_date, payment_status, created_at FROM practices ORDER BY id"),
        ("interactions", "SELECT id, uuid, client_id, practice_id, type, channel, title, content, direction, sentiment, created_at, team_member FROM interactions ORDER BY created_at DESC LIMIT 500"),
        ("practice_types", "SELECT * FROM practice_types"),
        ("client_preferences", "SELECT * FROM client_preferences"),
        ("client_invitations", "SELECT id, client_id, email, expires_at, used_at, created_at FROM client_invitations"),
        ("crm_settings", "SELECT * FROM crm_settings"),
    ],
    "02_TEAM.xlsx": [
        ("team_members", "SELECT id, name, email, role, department, language, active, last_login, created_at FROM team_members ORDER BY name"),
        ("team_employees", "SELECT employee_id, name, email, role, department, is_active, created_at FROM team_employees"),
        ("team_access", "SELECT id, user_id, role, is_active, last_login, created_at FROM team_access"),
        ("team_timesheet", "SELECT id, user_id, email, action_type, timestamp, notes FROM team_timesheet ORDER BY timestamp DESC LIMIT 1000"),
        ("departments", "SELECT * FROM departments"),
        ("team_work_sessions", "SELECT * FROM team_work_sessions ORDER BY session_start DESC LIMIT 100"),
    ],
    "03_MEMORY.xlsx": [
        ("memory_facts", "SELECT id, user_id, content, fact_type, confidence, source, created_at FROM memory_facts ORDER BY created_at DESC LIMIT 500"),
        ("episodic_memories", "SELECT id, user_id, event_type, title, description, emotion, occurred_at, source, created_at FROM episodic_memories ORDER BY created_at DESC LIMIT 500"),
        ("collective_memory", "SELECT id, memory_key, memory_type, memory_content, created_by, created_at, access_count FROM collective_memory"),
        ("conversations", "SELECT id, user_id, session_id, created_at, metadata->>'member_name' as member_name FROM conversations ORDER BY created_at DESC LIMIT 500"),
        ("conversation_ratings", "SELECT * FROM conversation_ratings"),
    ],
    "04_KNOWLEDGE.xlsx": [
        ("parent_documents", "SELECT id, document_id, type, title, char_count, pasal_count, created_at, mime_type, is_canonical FROM parent_documents ORDER BY created_at DESC"),
        ("kg_nodes_sample", "SELECT entity_id, entity_type, name, description, confidence, source_collection, created_at FROM kg_nodes ORDER BY created_at DESC LIMIT 1000"),
        ("kg_edges_sample", "SELECT relationship_id, source_entity_id, target_entity_id, relationship_type, confidence, created_at FROM kg_edges ORDER BY created_at DESC LIMIT 1000"),
        ("query_analytics", "SELECT id, query_text, language_preference, model_used, response_time_ms, document_count, created_at FROM query_analytics ORDER BY created_at DESC LIMIT 500"),
        ("kbli_blueprints", "SELECT * FROM kbli_blueprints"),
    ],
    "05_USERS.xlsx": [
        ("user_profiles", "SELECT id, email, full_name, phone, user_type, status, total_sessions, total_messages, language_pref, created_at FROM user_profiles ORDER BY created_at DESC"),
        ("users", "SELECT id, email, name, role, status, language_preference, created_at FROM users"),
        ("user_facts", "SELECT id, user_id, fact_type, fact_key, fact_value, confidence, learned_at FROM user_facts ORDER BY learned_at DESC LIMIT 500"),
        ("user_stats", "SELECT * FROM user_stats"),
        ("persistent_sessions", "SELECT * FROM persistent_sessions"),
    ],
    "06_CONTENT.xlsx": [
        ("news_items", "SELECT id, title, slug, summary, source, category, priority, status, published_at, view_count, ai_sentiment FROM news_items ORDER BY published_at DESC"),
        ("visa_types", "SELECT id, code, name, duration, category, cost_visa, renewable, foreign_eligible, created_at FROM visa_types ORDER BY code"),
        ("document_categories", "SELECT * FROM document_categories ORDER BY sort_order"),
        ("newsletter_subscribers", "SELECT id, email, name, categories, frequency, language, confirmed, source, created_at FROM newsletter_subscribers"),
    ],
    "07_SYSTEM.xlsx": [
        ("activity_log", "SELECT * FROM activity_log ORDER BY performed_at DESC LIMIT 500"),
        ("schema_migrations", "SELECT id, migration_name, migration_number, applied_at, execution_time_ms FROM schema_migrations ORDER BY migration_number"),
        ("migration_log", "SELECT * FROM migration_log"),
        ("folder_access_rules", "SELECT * FROM folder_access_rules"),
        ("email_activity_log", "SELECT * FROM email_activity_log ORDER BY created_at DESC LIMIT 200"),
    ],
}


async def run_query(conn: asyncpg.Connection, query: str) -> list[dict]:
    """Esegue query e ritorna risultati come lista di dict."""
    try:
        rows = await conn.fetch(query)
        result = []
        for r in rows:
            row_dict = {}
            for k, v in dict(r).items():
                if hasattr(v, "isoformat"):
                    row_dict[k] = v.isoformat()
                elif isinstance(v, (list, dict)):
                    row_dict[k] = json.dumps(v)
                elif isinstance(v, (bytes,)):
                    row_dict[k] = v.hex()[:50] + "..."  # Truncate binary
                else:
                    row_dict[k] = v
            result.append(row_dict)
        return result
    except Exception as e:
        print(f"  Query error: {e}")
        return []


async def export_to_excel():
    """Esporta tutte le tabelle in file Excel."""
    print(f"\n{'='*60}")
    print(f"POSTGRESQL EXPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # Connessione al database
    print("\nConnessione a PostgreSQL via fly proxy...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connesso!\n")
    except Exception as e:
        print(f"❌ Errore connessione: {e}")
        print("\nAssicurati che fly proxy sia attivo:")
        print("  fly proxy 15432:5432 -a nuzantara-postgres")
        return

    total_rows = 0
    total_tables = 0

    try:
        for excel_file, tables in EXCEL_FILES.items():
            filepath = OUTPUT_DIR / excel_file
            print(f"📁 {excel_file}")

            file_rows = 0
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for table_name, query in tables:
                    print(f"  📊 {table_name}...", end=" ", flush=True)

                    data = await run_query(conn, query)

                    if data:
                        df = pd.DataFrame(data)
                        sheet_name = table_name[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        print(f"✓ {len(data)} righe")
                        file_rows += len(data)
                        total_tables += 1
                    else:
                        pd.DataFrame().to_excel(writer, sheet_name=table_name[:31], index=False)
                        print("(vuoto)")

            total_rows += file_rows
            print(f"  → {file_rows} righe totali\n")

    finally:
        await conn.close()

    # Aggiorna README
    readme = OUTPUT_DIR / "README.md"
    readme.write_text(f"""# Database PostgreSQL Export

**Ultimo aggiornamento:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## File Excel

| File | Sheets | Righe | Contenuto |
|------|--------|-------|-----------|
| 01_CRM.xlsx | 7 | - | clients, practices, interactions, practice_types |
| 02_TEAM.xlsx | 6 | - | team_members, team_timesheet, departments |
| 03_MEMORY.xlsx | 5 | - | memory_facts, episodic_memories, conversations |
| 04_KNOWLEDGE.xlsx | 5 | - | parent_documents, kg_nodes, kg_edges |
| 05_USERS.xlsx | 5 | - | user_profiles, users, user_facts |
| 06_CONTENT.xlsx | 4 | - | news_items, visa_types, document_categories |
| 07_SYSTEM.xlsx | 5 | - | activity_log, schema_migrations |

**Totale: {total_rows:,} righe in {total_tables} tabelle**

## Aggiornamento Manuale

```bash
# 1. Avvia proxy (in un terminale separato)
fly proxy 15432:5432 -a nuzantara-rag

# 2. Esegui export (in altro terminale)
cd POSTGRESQL
python3 update_excel.py
```

## Aggiornamento Automatico (Cron)

```bash
# Usa lo script wrapper che gestisce il proxy
./update_with_proxy.sh
```

## Note

- Tabelle grandi (kg_nodes, kg_edges) sono limitate a 1000 righe
- Colonne pesanti (full_text, embedding) sono escluse
- Timestamp in formato ISO 8601
- Dati estratti da PostgreSQL su Fly.io (nuzantara-rag)
""")

    print(f"{'='*60}")
    print(f"✅ EXPORT COMPLETATO!")
    print(f"   {total_rows:,} righe in {total_tables} tabelle")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(export_to_excel())
