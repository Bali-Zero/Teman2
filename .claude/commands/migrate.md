# Migrate - Applica Migrazioni PostgreSQL

Applica le migrazioni PostgreSQL pendenti al database Fly.io.

## Istruzioni

1. **Lista migrazioni esistenti**:
   ```bash
   ls -la apps/backend-rag/backend/migrations/migration_*.py | tail -10
   ```

2. **Verifica ultima migrazione applicata**:
   ```bash
   fly ssh console -a nuzantara-rag -C "python -c \"
   import asyncio
   import asyncpg
   import os

   async def check():
       conn = await asyncpg.connect(os.environ['DATABASE_URL'])
       result = await conn.fetch('SELECT * FROM migrations ORDER BY applied_at DESC LIMIT 5')
       for r in result:
           print(f'{r[\"migration_name\"]} - {r[\"applied_at\"]}')
       await conn.close()

   asyncio.run(check())
   \""
   ```

3. **Applica migrazioni pendenti**:
   - Identifica quali migrazioni non sono ancora applicate
   - Per ogni migrazione pendente:
     ```bash
     fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.migration_XXX"
     ```

4. **Verifica applicazione**:
   - Ricontrolla la tabella migrations
   - Verifica che le nuove tabelle/colonne esistano

## Migrazioni disponibili

| Migration | Descrizione |
|-----------|-------------|
| 007 | CRM System Schema (clients, practices, interactions) |
| 012 | Fix conversation_id in interactions |
| 013 | Agentic RAG Tables (parent_documents, golden_answers) |
| 015 | Google Drive columns |
| 016 | Summary column in parent_documents |
| 018 | Collective Memory System |
| 019 | Episodic Memory System |
| 021 | Memory-Knowledge Graph Integration |
| 022 | Performance Indexes |
| 025 | Latest migration |

## Output atteso

```
## Migrazioni PostgreSQL

### Stato attuale
Ultima migrazione: migration_022 (2025-12-20)

### Migrazioni pendenti
- migration_025: Latest migration

### Applicazione
- [x] migration_025: OK

### Verifica
- [x] Tabella xyz creata
- [x] Indice abc aggiunto

Migrazione completata!
```
