# ZANTARA Services Reference

This document lists all available backend services that Zantara should be aware of and able to access.

## Overview

Zantara has access to multiple backend services through the unified API client. This document serves as a reference for what Zantara should know about each service.

## Service Categories

### 1. Conversations Service
**Purpose**: Persistent conversation storage and retrieval

**Endpoints**:
- `POST /api/bali-zero/conversations/save` - Save conversation to PostgreSQL
- `GET /api/bali-zero/conversations/history` - Load conversation history
- `DELETE /api/bali-zero/conversations/clear` - Clear conversation history
- `GET /api/bali-zero/conversations/stats` - Get conversation statistics

**What Zantara Should Know**:
- Can save conversations automatically after each turn
- Conversations are stored in PostgreSQL database
- Can load previous conversation history
- Conversations are linked to user email and session ID
- CRM data is auto-extracted from conversations

### 2. Memory Service
**Purpose**: Semantic memory search and storage

**Endpoints**:
- `POST /api/memory/embed` - Generate embedding for text
- `POST /api/memory/search` - Search semantic memories
- `POST /api/memory/store` - Store new memory vector
- `GET /api/memory/stats` - Get memory service statistics

**What Zantara Should Know**:
- Can search memories semantically using embeddings
- Can store important information as memories
- Memories are stored in Qdrant vector database
- Memories are linked to user ID
- Can retrieve relevant memories for context

### 3. CRM Services

#### CRM Clients
**Endpoints**:
- `GET /api/crm/clients/by-email/{email}` - Get client by email
- `GET /api/crm/clients/{client_id}/summary` - Get client summary
- `GET /api/crm/clients/stats/overview` - Get CRM statistics
- `POST /api/crm/clients` - Create new client
- `PUT /api/crm/clients/{client_id}` - Update client

**What Zantara Should Know**:
- Can look up client information by email
- Can get full client summary with practices and interactions
- Client data includes status, practices, and recent interactions

#### CRM Practices
**Endpoints**:
- `GET /api/crm/practices/client/{client_id}` - Get practices for client
- `POST /api/crm/practices` - Create new practice
- `PUT /api/crm/practices/{practice_id}` - Update practice

**What Zantara Should Know**:
- Practices represent client legal/business matters
- Each practice has a type (visa, tax, legal, etc.)
- Practices have status (active, completed, etc.)

#### CRM Interactions
**Endpoints**:
- `POST /api/crm/interactions` - Log interaction with client
- `GET /api/crm/interactions/client/{client_id}` - Get client interactions

**What Zantara Should Know**:
- Can log chatbot interactions to CRM
- Interactions are linked to clients and team members
- Interactions include type, summary, and timestamp

### 4. Agentic Functions Service
**Purpose**: Advanced AI capabilities and automation

**Endpoints**:
- `GET /api/agents/status` - Get status of all agents
- `POST /api/agents/journey/create` - Create client journey
- `GET /api/agents/compliance-alerts` - Get compliance alerts
- `POST /api/agents/pricing/calculate` - Calculate dynamic pricing
- `POST /api/agents/synthesis/cross-oracle` - Cross-oracle synthesis search

**Available Agents**:
1. Client Journey Orchestrator
2. Proactive Compliance Monitor
3. Knowledge Graph Builder
4. Cross-Oracle Synthesis Service
5. Dynamic Pricing Calculator
6. Autonomous Research Service

**What Zantara Should Know**:
- Can create automated client journeys
- Can monitor compliance deadlines
- Can calculate dynamic pricing for services
- Can perform cross-domain knowledge synthesis
- Can trigger autonomous research tasks

### 5. Oracle Services

#### Oracle V53 Ultra Hybrid
**Purpose**: Multi-domain knowledge search and synthesis

**Endpoints**:
- `POST /api/oracle/v53/query` - Query oracle with multiple domains
- `POST /api/oracle/v53/synthesis` - Cross-domain synthesis

**Domains Available**:
- Tax (tax_genius)
- Legal (legal_unified)
- Visa (visa_oracle)
- Property (bali_zero_pricing)
- KBLI (kbli_unified)
- Knowledge Base (knowledge_base)

