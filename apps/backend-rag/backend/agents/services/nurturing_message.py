"""
Nurturing Message Service

Responsibility: Generate personalized nurturing messages using AI.
"""

import asyncio
import logging
from typing import Any

from services.communication import detect_language, get_language_instruction

logger = logging.getLogger(__name__)

try:
    from llm.zantara_ai_client import ZantaraAIClient

    ZANTARA_AVAILABLE = True
except ImportError:
    ZantaraAIClient = None
    ZANTARA_AVAILABLE = False


class NurturingMessageService:
    """Service for generating personalized nurturing messages"""

    def __init__(self, ai_client: ZantaraAIClient | None = None):
        """
        Initialize NurturingMessageService.

        Args:
            ai_client: ZantaraAIClient instance (if None, will create new)
        """
        self.ai_client = ai_client or (ZantaraAIClient() if ZANTARA_AVAILABLE else None)

    async def generate_message(self, client_data: dict[str, Any], timeout: float = 30.0) -> str:
        """
        Generate personalized nurturing message with AI.

        Args:
            client_data: Client data with segment, risk_level, etc.
            timeout: Maximum time to wait for AI generation

        Returns:
            Generated message text
        """
        if not self.ai_client:
            return self._generate_fallback_message(client_data)

        prompt = self._build_prompt(client_data)

        try:
            # Add timeout for AI generation
            message = await asyncio.wait_for(
                self.ai_client.generate_text(prompt=prompt, max_tokens=300, temperature=0.7),
                timeout=timeout,
            )
            return message.strip()
        except asyncio.TimeoutError:
            logger.error(
                f"Timeout generating nurturing message for {client_data.get('name', 'client')}"
            )
            return self._generate_fallback_message(client_data)
        except Exception as e:
            logger.error(f"Error generating nurturing message: {e}", exc_info=True)
            return self._generate_fallback_message(client_data)

    def _build_prompt(self, client_data: dict[str, Any]) -> str:
        """Build AI prompt for message generation"""
        # Detect language from client name/notes (default to Italian for Bali Zero)
        client_name = client_data.get("name", "Client")
        client_notes = client_data.get("notes", "")
        detected_language = detect_language(f"{client_name} {client_notes}")
        language_instruction = get_language_instruction(detected_language)

        return f"""Generate a personalized WhatsApp message to nurture this client:

Client Profile:
- Name: {client_name}
- Segment: {client_data.get("segment", "unknown")}
- LTV Score: {client_data.get("ltv_score", 0)}/100
- Risk Level: {client_data.get("risk_level", "unknown")}
- Days Since Last Contact: {client_data.get("days_since_last_interaction", 0)}
- Total Interactions: {client_data.get("total_interactions", 0)}
- Practice Count: {client_data.get("practice_count", 0)}
- Avg Sentiment: {client_data.get("sentiment_score", 0)}/100

{language_instruction}

Guidelines:
1. Warm and personal tone (use their name)
2. Reference their specific situation if known
3. Provide genuine value (not just a check-in)
4. Include a clear, low-friction call-to-action
5. Max 2-3 sentences

Output ONLY the message text, no explanations."""

    def _generate_fallback_message(self, client_data: dict[str, Any]) -> str:
        """Generate fallback message when AI is not available"""
        name = client_data.get("name", "Cliente")
        segment = client_data.get("segment", "")
        risk_level = client_data.get("risk_level", "")

        if segment == "VIP":
            return f"Ciao {name}, come stai? È un po' che non ci sentiamo. C'è qualcosa di cui posso occuparmi per te?"
        elif risk_level == "HIGH_RISK":
            return f"Ciao {name}, spero tutto bene. Volevo solo sapere se hai bisogno di qualcosa."
        else:
            return f"Ciao {name}, ti mando un saluto! Se hai bisogno di supporto, sono qui."
