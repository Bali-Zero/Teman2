"""
Diagnostics Tool - System Health & Status Check
Permette a Zantara di diagnosticare lo stato dei servizi backend (DB, Redis, Qdrant).
"""

import logging

import asyncpg
import httpx
from redis.asyncio import Redis

from app.core.config import settings
from services.rag.agent.structures import BaseTool

logger = logging.getLogger(__name__)


class DiagnosticsTool(BaseTool):
    """
    Tool diagnostico per verificare lo stato dei servizi infrastrutturali.
    Utile per debugging e "self-healing".
    """

    @property
    def name(self) -> str:
        return "system_diagnostics"

    @property
    def description(self) -> str:
        return "Check the health and status of backend systems (Database, Redis, Qdrant). Use this when there are connection errors or to verify system integrity."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "check_type": {
                    "type": "string",
                    "enum": ["all", "database", "redis", "qdrant", "internet"],
                    "description": "The specific system component to check (default: all)",
                }
            },
            "required": [],
        }

    async def execute(self, check_type: str = "all", **kwargs) -> str:
        """Esegue i controlli diagnostici richiesti"""
        results = []

        if check_type in ["all", "database"]:
            results.append(await self._check_database())

        if check_type in ["all", "redis"]:
            results.append(await self._check_redis())

        if check_type in ["all", "qdrant"]:
            results.append(await self._check_qdrant())

        if check_type in ["all", "internet"]:
            results.append(await self._check_internet())

        return "\n\n".join(results)

    async def _check_database(self) -> str:
        """Verifica connessione PostgreSQL"""
        if not settings.database_url:
            return "❌ Database: URL not configured"

        try:
            # Create a temporary connection just for the check
            conn = await asyncpg.connect(settings.database_url)
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return f"✅ Database: Connected ({version.split()[0]}...)"
        except Exception as e:
            return f"❌ Database: Connection failed - {str(e)}"

    async def _check_redis(self) -> str:
        """Verifica connessione Redis"""
        if not settings.redis_url:
            return "❌ Redis: URL not configured"

        try:
            r = Redis.from_url(settings.redis_url, decode_responses=True)
            await r.ping()
            await r.close()
            return "✅ Redis: Connected & Ready"
        except Exception as e:
            return f"❌ Redis: Connection failed - {str(e)}"

    async def _check_qdrant(self) -> str:
        """Verifica connessione Qdrant"""
        if not settings.qdrant_url:
            return "❌ Qdrant: URL not configured"

        try:
            url = f"{settings.qdrant_url.rstrip('/')}/collections"
            headers = {}
            if settings.qdrant_api_key:
                headers["api-key"] = settings.qdrant_api_key

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    collections = resp.json().get("result", {}).get("collections", [])
                    count = len(collections)
                    names = [c.get("name") for c in collections[:3]]
                    suffix = "..." if count > 3 else ""
                    return f"✅ Qdrant: Connected ({count} collections: {', '.join(names)}{suffix})"
                else:
                    return f"❌ Qdrant: Error {resp.status_code} - {resp.text}"
        except Exception as e:
            return f"❌ Qdrant: Connection failed - {str(e)}"

    async def _check_internet(self) -> str:
        """Verifica connettività internet (verso Google DNS)"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get("https://www.google.com")
                if resp.status_code == 200:
                    return "✅ Internet: Connected"
                return f"⚠️ Internet: Status {resp.status_code}"
        except Exception as e:
            return f"❌ Internet: Unreachable - {str(e)}"
