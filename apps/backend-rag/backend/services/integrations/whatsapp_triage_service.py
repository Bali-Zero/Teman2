"""
WhatsApp Triage Service
Intelligent routing: Personal messages → Human, Business queries → AI RAG

Handles:
- Contact whitelist (family, close friends)
- Context detection (personal vs business)
- Explicit human requests (/human command)
- Smart escalation decisions
"""

import logging
from enum import Enum

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class TriageDecision(str, Enum):
    """Triage decision types"""

    ESCALATE_PERSONAL = "escalate_personal"  # Personal contact (whitelist)
    ESCALATE_REQUEST = "escalate_request"  # User asked for human
    ESCALATE_CONTEXT = "escalate_context"  # Personal context detected
    BOT_CAN_HANDLE = "bot_can_handle"  # Business query for AI
    OFFER_CHOICE = "offer_choice"  # Ambiguous, ask user


class WhatsAppTriageService:
    """Service to determine if message should go to human or AI."""

    def __init__(self) -> None:
        # Personal contacts whitelist (from env var)
        whitelist = settings.whatsapp_personal_contacts or ""
        self.personal_contacts = {phone.strip() for phone in whitelist.split(",") if phone.strip()}
        # Allowed numbers whitelist — if set, all other numbers are silently ignored
        allowed = settings.whatsapp_allowed_numbers or ""
        self.allowed_numbers: set[str] = {
            phone.strip() for phone in allowed.split(",") if phone.strip()
        }

    def is_allowed(self, phone: str) -> bool:
        """Return True if the phone number is allowed to interact with the bot.
        If no whitelist is configured, everyone is allowed."""
        if not self.allowed_numbers:
            return True
        normalized = phone.lstrip("+")
        return normalized in self.allowed_numbers

    async def should_escalate(
        self,
        phone: str,
        message_text: str,
        sender_name: str | None = None,  # noqa: ARG002
    ) -> tuple[TriageDecision, str]:
        """
        Determine if message should escalate to human.

        Args:
            phone: Sender phone number (format: "6281234567890")
            message_text: Message content
            sender_name: Optional sender name from WhatsApp

        Returns:
            (decision, reason) tuple
        """

        # Normalize phone (remove + if present)
        normalized_phone = phone.lstrip("+")

        # 1. WHITELIST CHECK: Personal contacts always escalate
        if normalized_phone in self.personal_contacts:
            logger.info(f"Escalating to human: whitelist contact {phone}")
            return TriageDecision.ESCALATE_PERSONAL, "personal_contact"

        # 2. EXPLICIT HUMAN REQUEST
        explicit_triggers = [
            "/human",
            "/zero",
            "parla con zero",
            "voglio zero",
            "speak to zero",
            "talk to zero",
            "bicara dengan zero",
            "saya mau zero",
        ]

        message_lower = message_text.lower().strip()
        if any(trigger in message_lower for trigger in explicit_triggers):
            logger.info(f"Escalating to human: explicit request from {phone}")
            return TriageDecision.ESCALATE_REQUEST, "explicit_request"

        # 3. PERSONAL CONTEXT DETECTION
        personal_keywords = [
            # Italian
            "mamma",
            "papà",
            "famiglia",
            "cena",
            "pranzo",
            "compleanno",
            "ci vediamo",
            "ti amo",
            "come stai tu",
            "weekend",
            "domenica",
            "sabato",
            "festa",
            # English
            "mom",
            "dad",
            "family",
            "dinner",
            "lunch",
            "birthday",
            "see you",
            "love you",
            "how are you",
            "party",
            # Indonesian
            "ibu",
            "ayah",
            "keluarga",
            "makan",
            "ulang tahun",
            "ketemu",
            "sayang",
            "apa kabar kamu",
        ]

        if any(keyword in message_lower for keyword in personal_keywords):
            logger.info(f"Escalating to human: personal context detected from {phone}")
            return TriageDecision.ESCALATE_CONTEXT, "personal_context"

        # 4. BUSINESS CONTEXT (AI can handle)
        business_keywords = [
            # Visa-related
            "kitas",
            "kitap",
            "visa",
            "voa",
            "b211",
            "e28a",
            "e28c",
            "c312",
            "imta",
            "rptka",
            "work permit",
            "izin kerja",
            "d12",
            "e33g",
            "investor",
            "retirement",
            "second home",
            "freelance",
            "remote worker",
            "digital nomad",
            "extension",
            "perpanjangan",
            "sponsor",
            # Company/Business
            "pt pma",
            "company",
            "business",
            "perusahaan",
            "badan usaha",
            "nib",
            "oss",
            # Tax
            "tax",
            "pajak",
            "npwp",
            "spt",
            # Pricing
            "quanto costa",
            "berapa harga",
            "how much",
            "price",
            "cost",
            "biaya",
            "tarif",
            # Service inquiry
            "servizi",
            "layanan",
            "services",
            "bali zero",
            "zantara",
        ]

        if any(keyword in message_lower for keyword in business_keywords):
            logger.info(f"AI handling business query from {phone}")
            return TriageDecision.BOT_CAN_HANDLE, "business_query"

        # 5. GREETING CHECK (first message)
        greetings = [
            "ciao",
            "hello",
            "hi",
            "halo",
            "hey",
            "good morning",
            "good afternoon",
            "selamat pagi",
            "selamat siang",
            "buongiorno",
        ]

        # If ONLY greeting (short message), offer choice
        if len(message_text.split()) <= 3 and any(
            greeting in message_lower for greeting in greetings
        ):
            logger.info(f"Offering choice to {phone}: greeting message")
            return TriageDecision.OFFER_CHOICE, "greeting_only"

        # 6. DEFAULT: Let AI handle everything else (Zero style — always respond)
        logger.info(f"AI handling general query from {phone}")
        return TriageDecision.BOT_CAN_HANDLE, "general_query"

    def get_escalation_message(
        self,
        decision: TriageDecision,
        sender_name: str | None = None,
    ) -> str:
        """
        Get appropriate message for escalation.

        Args:
            decision: Triage decision
            sender_name: Optional sender name

        Returns:
            Message to send to user
        """

        greeting = f"Ciao {sender_name}!" if sender_name else "Ciao!"

        if decision == TriageDecision.ESCALATE_PERSONAL:
            return f"{greeting} Un attimo, ti richiamo 👋"

        if decision == TriageDecision.ESCALATE_REQUEST:
            return "Un momento, ti rispondo a breve 📞"

        if decision == TriageDecision.ESCALATE_CONTEXT:
            return f"{greeting} Dammi un secondo!"

        return "Un attimo..."

    def get_welcome_message(self, sender_name: str | None = None) -> str:
        """
        Get welcome message for ambiguous/choice situations.

        Args:
            sender_name: Optional sender name

        Returns:
            Welcome message offering choice
        """

        greeting = f"Hi {sender_name}!" if sender_name else "Hi!"

        return f"""{greeting} 👋

I'm Zantara, the AI assistant for Bali Zero. How can I help you? Visas, KITAS, company setup — just ask!"""


# Singleton instance
whatsapp_triage_service = WhatsAppTriageService()
