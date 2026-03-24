"""
CRM Query Optimizer

Query ottimizzate e batch operations per massima performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class CRMQueryOptimizer:
    """Ottimizzatore query per operazioni CRM frequenti."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def batch_insert_clients(self, clients: list[dict[str, Any]]) -> list[int]:
        """
        Inserimento batch clienti in transazione ACID.

        Args:
            clients: Lista di dizionari con dati cliente

        Returns:
            Lista di ID clienti creati
        """
        if not clients:
            return []

        query = """
            INSERT INTO clients (
                full_name, email, phone, whatsapp, nationality,
                passport_number, status, client_type, assigned_to,
                custom_fields, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW()
            )
            RETURNING id
        """

        params = [
            (
                c.get("full_name"),
                c.get("email"),
                c.get("phone"),
                c.get("whatsapp"),
                c.get("nationality"),
                c.get("passport_number"),
                c.get("status", "active"),
                c.get("client_type", "individual"),
                c.get("assigned_to"),
                c.get("custom_fields", {}),
            )
            for c in clients
        ]

        # Transazione ACID: tutti o nessuno
        async with self.db_pool.acquire() as conn, conn.transaction():
            ids = []
            for p in params:
                row = await conn.fetchrow(query, *p)
                if row:
                    ids.append(row["id"])
            return ids

    # Allowed columns for dynamic UPDATE to prevent SQL injection
    ALLOWED_PRACTICE_COLUMNS = frozenset(
        {
            "status",
            "priority",
            "assigned_to",
            "notes",
            "quoted_price",
            "actual_price",
            "paid_amount",
            "currency",
            "start_date",
            "completion_date",
            "expiry_date",
            "next_renewal_date",
            "practice_type_id",
            "client_id",
        }
    )

    async def batch_update_practices(self, updates: list[dict[str, Any]]) -> int:
        """
        Aggiornamento batch pratiche.

        Args:
            updates: Lista di update con id e campi da aggiornare

        Returns:
            Numero di righe aggiornate
        """
        if not updates:
            return 0

        async with self.db_pool.acquire() as conn, conn.transaction():
            total_updated = 0

            for update in updates:
                practice_id = update.pop("id")
                if not update:
                    continue

                # Costruisci query dinamica — solo colonne nella whitelist
                fields = []
                values = []
                for i, (key, value) in enumerate(update.items(), start=1):
                    if key not in self.ALLOWED_PRACTICE_COLUMNS:
                        raise ValueError(f"Column '{key}' not allowed for practice update")
                    fields.append(f"{key} = ${i}")
                    values.append(value)

                values.append(practice_id)

                query = f"""
                        UPDATE practices
                        SET {", ".join(fields)}, updated_at = NOW()
                        WHERE id = ${len(values)}
                    """

                result = await conn.execute(query, *values)
                total_updated += int(result.split()[-1])

            return total_updated

    async def get_clients_with_practices(self, client_ids: list[int]) -> list[dict[str, Any]]:
        """
        Recupera clienti con le loro pratiche in una singola query.

        Args:
            client_ids: Lista di ID clienti

        Returns:
            Lista clienti con pratiche annidate
        """
        if not client_ids:
            return []

        async with self.db_pool.acquire() as conn:
            query = """
                SELECT
                    c.*,
                    COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'id', p.id,
                                'status', p.status,
                                'practice_type', pt.name,
                                'start_date', p.start_date,
                                'completion_date', p.completion_date
                            ) ORDER BY p.created_at DESC
                        ) FILTER (WHERE p.id IS NOT NULL),
                        '[]'::jsonb
                    ) as practices
                FROM clients c
                LEFT JOIN practices p ON p.client_id = c.id
                LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE c.id = ANY($1)
                GROUP BY c.id
            """

            rows = await conn.fetch(query, client_ids)
            return [dict(row) for row in rows]

    async def search_clients_optimized(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict], int]:
        """
        Ricerca clienti ottimizzata con full-text search.

        Args:
            query: Termine di ricerca
            limit: Limite risultati
            offset: Offset per paginazione

        Returns:
            Tuple (risultati, conteggio totale)
        """
        async with self.db_pool.acquire() as conn:
            # Normalizza query per tsvector
            " & ".join(query.split())

            # Cerca con tsvector se disponibile, altrimenti LIKE
            sql = """
                WITH results AS (
                    SELECT
                        c.*,
                        CASE
                            WHEN c.full_name ILIKE $1 THEN 3
                            WHEN c.email ILIKE $1 THEN 2
                            WHEN c.phone ILIKE $1 THEN 1
                            ELSE 0
                        END as relevance
                    FROM clients c
                    WHERE
                        c.full_name ILIKE $1
                        OR c.email ILIKE $1
                        OR c.phone ILIKE $1
                        OR c.passport_number ILIKE $1
                )
                SELECT *, COUNT(*) OVER() as total_count
                FROM results
                ORDER BY relevance DESC, full_name ASC
                LIMIT $2 OFFSET $3
            """

            search_pattern = f"%{query}%"
            rows = await conn.fetch(sql, search_pattern, limit, offset)

            if not rows:
                return [], 0

            total = rows[0]["total_count"]
            results = [{k: v for k, v in dict(row).items() if k != "total_count"} for row in rows]

            return results, total

    async def get_practice_statistics(self, assigned_to: str | None = None) -> dict[str, Any]:
        """
        Statistiche pratiche aggregate.

        Args:
            assigned_to: Filtra per assegnatario (opzionale)

        Returns:
            Dizionario con statistiche
        """
        async with self.db_pool.acquire() as conn:
            base_query = """
                SELECT
                    status,
                    priority,
                    COUNT(*) as count,
                    SUM(quoted_price) as total_quoted,
                    SUM(actual_price) as total_actual,
                    SUM(paid_amount) as total_paid
                FROM practices
                WHERE 1=1
            """

            params = []
            if assigned_to:
                base_query += " AND assigned_to = $1"
                params.append(assigned_to)

            base_query += " GROUP BY status, priority"

            rows = await conn.fetch(base_query, *params)

            # Aggrega risultati
            stats = {
                "by_status": {},
                "by_priority": {},
                "financials": {"total_quoted": 0, "total_actual": 0, "total_paid": 0},
            }

            for row in rows:
                status = row["status"]
                priority = row["priority"]
                count = row["count"]

                stats["by_status"][status] = stats["by_status"].get(status, 0) + count
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + count

                stats["financials"]["total_quoted"] += float(row["total_quoted"] or 0)
                stats["financials"]["total_actual"] += float(row["total_actual"] or 0)
                stats["financials"]["total_paid"] += float(row["total_paid"] or 0)

            return stats

    async def get_overdue_practices(self, days: int = 7) -> list[dict[str, Any]]:
        """
        Recupera pratiche scadute o in scadenza.

        Args:
            days: Giorni per considerare "in scadenza"

        Returns:
            Lista pratiche scadute/in scadenza
        """
        async with self.db_pool.acquire() as conn:
            threshold = datetime.utcnow() + timedelta(days=days)

            query = """
                SELECT
                    p.*,
                    c.full_name as client_name,
                    c.email as client_email,
                    c.phone as client_phone,
                    pt.name as practice_type_name
                FROM practices p
                JOIN clients c ON c.id = p.client_id
                JOIN practice_types pt ON pt.id = p.practice_type_id
                WHERE
                    p.status NOT IN ('completed', 'cancelled')
                    AND (
                        p.expiry_date < NOW()
                        OR p.next_renewal_date < $1
                    )
                ORDER BY
                    CASE
                        WHEN p.expiry_date < NOW() THEN 0
                        ELSE 1
                    END,
                    p.expiry_date ASC
            """

            rows = await conn.fetch(query, threshold)
            return [dict(row) for row in rows]


async def health_check_crm_tables(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Verifica integrità tabelle CRM.

    Returns:
        Dict con stato tabelle
    """
    async with db_pool.acquire() as conn:
        checks = {}

        # Conta record per tabella (query separate — nessuna interpolazione di nomi tabella)
        checks["clients"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM clients")}
        checks["practices"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM practices")}
        checks["practice_types"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM practice_types")}
        checks["interactions"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM interactions")}

        # Verifica clienti senza pratiche
        orphan_clients = await conn.fetchval("""
            SELECT COUNT(*) FROM clients c
            WHERE NOT EXISTS (
                SELECT 1 FROM practices p WHERE p.client_id = c.id
            )
        """)
        checks["orphan_clients"] = orphan_clients

        # Verifica pratiche senza cliente
        orphan_practices = await conn.fetchval("""
            SELECT COUNT(*) FROM practices p
            WHERE NOT EXISTS (
                SELECT 1 FROM clients c WHERE c.id = p.client_id
            )
        """)
        checks["orphan_practices"] = orphan_practices

        return checks
