"""
Birthplace Enrichment Service

Enriches client birthplace data with cultural context using local Ollama LLM.
Runs as a cron job at 22:00 Bali time (Asia/Makassar).

Data enriched:
- Famous people from the city
- Important historical events
- Cultural facts and traditions
- Local specialties and cuisine
- Conversation starters for Zantara
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_BASE_URL = settings.ollama_url
OLLAMA_MODEL = "qwen3.5:9b"  # Fast local model for cultural enrichment
OLLAMA_TIMEOUT = 120.0  # 2 minutes for generation

# Batch settings
BATCH_SIZE = 10  # Process 10 clients per run to avoid overloading Ollama


class BirthplaceEnrichmentService:
    """Service to enrich client birthplace data with cultural context."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._client: httpx.AsyncClient | None = None

    def _get_client(self, timeout: float = OLLAMA_TIMEOUT) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("BirthplaceEnrichmentService HTTP client closed.")

    async def get_clients_needing_enrichment(self, limit: int = BATCH_SIZE) -> list[dict]:
        """
        Get clients with birthplace set but not yet enriched.

        Returns:
            List of clients needing enrichment
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, birthplace, nationality, custom_fields
                FROM clients
                WHERE birthplace IS NOT NULL
                  AND birthplace != ''
                  AND birthplace_enrichment_date IS NULL
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def call_ollama(self, prompt: str) -> str | None:
        """
        Call local Ollama LLM for enrichment.

        Args:
            prompt: The prompt to send to Ollama

        Returns:
            Generated text or None if failed
        """
        try:
            client = self._get_client(timeout=OLLAMA_TIMEOUT)
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500,
                    },
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                logger.error(f"Ollama returned status {response.status_code}")
                return None
        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return None

    def build_enrichment_prompt(self, birthplace: str, nationality: str | None) -> str:
        """
        Build prompt for birthplace enrichment.

        Args:
            birthplace: City/country of birth
            nationality: Client's nationality (optional)

        Returns:
            Prompt string for Ollama
        """
        context = f"Place: {birthplace}"
        if nationality:
            context += f"\nNationality context: {nationality}"

        return f"""You are a cultural knowledge assistant helping a luxury concierge service in Bali.
Research and provide interesting facts about a client's birthplace that could be used in personalized conversations.

{context}

Provide a JSON response with these fields:
{{
  "famous_people": ["List 2-3 famous people born there"],
  "historical_events": ["1-2 significant historical events"],
  "cultural_facts": ["2-3 interesting cultural traditions or facts"],
  "local_specialties": ["2-3 famous foods, products, or crafts"],
  "conversation_starters": ["2-3 personalized conversation topics for a concierge"]
}}

Keep responses concise and relevant for building rapport with clients.
Return ONLY the JSON object, no additional text."""

    def parse_enrichment_response(self, response: str) -> dict | None:
        """
        Parse Ollama response into structured data.

        Args:
            response: Raw response from Ollama

        Returns:
            Parsed dictionary or None if parsing failed
        """
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json.loads(json_match.group())
            return None
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Ollama response as JSON: {response[:200]}")
            return None

    async def enrich_client(self, client: dict) -> bool:
        """
        Enrich a single client's birthplace data.

        Args:
            client: Client dictionary with id, birthplace, etc.

        Returns:
            True if enrichment succeeded
        """
        client_id = client["id"]
        birthplace = client["birthplace"]
        nationality = client.get("nationality")

        logger.info(f"Enriching birthplace for client {client_id}: {birthplace}")

        # Build and send prompt
        prompt = self.build_enrichment_prompt(birthplace, nationality)
        response = await self.call_ollama(prompt)

        if not response:
            logger.warning(f"No response from Ollama for client {client_id}")
            return False

        # Parse response
        enrichment_data = self.parse_enrichment_response(response)
        if not enrichment_data:
            logger.warning(f"Failed to parse enrichment for client {client_id}")
            return False

        # Update client record
        try:
            async with self.db_pool.acquire() as conn:
                # Get existing custom_fields
                existing = client.get("custom_fields") or {}
                if isinstance(existing, str):
                    existing = json.loads(existing)

                # Add enrichment data
                existing["birthplace_enrichment"] = {
                    "data": enrichment_data,
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "model": OLLAMA_MODEL,
                }

                await conn.execute(
                    """
                    UPDATE clients
                    SET custom_fields = $1,
                        birthplace_enrichment_date = NOW(),
                        updated_at = NOW()
                    WHERE id = $2
                    """,
                    json.dumps(existing),
                    client_id,
                )
                logger.info(f"Successfully enriched client {client_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to update client {client_id}: {e}")
            return False

    async def run_batch_enrichment(self) -> dict[str, Any]:
        """
        Run batch enrichment for clients needing it.

        Returns:
            Statistics dictionary
        """
        stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "clients_processed": 0,
            "successful": 0,
            "failed": 0,
        }

        # Check if Ollama is available
        try:
            client = self._get_client(timeout=5.0)
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code != 200:
                logger.error("Ollama is not available")
                stats["error"] = "Ollama not available"
                return stats
        except Exception as e:
            # In production, Ollama might not be available. Log warning and exit gracefully.
            logger.warning(
                f"⚠️ Birthplace Enrichment skipped: Cannot connect to Ollama ({e}). This is expected if running on Fly.io without sidecar."
            )
            stats["error"] = f"Cannot connect to Ollama: {e}"
            return stats

        # Get clients needing enrichment
        clients = await self.get_clients_needing_enrichment()
        stats["clients_to_process"] = len(clients)

        if not clients:
            logger.info("No clients need birthplace enrichment")
            return stats

        logger.info(f"Processing {len(clients)} clients for birthplace enrichment")

        for client in clients:
            stats["clients_processed"] += 1
            success = await self.enrich_client(client)
            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1

            # Small delay between requests to avoid overwhelming Ollama
            await asyncio.sleep(1)

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Enrichment batch complete: {stats}")
        return stats


async def run_birthplace_enrichment_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Task function for autonomous scheduler.

    Args:
        db_pool: Database connection pool

    Returns:
        Task result statistics
    """
    service = BirthplaceEnrichmentService(db_pool)
    return await service.run_batch_enrichment()
