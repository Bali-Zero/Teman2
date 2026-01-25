# 🐍 NUZANTARA - BACKEND ESSENTIAL CODE

**Generated:** 2026-01-25
**Scope:** Core architecture, RAG pipeline, LLM integration

---

## 📁 STRUTTURA ESSENZIALE

```
apps/backend-rag/
├── backend/
│   ├── app/
│   │   ├── main_cloud.py          # 🚀 Entrypoint FastAPI
│   │   ├── routers/
│   │   │   ├── agentic_rag.py     # 🧠 Chat/RAG API
│   │   │   ├── crm_clients.py     # 👥 CRM
│   │   │   ├── whatsapp_chat.py   # 📱 WhatsApp
│   │   │   └── auth.py            # 🔐 Autenticazione
│   │   └── core/
│   │       ├── config.py          # ⚙️ Settings
│   │       └── qdrant_db.py       # 🔮 Vector DB
│   └── services/
│       ├── rag/
│       │   └── agentic/
│       │       ├── orchestrator.py    # 🎯 CORE: Query processing
│       │       ├── llm_gateway.py     # 🤖 LLM routing & fallback
│       │       ├── pipeline.py        # 📊 Processing pipeline
│       │       └── reasoning.py       # 💭 ReAct reasoning
│       └── search/
│           └── search_service.py      # 🔍 Qdrant search
```

---

## 1️⃣ ENTRYPOINT (`main_cloud.py`)

```python
"""FastAPI entrypoint - Minimal, delegates to app_factory"""
from backend.app.setup.app_factory import create_app
from backend.app.setup.sentry_config import init_sentry

# Initialize Sentry first
init_sentry()

# Create FastAPI app
app = create_app()
```

**Run:** `uvicorn app.main_cloud:app --host 0.0.0.0 --port 8080`

---

## 2️⃣ AGENTIC RAG ORCHESTRATOR (`orchestrator.py`)

Il cuore del sistema RAG. Coordina tutto il processing delle query.

```python
class AgenticRAGOrchestrator:
    """
    Orchestrator for Agentic RAG with Tool Use.
    Implements ReAct: Thought → Action → Observation → Repeat
    
    Routing Tiers:
    - Fast (Flash) - Default, cost-effective
    - Pro (Pro) - Complex queries  
    - DeepThink - Reasoning-heavy tasks
    
    Fallback Cascade:
    Gemini Flash → Flash-Lite → OpenRouter
    """
    
    def __init__(
        self,
        tools: list[BaseTool],           # Available tools
        db_pool: Any = None,              # PostgreSQL pool
        semantic_cache: SemanticCache = None,
        retriever: Any = None,            # SearchService
        llm_gateway: LLMGateway = None,   # LLM routing
    ):
        self.tools = {tool.name: tool for tool in tools}
        self.llm_gateway = llm_gateway or LLMGateway()
        self.intent_classifier = IntentClassifier()
        self.emotional_service = EmotionalAttunementService()
        self.prompt_builder = SystemPromptBuilder()
        
    async def run_query(
        self,
        query: str,
        user_id: str,
        session_id: str,
        conversation_history: list = None,
    ) -> CoreResult:
        """
        Main query processing pipeline.
        
        1. Classify intent → determine tier
        2. Check semantic cache
        3. Retrieve context from Qdrant
        4. Build prompt with persona
        5. Execute LLM call
        6. Process tools if needed (ReAct loop)
        7. Cache and return result
        """
        
    async def run_stream(
        self,
        query: str,
        ...
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Streaming version - yields events:
        - 'token': Partial response text
        - 'sources': Retrieved documents
        - 'tool_call': Tool execution
        - 'thinking': Reasoning steps
        - 'done': Final result
        """
```

---

## 3️⃣ LLM GATEWAY (`llm_gateway.py`)

Gestisce tutte le chiamate LLM con fallback automatico.

```python
# Model Tier Constants
TIER_FLASH = 0     # Fast, cost-effective (default) - gemini-2.5-flash
TIER_LITE = 1      # Alias for FLASH
TIER_PRO = 2       # Alias for FLASH (no separate pro tier)
TIER_FALLBACK = 3  # Stable fallback - gemini-2.0-flash

class LLMGateway:
    """
    Unified gateway for LLM interactions with intelligent fallback.
    
    Responsibilities:
    - Initialize Gemini models (via GenAIClient)
    - Handle OpenRouter fallback for high availability
    - Route requests to appropriate model tier
    - Cascade fallback: Flash → Flash-Lite → OpenRouter
    - Native function calling support
    """
    
    def __init__(self, gemini_tools: list = None):
        # Primary: gemini-2.5-flash (GA stable)
        self.model_name_flash = "gemini-2.5-flash"
        # Fallback: gemini-2.0-flash (deprecated Mar 2026)
        self.model_name_fallback = "gemini-2.0-flash"
        # OpenRouter as last resort
        self._openrouter_client: OpenRouterClient | None = None
        
    async def send_message(
        self,
        chat: ChatSession,
        message: str,
        tier: int = TIER_FLASH,
    ) -> tuple[str, str, Any]:
        """
        Send message with automatic fallback.
        
        Returns: (response_text, model_used, response_object)
        
        Fallback cascade:
        1. Try primary model (gemini-2.5-flash)
        2. On quota/error → fallback model (gemini-2.0-flash)
        3. Still failing → OpenRouter (claude-3-haiku)
        """
```

