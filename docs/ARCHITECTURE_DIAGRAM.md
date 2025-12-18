# NUZANTARA — Architecture Diagrams

## 1. System Overview

```mermaid
flowchart TB
    subgraph CLIENT["CLIENT LAYER"]
        UI["Web Application<br/>(Next.js / React)<br/>━━━━━━━━━━<br/>STATELESS"]
    end

    subgraph EDGE["EDGE / CDN"]
        CDN["Global CDN<br/>(Fly.io Edge)"]
    end

    subgraph BACKEND["BACKEND LAYER"]
        subgraph API["API Gateway"]
            AUTH["Auth Middleware<br/>JWT + API Key"]
            RATE["Rate Limiter"]
            ROUTER["Request Router"]
        end

        subgraph ORCHESTRATION["Orchestration Layer"]
            INTEL["Intelligent Router<br/>(Domain Scoring)"]
            AGENT["Agentic Orchestrator<br/>(ReAct Loop)"]
            MEMORY["Memory Service"]
        end

        subgraph SERVICES["Service Layer"]
            SEARCH["Search Service"]
            CONV["Conversation Service"]
            CRM["CRM Service"]
            INGEST["Ingestion Service"]
        end
    end

    subgraph AI["AI / LLM LAYER"]
        PROMPT["Prompt Manager"]
        TOOLS["Tool Registry<br/>━━━━━━━━━━<br/>Vector Search<br/>SQL Query<br/>Calculator<br/>Vision"]
        PERSONALITY["Personality Layer<br/>(Style Transfer)"]
    end

    subgraph DATA["DATA LAYER"]
        PG[("PostgreSQL<br/>━━━━━━━━━━<br/>Users, CRM,<br/>Conversations,<br/>Memory Facts<br/>━━━━━━━━━━<br/>STATEFUL")]
        QDRANT[("Qdrant<br/>━━━━━━━━━━<br/>25K+ Documents<br/>8 Collections<br/>━━━━━━━━━━<br/>STATEFUL")]
        REDIS[("Redis<br/>━━━━━━━━━━<br/>Cache, PubSub,<br/>Rate Limits<br/>━━━━━━━━━━<br/>OPTIONAL")]
    end

    subgraph EXTERNAL["EXTERNAL SERVICES"]
        GEMINI["Google Gemini<br/>(Primary LLM)"]
        OPENAI["OpenAI<br/>(Embeddings)"]
        OPENROUTER["OpenRouter<br/>(Fallback LLMs)"]
    end

    subgraph MONITORING["OBSERVABILITY"]
        PROM["Prometheus"]
        ALERT["Alertmanager"]
        GRAFANA["Grafana"]
        SENTRY["Sentry<br/>(Error Tracking)"]
    end

    %% Client connections
    UI -->|"HTTPS"| CDN
    CDN -->|"REST / SSE"| AUTH
    UI <-->|"WebSocket<br/>(WSS)"| ROUTER

    %% API Gateway flow
    AUTH --> RATE
    RATE --> ROUTER
    ROUTER --> INTEL

    %% Orchestration flow
    INTEL --> AGENT
    INTEL --> SEARCH
    AGENT --> TOOLS
    AGENT --> PROMPT
    AGENT --> MEMORY

    %% Service layer connections
    SEARCH --> QDRANT
    CONV --> PG
    CRM --> PG
    MEMORY --> PG
    INGEST --> QDRANT
    INGEST --> PG

    %% AI layer connections
    PROMPT --> GEMINI
    PROMPT -.->|"Fallback"| OPENROUTER
    TOOLS --> SEARCH
    TOOLS --> PG
    PERSONALITY --> GEMINI

    %% Embedding generation
    SEARCH -->|"Embeddings"| OPENAI

    %% Cache connections
    RATE -.-> REDIS
    ROUTER -.->|"PubSub"| REDIS
    MEMORY -.-> REDIS

    %% Monitoring connections
    BACKEND -.->|"Metrics"| PROM
    PROM --> ALERT
    PROM --> GRAFANA
    UI -.->|"Errors"| SENTRY
    BACKEND -.->|"Errors"| SENTRY
```

---

## 2. Request Data Flow

```mermaid
flowchart LR
    subgraph REQUEST["REQUEST FLOW"]
        direction TB
        Q["User Query"]
        Q --> V["Validate & Auth"]
        V --> R["Route by Domain"]
        R --> E["Generate Embedding"]
        E --> S["Semantic Search"]
        S --> C["Build Context"]
        C --> L["LLM Generation"]
        L --> P["Apply Personality"]
        P --> A["Stream Response"]
    end

    subgraph STORAGE["STATE CHANGES"]
        direction TB
        S1["Save Message"]
        S2["Extract Memory Facts"]
        S3["Update CRM"]
        S4["Log Audit Trail"]
    end

    A --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
```

