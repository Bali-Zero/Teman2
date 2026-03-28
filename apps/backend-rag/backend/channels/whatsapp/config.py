"""
WhatsApp Channel Configuration.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

from dataclasses import dataclass


@dataclass
class WhatsAppChannelConfig:
    """
    Configuration for WhatsApp channel adapter (Meta Cloud API).

    Attributes:
        access_token: Meta WhatsApp Cloud API access token
        phone_number_id: WhatsApp Business Account phone number ID
        business_account_id: WhatsApp Business Account ID
        max_message_length: Max length (1600 chars for WhatsApp)
        supports_markdown: Basic formatting (bold, italic)
        supports_media: Image, video, document support
        webhook_verify_token: Token for webhook verification
    """

    access_token: str
    phone_number_id: str
    business_account_id: str | None = None
    max_message_length: int = 1600  # WhatsApp limit
    supports_markdown: bool = True  # Limited (*bold*, _italic_)
    supports_media: bool = True
    webhook_verify_token: str | None = None

    # API settings
    api_version: str = "v18.0"
    api_base_url: str = "https://graph.facebook.com"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.access_token:
            raise ValueError("access_token is required")

        if not self.phone_number_id:
            raise ValueError("phone_number_id is required")

        if self.max_message_length > 4096:
            raise ValueError("WhatsApp max_message_length cannot exceed 4096")
