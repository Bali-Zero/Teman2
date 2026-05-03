"""Channel adapters for multi-channel output formatting."""

from nuzantara_graph.channels.base import ChannelAdapter
from nuzantara_graph.channels.web import WebChannelAdapter
from nuzantara_graph.channels.telegram import TelegramChannelAdapter
from nuzantara_graph.channels.whatsapp import WhatsAppChannelAdapter
from nuzantara_schemas.state import ChannelType

__all__ = [
    "ChannelAdapter",
    "WebChannelAdapter",
    "TelegramChannelAdapter",
    "WhatsAppChannelAdapter",
    "get_channel_adapter",
]

_ADAPTERS: dict[ChannelType, type[ChannelAdapter]] = {
    ChannelType.WEB: WebChannelAdapter,
    ChannelType.TELEGRAM: TelegramChannelAdapter,
    ChannelType.WHATSAPP: WhatsAppChannelAdapter,
}


def get_channel_adapter(channel: ChannelType) -> ChannelAdapter:
    """Get the appropriate channel adapter for the given channel type."""
    adapter_cls = _ADAPTERS.get(channel, WebChannelAdapter)
    return adapter_cls()
