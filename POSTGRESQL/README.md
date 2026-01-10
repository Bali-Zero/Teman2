# Database PostgreSQL Export

**Ultimo aggiornamento:** 2026-01-10 14:59:18

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

**Totale: 6,737 righe in 36 tabelle**

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
