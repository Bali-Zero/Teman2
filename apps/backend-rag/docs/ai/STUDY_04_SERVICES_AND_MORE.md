# 📦 PARTE 4-8: Services, DB, Middleware, Agents, Plugins

> Overview delle parti rimanenti del backend

---

## 4️⃣ SERVICES - Business Logic Domains

**Location:** `backend/services/`

### 26 Domini Organizzati per Area

#### 🔍 **Search & RAG**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `search/` | 5 | SearchService, SemanticCache, Citations |
| `rag/` | 4 | Vision RAG, KG-enhanced retrieval |
| `routing/` | 13 | GoldenRouter, ConflictResolver, Fallbacks |

#### 💼 **CRM & Business**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `crm/` | 11 | Client management, AI extraction |
| `portal/` | 3 | Client portal services |
| `invoicing/` | 3 | Invoice generation |
| `pricing/` | 4 | Dynamic pricing |
| `journey/` | 5 | Client journey tracking |

#### 🧠 **AI & Memory**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `memory/` | 11 | Episodic + Collective memory |
| `oracle/` | 12 | Main RAG orchestrator |
| `llm_clients/` | 6 | LLM provider wrappers |
| `classification/` | 2 | Intent classification |
| `knowledge_graph/` | 7 | Entity extraction, graph |

#### 📊 **Analytics & Monitoring**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `analytics/` | 14 | Team metrics, burnout detection |
| `monitoring/` | 6 | Health checks, alerts |
| `compliance/` | 5 | Legal compliance tracking |

#### 🔄 **Ingestion & Processing**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `ingestion/` | 12 | Document pipeline |
| `intel/` | 5 | News/intel gathering |
| `article_composer/` | 5 | AI content generation |

#### 🔧 **Utilities**
| Service | Files | Descrizione |
|---------|-------|-------------|
| `misc/` | 25 | Various utilities |
| `communication/` | 5 | Language detection |
| `integrations/` | 12 | Google Drive, GitHub |
| `response/` | 3 | Response formatting |
| `tools/` | 3 | Tool definitions |

### Key Service Patterns

```python
# Singleton with lazy initialization
_service_instance = None

def get_service() -> MyService:
    global _service_instance
    if _service_instance is None:
        _service_instance = MyService()
    return _service_instance

# Dependency injection
class MyService:
    def __init__(
        self,
        db: AsyncSession = Depends(get_db),
        cache: Cache = Depends(get_cache)
    ):
        self.db = db
        self.cache = cache
```

---

## 5️⃣ DATABASE - PostgreSQL Layer

**Location:** `backend/db/`

### Files

```
db/
├── __init__.py           # Connection pool
├── migrate.py            # Migration runner
├── migration_base.py     # Base migration class
├── migration_manager.py  # Auto-migration (13KB)
├── utils.py              # DB utilities
├── migrations_v2/        # Current migrations
└── migrations_legacy_archive/  # Old migrations
```

### Connection Pool

```python
# db/__init__.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session
```

### Migration System

```python
# db/migration_manager.py
class MigrationManager:
    """
    Auto-migration system.
    
    Features:
    - Version tracking
    - Rollback support
    - Dry-run mode
    - Parallel execution
    """
    
    async def run_migrations(self, target_version: str = None):
        """Run pending migrations."""
        current = await self._get_current_version()
        pending = self._get_pending_migrations(current, target_version)
        
        for migration in pending:
            await self._run_migration(migration)
    
    async def rollback(self, steps: int = 1):
        """Rollback N migrations."""
        pass
```

### Main Tables

| Table | Purpose |
|-------|---------|
| `users` | System users |
| `conversations` | Chat sessions |
| `messages` | Individual messages |
| `memory_facts` | Extracted facts |
| `intel_articles` | News articles |
| `crm_clients` | CRM clients |
| `crm_interactions` | Client interactions |
| `crm_practices` | Visa/business practices |
| `portal_users` | Portal access |
| `analytics_events` | Telemetry |
| `feedback` | User feedback |

---

## 6️⃣ MIDDLEWARE - Request Processing

