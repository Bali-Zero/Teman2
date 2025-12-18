#!/usr/bin/env python3
"""
Ingest Backend Services Documentation into Qdrant Knowledge Base

This script generates comprehensive documentation about all backend services
and ingests it into Qdrant so Zantara can access and use them.

Usage:
    python scripts/ingest_backend_services_docs.py [--collection COLLECTION_NAME]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from core.embeddings import EmbeddingsGenerator
from core.qdrant_db import QdrantClient
from dotenv import load_dotenv

# Load environment variables
env_path = backend_path.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Try alternative locations
    alt_paths = [
        backend_path / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    for alt_path in alt_paths:
        if alt_path.exists():
            load_dotenv(dotenv_path=alt_path, override=True)
            break

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_backend_services_docs() -> list[dict[str, str]]:
    """
    Generate comprehensive documentation for all backend services.

    Returns:
        List of documents with 'content' and 'metadata' keys
    """
    docs = []

    # ========================================
    # 1. CRM SERVICES DOCUMENTATION
    # ========================================
    crm_docs = [
        {
            "content": """
# CRM Services - Backend API Documentation

## Overview
The CRM (Customer Relationship Management) system provides comprehensive client and practice management capabilities.

## Available Endpoints

### Client Management
- **GET /api/crm/clients/by-email/{email}**: Get client information by email address
  - Returns: Client details including ID, name, status, and associated practices
  - Example: GET /api/crm/clients/by-email/client@example.com

- **GET /api/crm/clients/{client_id}/summary**: Get comprehensive client summary
  - Returns: Client summary with practices, recent interactions, and status
  - Example: GET /api/crm/clients/123/summary

- **GET /api/crm/clients/stats/overview**: Get CRM statistics overview
  - Returns: Overall CRM statistics and metrics

### Practice Management
- **POST /api/crm/practices**: Create a new practice for a client
  - Body: {client_id, practice_type, status, description}
  - Returns: Created practice details

- **GET /api/crm/practices/{practice_id}**: Get practice details
  - Returns: Practice information and status

### Interaction Logging
- **POST /api/crm/interactions**: Log an interaction with a client
  - Body: {client_id, interaction_type, summary, team_member}
  - Returns: Created interaction record
  - Types: 'chat', 'email', 'call', 'meeting', 'document'

### Shared Memory
- **GET /api/crm/shared-memory/{client_id}**: Get shared memory for a client
  - Returns: Shared context and notes about the client

## Python Tools Available
- CRM data is automatically extracted from conversations
- Auto-CRM service processes chat messages to create/update client records
- Client context is automatically attached to chat sessions

## Usage Examples
To get client information:
```python
GET /api/crm/clients/by-email/test@example.com
Authorization: Bearer <JWT_TOKEN>
```

To log an interaction:
```python
POST /api/crm/interactions
{
  "client_id": 123,
  "interaction_type": "chat",
  "summary": "Discussed visa requirements",
  "team_member": "user@balizero.com"
}
```
""",
            "metadata": {
                "service": "crm",
                "category": "backend_services",
                "type": "api_documentation",
                "title": "CRM Services API Documentation",
            },
        },
        {
            "content": """
# CRM Auto-Extraction from Conversations

## How It Works
The Auto-CRM service automatically extracts client information from chat conversations:

1. **Conversation Processing**: When a conversation is saved, Auto-CRM analyzes the messages
2. **Entity Extraction**: Extracts client names, emails, practice types, and requirements
3. **Client Creation**: Automatically creates or updates client records in the CRM
4. **Practice Linking**: Links extracted practices to client records
5. **Interaction Logging**: Logs the conversation as an interaction

## Extracted Information
- Client name and contact information
- Practice types (visa, company formation, tax, etc.)
- Requirements and status
- Important dates and deadlines
- Notes and context

