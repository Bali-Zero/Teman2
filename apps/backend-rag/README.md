# Nuzantara RAG Backend

**Production-Ready AI-Powered RAG System for Business Intelligence**

![Version](https://img.shields.io/badge/version-v100--qdrant-blue)
![Status](https://img.shields.io/badge/status-production-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)

## Overview

Nuzantara RAG Backend is a FastAPI-based Retrieval-Augmented Generation (RAG) system designed for Indonesian business consulting. It provides intelligent document search, multi-oracle synthesis, and AI-powered responses.

**Live URL:** https://nuzantara-rag.fly.dev/

## Architecture

```
backend/
├── app/              # FastAPI application, routes, models
├── core/             # Database, embeddings, parsers
├── llm/              # LLM client wrappers (Gemini, OpenRouter)
├── prompts/          # System prompts and personas
├── services/         # Business logic services
│   ├── analytics/    # Team analytics, productivity scoring
│   ├── crm/          # CRM extraction and automation
│   ├── ingestion/    # Document processing pipeline
│   ├── intel/        # Intelligence gathering
│   ├── llm_clients/  # Gemini, Vertex AI, DeepSeek
│   ├── memory/       # PostgreSQL-backed memory service
│   ├── oracle/       # Multi-domain Oracle system
│   ├── rag/          # Core RAG, verification, vision
│   ├── routing/      # Smart query routing
│   └── search/       # Vector search services
└── utils/            # Utilities and helpers
```

## Key Features

- **Multi-Oracle System**: Domain-specific oracles for visas, KBLI codes, taxation, legal, and property
- **Cross-Oracle Synthesis**: Intelligent query routing and response synthesis
- **Knowledge Graph**: Entity extraction and relationship mapping
- **Memory Service**: PostgreSQL-backed conversation memory
- **Agentic RAG**: Multi-step reasoning with tool usage
- **Verification Service**: Draft-verify pattern for hallucination prevention

## Infrastructure

### Vector Database: Qdrant Cloud

**Production:** Qdrant Cloud (GCP us-east4-0)

- URL: `https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333`
- Collections: 7 (legal, tax, training, kbli_2025_final, immigration, visa, pricing)
- Architecture: Parent Document Retriever pattern
  - Child chunks → Qdrant (semantic search with metadata filters)
  - Parent docs → PostgreSQL (full context retrieval)

**Local Development:** Docker Qdrant (`localhost:6333`)

```bash
# Start local Qdrant
docker run -d -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant:latest

# Verify connection
curl http://localhost:6333/collections
```

### Database: PostgreSQL

**Production:** Fly.io Postgres

- URL: Configured via `DATABASE_URL` env var
- Tables: `kbli_documents` (parent docs), `kg_nodes`, `kg_edges` (knowledge graph)

**Local Development:** Homebrew PostgreSQL

- Database: `nuzantara`
- User: `nuzantara`

### Deployment: Fly.io

**Backend API:** `nuzantara-rag` app (https://nuzantara-rag.fly.dev)

**Environment Variables:**

```bash
# Required
QDRANT_URL=https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=<jwt-token>
DATABASE_URL=<postgres-url>
OPENAI_API_KEY=<key>
GOOGLE_API_KEY=<key>

# Optional
QDRANT_COLLECTION_NAME=kbli_2025_final
```

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn backend.app.main:app --reload

# Run tests
pytest -v

# Run sentinel (lint + test + health)
./sentinel
```

## Testing Status

**Unit Tests Progress:** 3649 passing (+2048 fixed) | 331 failed | 127 errors

Recent fixes (Mar 2026):

- ✅ Fixed 2048+ async/await patterns across test suite
- ✅ Updated collection names: `bali_zero_pricing` → `bali_zero_pricing_hybrid`
- ✅ Fixed AsyncMock patterns for httpx and async methods
- ✅ Fixed test_cache.py, test_core_cache.py, test_core_utilities_comprehensive.py
- ✅ Fixed test_github_publisher.py (26/26 passing individually)
- ✅ Fixed test_search_service_extended.py (21/21 passing individually)

**Known Issues:**

- Some tests pass individually but fail in full suite (test isolation issues)
- 127 ModuleNotFoundError to investigate
- Test infrastructure refactoring needed for full suite stability

## Documentation

| Document                                                                   | Description                                |
| -------------------------------------------------------------------------- | ------------------------------------------ |
| [docs/README.md](docs/README.md)                                           | Backend docs index and quick links         |
| [docs/OPENAPI.md](docs/OPENAPI.md)                                         | OpenAPI / Swagger usage and regeneration   |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                               | Architecture diagrams (Mermaid)            |
| [docs/DOCSTRINGS.md](docs/DOCSTRINGS.md)                                   | Docstring standards for endpoints/services |
| [CLAUDE.md](CLAUDE.md)                                                     | AI assistant context and guidelines        |
| [NUZANTARA_COMPLETE_DOCUMENTATION.md](NUZANTARA_COMPLETE_DOCUMENTATION.md) | Full project documentation                 |
| [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)                             | Testing best practices                     |
| [docs/ai/](docs/ai/)                                                       | AI-specific documentation                  |

## API Endpoints

Core endpoints are documented in Swagger UI and the OpenAPI schema:

- Swagger UI: `/docs`
- OpenAPI JSON: `/api/v1/openapi.json`
- Reference docs: `docs/OPENAPI.md`

Examples:

- `POST /api/v1/chat` - Main chat endpoint
- `POST /api/v1/search` - Document search
- `GET /health` - Health check
- `POST /api/v1/oracle/{collection}/query` - Oracle-specific queries

## Services Documentation

All services follow these documentation standards:

### Module Docstring

```python
"""
Service Name - Brief Description

Detailed description of the service's purpose and responsibilities.
"""
```

### Class Docstring

```python
class ServiceClass:
    """
    Brief description.

    Detailed description with usage examples if applicable.

    Attributes:
        attribute_name: Description of the attribute.
    """
```

### Method Docstring

```python
def method_name(self, param: str, limit: int = 10) -> Result:
    """
    Brief description of what the method does.

    Args:
        param: Description of parameter.
        limit: Maximum results to return.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is invalid.
    """
```

## Development Guidelines

1. **Type Hints**: All function parameters and returns must have type hints
2. **Docstrings**: All public classes and methods must have docstrings
3. **Async-First**: Use `async/await` for I/O operations
4. **Structured Logging**: Use `logger` instead of `print()`
5. **Error Handling**: Always handle exceptions appropriately

## Sentry Error Tracking

Sentry is initialized in `backend/app/setup/sentry_config.py` and wired from
all three entrypoints (`main_cloud`, `main_api`, `main_rag`). Configuration
is entirely env-driven.

### Env vars

| Variable                        | Default (prod)         | Purpose                                                          |
| ------------------------------- | ---------------------- | ---------------------------------------------------------------- |
| `SENTRY_DSN`                    | (unset → Sentry off)   | Set in Fly secrets for `nuzantara-rag`                           |
| `SKIP_SENTRY_INIT`              | unset                  | Kill-switch. Any truthy value → `init_sentry()` is a no-op       |
| `SENTRY_TRACES_SAMPLE_RATE`     | `0.0`                  | APM opt-in. Keep `<= 0.02` in prod (free-tier quota)             |
| `SENTRY_PROFILES_SAMPLE_RATE`   | `0.0`                  | Profiling opt-in                                                 |
| `SENTRY_SEND_DEFAULT_PII`       | unset (false)          | Leave unset; PII scrubbing is handled by `before_send`           |
| `SENTRY_RELEASE`                | `nuzantara-backend@1.0.0` | Set per deploy for release-health tracking                    |
| `ENVIRONMENT`                   | `development`          | `production` unlocks quota-safe defaults                         |

### PII policy (UU PDP)

The `_before_send` hook scrubs every event before it leaves the process:

- **Redacted keys** (case-insensitive, any nesting depth):
  `npwp`, `nib`, `tax_id`, `passport`, `email`, `phone`, `client_id`,
  `name`, `surname`, plus any suffixed variants (`client_email`,
  `primary_surname`, …).
- **Redacted patterns in free text**: email regex
  (`[\w.+-]+@[\w.-]+\.[\w.-]+`) and Bali Zero client_id pattern
  (`CL-\d{3,}`).
- **Query strings**: parsed `k=v&k=v` and redacted per-key; non-PII keys
  survive for debuggability.
- **Applies to**: `request.data`, `request.query_string`, `request.url`,
  `exception.values[*].stacktrace.frames[*].vars`, `breadcrumbs`,
  `user`, `extra`, `contexts`, top-level `message`.

Contract is enforced by `tests/test_sentry_pii_redaction.py` (13 cases).
**Do not bypass this hook.** If you add a new PII field, update both
`_PII_KEY_SUBSTRINGS` in `sentry_config.py` and `PII_SAMPLES` in the test.

### Quota policy

Free tier = 5,000 events/month shared across error + transaction.
`traces_sample_rate = 0.1` would burn that in days on a real-traffic deploy,
after which Sentry silently drops error events too. Defaults therefore:

- Prod: `SENTRY_TRACES_SAMPLE_RATE = 0.0` (errors only).
- Dev: `1.0` (full tracing, local only).
- Opt-in: if APM is needed in prod, set it explicitly and keep it
  `<= 0.02`. `scripts/sentry-quota-check.sh` flags violations.

### Alert dedup with Telegram

Cron failures and deploy crashes already page Telegram
(`~/scripts/fly-health-check.sh`, `.github/workflows/fly-deploy.yml`).
Any Sentry event with `tags.source in {cron, deploy}` is dropped by
`_before_send`, so the same incident doesn't fire twice.

### Kill-switch

If Sentry itself misbehaves (noisy alerts, SDK bug), flip the switch:

```bash
fly secrets set SKIP_SENTRY_INIT=1 -a nuzantara-rag
```

`init_sentry()` returns immediately on startup and no events are emitted.
Unset the secret to re-enable.

## Deployment

Deployed on Fly.io:

```bash
# Deploy
fly deploy

# Check status
fly status

# View logs
fly logs
```

## License

Proprietary - Nuzantara Business Systems

---

_"The lobster way"_ 🦞
