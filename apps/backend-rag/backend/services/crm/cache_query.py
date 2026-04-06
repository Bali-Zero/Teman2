"""
CRM Cache & Query — consolidated module.

Merges:
  - cache_manager.py  (CRMCache, QueryCache, cache_crm_result, invalidate_*)
  - query_optimizer.py (CRMQueryOptimizer, health_check_crm_tables)
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, TypeVar

import asyncpg

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ─────────────────────────────────────────────────────────────────────────────
# CRMCache — in-memory TTL cache
# ─────────────────────────────────────────────────────────────────────────────

class CRMCache:
    """Cache in-memory per dati CRM con TTL."""

    def __init__(self, default_ttl: int = 300) -> None:
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Recupera valore dalla cache."""
        async with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if datetime.now(timezone.utc) > expiry:
                del self._cache[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Salva valore in cache."""
        ttl = ttl or self._default_ttl
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        async with self._lock:
            self._cache[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Elimina chiave dalla cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear_pattern(self, pattern: str) -> int:
        """Elimina tutte le chiavi che matchano pattern."""
        async with self._lock:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for k in keys_to_delete:
                del self._cache[k]
            return len(keys_to_delete)

    async def clear(self) -> None:
        """Pulisce tutta la cache."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Rimuove elementi scaduti. Ritorna numero elementi rimossi."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            expired = [k for k, (_, expiry) in self._cache.items() if now > expiry]
            for k in expired:
                del self._cache[k]
            return len(expired)


# Singleton instance
crm_cache = CRMCache()


def cache_crm_result(ttl: int = 300, key_prefix: str = "") -> Any:
    """Decorator per caching risultati funzioni CRM."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            key_data = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            cached = await crm_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache HIT for {func.__name__}")
                return cached
            result = await func(*args, **kwargs)
            await crm_cache.set(cache_key, result, ttl)
            logger.debug(f"Cache MISS for {func.__name__}")
            return result

        return async_wrapper

    return decorator


def invalidate_client_cache(client_id: int) -> None:
    """Invalida tutta la cache relativa a un cliente."""
    asyncio.create_task(crm_cache.clear_pattern(f"client:{client_id}"))


def invalidate_practice_cache(practice_id: int) -> None:
    """Invalida tutta la cache relativa a una pratica."""
    asyncio.create_task(crm_cache.clear_pattern(f"practice:{practice_id}"))


# ─────────────────────────────────────────────────────────────────────────────
# QueryCache — lookup cache for frequent DB queries
# ─────────────────────────────────────────────────────────────────────────────

class QueryCache:
    """Cache specifica per query database frequenti."""

    def __init__(self) -> None:
        self._client_by_email: dict[str, tuple[int, datetime]] = {}
        self._client_by_phone: dict[str, tuple[int, datetime]] = {}
        self._practice_types: list[dict] | None = None
        self._practice_types_updated: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_client_by_email(self, email: str) -> int | None:
        async with self._lock:
            if email not in self._client_by_email:
                return None
            client_id, expiry = self._client_by_email[email]
            if datetime.now(timezone.utc) > expiry:
                del self._client_by_email[email]
                return None
            return client_id

    async def set_client_by_email(self, email: str, client_id: int, ttl: int = 600) -> None:
        async with self._lock:
            self._client_by_email[email.lower()] = (
                client_id,
                datetime.now(timezone.utc) + timedelta(seconds=ttl),
            )

    async def get_client_by_phone(self, phone: str) -> int | None:
        async with self._lock:
            normalized = self._normalize_phone(phone)
            if normalized not in self._client_by_phone:
                return None
            client_id, expiry = self._client_by_phone[normalized]
            if datetime.now(timezone.utc) > expiry:
                del self._client_by_phone[normalized]
                return None
            return client_id

    async def set_client_by_phone(self, phone: str, client_id: int, ttl: int = 600) -> None:
        async with self._lock:
            normalized = self._normalize_phone(phone)
            self._client_by_phone[normalized] = (
                client_id,
                datetime.now(timezone.utc) + timedelta(seconds=ttl),
            )

    async def get_practice_types(self) -> list[dict] | None:
        async with self._lock:
            if self._practice_types is None:
                return None
            if (
                self._practice_types_updated
                and datetime.now(timezone.utc) - self._practice_types_updated > timedelta(hours=1)
            ):
                self._practice_types = None
                return None
            return self._practice_types

    async def set_practice_types(self, types: list[dict]) -> None:
        async with self._lock:
            self._practice_types = types
            self._practice_types_updated = datetime.now(timezone.utc)

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        from backend.services.crm.validators import normalize_phone_e164
        result = normalize_phone_e164(phone)
        return result or phone

    async def invalidate_client(self, client_id: int) -> None:
        async with self._lock:
            emails_to_remove = [
                email for email, (cid, _) in self._client_by_email.items() if cid == client_id
            ]
            for email in emails_to_remove:
                del self._client_by_email[email]
            phones_to_remove = [
                phone for phone, (cid, _) in self._client_by_phone.items() if cid == client_id
            ]
            for phone in phones_to_remove:
                del self._client_by_phone[phone]


# Singleton
query_cache = QueryCache()


# ─────────────────────────────────────────────────────────────────────────────
# CRMQueryOptimizer — optimised batch/search queries
# ─────────────────────────────────────────────────────────────────────────────

class CRMQueryOptimizer:
    """Ottimizzatore query per operazioni CRM frequenti."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    async def batch_insert_clients(self, clients: list[dict[str, Any]]) -> list[int]:
        """Inserimento batch clienti in transazione ACID (single multi-row INSERT)."""
        if not clients:
            return []

        import json as _json

        # Build multi-row VALUES clause: ($1,$2,...,$10), ($11,$12,...,$20), ...
        value_rows = []
        all_params: list[Any] = []
        for i, c in enumerate(clients):
            base = i * 10
            placeholders = ", ".join(f"${base + j}" for j in range(1, 11))
            value_rows.append(f"({placeholders}, NOW(), NOW())")
            all_params.extend([
                c.get("full_name"),
                c.get("email"),
                c.get("phone"),
                c.get("whatsapp"),
                c.get("nationality"),
                c.get("passport_number"),
                c.get("status", "active"),
                c.get("client_type", "individual"),
                c.get("assigned_to"),
                _json.dumps(c.get("custom_fields", {})),
            ])

        query = f"""
            INSERT INTO clients (
                full_name, email, phone, whatsapp, nationality,
                passport_number, status, client_type, assigned_to,
                custom_fields, created_at, updated_at
            ) VALUES {", ".join(value_rows)}
            RETURNING id
        """
        async with self.db_pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(query, *all_params)
            return [row["id"] for row in rows]

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
        },
    )

    async def batch_update_practices(self, updates: list[dict[str, Any]]) -> int:
        """Aggiornamento batch pratiche.

        Note: loop is intentional — each update may target different columns,
        so executemany/multi-row UPDATE is not feasible. All runs in one
        transaction to minimize round-trip overhead.
        """
        if not updates:
            return 0

        async with self.db_pool.acquire() as conn, conn.transaction():
            total_updated = 0
            for update in updates:
                practice_id = update.pop("id")
                if not update:
                    continue
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
        """Recupera clienti con le loro pratiche in una singola query."""
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
        self, query: str, limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Ricerca clienti ottimizzata con full-text search."""
        async with self.db_pool.acquire() as conn:
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
        """Statistiche pratiche aggregate."""
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
            stats: dict[str, Any] = {
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
        """Recupera pratiche scadute o in scadenza."""
        async with self.db_pool.acquire() as conn:
            threshold = datetime.now(timezone.utc) + timedelta(days=days)
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
    """Verifica integrità tabelle CRM."""
    async with db_pool.acquire() as conn:
        checks: dict[str, Any] = {}
        checks["clients"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM clients")}
        checks["practices"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM practices")}
        checks["practice_types"] = {
            "count": await conn.fetchval("SELECT COUNT(*) FROM practice_types"),
        }
        checks["interactions"] = {"count": await conn.fetchval("SELECT COUNT(*) FROM interactions")}
        checks["orphan_clients"] = await conn.fetchval("""
            SELECT COUNT(*) FROM clients c
            WHERE NOT EXISTS (
                SELECT 1 FROM practices p WHERE p.client_id = c.id
            )
        """)
        checks["orphan_practices"] = await conn.fetchval("""
            SELECT COUNT(*) FROM practices p
            WHERE NOT EXISTS (
                SELECT 1 FROM clients c WHERE c.id = p.client_id
            )
        """)
        return checks
