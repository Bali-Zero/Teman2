"""
CRM Enrichment — consolidated module.

Merges:
  - birthplace_enrichment_service.py  (BirthplaceEnrichmentService, run_birthplace_enrichment_task)
  - conversation_title_generator.py   (generate_conversation_title)
  - ai_crm_extractor.py               (AICRMExtractor, get_extractor, AsyncpgJSONEncoder)
"""

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# AICRMExtractor (from ai_crm_extractor.py)
# ─────────────────────────────────────────────────────────────────────────────

class AsyncpgJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle asyncpg types (UUID, datetime)."""

    def default(self, obj: object) -> str:
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class AICRMExtractor:
    """AI-powered entity extraction from conversations."""

    def __init__(self, ai_client=None) -> None:
        from backend.llm.zantara_ai_client import ZantaraAIClient
        try:
            self.client = ai_client if ai_client else ZantaraAIClient()
            logger.info(f"✅ AICRMExtractor initialized with ZANTARA AI for {settings.COMPANY_NAME}")
        except (ImportError, RuntimeError, AttributeError) as e:
            logger.error(f"❌ Failed to initialize ZANTARA AI (import/runtime): {e}", exc_info=True)
            raise
        except Exception as e:  # noqa: BLE001 — unknown failure modes in LLM client init must surface
            logger.error(f"❌ Failed to initialize ZANTARA AI (unexpected): {e}", exc_info=True)
            raise

    async def extract_from_conversation(
        self, messages: list[dict], existing_client_data: dict | None = None,
    ) -> dict:
        conversation_text = "\n\n".join(
            [f"{msg['role'].upper()}: {msg['content']}" for msg in messages],
        )
        existing_data_str = "NO EXISTING CLIENT DATA"
        if existing_client_data:
            existing_data_str = "EXISTING CLIENT DATA:\\n" + json.dumps(
                existing_client_data, indent=2, cls=AsyncpgJSONEncoder,
            )

        extraction_prompt = f"""You are an AI assistant analyzing a customer service conversation for {settings.COMPANY_NAME}, a company providing immigration, visa, company setup, and tax services in Bali, Indonesia.

Your task is to extract structured information from the conversation to populate a CRM system.

{settings.COMPANY_NAME.upper()} SERVICES (practice_type_code):
- KITAS: Limited Stay Permit (work permit)
- PT_PMA: Foreign Investment Company
- INVESTOR_VISA: Investor Visa
- RETIREMENT_VISA: Retirement Visa (55+)
- NPWP: Tax ID Number
- BPJS: Health Insurance
- IMTA: Work Permit

CONVERSATION:
{conversation_text}

{existing_data_str}

Extract the following information and return ONLY valid JSON (no markdown, no extra text):
"""
        content = ""
        try:
            response = await self.client.conversational(
                extraction_prompt, "system_crm_extractor", max_tokens=8192,
            )
            content = response["text"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            extracted_data = json.loads(content)
            client_confidence = extracted_data.get("client", {}).get("confidence", 0.0)
            logger.info(f"✅ Extracted CRM data with {client_confidence:.2f} client confidence")

            # Threshold: low-confidence extractions should not auto-populate CRM
            if client_confidence < 0.7:
                logger.warning(
                    f"⚠️ Low confidence extraction ({client_confidence:.2f} < 0.70) — "
                    f"marking as low_confidence to prevent auto-assignment"
                )
                extracted_data["_low_confidence"] = True

            return extracted_data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse extraction JSON: {e}", exc_info=True)
            logger.error(f"Raw response: {content}", exc_info=True)
            return self._get_empty_extraction()
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.error(f"❌ Extraction failed (LLM/data): {e}", exc_info=True)
            return self._get_empty_extraction()
        except Exception as e:  # noqa: BLE001 — fallback so extraction never crashes caller
            logger.error(f"❌ Extraction failed (unexpected): {e}", exc_info=True)
            return self._get_empty_extraction()

    def _get_empty_extraction(self) -> dict:
        return {
            "client": {
                "full_name": None, "email": None, "phone": None,
                "whatsapp": None, "nationality": None, "confidence": 0.0,
            },
            "practice_intent": {"detected": False, "practice_type_code": None, "confidence": 0.0, "details": ""},
            "sentiment": "neutral", "urgency": "normal", "summary": "",
            "action_items": [], "topics_discussed": [],
            "extracted_entities": {"dates": [], "amounts": [], "locations": [], "documents_mentioned": []},
        }

    async def enrich_client_data(self, extracted: dict, existing_client: dict | None = None) -> dict:
        if not existing_client:
            return extracted["client"]
        merged = existing_client.copy()
        if extracted["client"]["confidence"] >= 0.6:
            for field in ["full_name", "email", "phone", "whatsapp", "nationality"]:
                extracted_value = extracted["client"].get(field)
                if extracted_value and not merged.get(field):
                    merged[field] = extracted_value
        return merged

    async def should_create_practice(self, extracted: dict) -> bool:
        practice = extracted.get("practice_intent", {})
        return (
            practice.get("detected", False)
            and practice.get("confidence", 0) >= 0.7
            and practice.get("practice_type_code") is not None
        )


_extractor_instance: AICRMExtractor | None = None


def get_extractor(ai_client: Any = None) -> AICRMExtractor:
    """Get or create singleton extractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        try:
            _extractor_instance = AICRMExtractor(ai_client=ai_client)
            logger.info("✅ AI CRM Extractor initialized")
        except (ImportError, RuntimeError, AttributeError) as e:
            logger.warning(f"⚠️  AI CRM Extractor not available (import/runtime): {e}")
            raise
        except Exception as e:  # noqa: BLE001 — unknown init failures must still surface to caller
            logger.warning(f"⚠️  AI CRM Extractor not available (unexpected): {e}")
            raise
    return _extractor_instance


