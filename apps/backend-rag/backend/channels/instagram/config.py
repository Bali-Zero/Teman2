"""Instagram Channel Configuration."""

from dataclasses import dataclass


@dataclass
class InstagramChannelConfig:
    """Instagram Business Account configuration."""

    access_token: str
    instagram_account_id: str
    max_message_length: int = 1000  # Instagram DM limit
    supports_markdown: bool = False  # Plain text only
    supports_media: bool = True

    def __post_init__(self) -> None:
        if not self.access_token:
            raise ValueError("access_token required")
        if not self.instagram_account_id:
            raise ValueError("instagram_account_id required")
