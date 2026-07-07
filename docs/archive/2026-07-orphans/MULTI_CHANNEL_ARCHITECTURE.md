# Multi-Channel Architecture - Zantara Platform

**Data:** 2026-01-16
**Status:** Design Proposal
**Owner:** Architecture Team

---

## 🎯 Obiettivo

Supportare Zantara su **multiple piattaforme** con **logica business centralizzata** e **UX ottimizzata per ogni canale**.

**Canali (7 attivi/scaffold):**

- ✅ Web App (esistente)
- ✅ Telegram (esistente)
- ✅ WhatsApp Business API (esistente)
- ✅ Instagram DM (esistente)
- ✅ X (Twitter) DM (esistente)
- 🔄 Google Chat (scaffold)
- 🔄 Slack (scaffold)

---

## 🏗️ Architettura Proposta

### Layer Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHANNEL LAYER (7 channels)                    │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐│
│  │ Web  │ │Telegr│ │Whats │ │Insta │ │  X   │ │Google│ │Slack││
│  │ App  │ │ Bot  │ │ App  │ │  DM  │ │  DM  │ │ Chat │ │     ││
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬──┘│
│     │        │        │        │        │        │        │    │
└─────┼────────┼────────┼────────┼────────┼────────┼────────┼────┘
      │        │        │        │        │        │        │
      └────────┴────────┴────────┴────────┴────────┴────────┘
                          │
              ┌───────────▼──────────────┐
              │   CHANNEL ROUTER         │
              │  (Message Normalization) │
              └───────────┬──────────────┘
                          │
              ┌───────────▼──────────────┐
              │   CONVERSATION ENGINE    │
              │  - Context Management    │
              │  - User State            │
              │  - Session Handling      │
              └───────────┬──────────────┘
                          │
              ┌───────────▼──────────────┐
              │   ORCHESTRATOR (Core)    │
              │  - RAG Pipeline          │
              │  - Tool Execution        │
              │  - Reasoning (ReAct)     │
              └───────────┬──────────────┘
                          │
              ┌───────────▼──────────────┐
              │   RESPONSE FORMATTER     │
              │  (Channel-Specific UX)   │
              └───────────┬──────────────┘
                          │
              ┌───────────▼──────────────┐
              │   CHANNEL ADAPTERS       │
              │  (Platform-Specific API) │
              └──────────────────────────┘
```

---

## 📦 Struttura Directory Proposta

```
apps/backend-rag/backend/
├── channels/                          # NUOVO: Channel Layer
│   ├── __init__.py
│   ├── base.py                        # BaseChannel abstract class
│   ├── router.py                      # ChannelRouter (dispatch logic)
│   │
│   ├── web/                           # Web App Channel
│   │   ├── __init__.py
│   │   ├── adapter.py                 # WebChannelAdapter
│   │   ├── formatter.py               # WebResponseFormatter
│   │   └── config.py                  # Web-specific config
│   │
│   ├── telegram/                      # Telegram Channel
│   │   ├── __init__.py
│   │   ├── adapter.py                 # TelegramChannelAdapter
│   │   ├── formatter.py               # TelegramResponseFormatter
│   │   ├── webhook.py                 # Webhook handler (migrato da routers/)
│   │   └── config.py                  # Telegram-specific (timeout 45s, etc)
│   │
│   ├── whatsapp/                      # WhatsApp Business Channel
│   │   ├── __init__.py
│   │   ├── adapter.py                 # WhatsAppChannelAdapter
│   │   ├── formatter.py               # WhatsAppResponseFormatter
│   │   ├── webhook.py                 # WhatsApp webhook
│   │   └── config.py                  # WhatsApp-specific (template msgs, etc)
│   │
│   ├── instagram/                     # Instagram DM Channel
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── formatter.py
│   │   └── config.py
│   │
│   ├── twitter/                       # X (Twitter) DM Channel
│   │   ├── __init__.py
│   │   ├── adapter.py
│   │   ├── formatter.py
│   │   └── config.py
│   │
│   └── formatters/                    # Shared formatters
│       ├── markdown.py                # Markdown → Platform-specific
│       ├── citations.py               # Citations formatting
│       └── media.py                   # Image/Video formatting
│
├── conversation/                      # NUOVO: Conversation Engine
│   ├── __init__.py
│   ├── engine.py                      # ConversationEngine (unified)
│   ├── context.py                     # Context management
│   ├── state.py                       # User state machine
│   └── session.py                     # Session storage
│
├── services/rag/agentic/              # ESISTENTE: Core Orchestrator
│   ├── orchestrator.py                # NO CAMBIO (channel-agnostic)
│   ├── reasoning.py
│   └── ...
│
└── app/routers/                       # ESISTENTE: API Routers
    ├── agentic_rag.py                 # Web API (chiama ChannelRouter)
    └── ...                            # Altri endpoint REST