# ─────────────────────────────────────────────────────────────────────────────
# BirthplaceEnrichmentService (from birthplace_enrichment_service.py)
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = settings.ollama_url
OLLAMA_MODEL = "qwen3.5:9b"
OLLAMA_TIMEOUT = 120.0
BATCH_SIZE = 10


class BirthplaceEnrichmentService:
    """Service to enrich client birthplace data with cultural context."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self._client: httpx.AsyncClient | None = None

    def _get_client(self, timeout: float = OLLAMA_TIMEOUT) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("BirthplaceEnrichmentService HTTP client closed.")

    async def get_clients_needing_enrichment(self, limit: int = BATCH_SIZE) -> list[dict]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, birthplace, nationality, custom_fields
                FROM clients
                WHERE birthplace IS NOT NULL AND birthplace != ''
                  AND birthplace_enrichment_date IS NULL
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def call_ollama(self, prompt: str) -> str | None:
        try:
            client = self._get_client(timeout=OLLAMA_TIMEOUT)
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.7, "num_predict": 500}},
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            logger.error(f"Ollama returned status {response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return None
        except httpx.HTTPError as e:
            logger.error(f"Ollama request failed (HTTP): {e}")
            return None
        except Exception as e:  # noqa: BLE001 — enrichment is best-effort, never crash cron caller
            logger.error(f"Ollama request failed (unexpected): {e}", exc_info=True)
            return None

    def build_enrichment_prompt(self, birthplace: str, nationality: str | None) -> str:
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
        import re
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json.loads(json_match.group())
            return None
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Ollama response as JSON: {response[:200]}")
            return None

    async def enrich_client(self, client: dict) -> bool:
        client_id = client["id"]
        birthplace = client["birthplace"]
        nationality = client.get("nationality")
        logger.info(f"Enriching birthplace for client {client_id}: {birthplace}")

        prompt = self.build_enrichment_prompt(birthplace, nationality)
        response = await self.call_ollama(prompt)
        if not response:
            logger.warning(f"No response from Ollama for client {client_id}")
            return False

        enrichment_data = self.parse_enrichment_response(response)
        if not enrichment_data:
            logger.warning(f"Failed to parse enrichment for client {client_id}")
            return False

        try:
            async with self.db_pool.acquire() as conn:
                existing = client.get("custom_fields") or {}
                if isinstance(existing, str):
                    existing = json.loads(existing)
                existing["birthplace_enrichment"] = {
                    "data": enrichment_data,
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                    "model": OLLAMA_MODEL,
                }
                await conn.execute(
                    """
                    UPDATE clients
                    SET custom_fields = $1, birthplace_enrichment_date = NOW(), updated_at = NOW()
                    WHERE id = $2
                    """,
                    json.dumps(existing), client_id,
                )
                logger.info(f"Successfully enriched client {client_id}")
                return True
        except (asyncpg.PostgresError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to update client {client_id} (DB/serialization): {e}", exc_info=True)
            return False
        except Exception as e:  # noqa: BLE001 — enrichment never crashes the batch loop
            logger.error(f"Failed to update client {client_id} (unexpected): {e}", exc_info=True)
            return False

    async def run_batch_enrichment(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "clients_processed": 0, "successful": 0, "failed": 0,
        }
        try:
            client = self._get_client(timeout=5.0)
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code != 200:
                logger.error("Ollama is not available")
                stats["error"] = "Ollama not available"
                return stats
        except httpx.HTTPError as e:
            logger.warning(f"⚠️ Birthplace Enrichment skipped: Cannot connect to Ollama ({e}).")
            stats["error"] = f"Cannot connect to Ollama: {e}"
            return stats
        except Exception as e:  # noqa: BLE001 — availability probe must never propagate to scheduler
            logger.warning(
                f"⚠️ Birthplace Enrichment skipped: unexpected error probing Ollama ({e}).",
                exc_info=True,
            )
            stats["error"] = f"Ollama probe error: {e}"
            return stats

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
            await asyncio.sleep(1)

        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Enrichment batch complete: {stats}")
        return stats


async def run_birthplace_enrichment_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """Task function for autonomous scheduler."""
    service = BirthplaceEnrichmentService(db_pool)
    return await service.run_batch_enrichment()


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Title Generator (from conversation_title_generator.py)
# ─────────────────────────────────────────────────────────────────────────────

_TITLE_PROMPT = """Generate a concise, professional title (max {max_length} characters) for a conversation starting with this message:

"{message}"

Requirements:
- Professional and clear
- Under {max_length} characters
- No quotes or special formatting
- Capture main topic/intent
- Language: Match the input language (Italian, English, etc.)

Return ONLY the title text, nothing else."""


async def generate_conversation_title(
    conversation_id: str, first_user_message: str, max_length: int = 50,
) -> str | None:
    """Generate concise title from first user message. Tries Ollama first, falls back to Gemini."""
    if not first_user_message or len(first_user_message.strip()) < 10:
        logger.info(
            f"Skipping title generation for conv {conversation_id}: "
            f"message too short ({len(first_user_message)} chars)",
        )
        return None

    prompt = _TITLE_PROMPT.format(max_length=max_length, message=first_user_message[:200])

    title = await _generate_title_via_ollama(conversation_id, prompt, max_length)
    if title:
        return title

    title = await _generate_title_via_gemini(conversation_id, prompt, max_length)
    if title:
        return title

    logger.warning(f"All title generation methods failed for conv {conversation_id}")
    return None


async def _generate_title_via_ollama(conversation_id: str, prompt: str, max_length: int) -> str | None:
    try:
        from backend.llm.ollama_client import MODEL_FAST, ollama_chat
        logger.info(f"Generating title for conv {conversation_id} via Ollama ({MODEL_FAST})...")
        result = await ollama_chat(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL_FAST,
            temperature=0.3,
            max_tokens=60,
            timeout=10.0,
        )
        if not result:
            return None
        title = _clean_title(result, max_length)
        logger.info(f'✅ Generated title for conv {conversation_id} via Ollama: "{title}"')
        return title
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning(f"Ollama title generation error for conv {conversation_id}: {e}")
        return None
    except Exception as e:  # noqa: BLE001 — title generation is best-effort; Gemini fallback follows
        logger.warning(
            f"Ollama title generation unexpected error for conv {conversation_id}: {e}",
            exc_info=True,
        )
        return None


async def _generate_title_via_gemini(conversation_id: str, prompt: str, max_length: int) -> str | None:
    try:
        from backend.llm.genai_client import get_genai_client
        client = get_genai_client()
        if not client or not client.is_available:
            logger.warning("GenAI client not available, skipping Gemini fallback")
            return None
        logger.info(f"Generating title for conv {conversation_id} via Gemini Flash...")
        result = await client.generate_content(
            contents=prompt,
            model="gemini-2.0-flash-lite",
            max_output_tokens=30,
            temperature=0.3,
        )
        if not result or not result.get("text"):
            return None
        title = _clean_title(result["text"], max_length)
        logger.info(f'✅ Generated title for conv {conversation_id} via Gemini: "{title}"')
        return title
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning(f"Gemini title generation error for conv {conversation_id}: {e}")
        return None
    except Exception as e:  # noqa: BLE001 — title generation is best-effort and must never crash caller
        logger.warning(
            f"Gemini title generation unexpected error for conv {conversation_id}: {e}",
            exc_info=True,
        )
        return None


def _clean_title(raw: str, max_length: int) -> str:
    title = raw.strip().strip('"').strip("'").strip()
    if "<think>" in title:
        title = title.split("</think>")[-1].strip()
    return title[:max_length]
