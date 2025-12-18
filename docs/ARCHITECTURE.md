# ARCHITECTURE.md

## 1. High-Level Structure

The project is a **Monorepo** containing multiple applications and packages, managed via npm workspaces.

### Root Directory
- **`apps/`**: Contains the main applications.
- **`packages/`**: Shared libraries (if any).
- **`deploy/`**: Static deployment artifacts (likely for a landing page or documentation).
- **`scripts/`**: Global maintenance and analysis scripts.

### Key Applications (`apps/`)

| App Name | Path | Type | Description |
| :--- | :--- | :--- | :--- |
| **mouth** | `apps/mouth` | Frontend | Next.js 14 application with React Server Components. |
| **backend-rag** | `apps/backend-rag` | Backend | AI/RAG service, Python + FastAPI + Qdrant. |

---

## 2. Data Flow & Dependencies

### Data Flow Diagram (Conceptual)

```mermaid
graph TD
    User[User Browser] -->|HTTPS| WebApp[WebApp (Next.js)]
    WebApp -->|/api/*| BackendRAG[Backend RAG (Python)]

    BackendRAG -->|Vector Search| Qdrant[(Qdrant Cloud)]
    BackendRAG -->|LLM API| AI_Providers[OpenAI / Anthropic / Google]

    %% Jaksel AI System
    BackendRAG -->|Jaksel Users Only| JakselSystem[Jaksel AI System]
    JakselSystem -->|Primary| HF_Inference[Hugging Face Inference API]
    JakselSystem -->|Fallback 1| HF_Spaces[Hugging Face Spaces]
    JakselSystem -->|Fallback 2| OllamaTunnel[Ollama via Tunnel]
    JakselSystem -->|Fallback 3| OllamaLocal[Local Ollama]
    JakselSystem -->|Italian Queries| TranslationLayer[Translation Layer ID→IT]
```

### Critical Dependencies
- **Frontend -> Backend RAG**: The Next.js application calls the `nuzantara-rag.fly.dev` API.
- **Backend RAG -> AI Services**: Heavily relies on external AI APIs and Qdrant for vector storage.
- **Jaksel AI System**: Multi-tier fallback system ensuring 99%+ uptime for personality responses.

---

## 5. Jaksel AI System Architecture

### Overview
**Status**: ✅ ACTIVE (Production - Official Voice)

Jaksel is the **official personality layer** for ALL Zantara responses. It provides casual, friendly responses using Jakarta Selatan (Jaksel) slang, adapted to the user's language (190+ languages supported).

### Architecture Flow

```
User Query
    ↓
┌─────────────────────────────────────┐
│   Jaksel reads query (context only) │  ← Extracts: language, tone, style
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│   Gemini 2.5 Flash elaborates       │  ← RAG + reasoning (simple or complex)
│   response                           │
└─────────────────────────────────────┘
    ↓
    Professional answer from Gemini
    ↓
┌─────────────────────────────────────┐
│   Jaksel receives Gemini response    │
│   Applies: tone + personality        │  ← Gemma 9B via Oracle Cloud
│   Adapts to user's language          │
└─────────────────────────────────────┘
    ↓
    Final response with Jaksel style
```

### Core Components

#### 5.1 SimpleJakselCallerHF
**Location**: `apps/backend-rag/backend/app/routers/simple_jaksel_caller.py`

**Features**:
- **Context Analysis**: `analyze_query_context()` - Reads user query to extract language, formality, tone (NO response generation)
- **Style Application**: `apply_jaksel_style()` - Receives Gemini response and applies Jaksel personality + adapts language
- **Multilingual Support**: Detects and adapts to 190+ languages while maintaining Jaksel personality
- **Style Transfer**: Converts professional AI responses into Jaksel slang (e.g., "basically", "literally", "which is")
- **No-Info Handling**: Translates standard "I don't know" responses into character-appropriate apologies
- **Universal Activation**: Applied to ALL users (no whitelist)

#### 5.2 Integration Points
- **Called From**: `IntelligentRouter` (`stream_chat` and `route_chat`) - **ALWAYS** applied
- **Mechanism**: Two-step process:
  1. Context extraction from user query
  2. Post-processing of Gemini response with Jaksel personality
