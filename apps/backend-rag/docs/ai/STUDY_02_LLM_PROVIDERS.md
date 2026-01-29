# 🤖 PARTE 2: LLM Providers

> Sistema multi-provider per AI generation

---

## Overview

**Location:** `backend/llm/`

Il sistema LLM gestisce tutti i provider AI con fallback automatico, rate limiting, e cost tracking.

---

## Architettura

```
┌─────────────────────────────────────────┐
│          ZantaraAIClient                │
│  (Main orchestrator - 28KB)             │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     GenAIClient (Gemini)        │    │
│  │     - Service Account auth      │    │
│  │     - API Key fallback          │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     Helper Services             │    │
│  │     - PromptManager             │    │
│  │     - RetryHandler              │    │
│  │     - TokenEstimator            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│           LLM Providers                 │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Gemini  │  │ Vertex  │  │DeepSeek │  │
│  │(primary)│  │  (GCP)  │  │ (cheap) │  │
│  └─────────┘  └─────────┘  └─────────┘  │
│                                         │
│  ┌─────────┐  ┌──────────┐              │
│  │ Ollama  │  │OpenRouter│              │
│  │ (local) │  │ (multi)  │              │
│  └─────────┘  └──────────┘              │
└─────────────────────────────────────────┘
```

---

## Files Structure

```
llm/
├── __init__.py              # Exports
├── zantara_ai_client.py     # Main orchestrator (28KB)
├── genai_client.py          # Google GenAI SDK wrapper (20KB)
├── prompt_manager.py        # System prompts (12KB)
├── retry_handler.py         # Retry logic (3KB)
├── token_estimator.py       # Token counting (4KB)
├── fallback_messages.py     # Fallback responses (2KB)
├── base.py                  # Base classes (2KB)
├── client.py                # Legacy client (5KB)
├── provider_registry.py     # Provider registration (2KB)
├── adapters/
│   └── gemini.py            # Gemini adapter
└── providers/
    ├── gemini.py            # Gemini provider
    ├── vertex.py            # Vertex AI provider
    ├── deepseek.py          # DeepSeek provider
    ├── ollama.py            # Ollama local provider
    └── openrouter.py        # OpenRouter multi-provider
```

---

## ZantaraAIClient

**File:** `llm/zantara_ai_client.py` (28KB)

```python
class ZantaraAIClientConstants:
    """Configuration constants."""
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2.0
    RETRY_BACKOFF_FACTOR = 2
    DEFAULT_MAX_TOKENS = 8192
    DEFAULT_TEMPERATURE = 0.4  # Factual, consistent

class ZantaraAIClient:
    """
    Primary AI engine for Nuzantara.

    Features:
    - Multi-provider support
    - Automatic fallback
    - Streaming support
    - Tool/function calling
    - Cost tracking
    - Mock mode for testing
    """

    def __init__(self, api_key: str = None, model: str = None):
        # Auth: Service Account preferred, API Key fallback
        has_service_account = bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or
            os.environ.get("GOOGLE_CREDENTIALS_JSON")
        )

        # Initialize GenAI client
        self._genai_client = GenAIClient(api_key=api_key)

        # Default model
        self.model = model or "gemini-2.0-flash-001"

        # Pricing (per 1M tokens)
        self.pricing = {
            "input": 0.15,   # $0.15/1M input
            "output": 0.60   # $0.60/1M output
        }

        # Helper services
        self.prompt_manager = PromptManager()
        self.retry_handler = RetryHandler(...)
        self.token_estimator = TokenEstimator(model=self.model)
```

### Main Methods

```python
async def chat(
    self,
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 8192,
    tools: list[dict] = None,
    system_prompt: str = None
) -> dict:
    """
    Async chat completion.

    Args:
        messages: [{"role": "user/assistant", "content": "..."}]
        temperature: 0.0-2.0
        max_tokens: Max output tokens
        tools: Function definitions for tool calling
        system_prompt: Override system prompt

    Returns:
        {
            "content": "...",
            "model": "gemini-2.0-flash",
            "usage": {"input_tokens": X, "output_tokens": Y},
            "tool_calls": [...] or None
        }
    """
    pass

async def stream(
    self,
    messages: list[dict],
    temperature: float = 0.4,
    max_tokens: int = 8192
) -> AsyncGenerator[str, None]:
    """
    Streaming chat completion.

    Yields chunks of text as they're generated.
    """
    async for chunk in self._genai_client.stream(...):
        yield chunk.text
```