---

## 4️⃣ RAG ROUTER (`agentic_rag.py`)

API endpoints per chat e streaming.

```python
router = APIRouter(prefix="/api/agentic-rag", tags=["RAG"])

@router.post("/query")
async def query(
    request: QueryRequest,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    """Non-streaming query endpoint"""
    result = await orchestrator.run_query(
        query=request.query,
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return QueryResponse(
        answer=result.answer,
        sources=result.sources,
        metadata=result.metadata,
    )

@router.post("/stream")
async def stream(
    request: StreamRequest,
    orchestrator: AgenticRAGOrchestrator = Depends(get_orchestrator),
):
    """
    SSE streaming endpoint.
    
    Event types:
    - token: Partial text
    - sources: Retrieved docs
    - tool_call/tool_result: Tool execution
    - thinking: Reasoning steps
    - done: Complete
    - error: Error occurred
    """
    async def event_generator():
        async for event in orchestrator.run_stream(...):
            yield f"event: {event.type}\ndata: {event.data}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

---

## 5️⃣ SEARCH SERVICE (`search_service.py`)

Ricerca semantica in Qdrant.

```python
class SearchService:
    """
    Semantic search with hybrid retrieval.
    
    Features:
    - Vector similarity search (cosine)
    - BM25 keyword scoring
    - Hybrid fusion (RRF)
    - Reranking with Cohere
    """
    
    async def search(
        self,
        query: str,
        collection: str = "nuzantara_knowledge",
        limit: int = 10,
        filters: dict = None,
    ) -> list[SearchResult]:
        """
        1. Embed query → vector
        2. Search Qdrant (ANN)
        3. Optionally rerank results
        4. Return with scores and metadata
        """
```

---

## 6️⃣ MULTI-AI ADAPTER (`multi_ai_adapter.py`)

Router per task specifici verso AI diversi.

```python
class AITool(Enum):
    QWEN = "qwen"          # Ollama locale - Privacy, test gen
    GEMINI = "gemini"      # Gemini CLI - Code analysis
    CLAUDE = "claude"      # Claude Max - Architecture, complex reasoning
    CURSOR = "cursor"      # IDE integration
    WINDSURF = "windsurf"  # AI-powered editing

class TaskType(Enum):
    TEST_GENERATION = "test_generation"     # → Qwen
    CODE_ANALYSIS = "code_analysis"         # → Gemini
    ARCHITECTURE = "architecture"           # → Claude
    REFACTORING = "refactoring"             # → Gemini
    PRIVACY_SENSITIVE = "privacy_sensitive" # → Qwen (locale)

# Routing logic
ROUTING_TABLE = {
    TaskType.TEST_GENERATION: AITool.QWEN,      # Locale, veloce
    TaskType.CODE_ANALYSIS: AITool.GEMINI,      # Buono per codice
    TaskType.ARCHITECTURE: AITool.CLAUDE,       # Ragionamento complesso
    TaskType.REFACTORING: AITool.GEMINI,        # Modifiche codice
    TaskType.PRIVACY_SENSITIVE: AITool.QWEN,    # Mai lascia la macchina
}
```

---

## 📊 DATABASE CONNECTIONS

```python
# PostgreSQL (structured data)
POSTGRES_URL = "postgresql://user:pass@host:5432/nuzantara"

# Qdrant (vectors)
QDRANT_HOST = "qdrant.cloud.example"
QDRANT_API_KEY = "..."
COLLECTIONS = [
    "nuzantara_knowledge",   # Main KB
    "bali_intel",            # News/Intel
    "legal_documents",       # Laws
    "training_conversations" # Chat history
]

# Redis (cache/sessions)
REDIS_URL = "redis://localhost:6379"
```

---

## 🔄 REQUEST FLOW

```
User Query
    │
    ▼
[agentic_rag.py] Router
    │
    ▼
[orchestrator.py] Classify Intent
    │
    ├── Simple → TIER_FLASH
    ├── Complex → TIER_PRO
    └── Reasoning → DeepThink
    │
    ▼
[search_service.py] Retrieve Context
    │
    ▼
[llm_gateway.py] Call LLM
    │
    ├── Gemini 2.5 Flash (primary)
    ├── Gemini 2.0 Flash (fallback)
    └── OpenRouter (last resort)
    │
    ▼
[Response + Sources]
```

---

## 🛠️ KEY DEPENDENCIES

```toml
# pyproject.toml essentials
fastapi = "^0.115"
uvicorn = "^0.32"
google-genai = "^1.0"        # New Gemini SDK
qdrant-client = "^1.12"
asyncpg = "^0.30"
redis = "^5.0"
anthropic = "^0.40"          # Claude fallback
httpx = "^0.28"
pydantic = "^2.10"
```