- **Response Format**:
  ```json
  {
    "success": true,
    "response": "Ciao! Praticamente, il contratto è basically un documento legale...",
    "language": "it",
    "model_used": "gemma-9b-jaksel",
    "connected_via": "https://jaksel.balizero.com"
  }
  ```

### Deployment Details
- **Current Status**: **Active via Production Endpoint**.
- **Primary Endpoint**: `https://jaksel.balizero.com` (Oracle Cloud VM + Ollama).
- **Model**: `zantara:latest` (Gemma 9B Fine-tuned - Sahabat AI → Jaksel custom).
- **Fallback**: Gemini 2.5 Flash with style-transfer prompt.
- **Health Monitoring**: Logs track success/failure rates and fallback activation.
- **Configuration**: Centralized in `apps/backend-rag/backend/app/core/config.py`:
  - `jaksel_oracle_url`: Production endpoint
  - `jaksel_tunnel_url`: Backup tunnel
  - `jaksel_enabled`: Feature flag

---

## 4. Technology Stack

### Frontend (`apps/mouth`)
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5
- **UI**: React 18, Tailwind CSS, shadcn/ui (60+ components), Radix UI
- **State Management**: Zustand (with localStorage persistence)
- **API Communication**: Fetch API, Axios, OpenAPI client
- **Real-time**: WebSockets, Server-Sent Events (SSE)
- **Forms**: React Hook Form
- **Charts**: Recharts
- **Icons**: Lucide React
- **Testing**: Jest, Playwright, Testing Library
- **Package Manager**: npm

### Backend RAG (`apps/backend-rag`)
- **Runtime**: Python 3.11 (Slim Docker image)
- **Framework**: FastAPI + Uvicorn (async-first)
- **Database**: PostgreSQL (asyncpg with connection pooling, min=5, max=20)
- **Vector DB**: Qdrant Cloud (~25k documents, 1536-dim embeddings)
- **Cache**: Redis (optional, for WebSocket and rate limiting)
- **AI/ML**: Qdrant Client, Sentence Transformers, Cross-Encoder Reranker
- **AI Providers**: Google Gemini 2.5 Flash (primary), OpenAI, Anthropic
- **Package Manager**: pip (`requirements.txt`, `pyproject.toml`)
- **Architecture Stats**: 205 Python files, 25 routers, 68 services, 16 migrations
- **Special Features**:
  - **Jaksel AI System**: Custom Gemma 9B model fine-tuned with Jakarta Selatan personality
  - **Agentic RAG**: Multi-step retrieval with ReAct loop and HyDE
  - **CRM System**: Full client/practice/interaction management with Auto-CRM
  - **Plugin System**: Auto-discovery and sandboxed execution
  - **Autonomous Agents**: Client Value Predictor, Conversation Trainer, Knowledge Graph Builder

---

## 3. Qdrant Vector Database Structure

### Overview
The platform uses **Qdrant Cloud** as the vector database for RAG (Retrieval-Augmented Generation). All collections use **OpenAI text-embedding-3-small** embeddings (1536 dimensions) with **Cosine similarity**.

### Document Structure

Each document in Qdrant follows this structure:

```json
{
  "id": "uuid-or-number",
  "vector": [1536 float values],
  "payload": {
    "text": "chunk content...",
    "metadata": {}
  }
}
```

### Collections Overview

| Collection | Documents | Purpose | Metadata Structure |
|------------|-----------|---------|-------------------|
| `bali_zero_pricing` | 29 | Service pricing information | Empty `{}` - data in text |
| `bali_zero_team` | 43 | Team member profiles | **Rich structured** (26 fields) |
| `visa_oracle` | 1,612 | Visa and immigration regulations | Empty `{}` - JSON in text |
| `kbli_unified` | 8,886 | Business classification codes (KBLI) | Empty `{}` - Markdown in text |
| `tax_genius` | 895 | Indonesian tax regulations | Empty `{}` - Structured text |
| `legal_unified` | 5,041 | Indonesian laws and regulations | Empty `{}` - Legal text chunks |
| `knowledge_base` | 8,923 | General knowledge base | Empty `{}` - Mixed content |
| `property_unified` | 29 | Property and real estate info | Empty `{}` - Property descriptions |

