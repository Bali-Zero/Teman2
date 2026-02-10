"""Twitter Channel Configuration."""
from dataclasses import dataclass

@dataclass
class TwitterChannelConfig:
    """Twitter API v2 configuration."""
    bearer_token: str
    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    access_token_secret: str | None = None
    max_message_length: int = 10000  # Twitter DM limit
    supports_markdown: bool = False  # Plain text only
    supports_media: bool = True
    
    def __post_init__(self):
        if not self.bearer_token:
            raise ValueError("bearer_token required")
