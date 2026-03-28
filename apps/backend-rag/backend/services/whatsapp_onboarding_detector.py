"""
WhatsApp Onboarding Intent Detector

Detects when a WhatsApp message indicates a new client onboarding scenario
and automatically triggers the chain_new_client_onboarding workflow.

Author: Cascade
Date: 2026-03-02
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OnboardingIntentDetector:
    """Detect new client onboarding intent from WhatsApp messages."""

    # Keywords that indicate new client onboarding intent
    NEW_CLIENT_KEYWORDS = [
        # English
        "new client",
        "onboard",
        "sign up",
        "register",
        "start business",
        "open company",
        "need visa",
        "moving to bali",
        "relocating",
        # Italian
        "nuovo cliente",
        "nuova cliente",
        "registrare",
        "aprire azienda",
        "trasferirmi",
        "trasferimento",
        "voglio aprire",
        # Indonesian
        "klien baru",
        "daftar",
        "buka perusahaan",
        "butuh visa",
    ]

    # Patterns that suggest business description
    BUSINESS_PATTERNS = [
        r"(?:business|company|azienda|perusahaan)[\s:]+(.+)",
        r"(?:doing|facendo|melakukan)[\s:]+(.+)",
        r"(?:want to|voglio|ingin)[\s:]+(.+)",
    ]

    def __init__(self, mcp_base_url: str = "http://localhost:8000") -> None:
        """Initialize detector with MCP server URL."""
        self.mcp_base_url = mcp_base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def detect_and_trigger(
        self,
        phone: str,
        message_text: str,
        sender_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Detect new client onboarding intent and trigger chain if detected.

        Args:
            phone: WhatsApp phone number
            message_text: Message content
            sender_name: Optional sender name

        Returns:
            Chain result if triggered, None otherwise
        """
        # Check if message contains new client intent
        if not self._has_onboarding_intent(message_text):
            return None

        logger.info(f"🎯 New client onboarding intent detected from {phone}")

        # Extract information from message
        extracted = self._extract_info(message_text, sender_name)

        if not extracted.get("name"):
            logger.warning(f"Cannot trigger onboarding: missing name for {phone}")
            return None

        # Trigger chain_new_client_onboarding via MCP
        try:
            result = await self._trigger_onboarding_chain(
                name=extracted["name"],
                email=extracted.get("email", f"{phone}@whatsapp.temp"),
                nationality=extracted.get("nationality", "Unknown"),
                business_description=extracted.get("business_description", "General business"),
                phone=phone,
            )
            logger.info(f"✅ Onboarding chain triggered for {phone}: {result.get('client_id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to trigger onboarding chain for {phone}: {e}")
            return None

    def _has_onboarding_intent(self, message_text: str) -> bool:
        """Check if message contains new client onboarding keywords."""
        text_lower = message_text.lower()
        return any(keyword in text_lower for keyword in self.NEW_CLIENT_KEYWORDS)

    def _extract_info(self, message_text: str, sender_name: str | None) -> dict[str, Any]:
        """
        Extract client information from message.

        Returns:
            Dict with name, email, nationality, business_description
        """
        info: dict[str, Any] = {}

        # Name: use sender_name or try to extract from message
        if sender_name:
            info["name"] = sender_name
        else:
            # Try to extract name from patterns like "My name is X" or "I'm X"
            name_match = re.search(
                r"(?:my name is|i'm|i am|sono|mi chiamo|nama saya)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                message_text,
                re.IGNORECASE,
            )
            if name_match:
                info["name"] = name_match.group(1).strip()

        # Email: extract if present
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message_text)
        if email_match:
            info["email"] = email_match.group(0)

        # Nationality: extract if mentioned
        nationality_match = re.search(
            r"(?:from|nationality|nazionalità|kewarganegaraan)\s+([A-Z][a-z]+)",
            message_text,
            re.IGNORECASE,
        )
        if nationality_match:
            info["nationality"] = nationality_match.group(1).strip()

        # Business description: extract from patterns
        for pattern in self.BUSINESS_PATTERNS:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                info["business_description"] = match.group(1).strip()
                break

        # If no business description found, use the whole message (cleaned)
        if not info.get("business_description"):
            # Remove common phrases to get core business description
            cleaned = message_text
            for phrase in ["new client", "nuovo cliente", "klien baru", "onboard", "sign up"]:
                cleaned = re.sub(phrase, "", cleaned, flags=re.IGNORECASE)
            info["business_description"] = cleaned.strip() or "General business inquiry"

        return info

    async def _trigger_onboarding_chain(
        self,
        name: str,
        email: str,
        nationality: str,
        business_description: str,
        phone: str,
    ) -> dict[str, Any]:
        """
        Call chain_new_client_onboarding via MCP server.

        Note: This assumes the MCP server exposes the chain as an HTTP endpoint.
        If using stdio MCP, this would need to be adapted.
        """
        # For now, we'll call the backend endpoint directly
        # In production, this should go through the MCP server
        payload = {
            "name": name,
            "email": email,
            "nationality": nationality,
            "business_description": business_description,
            "phone": phone,
        }

        # Note: The actual implementation depends on how the MCP chain is exposed
        # This is a placeholder that would need to be connected to the actual MCP invocation
        logger.info(f"Would trigger chain_new_client_onboarding with: {payload}")

        # Return mock result for now
        return {
            "chain": "new_client_onboarding",
            "triggered_by": "whatsapp_auto_detect",
            "payload": payload,
            "status": "queued",
        }


# Singleton instance
_detector_instance: OnboardingIntentDetector | None = None


def get_onboarding_detector() -> OnboardingIntentDetector:
    """Get singleton instance of OnboardingIntentDetector."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = OnboardingIntentDetector()
    return _detector_instance