```

---

## 🔌 Interface Unificata

### 1. BaseChannel (Abstract Class)

```python
# channels/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any
from dataclasses import dataclass

@dataclass
class ChannelMessage:
    """Normalized message format across all channels"""
    user_id: str
    session_id: str
    text: str
    media: list[str] | None = None  # URLs to images/videos
    metadata: dict[str, Any] | None = None
    channel: str = "unknown"

@dataclass
class ChannelResponse:
    """Normalized response format"""
    text: str
    sources: list[dict] | None = None
    metadata: dict[str, Any] | None = None
    media: list[str] | None = None

class BaseChannel(ABC):
    """Abstract base class for all channels"""

    def __init__(self, config: dict):
        self.config = config
        self.timeout = config.get("timeout", 30.0)
        self.update_interval = config.get("update_interval", 2.0)

    @abstractmethod
    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Normalize incoming message from platform-specific format"""
        pass

    @abstractmethod
    async def send_response(
        self,
        channel_id: str,
        response: ChannelResponse
    ) -> None:
        """Send response in platform-specific format"""
        pass

    @abstractmethod
    async def send_status_update(
        self,
        channel_id: str,
        status: str
    ) -> None:
        """Send typing indicator / status update"""
        pass

    @abstractmethod
    async def stream_response(
        self,
        channel_id: str,
        response_stream: AsyncIterator[ChannelResponse]
    ) -> None:
        """Handle streaming responses with platform-specific optimizations"""
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return channel name (e.g., 'telegram', 'whatsapp')"""
        pass

    @property
    @abstractmethod
    def supports_markdown(self) -> bool:
        """Whether channel supports markdown formatting"""
        pass

    @property
    @abstractmethod
    def supports_media(self) -> bool:
        """Whether channel supports image/video"""
        pass

    @property
    @abstractmethod
    def max_message_length(self) -> int:
        """Max chars per message (Telegram: 4096, Twitter: 10000)"""
        pass
```

---

### 2. Channel-Specific Implementations

#### Telegram Adapter

```python
# channels/telegram/adapter.py
from channels.base import BaseChannel, ChannelMessage, ChannelResponse
from channels.telegram.config import TelegramConfig
from services.integrations.telegram_bot_service import TelegramBotService

