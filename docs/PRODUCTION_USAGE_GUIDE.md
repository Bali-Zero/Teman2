# 🚀 Zantara Production Usage Guide

**Status**: Verified v5.4 Ultra Hybrid  
**Last Updated**: December 18, 2025

This guide provides the essential coordinates and instructions for interacting with the Zantara system in production.

---

## 1. 🌐 System Coordinates

| Component | Production URL | Port | Status |
|-----------|---------------|------|--------|
| **Backend API** | `https://nuzantara-rag.fly.dev` | 443 (8080 internal) | ✅ Online |
| **Qdrant Vector DB** | `https://nuzantara-qdrant.fly.dev` | 443 | ✅ Online |
| **Frontend** | `https://nuzantara-mouth.fly.dev` | 443 | ⚠️ Check Config |
| **Database** | Postgres (Fly Internal) | 5432 | ✅ Online |

---

## 2. 🔑 Authentication

All protected endpoints require authentication via Header.

### Method A: API Key (Recommended for Scripts/Tools)
```http
X-API-Key: <YOUR_SECURE_API_KEY>
```

### Method B: JWT Token (Frontend/User)
```http
Authorization: Bearer <JWT_TOKEN>
```

---

## 3. 🗺️ Critical API Endpoints

### 💬 Chat & RAG (Primary)
* **Endpoint**: `POST /api/chat/stream`
* **Purpose**: Main conversational interface with Agentic RAG.
* **Features**: Streaming, Memory, Tool Use, Performance Metrics.
* **Payload**:
  ```json
  {
    "message": "User query here",
    "user_id": "unique_id",
    "conversation_history": []
  }
  ```

### 📊 Observability
* **Endpoint**: `GET /metrics`
* **Purpose**: Prometheus metrics for monitoring latency, errors, and RAG pipeline performance.
* **Key Metrics**: `zantara_rag_pipeline_duration_seconds`, `zantara_rag_early_exit_total`.

### 🏥 Health
* **Endpoint**: `GET /health`
* **Purpose**: Deep health check of API, Database, and Cache connections.

### 🔮 Oracle (Hybrid/Legacy)
* **Endpoint**: `POST /api/oracle/query`
* **Purpose**: Specific oracle logic. **Note**: Does NOT emit Phase 1 performance metrics.

---

## 4. 🛠️ Usage Examples (Curl)

### Start a Chat Stream
```bash
curl -N -X POST https://nuzantara-rag.fly.dev/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "message": "Quali sono i requisiti per il KITAS investitori?",
    "user_id": "prod_test_user"
  }'
```

### Verify Performance Metrics
```bash
# Check RAG Pipeline Duration
curl -s https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_pipeline_duration
```

### Check System Health
```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool
```

---

## 5. 🚑 Quick Recovery

If the system is unresponsive or behaving abnormally:

1. **Check Logs**:
   ```bash
   fly logs --app nuzantara-rag
   ```

2. **Restart Backend**:
   ```bash
   fly apps restart nuzantara-rag
   ```

3. **Check Deploy Status**:
   ```bash
   fly status --app nuzantara-rag
   ```
