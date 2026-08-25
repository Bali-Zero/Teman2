"""
WhatsApp Service - Inbound + Outbound
Uses Meta WhatsApp Business Cloud API

Handles:
- Sending messages to users
- Receiving webhook events
- Managing conversations
"""

import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.core.constants import HttpTimeoutConstants
from backend.services.rag.agentic._reasoning_stubs import get_localized_stub
from backend.utils.message_chunker import chunk_message
from backend.security.pii_log_identifier import redact_identifier_for_log

logger = logging.getLogger(__name__)

# WhatsApp Cloud API refuses a text body over this many characters.
WHATSAPP_BODY_LIMIT = 4096

# What a client sees when we could not name their language. A single ellipsis is
# understood as "there was more" in every language this bot speaks, and it is the
# only marker that cannot be WRONG. See fit_to_whatsapp_limit for why the
# localized sentence is opt-in rather than the default.
_NEUTRAL_TRUNCATION_MARKER = "…"


def fit_to_whatsapp_limit(text: str, language: str | None = None) -> str:
    """Cut an over-long body at a word boundary and mark it, instead of severing it.

    Until 2026-08-11 ``send_message`` enforced the limit with ``text[:4096]``: a
    silent cut, mid-word, with nothing telling the recipient anything was
    removed — they cannot tell a finished answer from a decapitated one.

    Measured live on ordinary client questions (two probes, 37 questions, cold
    start, no history): **~10% crossed the limit**. Worst case, "What is Hak
    Pakai and how long does it last?" returned 13,671 characters, so 9,575 —
    70% of the answer — disappeared. Production agrees at a lower rate on a much
    smaller sample: 4 of 311 bot replies, worst 7,521. It is not a fixed set of
    long questions either: that same question asked three times returned
    1,364 / 13,671 / 2,123 characters.

    **Why this lives here and not in the bot.** A first version of this cure sat
    in ``wa_inbox_bot``. The pre-existing test for the old behaviour said in its
    own docstring that truncation is "whatsapp_service.py's job", and a census
    agreed: ``send_message`` has ~14 non-test call sites — the outbox worker, the
    conversations router, compliance alerts, the client-value predictor — and
    only two of them (``whatsapp_chat.py``) chunk beforehand. Curing the bot
    would have cured one producer and left the rest severing words.

    **Why the localized sentence is opt-in.** ``detect_query_language`` is tuned
    for QUERIES: measured on an Italian *answer* it returns ``ENGLISH``. So this
    function cannot infer the recipient's language from the text it is sending,
    and guessing would put an English apology under an Italian message. Callers
    that know the language (they saw the incoming message) pass it and their
    client gets the full sentence; everyone else gets the boundary cut plus a
    neutral ellipsis, which is strictly better than a severed word and cannot be
    wrong.

    Neither marker promises the remainder. Nothing retains it, so "ask me to
    continue" would be a promise this path cannot keep.

    Fails OPEN: if anything here misbehaves the caller keeps the untouched text
    and the payload builder truncates exactly as it did before — a worse
    message, never a lost one.
    """
    # Self-guarding, not caller-guarded: without this a caller whose condition
    # drifts would append "I shortened this" to a message it did not shorten,
    # which is a lie about the text the recipient is holding.
    if len(text) <= WHATSAPP_BODY_LIMIT:
        return text

    try:
        marker = (
            get_localized_stub("truncated_tail", language)
            if language
            else _NEUTRAL_TRUNCATION_MARKER
        )
        # Budget from the SUFFIX, never from the chunker's default margin: that
        # margin is 96 characters and the localized sentence is longer, so a cure
        # that overflowed the limit it exists to respect would be its own bug.
        chunks = chunk_message(text, max_length=WHATSAPP_BODY_LIMIT - len(marker))
        if not chunks or not chunks[0]:
            return text
        return chunks[0] + marker
    # Broad on purpose: this is presentation. No failure of it may be the reason
    # a recipient gets nothing instead of a truncated something.
    except Exception as exc:
        logger.warning(
            "whatsapp: could not fit body to the %d-char limit: %s", WHATSAPP_BODY_LIMIT, exc
        )
        return text


