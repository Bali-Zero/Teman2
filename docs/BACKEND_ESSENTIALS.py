# ZANTARA BACKEND ESSENTIALS - PRODUCTION REFERENCE
# ==============================================================================
# 🚀 SYSTEM COORDINATES & PRODUCTION CONFIGURATION
# ==============================================================================
# Use this file as the SOURCE OF TRUTH for connecting to Zantara in Production.

# --- COORDINATES ---
PRODUCTION_URL = "https://nuzantara-rag.fly.dev"
PORT = 8080  # Standardized port
QDRANT_URL = "https://nuzantara-qdrant.fly.dev"
METRICS_URL = f"{PRODUCTION_URL}/metrics"
HEALTH_URL = f"{PRODUCTION_URL}/health"

# --- AUTHENTICATION ---
# Header: X-API-Key: <YOUR_SECURE_KEY>
# OR
# Header: Authorization: Bearer <JWT_TOKEN>

# ==============================================================================
# 1. CRITICAL API MAP
# ==============================================================================

API_ENDPOINTS = {
    "chat_stream": {
        "method": "POST",
        "path": "/api/chat/stream",
        "description": "Primary RAG Chat Endpoint (Streaming)",
        "payload": {
            "message": "User query",
            "user_id": "unique_user_id",
            "conversation_history": [],
            "metadata": {}
        },
        "response": "Server-Sent Events (SSE) stream"
    },
    "metrics": {
        "method": "GET",
        "path": "/metrics",
        "description": "Prometheus Metrics (Performance, Latency, Errors)",
        "access": "Public (Rate Limited)"
    },
    "health": {
        "method": "GET",
        "path": "/health",
        "description": "System Health Check (DB, Cache, API)",
        "response": {"status": "healthy", "components": {...}}
    },
    "oracle_query": {
        "method": "POST",
        "path": "/api/oracle/query",
        "description": "Legacy/Hybrid Oracle Endpoint (Non-Streaming/Streaming)",
        "note": "Does not emit Phase 1 performance metrics"
    }
}

# ==============================================================================
# 2. USAGE EXAMPLES (PRODUCTION)
# ==============================================================================

"""
### 1. STREAMING CHAT (CURL)
curl -N -X POST https://nuzantara-rag.fly.dev/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "message": "Quali sono i requisiti per il KITAS investitori?",
    "user_id": "prod_user_123"
  }'

### 2. CHECK PERFORMANCE METRICS
curl -s https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_ 

### 3. HEALTH CHECK
curl https://nuzantara-rag.fly.dev/health
"""

# ==============================================================================
# 3. CORE SERVICES MAPPING
# ==============================================================================

SERVICES_MAP = {
    "SearchService": "Core RAG logic. Handles Qdrant queries & reranking.",
    "IntelligentRouter": "Orchestrates chat flow (Agentic RAG).",
    "OracleService": "Hybrid/Legacy logic for /api/oracle/query.",
    "GoldenAnswerService": "Fast-path cached answers (Postgres)."
}

# ==============================================================================
# 4. DATABASE & INFRASTRUCTURE
# ==============================================================================

INFRASTRUCTURE = {
    "Platform": "Fly.io",
    "Region": "sin (Singapore)",
    "Database": "Postgres (Fly)",
    "VectorDB": "Qdrant (Fly)",
    "Embedding": "OpenAI text-embedding-3-small",
    "LLM": "Gemini 2.5 Flash / GPT-4o-mini"
}