**What Zantara Should Know**:
- Can search across multiple knowledge domains simultaneously
- Can synthesize answers from multiple sources
- Each domain has specialized knowledge
- Oracle uses hybrid search (semantic + keyword)

### 6. Knowledge Service
**Purpose**: Knowledge base search and retrieval

**Endpoints**:
- `POST /api/knowledge/search` - Semantic search in knowledge base
- `GET /api/knowledge/collections` - List available collections

**Collections Available**:
- `bali_zero_pricing` - Property pricing data
- `visa_oracle` - Visa and immigration information
- `tax_genius` - Tax regulations and information
- `legal_unified` - Indonesian legal documents
- `kbli_unified` - KBLI business classification
- `knowledge_base` - General knowledge base

**What Zantara Should Know**:
- Can search specific collections or all collections
- Uses semantic search with embeddings
- Returns relevant documents with scores
- Can filter by metadata

### 7. Ingestion Service
**Purpose**: Document ingestion into knowledge base

**Endpoints**:
- `POST /api/ingest/upload` - Upload and ingest document
- `POST /api/ingest` - Ingest documents from request
- `POST /api/oracle/ingest` - Ingest into oracle collections

**What Zantara Should Know**:
- Can ingest PDFs, text files, and other documents
- Documents are chunked and embedded
- Can specify target collection
- Supports batch ingestion

### 8. Image Generation Service
**Purpose**: AI image generation

**Endpoints**:
- `POST /api/image/generate` - Generate image from prompt

**What Zantara Should Know**:
- Uses Google Imagen AI
- Can generate images from text prompts
- Supports various aspect ratios and safety filters
- Returns image URLs

### 9. Productivity Service
**Purpose**: Team productivity tracking

**Endpoints**:
- `POST /api/productivity/clock-in` - Clock in
- `POST /api/productivity/clock-out` - Clock out
- `GET /api/productivity/daily-hours` - Get daily hours
- `GET /api/productivity/weekly-summary` - Get weekly summary
- `GET /api/productivity/monthly-summary` - Get monthly summary

**What Zantara Should Know**:
- Can track team member work hours
- Provides summaries and statistics
- Integrates with team activity tracking

### 10. Team Activity Service
**Purpose**: Track team member activities

**Endpoints**:
- `GET /api/team-activity/status` - Get team member statuses
- `GET /api/team-activity/stats` - Get activity statistics

**What Zantara Should Know**:
- Can see who is currently active
- Tracks team member availability
- Provides activity statistics

### 11. Notifications Service
**Purpose**: Send notifications to users

**Endpoints**:
- `POST /api/notifications/send` - Send notification
- `POST /api/notifications/template` - Send templated notification

**What Zantara Should Know**:
- Can send notifications to users
- Supports templates
- Can target specific users or groups

### 12. Health Service
**Purpose**: System health monitoring

**Endpoints**:
- `GET /api/health` - Health check
- `GET /api/health/detailed` - Detailed health status

**What Zantara Should Know**:
- Can check system health
- Returns status of all services
- Provides metrics and statistics

### 13. Handlers Service
**Purpose**: List and search available API handlers

**Endpoints**:
- `GET /api/handlers/list` - List all handlers
- `GET /api/handlers/search` - Search handlers

**What Zantara Should Know**:
- Can see all available API endpoints
- Can search for specific handlers
- Provides handler documentation

## Integration Points

### Frontend Integration
The webapp uses `zantaraAPI` which provides a unified interface to all these services:
- Session management
- Context building (combines CRM, Memory, Agents)
- Conversation saving
- Memory search and storage

### Backend Integration
All services are accessible through:
- REST API endpoints
- OpenAPI/Swagger documentation
- TypeScript generated client (`NuzantaraClient`)

## What Zantara Should Be Able To Do

1. **Know about services**: Zantara should be aware of all available services
2. **Guide users**: Help users understand what services are available
3. **Use services**: Access services through API calls when appropriate
4. **Explain capabilities**: Explain what each service can do
5. **Troubleshoot**: Help diagnose issues with service access

## Testing

Use `scripts/test_zantara_services.py` to test Zantara's knowledge of these services:

```bash
python scripts/test_zantara_services.py --token YOUR_TOKEN
```

This will ask Zantara questions about each service category and generate a report.