**Total Documents**: ~25,000+ (actively growing)

### Metadata Structure: `bali_zero_team`

The `bali_zero_team` collection is unique with rich structured metadata:

```json
{
  "id": "dewaayu",
  "name": "Dewa Ayu",
  "email": "dewa.ayu.tax@balizero.com",
  "role": "Tax Lead",
  "department": "tax",
  "team": "tax",
  "age": 24,
  "religion": "Hindu",
  "languages": ["id", "ban"],
  "preferred_language": "id",
  "expertise_level": "advanced",
  "pin": "259176",
  "traits": ["sweet", "social"],
  "notes": "Balinese tax lead who loves TikTok...",
  "location": "Bali",
  "emotional_preferences": {
    "tone": "friendly_helpful",
    "formality": "medium",
    "humor": "light"
  }
}
```

### Other Collections: Data in Text

Most collections store structured data **within the text content** rather than metadata:

- **`visa_oracle`**: Contains JSON structures in text (visa types, requirements, fees)
- **`kbli_unified`**: Markdown-formatted business codes with descriptions
- **`tax_genius`**: Structured tax tables and regulations in text
- **`legal_unified`**: Legal text chunks (shortest average: 237 chars)

### Chunk Statistics

- **Average chunk length**: 237-917 characters (varies by collection)
- **Chunking strategy**: Semantic chunking with overlap (100 chars default)
- **Embedding model**: OpenAI `text-embedding-3-small` (1536-dim)

### Analysis Tools

A dedicated analysis script is available:

```bash
python scripts/analyze_qdrant_documents.py
```

This script:
- Analyzes all collections structure
- Extracts metadata patterns
- Generates JSON and Markdown reports
- Outputs to `scripts/qdrant_analysis_reports/`

---

## 6. Observability & Automation

The project employs a "Full-Stack Observability" approach, ensuring health and consistency across Backend, Frontend, and API Contracts.

- **Detailed Documentation:** [FULL_STACK_OBSERVABILITY.md](./FULL_STACK_OBSERVABILITY.md)
- **Key Components:**
    - **Backend Sentinel:** `apps/core/sentinel.py`
    - **Frontend Sentinel:** `apps/core/sentinel_frontend.py`
    - **Contract Sentinel:** `apps/core/sentinel_contract.py`
    - **The Scribe:** Automated documentation generation.

---

## 7. Backend Services Architecture

### Core Services (68 total)
The backend is organized into specialized service layers:

| Category | Services | Purpose |
|----------|----------|---------|
| **RAG** | SearchService, CollectionManager, RerankerService, GoldenRouterService, QueryRouter | Vector search and retrieval |
| **Context** | ContextBuilder, AgenticRagOrchestrator, MultiTopicRetriever, ParentChildRetriever, ContextWindowManager | Context building and enrichment |
| **Memory** | MemoryServicePostgres, MemoryFactExtractor, CollectiveMemoryWorkflow, SessionService | User and team memory |
| **CRM** | AutoCRMService, ClientJourneyOrchestrator, ProactiveComplianceMonitor, AICRMExtractor | Customer relationship management |

### Memory & Knowledge Architecture: Three Truths

Zantara uses a **three-layer memory architecture** to ensure coherence and optimal retrieval:

#### Knowledge Truth (RAG KB)
- **Purpose**: Source of truth for business/legal answers
- **Storage**: Qdrant collections (`legal_unified`, `visa_oracle`, `tax_genius`, `kbli_unified`, `bali_zero_pricing`)
- **Flow**: Retrieval *with filters* (tier/status) → Rerank → Verifier → Citations
- **Governance**: Tier-based access control, exclude repealed laws, collection routing
- **Services**: `SearchService`, `ReRanker`, `VerificationService`, `CitationService`