**Location:** `backend/middleware/`

### Files

| File | LOC | Purpose |
|------|-----|---------|
| `hybrid_auth.py` | 800+ | Multi-strategy auth |
| `rate_limiter.py` | 250 | Redis rate limiting |
| `activity_logging.py` | 200 | Request/response logs |
| `request_tracing.py` | 170 | Correlation IDs |
| `error_monitoring.py` | 200 | Error tracking |

### HybridAuth

```python
# middleware/hybrid_auth.py
class HybridAuthMiddleware:
    """
    Multi-strategy authentication.
    
    Strategies (in order):
    1. API Key (X-API-Key header)
    2. JWT Bearer (Authorization header)
    3. Portal Token (X-Portal-Token)
    4. Service Account (internal)
    """
    
    async def __call__(self, request: Request, call_next):
        # Try strategies in order
        user = None
        
        # 1. API Key
        if api_key := request.headers.get("X-API-Key"):
            user = await self._verify_api_key(api_key)
        
        # 2. JWT
        elif auth := request.headers.get("Authorization"):
            if auth.startswith("Bearer "):
                user = await self._verify_jwt(auth[7:])
        
        # 3. Portal Token
        elif portal_token := request.headers.get("X-Portal-Token"):
            user = await self._verify_portal_token(portal_token)
        
        request.state.user = user
        return await call_next(request)
```

### Rate Limiter

```python
# middleware/rate_limiter.py
class RateLimiter:
    """
    Redis-based rate limiting.
    
    Strategies:
    - Fixed window
    - Sliding window
    - Token bucket
    
    Limits:
    - Per IP
    - Per API key
    - Per endpoint
    """
    
    def __init__(self, redis_client, default_limit: int = 100):
        self.redis = redis_client
        self.default_limit = default_limit  # per minute
    
    async def check_limit(self, key: str, limit: int = None) -> bool:
        """Return True if under limit."""
        limit = limit or self.default_limit
        current = await self.redis.incr(f"ratelimit:{key}")
        
        if current == 1:
            await self.redis.expire(f"ratelimit:{key}", 60)
        
        return current <= limit
```

---

## 7️⃣ AGENTS - Autonomous AI

**Location:** `backend/agents/`

### Structure

```
agents/
├── agents/              # Agent definitions
│   ├── client_value_predictor.py
│   ├── compliance_monitor.py
│   ├── knowledge_graph_builder.py
│   ├── proactive_outreach.py
│   ├── intel_collector.py
│   └── ...
├── services/            # Agent infrastructure
│   ├── agent_executor.py
│   ├── agent_registry.py
│   ├── agent_scheduler.py
│   └── ...
└── config/              # Agent configs
```

### Agent Types

| Agent | Purpose | Schedule |
|-------|---------|----------|
| **ClientValuePredictor** | Predice lifetime value | Daily |
| **ComplianceMonitor** | Monitora scadenze | Hourly |
| **KnowledgeGraphBuilder** | Costruisce grafo | On-demand |
| **ProactiveOutreach** | Suggerisce follow-up | Daily |
| **IntelCollector** | Raccoglie news | Every 4h |

### Agent Base Class

```python
# agents/services/base_agent.py
class BaseAgent:
    """
    Base class for autonomous agents.
    
    Lifecycle:
    1. initialize() - Setup resources
    2. run() - Main execution
    3. cleanup() - Release resources
    """
    
    name: str
    schedule: str  # Cron expression
    
    async def initialize(self):
        """Setup agent resources."""
        pass
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Execute agent logic."""
        raise NotImplementedError
    
    async def cleanup(self):
        """Cleanup after execution."""
        pass
```

### Agent Executor

```python
# agents/services/agent_executor.py
class AgentExecutor:
    """
    Executes agents with:
    - Timeout handling
    - Error isolation
    - Result logging
    - Retry logic
    """
    
    async def execute(
        self,
        agent: BaseAgent,
        context: AgentContext
    ) -> AgentResult:
        try:
            await agent.initialize()
            result = await asyncio.wait_for(
                agent.run(context),
                timeout=agent.timeout
            )
            return result
        except asyncio.TimeoutError:
            return AgentResult(status="timeout")
        except Exception as e:
            return AgentResult(status="error", error=str(e))
        finally:
            await agent.cleanup()
```

