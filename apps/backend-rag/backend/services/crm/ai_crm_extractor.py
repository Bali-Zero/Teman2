"""
ZANTARA CRM - AI Entity Extraction Service
Uses ZANTARA AI to extract structured data from conversations for CRM auto-population
"""

import json
import logging

from backend.llm.zantara_ai_client import ZantaraAIClient

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class AICRMExtractor:
    """
    AI-powered entity extraction from conversations
    Extracts: client info, practice intent, sentiment, urgency, action items
    """

    def __init__(self, ai_client=None):
        """Initialize with ZANTARA AI client"""
        try:
            self.client = ai_client if ai_client else ZantaraAIClient()
            logger.info(
                f"✅ AICRMExtractor initialized with ZANTARA AI for {settings.COMPANY_NAME}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize ZANTARA AI: {e}")
            raise

    async def extract_from_conversation(
        self, messages: list[dict], existing_client_data: dict | None = None
    ) -> dict:
        """
        Extract structured CRM data from conversation messages

        Args:
            messages: List of {role: "user"|"assistant", content: str}
            existing_client_data: Optional existing client info to enrich

        Returns:
            {
                "client": {
                    "full_name": str or None,
                    "email": str or None,
                    "phone": str or None,
                    "whatsapp": str or None,
                    "nationality": str or None,
                    "confidence": float (0-1)
                },
                "practice_intent": {
                    "detected": bool,
                    "practice_type_code": str or None (e.g., "KITAS", "PT_PMA"),
                    "confidence": float,
                    "details": str
                },
                "sentiment": str ("positive"|"neutral"|"negative"|"urgent"),
                "urgency": str ("low"|"normal"|"high"|"urgent"),
                "summary": str (1-2 sentence summary),
                "action_items": List[str],
                "topics_discussed": List[str],
                "extracted_entities": {
                    "dates": List[str],
                    "amounts": List[str],
                    "locations": List[str],
                    "documents_mentioned": List[str]
                }
            }
        """

        # Build conversation text
        conversation_text = "\n\n".join(
            [f"{msg['role'].upper()}: {msg['content']}" for msg in messages]
        )

        existing_data_str = "NO EXISTING CLIENT DATA"
        if existing_client_data:
            existing_data_str = "EXISTING CLIENT DATA:\\n" + json.dumps(
                existing_client_data, indent=2
            )

        # Extraction prompt
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

        try:
            # Use ZANTARA AI for extraction
            response = await self.client.conversational(
                extraction_prompt, "system_crm_extractor", max_tokens=8192
            )
            content = response["text"]
            content = content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            # Parse JSON
            extracted_data = json.loads(content)

            logger.info(
                f"✅ Extracted CRM data with {extracted_data['client']['confidence']:.2f} client confidence"
            )

            return extracted_data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse extraction JSON: {e}")
            logger.error(f"Raw response: {content}")
            # Return minimal structure
            return self._get_empty_extraction()

        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}")
            return self._get_empty_extraction()

    def _get_empty_extraction(self) -> dict:
        """Return empty extraction structure"""
        return {
            "client": {
                "full_name": None,
                "email": None,
                "phone": None,
                "whatsapp": None,
                "nationality": None,
                "confidence": 0.0,
            },
            "practice_intent": {
                "detected": False,
                "practice_type_code": None,
                "confidence": 0.0,
                "details": "",
            },
            "sentiment": "neutral",
            "urgency": "normal",
            "summary": "",
            "action_items": [],
            "topics_discussed": [],
            "extracted_entities": {
                "dates": [],
                "amounts": [],
                "locations": [],
                "documents_mentioned": [],
            },
        }

    async def enrich_client_data(
        self, extracted: dict, existing_client: dict | None = None
    ) -> dict:
        """
        Merge extracted data with existing client data (prefer non-null values)

        Args:
            extracted: Extracted client data from conversation
            existing_client: Existing client record from database

        Returns:
            Merged client data
        """

        if not existing_client:
            return extracted["client"]

        merged = existing_client.copy()

        # Update fields only if extracted value is not None and has good confidence
        if extracted["client"]["confidence"] >= 0.6:
            for field in ["full_name", "email", "phone", "whatsapp", "nationality"]:
                extracted_value = extracted["client"].get(field)
                if extracted_value and not merged.get(field):
                    merged[field] = extracted_value

        return merged

    async def should_create_practice(self, extracted: dict) -> bool:
        """
        Determine if we should auto-create a practice based on extraction

        Returns True if:
        - Practice intent detected
        - Confidence >= 0.7
        - Practice type is valid
        """

        practice = extracted.get("practice_intent", {})

        return (
            practice.get("detected", False)
            and practice.get("confidence", 0) >= 0.7
            and practice.get("practice_type_code") is not None
        )


# Singleton instance
_extractor_instance: AICRMExtractor | None = None


def get_extractor(ai_client=None) -> AICRMExtractor:
    """Get or create singleton extractor instance"""
    global _extractor_instance

    if _extractor_instance is None:
        try:
            _extractor_instance = AICRMExtractor(ai_client=ai_client)
            logger.info("✅ AI CRM Extractor initialized")
        except Exception as e:
            logger.warning(f"⚠️  AI CRM Extractor not available: {e}")
            raise

    return _extractor_instance