## Accessing CRM Data
Zantara can access CRM data through:
- Python tools: get_crm_context, log_crm_interaction
- API endpoints: /api/crm/clients/*, /api/crm/practices/*, /api/crm/interactions/*
- Auto-extraction: Automatic from conversations

## Tools Available
- `get_crm_context(email)`: Get CRM context for a user by email
- `log_crm_interaction(client_id, summary, type)`: Log an interaction
- `get_client_summary(client_id)`: Get comprehensive client summary
""",
            "metadata": {
                "service": "crm",
                "category": "backend_services",
                "type": "auto_extraction",
                "title": "CRM Auto-Extraction Guide",
            },
        },
    ]
    docs.extend(crm_docs)

    # ========================================
    # 2. CONVERSATIONS SERVICE DOCUMENTATION
    # ========================================
    conversations_docs = [
        {
            "content": """
# Conversations Service - Backend API Documentation

## Overview
The Conversations Service provides persistent storage and retrieval of chat conversations in PostgreSQL database.

## Available Endpoints

### Save Conversation
- **POST /api/bali-zero/conversations/save**: Save a conversation to PostgreSQL
  - Body: {
      user_email: string,
      messages: Array<{role: 'user'|'assistant', content: string, timestamp: string}>,
      session_id: string,
      metadata: object
    }
  - Returns: {conversation_id, messages_saved, crm: {processed, client_id, practice_id}}
  - Auto-CRM: Automatically processes conversation for CRM extraction

### Load Conversation History
- **GET /api/bali-zero/conversations/history**: Get conversation history for a user
  - Query params: userEmail, limit (default: 50), sessionId (optional)
  - Returns: {messages: Array<conversation messages>}

### Clear Conversation History
- **DELETE /api/bali-zero/conversations/clear**: Clear conversation history
  - Query params: userEmail, sessionId (optional)
  - Returns: success status

### Get Conversation Statistics
- **GET /api/bali-zero/conversations/stats**: Get conversation statistics
  - Query params: userEmail
  - Returns: Statistics about user conversations

## Database
- **Database**: PostgreSQL (nuzantara_rag)
- **Table**: conversations
- **Auto-CRM Integration**: Conversations are automatically processed for CRM data extraction

## Usage Examples
To save a conversation:
```python
POST /api/bali-zero/conversations/save
{
  "user_email": "user@example.com",
  "messages": [
    {"role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00Z"},
    {"role": "assistant", "content": "Hi!", "timestamp": "2024-01-01T00:00:01Z"}
  ],
  "session_id": "session_123",
  "metadata": {"source": "webapp"}
}
```

To load history:
```python
GET /api/bali-zero/conversations/history?userEmail=user@example.com&limit=50
```
""",
            "metadata": {
                "service": "conversations",
                "category": "backend_services",
                "type": "api_documentation",
                "title": "Conversations Service API Documentation",
            },
        },
    ]
    docs.extend(conversations_docs)

    # ========================================
    # 3. MEMORY SERVICE DOCUMENTATION
    # ========================================
    memory_docs = [
        {
            "content": """
# Memory Service - Backend API Documentation

## Overview
The Memory Service provides semantic memory storage and retrieval using Qdrant vector database with PostgreSQL metadata.

## Available Endpoints

### Generate Embedding
- **POST /api/memory/embed**: Generate embedding for text
  - Body: {text: string}
  - Returns: {embedding: Array<float>}
  - Uses: OpenAI text-embedding-3-small (1536 dimensions)

### Search Memories (Semantic)
- **POST /api/memory/search**: Search memories using semantic similarity
  - Body: {
      query_embedding: Array<float>,
      limit: number (default: 5),
      metadata_filter: object (optional)
    }
  - Returns: {results: Array<{document, score, metadata}>}

### Store Memory Vector
- **POST /api/memory/store**: Store a new memory vector
  - Body: {
      id: string,
      document: string,
      embedding: Array<float>,
      metadata: object
    }
  - Returns: success status

### Get Memory Statistics
- **GET /api/memory/stats**: Get memory service statistics
  - Returns: Statistics about stored memories

## Database
- **Vector Database**: Qdrant (https://nuzantara-qdrant.fly.dev)
- **Metadata Database**: PostgreSQL
- **Embedding Model**: OpenAI text-embedding-3-small (1536 dims)
- **Collection**: user_memories (in Qdrant)

## Usage Examples
To search memories:
```python
# First generate embedding
POST /api/memory/embed
{"text": "user preferences"}

# Then search with embedding
POST /api/memory/search
{
  "query_embedding": [0.1, 0.2, ...],
  "limit": 5,
  "metadata_filter": {"userId": "user@example.com"}
}
```

To store a memory:
```python
POST /api/memory/store
{
  "id": "mem_123",
  "document": "User prefers Italian language",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "userId": "user@example.com",
    "type": "preference",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

## Python Tools Available
- `retrieve_user_memory(user_id)`: Retrieve user memory profile
- `search_memory(query, user_id, limit)`: Search user memories semantically
""",
            "metadata": {
                "service": "memory",
                "category": "backend_services",
                "type": "api_documentation",
                "title": "Memory Service API Documentation",
            },
        },
        {
            "content": """
# Memory Service - Qdrant Vector Database

## Important: Database is QDRANT, NOT ChromaDB

The Memory Service uses **Qdrant** as the vector database, NOT ChromaDB.

## Technical Details
- **Vector Database**: Qdrant
- **URL**: https://nuzantara-qdrant.fly.dev
- **Collection**: user_memories
- **Embedding Dimensions**: 1536 (OpenAI text-embedding-3-small)
- **Distance Metric**: Cosine similarity
- **Metadata Storage**: PostgreSQL (for additional metadata)

## How It Works
1. User memories are stored as vectors in Qdrant
2. Each memory has an embedding (1536 dimensions)
3. Metadata is stored in PostgreSQL for fast filtering
4. Semantic search uses cosine similarity in Qdrant
5. Results are ranked by relevance score

## Collection Structure
- Collection name: `user_memories`
- Vector size: 1536
- Metadata fields: userId, type, timestamp, entities
- Indexed for fast filtering by userId and type
""",
            "metadata": {
                "service": "memory",
                "category": "backend_services",
                "type": "technical_details",
                "title": "Memory Service - Qdrant Database",
            },
        },
    ]
    docs.extend(memory_docs)

    # ========================================
    # 4. ZANTARA TOOLS (PYTHON) DOCUMENTATION
    # ========================================
    tools_docs = [
        {
            "content": """
# Zantara Tools - Python Native Tools

## Overview
Zantara Tools are Python-native tools that execute directly (no HTTP calls) for faster and more reliable access to backend services.

## Available Tools

### Pricing Tool
- **Tool Name**: `get_pricing`
- **Description**: Get official Bali Zero pricing information (NO AI generation)
- **Parameters**: {service_type: string, complexity: string, urgency: string}
- **Returns**: {base_price, final_price, breakdown}
- **Usage**: Direct Python execution, no HTTP overhead

### Team Tools
- **Tool Name**: `search_team_member`
- **Description**: Search for team members by name or email
- **Parameters**: {query: string}
- **Returns**: Array of matching team members

- **Tool Name**: `get_team_members_list`
- **Description**: Get list of all team members
- **Parameters**: {limit: number (optional)}
- **Returns**: Array of team member profiles

- **Tool Name**: `get_team_logins_today`
- **Description**: Get team login statistics for today
- **Returns**: Login statistics

- **Tool Name**: `get_team_active_sessions`
- **Description**: Get currently active user sessions
- **Returns**: Active session information

### Memory Tools
- **Tool Name**: `retrieve_user_memory`
- **Description**: Retrieve user memory profile
- **Parameters**: {user_id: string}
- **Returns**: User memory with facts, summary, counters

- **Tool Name**: `search_memory`
- **Description**: Search user memories semantically
- **Parameters**: {query: string, user_id: string, limit: number}
- **Returns**: Relevant memories ranked by similarity

## Execution
- **Method**: Direct Python execution (no HTTP proxy)
- **Location**: backend/services/zantara_tools.py
- **Executor**: ToolExecutor service
- **Performance**: Faster than HTTP-based tools

## How Zantara Uses These Tools
Zantara can call these tools during conversations:
1. User asks about pricing → Zantara calls `get_pricing`
2. User asks about team → Zantara calls `search_team_member` or `get_team_members_list`
3. User asks about past conversations → Zantara calls `retrieve_user_memory` or `search_memory`

## Example Tool Call
```python
# Zantara automatically calls tools when needed
tool_result = await tool_executor.execute_tool(
    tool_name="get_pricing",
    tool_input={"service_type": "visa", "complexity": "standard"},
    user_id="user@example.com"
)
```
""",
            "metadata": {
                "service": "tools",
                "category": "backend_services",
                "type": "python_tools",
                "title": "Zantara Python Tools Documentation",
            },
        },
    ]
    docs.extend(tools_docs)

    # ========================================
    # 5. AGENTIC FUNCTIONS DOCUMENTATION
    # ========================================
    agentic_docs = [
        {
            "content": """
# Agentic Functions - Backend API Documentation

## Overview
Agentic Functions provide automated workflows and intelligent automation capabilities.

## Available Endpoints

### Get Agents Status
- **GET /api/agents/status**: Get status of all agentic functions
  - Returns: {
      agents_available: Array<string>,
      active_journeys: Array<{journey_id, type, progress}>,
      pending_alerts: number
    }

### Create Client Journey
- **POST /api/agents/journey/create**: Create a new automated client journey
  - Body: {client_id: string, journey_type: string}
  - Returns: {journey_id, steps: Array<{id, name}>}
  - Journey Types: 'onboarding', 'visa_application', 'company_formation', etc.

### Get Compliance Alerts
- **GET /api/agents/compliance-alerts**: Get compliance alerts for clients
  - Query params: clientId (optional), severity (optional)
  - Returns: {alerts: Array<{type, severity, due_date, description}>}

### Calculate Dynamic Pricing
- **POST /api/agents/pricing/calculate**: Calculate dynamic pricing for services
  - Body: {serviceType: string, complexity: string, urgency: string}
  - Returns: {base_price, final_price, breakdown}

### Cross-Oracle Synthesis
- **POST /api/agents/synthesis/cross-oracle**: Perform cross-oracle synthesis search
  - Body: {query: string, domains: Array<string>}
  - Returns: {synthesized_answer, sources: Array<{domain, content, relevance}>}
  - Domains: ['tax', 'legal', 'visa', 'property']

## Usage Examples
To get agents status:
```python
GET /api/agents/status
Authorization: Bearer <JWT_TOKEN>
```

To create a journey:
```python
POST /api/agents/journey/create
{
  "client_id": "123",
  "journey_type": "visa_application"
}
```

To calculate pricing:
```python
POST /api/agents/pricing/calculate
{
  "serviceType": "visa",
  "complexity": "standard",
  "urgency": "normal"
}
```
""",
            "metadata": {
                "service": "agentic",
                "category": "backend_services",
                "type": "api_documentation",
                "title": "Agentic Functions API Documentation",
            },
        },
    ]
    docs.extend(agentic_docs)

    # ========================================
    # 6. GENERAL API KNOWLEDGE
    # ========================================
    general_docs = [
        {
            "content": """
# Backend API - Complete Service Overview

## Available Services

### Core Services
1. **CRM Services** (/api/crm/*)
   - Client management
   - Practice management
   - Interaction logging
   - Shared memory

2. **Conversations Service** (/api/bali-zero/conversations/*)
   - Save conversations to PostgreSQL
   - Load conversation history
   - Clear history
   - Get statistics

3. **Memory Service** (/api/memory/*)
   - Semantic memory storage (Qdrant)
   - Memory search
   - Embedding generation
   - User memory profiles

4. **Agentic Functions** (/api/agents/*)
   - Client journeys
   - Compliance monitoring
   - Dynamic pricing
   - Cross-oracle synthesis

### Authentication
- **JWT Token**: Bearer token in Authorization header
- **API Key**: X-API-Key header
- **Endpoint**: /api/auth/login (POST) or /api/auth/team-login (POST)

### Database Systems
- **PostgreSQL**: Main database (conversations, CRM, metadata)
- **Qdrant**: Vector database (memories, knowledge base)
- **Redis**: Caching (optional)

### Python Tools Available
- get_pricing: Official pricing
- search_team_member: Team search
- get_team_members_list: Team roster
- retrieve_user_memory: User memory
- search_memory: Memory search

### TypeScript Handlers Available
- Gmail operations
- Calendar operations
- Drive operations
- Docs/Sheets operations
- And more...

## How to Access Services
1. **Via API Endpoints**: Direct HTTP calls to /api/* endpoints
2. **Via Python Tools**: Use ToolExecutor to call Python tools
3. **Via TypeScript Handlers**: Use HandlerProxy to call TypeScript handlers

## Base URL
- Production: https://nuzantara-rag.fly.dev
- All endpoints are under /api/*

## Important Notes
- Qdrant is used for vector storage, NOT ChromaDB
- PostgreSQL is used for structured data
- Tools execute directly in Python (no HTTP overhead)
- Handlers execute via HTTP proxy to TypeScript backend
""",
            "metadata": {
                "service": "general",
                "category": "backend_services",
                "type": "overview",
                "title": "Backend API Complete Overview",
            },
        },
    ]
    docs.extend(general_docs)

    return docs


async def ingest_documents(
    collection_name: str = "knowledge_base", docs: list[dict] | None = None
) -> dict[str, any]:
    """
    Ingest documents into Qdrant collection.

    Args:
        collection_name: Name of Qdrant collection
        docs: List of documents (if None, generates them)

    Returns:
        Dictionary with ingestion results
    """
    if docs is None:
        docs = generate_backend_services_docs()

    logger.info(f"📚 Generated {len(docs)} documentation documents")
    logger.info(f"📦 Target collection: {collection_name}")

    # Initialize Qdrant client
    from app.core.config import settings

    qdrant_url = settings.qdrant_url
    logger.info(f"🔗 Connecting to Qdrant: {qdrant_url}")

    vector_db = QdrantClient(qdrant_url=qdrant_url, collection_name=collection_name)

    # Check if collection exists, create if not
    try:
        stats = vector_db.get_collection_stats()
        if "error" in stats:
            logger.info(f"📝 Creating collection: {collection_name}")
            vector_db.create_collection(vector_size=1536, distance="Cosine")
        else:
            logger.info(
                f"✅ Collection exists: {collection_name} ({stats.get('total_documents', 0)} docs)"
            )
    except Exception as e:
        logger.warning(f"⚠️ Collection check failed: {e}, attempting to create...")
        vector_db.create_collection(vector_size=1536, distance="Cosine")

    # Initialize embedder
    embedder = EmbeddingsGenerator()
    logger.info(f"✅ Embedder ready: {embedder.provider} ({embedder.dimensions} dims)")

    # Prepare documents
    contents = [doc["content"] for doc in docs]
    metadatas = [doc["metadata"] for doc in docs]

    # Generate embeddings
    logger.info(f"🔄 Generating embeddings for {len(contents)} documents...")
    embeddings = embedder.generate_batch_embeddings(contents)
    logger.info(f"✅ Generated {len(embeddings)} embeddings")

    # Generate IDs (Qdrant requires UUID or integer)
    import uuid

    ids = [str(uuid.uuid4()) for _ in docs]

    # Ingest into Qdrant
    logger.info(f"📥 Ingesting {len(docs)} documents into {collection_name}...")
    try:
        vector_db.upsert_documents(
            chunks=contents, embeddings=embeddings, metadatas=metadatas, ids=ids
        )
        logger.info(f"✅ Successfully ingested {len(docs)} documents")
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {e}")
        raise

    # Verify ingestion
    stats = vector_db.get_collection_stats()
    logger.info(f"📊 Collection stats: {stats}")

    return {
        "success": True,
        "collection": collection_name,
        "documents_ingested": len(docs),
        "total_documents": stats.get("total_documents", 0),
    }


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Ingest backend services documentation into Qdrant"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name (default: knowledge_base)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BACKEND SERVICES DOCUMENTATION INGESTION")
    logger.info("=" * 60)

    try:
        result = await ingest_documents(collection_name=args.collection)
        logger.info("\n" + "=" * 60)
        logger.info("✅ INGESTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Collection: {result['collection']}")
        logger.info(f"Documents ingested: {result['documents_ingested']}")
        logger.info(f"Total documents in collection: {result['total_documents']}")
        return 0
    except Exception as e:
        logger.error(f"\n❌ INGESTION FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
