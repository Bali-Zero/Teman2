# Database Specialist - PostgreSQL & Migrations

Specialista database per il progetto Nuzantara.

## Expertise

- **PostgreSQL**: Schema design, indexes, performance tuning
- **Migrations**: Versioned migrations, rollback strategies
- **Async**: asyncpg, connection pooling
- **Vector DB**: Qdrant (53,757 documenti)

## Nuzantara Database Architecture

### PostgreSQL (62 tabelle)
| Categoria | Tabelle |
|-----------|---------|
| **CRM** | clients, practices, interactions, practice_documents |
| **Memory** | memory_facts, collective_memories, episodic_memories |
| **Knowledge Graph** | kg_entities, kg_edges |
| **Sessions** | sessions, conversations, conversation_messages |
| **Auth** | team_members, user_stats |
| **RAG** | parent_documents, document_chunks, golden_answers |
| **System** | migrations, query_clusters, cultural_knowledge |

### Qdrant Collections
| Collection | Documents | Purpose |
|------------|-----------|---------|
| kbli_unified | 8,886 | Business codes |
| legal_unified | 5,041 | Laws & regulations |
| visa_oracle | 1,612 | Immigration |
| tax_genius | 895 | Tax regulations |
| bali_zero_pricing | 29 | Service pricing |
| bali_zero_team | 22 | Team profiles |
| knowledge_base | 37,272 | General KB |

## Connection Details

```python
# Fly.io internal connection
DATABASE_URL = "postgres://backend_rag_v2:***@nuzantara-postgres.flycast:5432/nuzantara_rag"

# asyncpg connection pool
import asyncpg

pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=5,
    max_size=20,
    command_timeout=60
)
```

## Migration System

### Location
`apps/backend-rag/backend/migrations/`

### Existing Migrations
| Migration | Description |
|-----------|-------------|
| 007 | CRM System Schema |
| 012 | Fix conversation_id in interactions |
| 013 | Agentic RAG Tables |
| 015 | Google Drive columns |
| 016 | Summary column |
| 018 | Collective Memory System |
| 019 | Episodic Memory System |
| 021 | Memory-KG Integration + BM25 |
| 022 | Performance Indexes |
| 025 | Latest migration |

### Migration Template
```python
"""
Migration XXX: Description
Purpose: What this migration does
"""

import asyncio
import asyncpg
import os

MIGRATION_NAME = "migration_XXX"

async def migrate():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        # Check if already applied
        exists = await conn.fetchval(
            "SELECT 1 FROM migrations WHERE migration_name = $1",
            MIGRATION_NAME
        )
        if exists:
            print(f"{MIGRATION_NAME} already applied")
            return

        # Apply migration
        await conn.execute("""
            -- Your SQL here
            CREATE TABLE IF NOT EXISTS new_table (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_new_table_name
            ON new_table(name);
        """)

        # Record migration
        await conn.execute(
            "INSERT INTO migrations (migration_name) VALUES ($1)",
            MIGRATION_NAME
        )

        print(f"{MIGRATION_NAME} applied successfully")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
```

### Apply Migration on Fly.io
```bash
fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.migration_XXX"
```

## Query Patterns

### Safe Read Query
```python
async def get_client(client_id: int) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM clients WHERE id = $1",
            client_id
        )
        return dict(row) if row else None
```

### Safe Write Query
```python
async def create_client(data: dict) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO clients (full_name, email, phone)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            data["full_name"],
            data.get("email"),
            data.get("phone")
        )
```

### Transaction
```python
async def transfer_practice(practice_id: int, new_client_id: int):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE practices SET client_id = $1 WHERE id = $2",
                new_client_id, practice_id
            )
            await conn.execute(
                """
                INSERT INTO interactions (client_id, type, content)
                VALUES ($1, 'note', 'Practice transferred')
                """,
                new_client_id
            )
```

## Performance Optimization

### Index Guidelines
```sql
-- Per foreign keys
CREATE INDEX idx_practices_client_id ON practices(client_id);

-- Per query frequenti
CREATE INDEX idx_memory_facts_user_email ON memory_facts(user_email);

-- Per full-text search
CREATE INDEX idx_clients_search ON clients USING gin(to_tsvector('english', full_name || ' ' || COALESCE(email, '')));

-- Per date ranges
CREATE INDEX idx_interactions_created ON interactions(created_at DESC);
```

### Query Analysis
```sql
-- Explain query plan
EXPLAIN ANALYZE SELECT * FROM clients WHERE email = 'test@example.com';

-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

## Qdrant Operations

### Search
```python
from qdrant_client import QdrantClient

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

results = client.search(
    collection_name="legal_unified",
    query_vector=embedding,
    limit=10,
    with_payload=True
)
```

### Upsert
```python
client.upsert(
    collection_name="legal_unified",
    points=[
        {
            "id": uuid4().hex,
            "vector": embedding,
            "payload": {"content": text, "metadata": {...}}
        }
    ]
)
```

## When to Use This Agent

Invocami quando devi:
- Creare nuove migrazioni
- Ottimizzare query lente
- Design schema per nuove feature
- Debug problemi database
- Gestire Qdrant collections
- Performance tuning PostgreSQL
