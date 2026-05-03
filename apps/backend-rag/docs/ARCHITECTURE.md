# Architecture (Mermaid)

This document provides high-level architecture diagrams for the backend. These
diagrams are kept intentionally concise to show system context, request flow,
and the ingestion/knowledge-graph pipeline.

## System Context

```mermaid
flowchart TD
    Client[Web / Mobile / Integrations] --> API[FastAPI Backend]
    API --> Auth[Auth + Security]
    API --> Router[Intelligent Router]
    Router --> Services[Domain Services]
    Services --> Postgres[(PostgreSQL)]
    Services --> Qdrant[(Qdrant Vector DB)]
    Services --> Redis[(Redis Cache)]
    Services --> LLMs[LLM Providers]
    Services --> Integrations[External Integrations]
    API --> Observability[Prometheus + OpenTelemetry]
```

## Chat / Agentic RAG Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Auth as Auth/Middleware
    participant Router as Query Router
    participant Search as Search/RAG
    participant LLM as LLM Gateway
    participant Memory as Memory Service

    Client->>API: POST /api/v1/chat
    API->>Auth: Verify API key/JWT/CSRF
    API->>Router: Classify + route request
    Router->>Search: Retrieve context (Qdrant/KB)
    Search-->>Router: Ranked context
    Router->>LLM: Build prompt + generate response
    LLM-->>Router: Structured response
    Router->>Memory: Persist conversation + facts
    Router-->>API: Response payload
    API-->>Client: 200 OK
```

## Ingestion + Knowledge Graph Pipeline

```mermaid
flowchart LR
    Source[Docs / Intel / Uploads] --> Ingest[Ingestion Router]
    Ingest --> Chunking[Chunk + Normalize]
    Chunking --> Embeddings[Embedding Service]
    Embeddings --> Qdrant[(Qdrant)]
    Chunking --> KG[KG Builder]
    KG --> Postgres[(PostgreSQL)]
    Ingest --> Metadata[Metadata + Audit]
    Metadata --> Postgres
```

## Observability & Health

```mermaid
flowchart TD
    API[FastAPI Backend] --> Metrics[Prometheus Metrics]
    API --> Traces[OpenTelemetry Traces]
    API --> Health[/health, /health/detailed/]
    Metrics --> Dashboards[Grafana / Alerting]
    Traces --> Collector[OTLP Collector]
```