---

## 3. Deployment Topology

```mermaid
flowchart TB
    subgraph INTERNET["INTERNET"]
        USER["Users"]
    end

    subgraph FLYIO["FLY.IO PLATFORM"]
        subgraph EDGE_NODES["Edge Network"]
            CDN1["CDN Node 1"]
            CDN2["CDN Node 2"]
        end

        subgraph APP_INSTANCES["Application Instances"]
            FE1["Frontend Instance"]
            FE2["Frontend Instance"]
            BE1["Backend Instance"]
            BE2["Backend Instance"]
        end

        subgraph MANAGED_DB["Managed Services"]
            PGFLY["PostgreSQL<br/>(Fly Postgres)"]
        end
    end

    subgraph EXTERNAL_MANAGED["EXTERNAL MANAGED SERVICES"]
        QDRANT_CLOUD["Qdrant Cloud"]
        REDIS_CLOUD["Redis Cloud<br/>(Optional)"]
    end

    subgraph LLM_PROVIDERS["LLM PROVIDERS"]
        GOOGLE["Google AI"]
        OAI["OpenAI"]
        OR["OpenRouter"]
    end

    USER --> CDN1
    USER --> CDN2
    CDN1 --> FE1
    CDN2 --> FE2
    FE1 --> BE1
    FE2 --> BE2
    BE1 --> PGFLY
    BE2 --> PGFLY
    BE1 --> QDRANT_CLOUD
    BE2 --> QDRANT_CLOUD
    BE1 -.-> REDIS_CLOUD
    BE2 -.-> REDIS_CLOUD
    BE1 --> GOOGLE
    BE1 --> OAI
    BE1 -.-> OR
```

---

## 4. Agentic RAG Flow (ReAct Pattern)

```mermaid
flowchart TD
    START["User Query"] --> THINK1["THOUGHT<br/>Analyze query intent"]
    THINK1 --> DECIDE{"Need more<br/>information?"}

    DECIDE -->|Yes| ACTION["ACTION<br/>Select & Execute Tool"]
    ACTION --> OBSERVE["OBSERVATION<br/>Process tool results"]
    OBSERVE --> THINK2["THOUGHT<br/>Evaluate quality"]
    THINK2 --> DECIDE

    DECIDE -->|No| ANSWER["FINAL ANSWER<br/>Synthesize response"]
    ANSWER --> STREAM["Stream to User<br/>with Citations"]

    subgraph TOOLS["Available Tools"]
        T1["Vector Search"]
        T2["SQL Query"]
        T3["Calculator"]
        T4["Vision/PDF"]
    end

    ACTION --> TOOLS
    TOOLS --> OBSERVE
```

---

## 5. Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as Auth Middleware
    participant B as Backend API
    participant DB as PostgreSQL

    U->>F: Login Request
    F->>B: POST /auth/login
    B->>DB: Validate Credentials
    DB-->>B: User Record
    B-->>F: JWT Token
    F->>F: Store Token

    U->>F: API Request
    F->>A: Request + Bearer Token
    A->>A: Validate JWT
    alt Token Valid
        A->>B: Forward Request
        B-->>F: Response
    else Token Invalid
        A-->>F: 401 Unauthorized
    end
```

---

## 6. WebSocket Real-Time Flow

```mermaid
sequenceDiagram
    participant U as User Browser
    participant WS as WebSocket Server
    participant R as Redis PubSub
    participant S as Backend Services

    U->>WS: Connect (WSS + Token)
    WS->>WS: Validate Token
    WS-->>U: Connection Accepted

    loop Heartbeat
        U->>WS: Ping
        WS-->>U: Pong
    end

    S->>R: Publish Notification
    R->>WS: Broadcast Event
    WS-->>U: Push Notification
```

---

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `──▶` | Synchronous request |
| `-.->` | Optional / Async |
| `(Database)` | Stateful storage |
| `[Service]` | Stateless component |
| `STATELESS` | Can scale horizontally |
| `STATEFUL` | Requires persistence |
| `OPTIONAL` | System works without it |

---

## How to View

1. **VS Code**: Install "Markdown Preview Mermaid Support" extension, then preview this file
2. **Online**: Use Mermaid Live Editor or compatible viewer
3. **Mermaid Live**: Copy diagrams to [mermaid.live](https://mermaid.live)
4. **Export**: Use Mermaid CLI to export as PNG/SVG