---

## GenAIClient

**File:** `llm/genai_client.py` (20KB)

```python
class GenAIClient:
    """
    Direct Google GenAI SDK wrapper.

    Uses new google-genai SDK (not deprecated google-generativeai).

    Features:
    - Service Account auth (ADC)
    - API Key auth (fallback)
    - Grounding with Google Search
    - Multimodal support
    - Code execution
    - Function calling
    """

    def __init__(self, api_key: str = None):
        from google import genai

        # Try Service Account first
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            self.client = genai.Client()
            self._auth_method = "service_account"
        elif api_key:
            self.client = genai.Client(api_key=api_key)
            self._auth_method = "api_key"
        else:
            raise ValueError("No credentials")

    async def generate(
        self,
        prompt: str,
        model: str = "gemini-2.0-flash-001",
        config: dict = None
    ) -> GenerateResponse:
        """Generate content."""
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        return response

    async def stream(self, prompt: str, model: str, config: dict):
        """Stream content."""
        async for chunk in self.client.aio.models.generate_content_stream(
            model=model,
            contents=prompt,
            config=config
        ):
            yield chunk
```

### Grounding with Search

```python
async def generate_with_grounding(self, prompt: str) -> dict:
    """
    Generate with Google Search grounding.

    Useful for:
    - Current events
    - Fact checking
    - Up-to-date information
    """
    from google.genai import types

    response = await self.client.aio.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )
    return {
        "content": response.text,
        "grounding_metadata": response.candidates[0].grounding_metadata
    }
```

---

## Providers

### 1. Gemini (Primary)

**File:** `llm/providers/gemini.py`

```python
class GeminiProvider:
    """
    Google Gemini via AI Studio.

    Models:
    - gemini-2.0-flash-001 (default, fast)
    - gemini-1.5-pro (complex tasks)
    - gemini-1.5-flash (cheaper)

    Pricing (per 1M tokens):
    - Input: $0.15
    - Output: $0.60
    """
```

### 2. Vertex AI

**File:** `llm/providers/vertex.py`

```python
class VertexAIProvider:
    """
    Google Vertex AI (enterprise).

    Requires:
    - GCP project
    - Service Account

    Benefits:
    - SLA guarantees
    - Enterprise features
    - VPC connectivity
    """
```

### 3. DeepSeek

**File:** `llm/providers/deepseek.py`

```python
class DeepSeekProvider:
    """
    DeepSeek for cheap, fast responses.

    Models:
    - deepseek-chat (main)
    - deepseek-coder (code)

    Pricing: ~10x cheaper than GPT-4
    Good for: Simple queries, bulk processing
    """
```

### 4. Ollama (Local)

**File:** `llm/providers/ollama.py`

```python
class OllamaProvider:
    """
    Local LLM via Ollama.

    Models:
    - qwen2.5:32b
    - llama3.2
    - codellama
    - mistral

    Benefits:
    - Free (no API costs)
    - Privacy (local)
    - Offline capability

    Drawbacks:
    - Requires GPU
    - Lower quality than cloud
    """
```

### 5. OpenRouter

**File:** `llm/providers/openrouter.py`

```python
class OpenRouterProvider:
    """
    Multi-provider gateway.

    Access to:
    - Claude (Anthropic)
    - GPT-4 (OpenAI)
    - Llama (Meta)
    - Mistral
    - etc.

    Unified API, pay-per-use.
    """
```

---

## Helper Services

### PromptManager

**File:** `llm/prompt_manager.py`