class TelegramChannelAdapter(BaseChannel):
    """Telegram-specific implementation"""

    def __init__(self, config: TelegramConfig):
        super().__init__(config)
        self.bot = TelegramBotService()
        self.timeout = 45.0  # Telegram webhook limit
        self.update_interval = 1.0  # Fast updates for Telegram

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Convert Telegram update → ChannelMessage"""
        message = raw_event.get("message", {})
        from_user = message.get("from", {})

        return ChannelMessage(
            user_id=f"telegram_{from_user.get('id')}",
            session_id=f"telegram_session_{message.get('chat', {}).get('id')}",
            text=message.get("text", ""),
            media=self._extract_media(message),
            metadata={
                "chat_id": message.get("chat", {}).get("id"),
                "message_id": message.get("message_id"),
                "from": from_user,
            },
            channel="telegram"
        )

    async def send_response(
        self,
        channel_id: str,
        response: ChannelResponse
    ) -> None:
        """Send formatted response to Telegram"""
        # Format with citations
        formatted = self._format_telegram_message(
            response.text,
            response.sources
        )

        # Truncate if needed
        if len(formatted) > self.max_message_length:
            formatted = formatted[:4000] + "\n\n_...continua..._"

        await self.bot.send_message(
            chat_id=channel_id,
            text=formatted,
        )

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """Send typing indicator"""
        await self.bot.send_chat_action(
            chat_id=channel_id,
            action="typing"
        )

    async def stream_response(
        self,
        channel_id: str,
        response_stream: AsyncIterator[ChannelResponse]
    ) -> None:
        """Telegram-optimized streaming with progressive updates"""
        # Implementation with 1s update interval, placeholder message, etc.
        pass

    @property
    def channel_name(self) -> str:
        return "telegram"

    @property
    def supports_markdown(self) -> bool:
        return True

    @property
    def supports_media(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return 4096

    def _extract_media(self, message: dict) -> list[str] | None:
        """Extract photo/video URLs from Telegram message"""
        # Implementation
        pass

    def _format_telegram_message(
        self,
        text: str,
        sources: list[dict] | None
    ) -> str:
        """Format with Telegram-specific citations"""
        # Implementation
        pass
```

#### WhatsApp Adapter

```python
# channels/whatsapp/adapter.py
from channels.base import BaseChannel, ChannelMessage, ChannelResponse
from channels.whatsapp.config import WhatsAppConfig

class WhatsAppChannelAdapter(BaseChannel):
    """WhatsApp Business API implementation"""

    def __init__(self, config: WhatsAppConfig):
        super().__init__(config)
        self.phone_number_id = config.phone_number_id
        self.access_token = config.access_token
        self.timeout = 60.0  # WhatsApp allows longer
        self.update_interval = 2.0  # WhatsApp rate limits

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Convert WhatsApp webhook → ChannelMessage"""
        entry = raw_event.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        message = messages[0] if messages else {}

        return ChannelMessage(
            user_id=f"whatsapp_{message.get('from')}",
            session_id=f"whatsapp_session_{message.get('from')}",
            text=message.get("text", {}).get("body", ""),
            media=self._extract_media(message),
            metadata={
                "phone_number": message.get("from"),
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp"),
            },
            channel="whatsapp"
        )

    async def send_response(
        self,
        channel_id: str,  # WhatsApp phone number
        response: ChannelResponse
    ) -> None:
        """Send message via WhatsApp Business API"""
        # WhatsApp supports very limited markdown
        formatted = self._format_whatsapp_message(
            response.text,
            response.sources
        )

        # Split if needed (WhatsApp limit: ~4096 chars)
        chunks = self._split_message(formatted, 4000)

        for chunk in chunks:
            await self._send_whatsapp_text(channel_id, chunk)

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """Mark as read + send typing indicator"""
        # WhatsApp doesn't have typing indicator in Business API
        # Just mark last message as read
        pass

    @property
    def channel_name(self) -> str:
        return "whatsapp"

    @property
    def supports_markdown(self) -> bool:
        return False  # WhatsApp Business API has limited formatting

    @property
    def supports_media(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return 4096

    async def _send_whatsapp_text(self, to: str, text: str) -> None:
        """Call WhatsApp Business API"""
        import httpx
        url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers)

    def _format_whatsapp_message(
        self,
        text: str,
        sources: list[dict] | None
    ) -> str:
        """Format with WhatsApp-friendly citations (no markdown)"""
        # Plain text format with numbered sources
        result = text
        if sources:
            result += "\n\n📚 Fonti:\n"
            for i, source in enumerate(sources, 1):
                result += f"{i}. {source.get('title', 'Source')}\n"
        return result

    def _split_message(self, text: str, max_len: int) -> list[str]:
        """Split long message into chunks"""
        # Implementation
        pass