#### People Truth (Memoria Viva)
- **Purpose**: Source of truth for people knowledge (team members, users, you)
- **Storage**: PostgreSQL (`memory_facts`, `user_stats`, `conversations`)
- **Flow**: Facts extraction → Deduplication → Persistence → Context retrieval
- **Governance**: Fact types, provenance, confidence scores, dedup, limits (max 10 facts/user)
- **Services**: `MemoryOrchestrator` (facade), `MemoryServicePostgres`, `MemoryFactExtractor`
- **Policy**: Single source of truth via `MemoryOrchestrator`; no duplicate queries

#### Recall Assist (Vector Memory)
- **Purpose**: Semantic recall for personal/team context (optional enhancement)
- **Storage**: Qdrant `zantara_memories` collection
- **Flow**: Activated **only** for `identity`/`team_query` intents → Semantic search → Candidate context
- **Governance**: Filtered by `userId`/team; treated as *candidate* context, not primary source
- **Services**: `memory_vector` router, `QdrantClient` (zantara_memories)
- **Policy**: **Not used** for business/legal queries; consolidation to Postgres when confirmed

**Key Principle**: Knowledge Truth answers questions; People Truth remembers people; Recall Assist helps recall personal context when needed.
| **Agents** | AutonomousResearchService, CrossOracleSynthesisService, KnowledgeGraphBuilder, AutoIngestionOrchestrator | Autonomous AI agents |
| **Communication** | NotificationHub, AlertService, HealthMonitor, StreamingService | Alerts and notifications |
| **Analytics** | TeamAnalyticsService, PersonalityService, RerankerAudit, TeamTimesheetService | Business intelligence |
| **Productivity** | GmailService, CalendarService, PDFVisionService, SmartOracle | Google Workspace integration |

### Middleware Stack
1. **CORS** - Cross-origin request handling
2. **HybridAuthMiddleware** - JWT + API key authentication
3. **ErrorMonitoringMiddleware** - Error detection and alerting
4. **RateLimitMiddleware** - IP/user rate limiting (Redis-backed)

---

## 10. Backend Module Structure (Refactored 2025-01)

### Overview
The backend has been refactored into a modular architecture for better maintainability and testability.

### Directory Structure

```
apps/backend-rag/backend/
├── app/
│   ├── auth/                    # Unified authentication module
│   │   ├── __init__.py
│   │   └── validation.py       # Consolidated auth validation logic
│   ├── core/                    # Core configuration and utilities
│   │   ├── config.py           # Environment variable validation
│   │   ├── constants.py
│   │   └── service_health.py
│   ├── routers/                 # API route handlers
│   │   ├── root_endpoints.py    # Root endpoints (/, /api/csrf-token, etc.)
│   │   ├── oracle_universal.py  # Oracle endpoints (refactored)
│   │   └── ...                  # Other routers
│   ├── setup/                   # Application setup modules
│   │   ├── __init__.py
│   │   └── router_registration.py  # Centralized router registration
│   ├── utils/                   # Utility modules
│   │   ├── state_helpers.py     # Type-safe app.state/request.state access
│   │   ├── error_handlers.py
│   │   └── logging_utils.py
│   └── main_cloud.py            # FastAPI application entrypoint (refactored)
├── services/                    # Business logic services
│   ├── oracle_config.py         # Oracle configuration service
│   ├── oracle_google_services.py # Google services for Oracle
│   ├── oracle_database.py       # Database operations for Oracle
│   └── ...                      # Other services
└── middleware/                  # Request/response middleware
    ├── hybrid_auth.py           # Authentication middleware
    ├── error_monitoring.py
    └── rate_limiter.py
```

### Key Refactoring Changes

#### 10.1 Authentication Consolidation
- **Before**: Auth validation logic duplicated across `main_cloud.py`, `hybrid_auth.py`, and `auth.py`
- **After**: Unified in `app/auth/validation.py` with single source of truth
- **Benefits**: Eliminates code duplication, easier to maintain and test

#### 10.2 Oracle Universal Router Refactoring
- **Before**: `oracle_universal.py` was 1308 lines with embedded services
- **After**: Split into:
  - `services/oracle_config.py` - Configuration management
  - `services/oracle_google_services.py` - Google Gemini/Drive integration
  - `services/oracle_database.py` - Database operations
  - `routers/oracle_universal.py` - Endpoint handlers only (~900 lines)
