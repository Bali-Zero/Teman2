"""
CRM Cache Manager

Gestione cache intelligente per dati CRM frequentemente accessati.
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class CRMCache:
    """Cache in-memory per dati CRM con TTL."""

    def __init__(self, default_ttl: int = 300) -> None:
        """
        Inizializza cache.

        Args:
            default_ttl: TTL default in secondi (5 minuti)
        """
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Recupera valore dalla cache."""
        async with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            if datetime.utcnow() > expiry:
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Salva valore in cache."""
        ttl = ttl or self._default_ttl
        expiry = datetime.utcnow() + timedelta(seconds=ttl)

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
        now = datetime.utcnow()
        async with self._lock:
            expired = [k for k, (_, expiry) in self._cache.items() if now > expiry]
            for k in expired:
                del self._cache[k]
            return len(expired)


# Singleton instance
crm_cache = CRMCache()


def cache_crm_result(ttl: int = 300, key_prefix: str = "") -> Any:
    """
    Decorator per caching risultati funzioni CRM.

    Args:
        ttl: Time to live in secondi
        key_prefix: Prefisso per la chiave cache
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator."""

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Genera chiave cache
            key_data = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"

            # Prova cache
            cached = await crm_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache HIT for {func.__name__}")
                return cached

            # Esegui funzione
            result = await func(*args, **kwargs)

            # Salva in cache
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


class QueryCache:
    """Cache specifica per query database frequenti."""

    def __init__(self) -> None:
        self._client_by_email: dict[str, tuple[int, datetime]] = {}
        self._client_by_phone: dict[str, tuple[int, datetime]] = {}
        self._practice_types: list[dict] | None = None
        self._practice_types_updated: datetime | None = None
        self._lock = asyncio.Lock()

    async def get_client_by_email(self, email: str) -> int | None:
        """Recupera client_id da email."""
        async with self._lock:
            if email not in self._client_by_email:
                return None
            client_id, expiry = self._client_by_email[email]
            if datetime.utcnow() > expiry:
                del self._client_by_email[email]
                return None
            return client_id

    async def set_client_by_email(self, email: str, client_id: int, ttl: int = 600) -> None:
        """Salva mapping email -> client_id."""
        async with self._lock:
            self._client_by_email[email.lower()] = (
                client_id,
                datetime.utcnow() + timedelta(seconds=ttl),
            )

    async def get_client_by_phone(self, phone: str) -> int | None:
        """Recupera client_id da telefono."""
        async with self._lock:
            normalized = self._normalize_phone(phone)
            if normalized not in self._client_by_phone:
                return None
            client_id, expiry = self._client_by_phone[normalized]
            if datetime.utcnow() > expiry:
                del self._client_by_phone[normalized]
                return None
            return client_id

    async def set_client_by_phone(self, phone: str, client_id: int, ttl: int = 600) -> None:
        """Salva mapping phone -> client_id."""
        async with self._lock:
            normalized = self._normalize_phone(phone)
            self._client_by_phone[normalized] = (
                client_id,
                datetime.utcnow() + timedelta(seconds=ttl),
            )

    async def get_practice_types(self) -> list[dict] | None:
        """Recupera tipi pratica (cachati per 1 ora)."""
        async with self._lock:
            if self._practice_types is None:
                return None
            if (
                self._practice_types_updated
                and datetime.utcnow() - self._practice_types_updated > timedelta(hours=1)
            ):
                self._practice_types = None
                return None
            return self._practice_types

    async def set_practice_types(self, types: list[dict]) -> None:
        """Salva tipi pratica in cache."""
        async with self._lock:
            self._practice_types = types
            self._practice_types_updated = datetime.utcnow()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalizza telefono per cache key.

        Uses the canonical E.164 normalization from validators.py.
        """
        from backend.services.crm.validators import normalize_phone_e164

        result = normalize_phone_e164(phone)
        return result or phone

    async def invalidate_client(self, client_id: int) -> None:
        """Invalida cache per cliente specifico."""
        async with self._lock:
            # Rimuovi da email cache
            emails_to_remove = [
                email for email, (cid, _) in self._client_by_email.items() if cid == client_id
            ]
            for email in emails_to_remove:
                del self._client_by_email[email]

            # Rimuovi da phone cache
            phones_to_remove = [
                phone for phone, (cid, _) in self._client_by_phone.items() if cid == client_id
            ]
            for phone in phones_to_remove:
                del self._client_by_phone[phone]


# Singleton
query_cache = QueryCache()
