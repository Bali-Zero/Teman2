# ⚙️ NUZANTARA TECHNICAL EXPLANATION

## 🏗️ Architecture: The Monorepo Ecosystem

Nuzantara is not a single app, but a **system of systems** managed as a monorepo. It uses a **Hub-and-Spoke** architecture where the Backend is the central hub and various frontends/services are the spokes.

### 1. The Core (Backend-RAG)

- **Role**: The centralized "Brain" and "State Manager".
- **Design**: Modular Monolith. It's one deployable unit (FastAPI) but internally organized into distinct modules (CRM, RAG, Comms) that could theoretically be split later.
- **Data Persistence**:
  - **PostgreSQL**: The "Source of Truth" for structured data (Users, Clients, Permissions).
  - **Qdrant**: The "Semantic Memory". Stores vector embeddings of documents, allowing the AI to "search by meaning".
  - **Redis**: The "Short-term Memory". Handles fast access data like user sessions and API rate limits.

### 2. The Face (Mouth)

- **Role**: The primary human interface.
- **Design**: Server-Side Rendered (SSR) for performance and SEO (on public pages), Client-Side interactivity for the dashboard.
- **Communication**: Talks to the backend exclusively via REST APIs.

### 3. The Satellites

- **Intel Scraper**: Autonomous python scripts that scour the web for relevant news/laws, process them, and feed them into the Backend/Qdrant.
- **Media**: Likely a service for generating or managing rich media content based on the system's data.

## 🔄 Critical Flows

### 🧠 The RAG Loop (Retrieval Augmented Generation)

This is how the system answers complex questions:

1.  **Input**: User asks "What are the visa requirements for X?" via Chat UI.
2.  **Embedding**: Backend converts the question into a vector (numbers).
3.  **Retrieval**: Qdrant finds documents mathematically similar to that vector.
4.  **Generation**: Backend sends the original question + the retrieved documents to the LLM (Gemini).
5.  **Output**: LLM generates a grounded answer based on those documents.

### 🔄 The Data Pipeline

1.  **Ingestion**: Scrapers fetch raw text -> Backend cleans/chunks it -> Embeds it -> Stores in Qdrant.
2.  **Access**: When an Agent or User queries, they access this curated knowledge base, not just the LLM's training data.