- **Benefits**: Better separation of concerns, easier to test individual components

#### 10.3 Main Application Refactoring
- **Before**: `main_cloud.py` was 1252 lines with mixed concerns
- **After**: Extracted:
  - `app/setup/router_registration.py` - Router inclusion logic
  - `app/routers/root_endpoints.py` - Root-level endpoints
  - `main_cloud.py` - Application setup and streaming endpoints (~1100 lines)
- **Benefits**: Clearer separation, easier to locate and modify code

#### 10.4 Type Safety Improvements
- **New**: `app/utils/state_helpers.py` provides type-safe access to `app.state` and `request.state`
- **Benefits**: Runtime type checking, better IDE support, fewer runtime errors

### API Naming Conventions

#### User Identification
- **Standard**: Use `user_id` for internal user identification (string UUID or ID)
- **Context**: Use `user_email` when email is specifically required (e.g., team member lookup)
- **Pattern**: 
  - Request parameters: `user_id` (preferred) or `user_email` (when needed)
  - Response fields: `user_id` for identification, `email` for display
  - Database queries: Use `user_id` for joins, `email` for lookups

#### Example Usage
```python
# ✅ Good: Use user_id for identification
@router.get("/user/{user_id}")
async def get_user(user_id: str):
    ...

# ✅ Good: Use user_email when email lookup is needed
@router.get("/user/by-email/{user_email}")
async def get_user_by_email(user_email: EmailStr):
    ...

# ✅ Good: Extract user_id from profile
user_id = user_profile.get("id") or user_profile.get("user_id")
user_email = user_profile.get("email")  # Only when needed
```

### Error Handling Standards

#### Exception Hierarchy
- **Critical Services**: `RuntimeError` for initialization failures
- **Database**: `asyncpg.PostgresError`, `ValueError`, `ConnectionError`
- **API**: `HTTPException` for HTTP errors
- **Validation**: `ValueError` for invalid input
- **Catch-all**: `Exception` with detailed logging (`exc_info=True`)

#### Example Pattern
```python
try:
    service = initialize_service()
except (ValueError, ConnectionError, RuntimeError) as e:
    # Handle expected errors
    logger.error(f"Service initialization failed: {e}")
except Exception as e:
    # Catch-all with full traceback
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

### SQL Query Best Practices

#### Column Selection
- **✅ Good**: Explicit column selection
  ```sql
  SELECT id, email, name, role FROM users WHERE id = $1
  ```
- **❌ Bad**: SELECT * (performance and maintainability issues)
  ```sql
  SELECT * FROM users WHERE id = $1
  ```

#### Benefits
- Better performance (only fetch needed columns)
- Clearer intent (explicit dependencies)
- Easier refactoring (schema changes don't break code)

---

## 8. Deployment Architecture

### Production (Fly.io)
- **Backend**: `nuzantara-rag` - 2 shared cores, 4GB RAM, 250 concurrent requests
- **Frontend**: `nuzantara-webapp` - 1 shared core, 1GB RAM, auto-scaling
- **Region**: Singapore (sin)
- **Strategy**: Rolling deployments with auto-rollback

### Testing & Deployment Pipeline
1. **Unit Tests** - Fast isolated tests with mocks
2. **Integration Tests** - Real PostgreSQL and Qdrant
3. **API Tests** - E2E with FastAPI TestClient
4. **Deployment** - Conditional on all tests passing

### Monitoring Stack
- **Prometheus**: Metrics collection (15s scrape interval)
- **Alertmanager**: Alert routing by severity (critical/warning/info)
- **Grafana**: Visualization dashboards
- **Jaeger**: Distributed tracing (OTLP)

---

## 9. Known Issues & Risks

1.  **`fly.toml` Versioning**: The `fly.toml` configuration files should be version controlled. Ensure backup of deployment configuration.
2.  **Complex Monorepo Scripts**: The root `package.json` has many scripts, some of which might be obsolete or overlapping (e.g., `start` vs `start:dev`).
3.  **Documentation Sprawl**: 100+ markdown files in `docs/` - consider consolidation.
