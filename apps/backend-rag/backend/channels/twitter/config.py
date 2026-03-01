"""Twitter/X Channel Configuration."""

from dataclasses import dataclass


@dataclass
class TwitterChannelConfig:
    """Twitter/X API v2 configuration."""

    consumer_key: str
    consumer_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: str = ""
    client_id: str = ""
    client_secret: str = ""
    max_message_length: int = 10000  # Twitter DM limit
    supports_markdown: bool = False  # Plain text only
    supports_media: bool = True

    def __post_init__(self) -> None:
        if not self.consumer_key or not self.consumer_secret:
            raise ValueError("consumer_key and consumer_secret required")
        if not self.access_token or not self.access_token_secret:
            raise ValueError("access_token and access_token_secret required")
