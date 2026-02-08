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

## Documentation

| Document                                                                   | Description                                  |
| -------------------------------------------------------------------------- | -------------------------------------------- |
| [docs/README.md](docs/README.md)                                           | Backend docs index and quick links           |
| [docs/OPENAPI.md](docs/OPENAPI.md)                                         | OpenAPI / Swagger usage and regeneration     |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                               | Architecture diagrams (Mermaid)              |
| [docs/DOCSTRINGS.md](docs/DOCSTRINGS.md)                                   | Docstring standards for endpoints/services   |
| [CLAUDE.md](CLAUDE.md)                                                     | AI assistant context and guidelines          |
| [NUZANTARA_COMPLETE_DOCUMENTATION.md](NUZANTARA_COMPLETE_DOCUMENTATION.md) | Full project documentation                   |
| [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)                             | Testing best practices                       |
| [docs/ai/](docs/ai/)                                                       | AI-specific documentation                    |

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