---

## 8️⃣ PLUGINS - Extensibility

**Location:** `backend/plugins/` + `backend/core/plugins/`

### Structure

```
plugins/
├── __init__.py          # Plugin loader
├── bali_zero/           # Pricing plugin
│   └── pricing_plugin.py
└── team/                # Team management
    ├── list_members_plugin.py
    └── search_member_plugin.py

core/plugins/
├── registry.py          # Plugin registry
└── executor.py          # Plugin executor
```

### Plugin Registry

```python
# core/plugins/registry.py
class PluginRegistry:
    """
    Dynamic plugin loading.
    
    Features:
    - Auto-discovery
    - Dependency injection
    - Lifecycle management
    """
    
    _plugins: dict[str, Plugin] = {}
    
    def register(self, name: str, plugin: Plugin):
        """Register a plugin."""
        self._plugins[name] = plugin
    
    def get(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        return self._plugins.get(name)
    
    def discover(self, package: str):
        """Auto-discover plugins in package."""
        import importlib
        import pkgutil
        
        pkg = importlib.import_module(package)
        for _, name, _ in pkgutil.iter_modules(pkg.__path__):
            module = importlib.import_module(f"{package}.{name}")
            if hasattr(module, "register_plugin"):
                module.register_plugin(self)
```

### Plugin Example

```python
# plugins/bali_zero/pricing_plugin.py
from backend.core.plugins import Plugin, PluginContext

class PricingPlugin(Plugin):
    """
    Dynamic pricing calculations.
    
    Capabilities:
    - Visa pricing
    - Business setup pricing
    - Tax service pricing
    """
    
    name = "bali_zero_pricing"
    version = "1.0.0"
    
    async def execute(
        self,
        context: PluginContext,
        params: dict
    ) -> dict:
        service_type = params.get("service_type")
        
        if service_type == "visa":
            return await self._calculate_visa_price(params)
        elif service_type == "business":
            return await self._calculate_business_price(params)
        else:
            return {"error": "Unknown service type"}

def register_plugin(registry: PluginRegistry):
    registry.register("pricing", PricingPlugin())
```

---

## 📊 Summary Statistics

| Component | Files | LOC (approx) |
|-----------|-------|--------------|
| **Services** | 120+ | ~25,000 |
| **Core** | 10 | ~3,600 |
| **LLM** | 15 | ~5,000 |
| **Routers** | 63 | ~15,000 |
| **Middleware** | 5 | ~1,600 |
| **DB** | 5 | ~1,000 |
| **Agents** | 20 | ~3,000 |
| **Plugins** | 5 | ~500 |
| **Tests** | 100+ | ~10,000 |
| **TOTAL** | ~350 | ~65,000 |

---

## 🔗 Key Relationships

```
┌─────────────────────────────────────────────────────────┐
│                      ROUTERS                            │
│   (HTTP endpoints - request/response handling)          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    MIDDLEWARE                           │
│   (Auth, Rate Limit, Logging, Tracing)                  │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                     SERVICES                            │
│   (Business logic - 26 domains)                         │
└───────┬─────────────┬─────────────┬─────────────────────┘
        │             │             │
        ▼             ▼             ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│   CORE    │   │    LLM    │   │  PLUGINS  │
│ (Qdrant,  │   │ (Gemini,  │   │(Extensible│
│ Embedding)│   │ DeepSeek) │   │  logic)   │
└─────┬─────┘   └─────┬─────┘   └───────────┘
      │               │
      ▼               │
┌───────────┐         │
│    DB     │◄────────┘
│(PostgreSQL│
│ + Redis)  │
└───────────┘

┌─────────────────────────────────────────────────────────┐
│                     AGENTS                              │
│   (Background autonomous tasks - scheduled)             │
└─────────────────────────────────────────────────────────┘
```

---

*"Modular, scalable, maintainable" 🧱*