```python
class PromptManager:
    """
    Manages system prompts and templates.

    Templates:
    - ZANTARA identity
    - Language-specific
    - Task-specific
    - Safety guidelines
    """

    def __init__(self):
        self._base_system_prompt = """
        You are ZANTARA, an AI assistant specialized in
        Indonesian immigration, business, and legal matters.

        Key traits:
        - Professional but friendly
        - Accurate and fact-based
        - Cite sources when available
        - Admit uncertainty when unsure
        """

    def get_system_prompt(self, context: dict) -> str:
        """Build context-aware system prompt."""
        pass
```

### RetryHandler

**File:** `llm/retry_handler.py`

```python
class RetryHandler:
    """
    Handles retries with exponential backoff.

    Retryable errors:
    - 429 (rate limit)
    - 500, 502, 503, 504 (server errors)
    - Timeout

    Non-retryable:
    - 400 (bad request)
    - 401, 403 (auth)
    - 404 (not found)
    """

    async def execute_with_retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except RetryableError as e:
                delay = self.base_delay * (self.backoff_factor ** attempt)
                await asyncio.sleep(delay)
        raise MaxRetriesExceeded()
```

### TokenEstimator

**File:** `llm/token_estimator.py`

```python
class TokenEstimator:
    """
    Estimates token count for cost tracking.

    Methods:
    - count_tokens(text) -> int
    - estimate_cost(input_tokens, output_tokens) -> float
    """

    def count_tokens(self, text: str) -> int:
        # Approximate: 1 token ≈ 4 chars for English
        # Adjust for other languages
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1_000_000) * self.pricing["input"]
        output_cost = (output_tokens / 1_000_000) * self.pricing["output"]
        return input_cost + output_cost
```

---

## LLM Clients in Services

**Location:** `backend/services/llm_clients/`

```
services/llm_clients/
├── __init__.py
├── deepseek_client.py    # DeepSeek wrapper
├── gemini_service.py     # Gemini service layer
├── openrouter_client.py  # OpenRouter wrapper
├── pricing.py            # Model pricing info
└── vertex_service.py     # Vertex AI service
```

---

## Model Selection Strategy

```python
def select_model(query: str, context: dict) -> str:
    """
    Select best model for query.

    Decision factors:
    - Query complexity
    - Required accuracy
    - Cost constraints
    - Response time needs
    """

    # Complex queries → Gemini 1.5 Pro
    if context.get("complex") or len(query) > 1000:
        return "gemini-1.5-pro"

    # Code-related → Gemini 2.0 Flash or DeepSeek Coder
    if context.get("code"):
        return "gemini-2.0-flash-001"

    # Bulk/cheap → DeepSeek
    if context.get("batch") or context.get("low_priority"):
        return "deepseek-chat"

    # Default → Gemini 2.0 Flash
    return "gemini-2.0-flash-001"
```

---

## Environment Variables

```bash
# Google AI (primary)
GOOGLE_API_KEY=your_api_key
GOOGLE_CREDENTIALS_JSON={"..."}  # Service Account
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json

# DeepSeek
DEEPSEEK_API_KEY=your_key

# OpenRouter
OPENROUTER_API_KEY=your_key

# Ollama (local)
OLLAMA_HOST=http://localhost:11434
```

---

## Usage Examples

### Basic Chat

```python
from backend.llm import ZantaraAIClient

client = ZantaraAIClient()

response = await client.chat([
    {"role": "user", "content": "What is KITAS?"}
])
print(response["content"])
```

### Streaming

```python
async for chunk in client.stream([
    {"role": "user", "content": "Explain PT PMA setup"}
]):
    print(chunk, end="", flush=True)
```

### With Tools

```python
tools = [{
    "name": "get_visa_price",
    "description": "Get visa pricing",
    "parameters": {
        "type": "object",
        "properties": {
            "visa_type": {"type": "string"}
        }
    }
}]

response = await client.chat(
    messages=[{"role": "user", "content": "How much is KITAS?"}],
    tools=tools
)

if response.get("tool_calls"):
    # Execute tool and continue conversation
    pass
```

---

_"Multi-brain, one voice" 🧠_