```

#### Web App Adapter

```python
# channels/web/adapter.py
from channels.base import BaseChannel, ChannelMessage, ChannelResponse
from typing import AsyncIterator

class WebChannelAdapter(BaseChannel):
    """Web App SSE streaming implementation"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.timeout = 120.0  # Web can wait longer
        self.update_interval = 0.0  # Stream every token

    async def receive_message(self, raw_event: dict) -> ChannelMessage:
        """Convert web API request → ChannelMessage"""
        return ChannelMessage(
            user_id=raw_event.get("user_id"),
            session_id=raw_event.get("session_id"),
            text=raw_event.get("query"),
            media=raw_event.get("images"),
            metadata={
                "conversation_history": raw_event.get("conversation_history"),
                "correlation_id": raw_event.get("correlation_id"),
            },
            channel="web"
        )

    async def send_response(
        self,
        channel_id: str,  # Not used for web (SSE connection)
        response: ChannelResponse
    ) -> None:
        """Not used - web uses stream_response"""
        pass

    async def send_status_update(self, channel_id: str, status: str) -> None:
        """Send SSE status event"""
        # Yields SSE event
        pass

    async def stream_response(
        self,
        channel_id: str,
        response_stream: AsyncIterator[dict]  # Raw orchestrator events
    ) -> AsyncIterator[str]:
        """Yield SSE-formatted events"""
        async for event in response_stream:
            # Format as SSE: data: {...}\n\n
            yield f"data: {json.dumps(event)}\n\n"

    @property
    def channel_name(self) -> str:
        return "web"

    @property
    def supports_markdown(self) -> bool:
        return True

    @property
    def supports_media(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return 100000  # No practical limit
```

---

### 3. Channel Router (Unified Entry Point)

```python
# channels/router.py
from channels.base import BaseChannel, ChannelMessage, ChannelResponse
from channels.telegram.adapter import TelegramChannelAdapter
from channels.whatsapp.adapter import WhatsAppChannelAdapter
from channels.web.adapter import WebChannelAdapter
from conversation.engine import ConversationEngine
from typing import AsyncIterator

class ChannelRouter:
    """Routes messages to appropriate channel adapter"""

    def __init__(self, conversation_engine: ConversationEngine):
        self.conversation_engine = conversation_engine
        self.adapters: dict[str, BaseChannel] = {}

        # Register channel adapters
        self._register_adapters()

    def _register_adapters(self):
        """Initialize all channel adapters"""
        from backend.app.core.config import settings

        # Telegram
        if settings.telegram_bot_token:
            self.adapters["telegram"] = TelegramChannelAdapter(
                config=settings.telegram_config
            )

        # WhatsApp
        if settings.whatsapp_access_token:
            self.adapters["whatsapp"] = WhatsAppChannelAdapter(
                config=settings.whatsapp_config
            )

        # Web
        self.adapters["web"] = WebChannelAdapter(
            config=settings.web_config
        )

        # ... other channels

    async def route_message(
        self,
        channel: str,
        raw_event: dict
    ) -> None:
        """
        Main routing logic:
        1. Get channel adapter
        2. Normalize message
        3. Process through ConversationEngine
        4. Send response via adapter
        """
        adapter = self.adapters.get(channel)
        if not adapter:
            raise ValueError(f"Channel {channel} not configured")

        # 1. Normalize incoming message
        message = await adapter.receive_message(raw_event)

        # 2. Send immediate status update (typing indicator)
        channel_id = self._extract_channel_id(message.metadata)
        await adapter.send_status_update(channel_id, "processing")

        # 3. Process through conversation engine
        response_stream = self.conversation_engine.process_message(
            message=message,
            channel_config={
                "timeout": adapter.timeout,
                "supports_markdown": adapter.supports_markdown,
                "supports_media": adapter.supports_media,
            }
        )

        # 4. Stream response via adapter
        await adapter.stream_response(channel_id, response_stream)

    def _extract_channel_id(self, metadata: dict) -> str:
        """Extract channel-specific ID (chat_id, phone_number, etc.)"""
        # Telegram
        if "chat_id" in metadata:
            return str(metadata["chat_id"])

        # WhatsApp
        if "phone_number" in metadata:
            return metadata["phone_number"]

        # Web (not used)
        return ""
```

---

### 4. Conversation Engine (Channel-Agnostic)

```python
# conversation/engine.py
from channels.base import ChannelMessage, ChannelResponse
from services.rag.agentic.orchestrator import Orchestrator
from typing import AsyncIterator

class ConversationEngine:
    """
    Channel-agnostic conversation processing
    - Context management
    - Session state
    - Orchestrator integration
    """

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator

    async def process_message(
        self,
        message: ChannelMessage,
        channel_config: dict
    ) -> AsyncIterator[ChannelResponse]:
        """
        Process message through RAG pipeline
        Yields ChannelResponse objects
        """
        # Load conversation context
        context = await self._load_context(message.session_id)

        # Stream through orchestrator
        async for event in self.orchestrator.stream_query(
            query=message.text,
            user_id=message.user_id,
            session_id=message.session_id,
            conversation_history=context.history,
        ):
            # Convert orchestrator events → ChannelResponse
            if event.get("type") == "token":
                yield ChannelResponse(
                    text=event.get("data", ""),
                    sources=None,
                    metadata={"event_type": "token"}
                )

            elif event.get("type") == "sources":
                yield ChannelResponse(
                    text="",
                    sources=event.get("data", []),
                    metadata={"event_type": "sources"}
                )

            # ... handle other event types

        # Save updated context
        await self._save_context(message.session_id, context)

    async def _load_context(self, session_id: str):
        """Load conversation history and user state"""
        # Implementation
        pass

    async def _save_context(self, session_id: str, context):
        """Save conversation history"""
        # Implementation
        pass
```

---

## 🔧 Channel-Specific Configurations

```python
# channels/telegram/config.py
from pydantic import BaseModel

class TelegramConfig(BaseModel):
    timeout: float = 45.0                  # Webhook limit
    update_interval: float = 1.0           # Fast updates
    max_message_length: int = 4096
    supports_markdown: bool = True
    supports_media: bool = True
    bot_token: str
    webhook_secret: str

    # Telegram-specific
    parse_mode: str = "Markdown"           # or "HTML"
    disable_notification: bool = False
    allow_sending_without_reply: bool = True


# channels/whatsapp/config.py
class WhatsAppConfig(BaseModel):
    timeout: float = 60.0
    update_interval: float = 2.0           # Rate limits
    max_message_length: int = 4096
    supports_markdown: bool = False        # Limited formatting
    supports_media: bool = True
    phone_number_id: str
    access_token: str

    # WhatsApp-specific
    verify_token: str                      # Webhook verification
    api_version: str = "v18.0"


# channels/web/config.py
class WebConfig(BaseModel):
    timeout: float = 120.0
    update_interval: float = 0.0           # Stream every token
    max_message_length: int = 100000
    supports_markdown: bool = True
    supports_media: bool = True

    # Web-specific
    cors_origins: list[str]
    sse_heartbeat_interval: float = 30.0
```

---

## 📝 Uso del Sistema

### Esempio: Telegram Webhook

```python
# app/routers/telegram.py (NEW - simplified)
from fastapi import APIRouter, Request
from channels.router import ChannelRouter

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    channel_router: ChannelRouter = Depends(get_channel_router)
):
    """Simplified webhook - delegates to ChannelRouter"""
    raw_event = await request.json()

    # Route to channel adapter
    await channel_router.route_message(
        channel="telegram",
        raw_event=raw_event
    )

    return {"ok": True}
```

### Esempio: WhatsApp Webhook

```python
# app/routers/whatsapp.py (NEW)
from fastapi import APIRouter, Request
from channels.router import ChannelRouter

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    channel_router: ChannelRouter = Depends(get_channel_router)
):
    """WhatsApp Business API webhook"""
    raw_event = await request.json()

    # Route to channel adapter
    await channel_router.route_message(
        channel="whatsapp",
        raw_event=raw_event
    )

    return {"ok": True}

@router.get("/webhook")
async def whatsapp_verify(
    request: Request,
    channel_router: ChannelRouter = Depends(get_channel_router)
):
    """WhatsApp webhook verification"""
    # Verification logic
    pass
```

### Esempio: Web SSE

```python
# app/routers/agentic_rag.py (UPDATED - uses ChannelRouter)
from sse_starlette.sse import EventSourceResponse
from channels.router import ChannelRouter

@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    user: dict = Depends(get_current_user_optional),
    channel_router: ChannelRouter = Depends(get_channel_router)
):
    """Web SSE endpoint - delegates to ChannelRouter"""

    # Prepare raw event
    raw_event = {
        "user_id": user.get("id") if user else "anonymous",
        "session_id": f"web_session_{user.get('id') if user else 'anon'}",
        "query": request.query,
        "images": request.images,
        "conversation_history": request.conversation_history,
    }

    # Get web adapter
    web_adapter = channel_router.adapters["web"]

    # Normalize message
    message = await web_adapter.receive_message(raw_event)

    # Stream response
    response_stream = channel_router.conversation_engine.process_message(
        message=message,
        channel_config={
            "timeout": web_adapter.timeout,
            "supports_markdown": True,
            "supports_media": True,
        }
    )

    # Stream as SSE
    return EventSourceResponse(
        web_adapter.stream_response("", response_stream)
    )
```

---

## 🔄 Migration Plan

### Phase 1: Foundation (Week 1)

- [ ] Create `channels/` directory structure
- [ ] Implement `BaseChannel` abstract class
- [ ] Implement `ChannelRouter`
- [ ] Implement `ConversationEngine`

### Phase 2: Migrate Existing Channels (Week 2)

- [ ] Migrate `TelegramChannelAdapter` from `routers/telegram.py`
- [ ] Migrate `WebChannelAdapter` from `routers/agentic_rag.py`
- [ ] Update routers to use `ChannelRouter`
- [ ] Test existing functionality (Telegram + Web)

### Phase 3: Add New Channels (Week 3-4)

- [ ] Implement `WhatsAppChannelAdapter`
- [ ] WhatsApp Business API integration
- [ ] Test WhatsApp end-to-end
- [ ] Add Instagram, X adapters (if needed)

### Phase 4: Optimization (Week 5+)

- [ ] Channel-specific performance tuning
- [ ] Response caching per channel
- [ ] Analytics per channel
- [ ] A/B testing framework

---

## ✅ Benefits

| Benefit             | Description                                      |
| ------------------- | ------------------------------------------------ |
| **DRY**             | Orchestrator logic written once, used everywhere |
| **Scalability**     | Add new channel = write 1 adapter (200 lines)    |
| **Consistency**     | Same AI behavior across all channels             |
| **Testing**         | Mock channels for unit tests                     |
| **Monitoring**      | Unified metrics across channels                  |
| **UX Optimization** | Channel-specific tuning (timeout, formatting)    |

---

## 🎯 Next Steps

1. **Review & Approve** architecture design
2. **Prototype** `BaseChannel` + `TelegramChannelAdapter`
3. **Test** migration without breaking existing
4. **Rollout** phase by phase

---

_Documento creato 2026-01-16, aggiornato 2026-03-22. Architecture per multi-channel Zantara platform (7 canali)._