class WhatsAppService:
    """Service for interacting with WhatsApp Business Cloud API."""

    def __init__(self) -> None:
        self._token = settings.whatsapp_api_token
        self._phone_number_id = settings.whatsapp_phone_number_id
        self._client: httpx.AsyncClient | None = None

    @property
    def token(self) -> str | None:
        """Token."""
        return self._token or settings.whatsapp_api_token

    @property
    def phone_number_id(self) -> str | None:
        """Phone number id."""
        return self._phone_number_id or settings.whatsapp_phone_number_id

    @property
    def api_url(self) -> str:
        """Api url."""
        return f"https://graph.facebook.com/v22.0/{self.phone_number_id}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=HttpTimeoutConstants.EXTERNAL_API_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def send_message(
        self,
        phone: str,
        text: str,
        reply_to_message_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a WhatsApp message.

        Args:
            phone: Recipient phone number (with country code, no +)
            text: Message text
            reply_to_message_id: Optional message ID to reply to
            language: Recipient's language, when the caller knows it (it saw the
                incoming message). Over-long bodies are cut at a word boundary
                either way; supplying this upgrades the marker from a neutral
                ellipsis to a sentence saying the reply was shortened. Do NOT
                guess it from `text` — see fit_to_whatsapp_limit.

        Returns:
            WhatsApp API response

        Note:
            Phone format: "6281234567890" (no + prefix)
            WhatsApp has 4096 char limit per message
        """
        if not self.token:
            raise ValueError("WhatsApp API token not configured")

        if not self.phone_number_id:
            raise ValueError("WhatsApp phone number ID not configured")

        # Ensure phone has no + prefix (Meta API format)
        if phone.startswith("+"):
            phone = phone[1:]

        client = await self._get_client()

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            # Cut at a boundary and mark it, rather than `text[:4096]` severing a
            # word in silence. fit_to_whatsapp_limit is a no-op below the limit,
            # so the overwhelming majority of sends are byte-identical to before.
            # The slice stays as a belt-and-braces guarantee that the payload can
            # never exceed what the API accepts, even if the fit fails open.
            "text": {"body": fit_to_whatsapp_limit(text, language)[:WHATSAPP_BODY_LIMIT]},
        }

        # Add reply context if provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        try:
            response = await client.post(
                f"{self.api_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            result = response.json()

            if response.status_code != 200:
                error_data = result.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                error_code = error_data.get("code", response.status_code)
                logger.error("WhatsApp API error [%s]: %s", error_code, error_msg)
                raise ValueError(f"WhatsApp API error [{error_code}]: {error_msg}")

            logger.info("Message sent to %s", redact_identifier_for_log(phone))
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to send WhatsApp message: %s", e)
            raise

    async def send_typing_action(
        self,
        phone: str,
    ) -> bool:
        """
        Send typing indicator (mark as read).

        Note: WhatsApp Cloud API doesn't have typing indicator.
        We mark the last message as read instead.

        Args:
            phone: Recipient phone number

        Returns:
            Success status
        """
        # WhatsApp Cloud API doesn't support typing indicator
        # This is a placeholder for consistency with other messaging services
        logger.debug(
            "Typing action not supported for WhatsApp, skipping for %s",
            redact_identifier_for_log(phone),
        )
        return True

    async def mark_message_read(
        self,
        message_id: str,
    ) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: Message ID to mark as read

        Returns:
            Success status
        """
        if not self.token or not self.phone_number_id:
            return False

        client = await self._get_client()

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            response = await client.post(
                f"{self.api_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            return response.status_code == 200

        except Exception as e:
            logger.warning("Failed to mark message as read: %s", e)
            return False

    def format_message(self, text: str) -> str:
        """
        Format message for WhatsApp.

        WhatsApp supports basic markdown:
        - *bold*
        - _italic_
        - ~strikethrough~
        - ```code```

        Args:
            text: Raw text

        Returns:
            Formatted text (currently passthrough, can be enhanced)
        """
        # For now, pass through as-is
        # WhatsApp handles basic markdown natively
        return text

    def chunk_message(self, text: str, max_length: int = 4000) -> list[str]:
        """
        Split long message into chunks for WhatsApp's 4096 char limit.

        Args:
            text: Full message text
            max_length: Maximum length per chunk (default 4000 for safety margin)

        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first to avoid breaking mid-sentence
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            # If adding this paragraph exceeds limit, save current chunk
            if len(current_chunk) + len(para) + 2 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # If single paragraph is too long, split by newlines
                if len(para) > max_length:
                    lines = para.split("\n")
                    for line in lines:
                        if len(current_chunk) + len(line) + 1 > max_length:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"
                else:
                    current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


# Singleton instance
whatsapp_service = WhatsAppService()
