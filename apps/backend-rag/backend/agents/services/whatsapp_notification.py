"""
WhatsApp Notification Service

Responsibility: Send WhatsApp messages via Twilio.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class WhatsAppNotificationService:
    """Service for sending WhatsApp messages via Twilio"""

    def __init__(
        self,
        twilio_sid: str | None = None,
        twilio_token: str | None = None,
        whatsapp_number: str | None = None,
    ):
        """
        Initialize WhatsAppNotificationService.

        Args:
            twilio_sid: Twilio Account SID
            twilio_token: Twilio Auth Token
            whatsapp_number: Twilio WhatsApp number
        """
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token
        self.whatsapp_number = whatsapp_number

    async def send_message(
        self, phone: str, message: str, max_retries: int = 3, timeout: float = 30.0
    ) -> str | None:
        """
        Send WhatsApp message via Twilio with retry logic and timeout.

        Args:
            phone: Phone number (with or without +)
            message: Message text to send
            max_retries: Maximum retry attempts
            timeout: Maximum time to wait for send operation

        Returns:
            Message SID if successful, None otherwise
        """
        if not self.twilio_sid or not self.twilio_token:
            logger.warning("Twilio credentials not configured")
            return None

        # Format phone number
        if not phone.startswith("+"):
            phone = "+" + phone

        async def _send_with_retry():
            from twilio.rest import Client

            client = Client(self.twilio_sid, self.twilio_token)

            for attempt in range(max_retries):
                try:
                    # Run in executor to avoid blocking (Twilio SDK is sync)
                    loop = asyncio.get_event_loop()
                    message_obj = await loop.run_in_executor(
                        None,
                        lambda: client.messages.create(
                            from_=f"whatsapp:{self.whatsapp_number}",
                            body=message,
                            to=f"whatsapp:{phone}",
                        ),
                    )
                    return message_obj.sid
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2**attempt  # Exponential backoff
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {phone}, retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise

        try:
            return await asyncio.wait_for(_send_with_retry(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Timeout sending WhatsApp message to {phone}")
            return None
        except Exception as e:
            logger.error(f"Error sending WhatsApp message to {phone}: {e}", exc_info=True)
            return None










