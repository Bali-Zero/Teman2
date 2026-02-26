# API Reference — Nuzantara Backend

**Version:** 5.2.0
**Base URL:** `https://nuzantara-rag.fly.dev`
**Last Generated:** 2026-02-26
**Total Routers:** 83+ files | **Total Endpoints:** 200+

---

## Authentication

All endpoints require JWT authentication unless marked **PUBLIC**.

**Auth methods (priority order):**

1. `X-API-Key` header (fastest, in-memory validation)
2. Cookie JWT (`access_token` cookie, browser clients)
3. `Authorization: Bearer <token>` header

**Roles:** `admin`, `founder`, `team_member`, `client`

---

## Table of Contents

1. [Core Chat & RAG](#1-core-chat--rag)
2. [Agent System](#2-agent-system)
3. [KBLI (Business Classification)](#3-kbli-business-classification)
4. [CRM — Clients](#4-crm--clients)
5. [CRM — Practices](#5-crm--practices)
6. [CRM — Analytics & Migration](#6-crm--analytics--migration)
7. [Portal (Client-Facing)](#7-portal-client-facing)
8. [Conversations](#8-conversations)
9. [Knowledge & Ingestion](#9-knowledge--ingestion)
10. [Knowledge Graph](#10-knowledge-graph)
11. [Analytics & Monitoring](#11-analytics--monitoring)
12. [Notifications](#12-notifications)
13. [Integrations — Google Drive](#13-integrations--google-drive)
14. [Integrations — Zoho](#14-integrations--zoho)
15. [Channels — Telegram](#15-channels--telegram)
16. [Channels — WhatsApp](#16-channels--whatsapp)
17. [Channels — Instagram](#17-channels--instagram)
18. [Channels — Twitter/X](#18-channels--twitterx)
19. [Voice](#19-voice)
20. [Article Composer](#20-article-composer)
21. [Autonomous Execution](#21-autonomous-execution)
22. [Workflow Analytics](#22-workflow-analytics)
23. [Health & System](#23-health--system)
24. [Test & Debug Endpoints](#24-test--debug-endpoints)

---

## 1. Core Chat & RAG

**Router:** `agentic_rag.py` | **Prefix:** `/api/agentic-rag`

| Method | Path                                 | Auth       | Description                           |
| ------ | ------------------------------------ | ---------- | ------------------------------------- |
| POST   | `/api/agentic-rag/query`             | Required   | Synchronous RAG query with tool use   |
| POST   | `/api/agentic-rag/stream`            | **PUBLIC** | SSE streaming chat (primary endpoint) |
| POST   | `/api/agentic-rag/proactive-trigger` | Required   | Trigger proactive suggestions         |

### SSE Stream Events

The `/stream` endpoint emits these SSE event types:

| Event            | Description                           |
| ---------------- | ------------------------------------- |
| `token`          | Incremental text token                |
| `sources`        | Retrieved document sources            |
| `metadata`       | Query metadata (model, latency, cost) |
| `thinking`       | LLM reasoning step                    |
| `tool_call`      | Tool invocation                       |
| `reasoning_step` | Multi-step reasoning                  |
| `error`          | Error during processing               |
| `done`           | Stream complete                       |

**Timeouts:** 120s request, 300s idle, 600s max total.

### A/B Testing Sub-routes

| Method | Path                                                        | Auth     | Description                         |
| ------ | ----------------------------------------------------------- | -------- | ----------------------------------- |
| POST   | `/api/agentic-rag/ab-test/feedback`                         | Required | Submit user feedback for experiment |
| GET    | `/api/agentic-rag/ab-test/results/{experiment}`             | Required | Get experiment results              |
| GET    | `/api/agentic-rag/ab-test/dashboard`                        | Required | A/B test dashboard                  |
| GET    | `/api/agentic-rag/ab-test/experiments`                      | Required | List all experiments                |
| POST   | `/api/agentic-rag/ab-test/experiments/{experiment}/control` | Required | Control experiment                  |
| GET    | `/api/agentic-rag/ab-test/user/{user_id}/exposure`          | Required | Get user's experiment exposure      |

---

## 2. Agent System

### Agent Invoke

**Router:** `agent.py` | **Prefix:** `/api/agent`

| Method | Path                | Auth       | Description          |
| ------ | ------------------- | ---------- | -------------------- |
| POST   | `/api/agent/invoke` | Required   | Invoke AI agent task |
| GET    | `/api/agent/health` | **PUBLIC** | Agent health check   |

### Generals (Multi-Agent)

**Router:** `agents.py` | **Prefix:** `/api/agents`

| Method | Path                                 | Auth     | Description                  |
| ------ | ------------------------------------ | -------- | ---------------------------- |
| GET    | `/api/agents/status`                 | Required | All generals status          |
| GET    | `/api/agents/activity`               | Required | Recent general activity log  |
| GET    | `/api/agents/stats`                  | Required | General execution statistics |
| POST   | `/api/agents/tasks`                  | Required | Submit task to generals      |
| GET    | `/api/agents/tasks/{task_id}`        | Required | Get task status              |
| DELETE | `/api/agents/tasks/{task_id}`        | Required | Cancel task                  |
| GET    | `/api/agents/tasks/{task_id}/result` | Required | Get task result              |
| POST   | `/api/agents/tasks/{task_id}/wait`   | Required | Wait for task completion     |
| GET    | `/api/agents/memory/{key}`           | Required | Read shared memory           |
| PUT    | `/api/agents/memory/{key}`           | Required | Write shared memory          |

---

## 3. KBLI (Business Classification)

**Router:** `kbli_notebook.py` | **Prefix:** `/api/v1/kbli-notebook` | **All PUBLIC**

| Method | Path                                   | Auth       | Description                      |
| ------ | -------------------------------------- | ---------- | -------------------------------- |
| GET    | `/api/v1/kbli-notebook/search`         | **PUBLIC** | Search KBLI codes by query       |
| GET    | `/api/v1/kbli-notebook/inspect/{code}` | **PUBLIC** | Inspect single KBLI code details |
| POST   | `/api/v1/kbli-notebook/chat`           | **PUBLIC** | AI chat about KBLI regulations   |
| GET    | `/api/v1/kbli-notebook/sectors`        | **PUBLIC** | List all KBLI sectors            |
| GET    | `/api/v1/kbli-notebook/compare`        | **PUBLIC** | Compare multiple KBLI codes      |

**Note:** KBLI uses flat Qdrant payload (not nested). See `AI_ONBOARDING.md` for details.

---

## 4. CRM — Clients

**Router:** `crm_clients.py` | **Prefix:** `/api/crm/clients`

| Method | Path                                       | Auth     | Description                                    |
| ------ | ------------------------------------------ | -------- | ---------------------------------------------- |
| GET    | `/api/crm/clients`                         | Required | List clients (admin: all, team: assigned only) |
| GET    | `/api/crm/clients/{client_id}`             | Required | Get client details                             |
| POST   | `/api/crm/clients`                         | Required | Create new client                              |
| PUT    | `/api/crm/clients/{client_id}`             | Required | Update client                                  |
| DELETE | `/api/crm/clients/{client_id}`             | Admin    | Delete client                                  |
| GET    | `/api/crm/clients/{client_id}/timeline`    | Required | Client interaction timeline                    |
| POST   | `/api/crm/clients/{client_id}/interaction` | Required | Log client interaction                         |

**RBAC:** Admins (`zero@balizero.com`, `admin@balizero.com`) see all clients. Team members see only `assigned_to = own_email`.

---

## 5. CRM — Practices

**Router:** `crm_practices.py` | **Prefix:** `/api/crm/practices`

| Method | Path                                      | Auth     | Description                    |
| ------ | ----------------------------------------- | -------- | ------------------------------ |
| GET    | `/api/crm/practices`                      | Required | List practices (RBAC filtered) |
| GET    | `/api/crm/practices/{practice_id}`        | Required | Get practice details           |
| POST   | `/api/crm/practices`                      | Required | Create practice                |
| PUT    | `/api/crm/practices/{practice_id}`        | Required | Update practice                |
| PATCH  | `/api/crm/practices/{practice_id}/status` | Required | Update practice status         |
| GET    | `/api/crm/practices/expiry-alerts`        | Required | Get expiring practice alerts   |

---

## 6. CRM — Analytics & Migration

### CRM Analytics

**Router:** `crm_analytics.py` | **Prefix:** `/api/crm/analytics`

| Method | Path                                  | Auth     | Description               |
| ------ | ------------------------------------- | -------- | ------------------------- |
| GET    | `/api/crm/analytics/overview`         | Required | CRM dashboard overview    |
| GET    | `/api/crm/analytics/completion-rates` | Required | Practice completion rates |
| GET    | `/api/crm/analytics/response-times`   | Required | Response time metrics     |
| GET    | `/api/crm/analytics/sla-compliance`   | Required | SLA compliance report     |
| GET    | `/api/crm/analytics/revenue`          | Required | Revenue analytics         |

### CRM Migration

**Router:** `crm_migration.py` | **Prefix:** `/api/crm/migration`

| Method | Path                        | Auth  | Description            |
| ------ | --------------------------- | ----- | ---------------------- |
| POST   | `/api/crm/migration/import` | Admin | Import legacy CRM data |
| GET    | `/api/crm/migration/status` | Admin | Migration status       |

### CRM Drive Folders

**Router:** `crm_drive_folders.py` | **Prefix:** `/api/crm/drive-folders`

| Method | Path                                 | Auth     | Description                |
| ------ | ------------------------------------ | -------- | -------------------------- |
| POST   | `/api/crm/drive-folders/create`      | Required | Create client Drive folder |
| GET    | `/api/crm/drive-folders/{client_id}` | Required | Get client's Drive folder  |

---

## 7. Portal (Client-Facing)

**Router:** `portal.py` | **Prefix:** `/api/portal`

| Method | Path                           | Auth     | Description                     |
| ------ | ------------------------------ | -------- | ------------------------------- |
| GET    | `/api/portal/dashboard`        | Required | Client portal dashboard         |
| GET    | `/api/portal/visa-status`      | Required | Visa/practice status for client |
| GET    | `/api/portal/messages`         | Required | Client messages                 |
| POST   | `/api/portal/messages`         | Required | Send message to team            |
| GET    | `/api/portal/documents`        | Required | Client documents list           |
| POST   | `/api/portal/documents/upload` | Required | Upload document                 |
| GET    | `/api/portal/timeline`         | Required | Client's practice timeline      |

---

## 8. Conversations

**Router:** `conversations.py` | **Prefix:** `/api/conversations`

| Method | Path                                    | Auth     | Description               |
| ------ | --------------------------------------- | -------- | ------------------------- |
| GET    | `/api/conversations`                    | Required | List user conversations   |
| GET    | `/api/conversations/{session_id}`       | Required | Get conversation messages |
| DELETE | `/api/conversations/{session_id}`       | Required | Delete conversation       |
| PUT    | `/api/conversations/{session_id}/title` | Required | Update conversation title |

---

## 9. Knowledge & Ingestion

### Knowledge Service

**Router:** (module) `modules/knowledge/` | **Prefix:** `/api/knowledge`

| Method | Path                         | Auth     | Description                        |
| ------ | ---------------------------- | -------- | ---------------------------------- |
| POST   | `/api/knowledge/search`      | Required | Semantic search across collections |
| GET    | `/api/knowledge/collections` | Required | List Qdrant collections            |

### Ingestion

**Router:** `ingest.py` | **Prefix:** `/api/ingest`

| Method | Path                   | Auth  | Description                     |
| ------ | ---------------------- | ----- | ------------------------------- |
| POST   | `/api/ingest/document` | Admin | Ingest document into vector DB  |
| POST   | `/api/ingest/batch`    | Admin | Batch ingest multiple documents |

### Gumloop Ingestion

**Router:** `gumloop_ingestion.py` | **Prefix:** `/api/gumloop`

| Method | Path                  | Auth  | Description                  |
| ------ | --------------------- | ----- | ---------------------------- |
| POST   | `/api/gumloop/ingest` | Admin | Ingest from Gumloop pipeline |

---

## 10. Knowledge Graph

**Router:** `kg_agentic.py` | **Prefix:** `/api/kg`

| Method | Path                | Auth     | Description                  |
| ------ | ------------------- | -------- | ---------------------------- |
| POST   | `/api/kg/query`     | Required | KG-augmented query           |
| GET    | `/api/kg/stats`     | Required | KG statistics (nodes, edges) |
| GET    | `/api/kg/visualize` | Required | KG visualization data        |

---

## 11. Analytics & Monitoring

### Query Analytics

**Router:** `query_analytics.py` | **Prefix:** `/api/analytics/queries`

| Method | Path                            | Auth  | Description               |
| ------ | ------------------------------- | ----- | ------------------------- |
| GET    | `/api/analytics/queries`        | Admin | Query analytics dashboard |
| GET    | `/api/analytics/queries/failed` | Admin | Failed queries log        |
| GET    | `/api/analytics/queries/trends` | Admin | Query volume trends       |

### Team Analytics

**Router:** `team_analytics.py` | **Prefix:** `/api/analytics/team`

| Method | Path                               | Auth  | Description               |
| ------ | ---------------------------------- | ----- | ------------------------- |
| GET    | `/api/analytics/team/productivity` | Admin | Team productivity metrics |
| GET    | `/api/analytics/team/burnout`      | Admin | Burnout risk indicators   |
| GET    | `/api/analytics/team/hours`        | Admin | Team working hours        |

### General Analytics

**Router:** `analytics.py` | **Prefix:** `/api/analytics`

| Method | Path                      | Auth  | Description                    |
| ------ | ------------------------- | ----- | ------------------------------ |
| GET    | `/api/analytics/overview` | Admin | System-wide analytics overview |

### Dashboard Summary

**Router:** `dashboard_summary.py` | **Prefix:** `/api/dashboard`

| Method | Path                     | Auth     | Description            |
| ------ | ------------------------ | -------- | ---------------------- |
| GET    | `/api/dashboard/summary` | Required | Dashboard summary data |

### RAG Monitoring

**Router:** `monitoring_rag.py` | **Prefix:** `/api/monitoring`

| Method | Path                                | Auth  | Description              |
| ------ | ----------------------------------- | ----- | ------------------------ |
| GET    | `/api/monitoring/retrieval-quality` | Admin | Retrieval quality scores |
| GET    | `/api/monitoring/scores-trend`      | Admin | Score trends over time   |
| GET    | `/api/monitoring/abstain-rate`      | Admin | ABSTAIN response rate    |
| GET    | `/api/monitoring/latency`           | Admin | Latency percentiles      |
| POST   | `/api/monitoring/alert-threshold`   | Admin | Set alert thresholds     |
| GET    | `/api/monitoring/alert-threshold`   | Admin | Get alert thresholds     |

---

## 12. Notifications

**Router:** `modules/notifications/router.py` | **Prefix:** `/api/notifications`

| Method | Path                              | Auth     | Description               |
| ------ | --------------------------------- | -------- | ------------------------- |
| GET    | `/api/notifications`              | Required | List user notifications   |
| GET    | `/api/notifications/unread-count` | Required | Unread notification count |
| PUT    | `/api/notifications/{id}/read`    | Required | Mark notification as read |
| PUT    | `/api/notifications/read-all`     | Required | Mark all as read          |

### Notification Admin

**Router:** `modules/notifications/admin_router.py` | **Prefix:** `/api/notifications/admin`

| Method | Path                                 | Auth  | Description                 |
| ------ | ------------------------------------ | ----- | --------------------------- |
| POST   | `/api/notifications/admin/send`      | Admin | Send notification to user   |
| GET    | `/api/notifications/admin/stats`     | Admin | Notification statistics     |
| POST   | `/api/notifications/admin/check-now` | Admin | Trigger manual expiry check |

---

## 13. Integrations — Google Drive

### Drive Auth

**Router:** `admin_drive_auth.py` | **Prefix:** `/api/admin/drive`

| Method | Path                        | Auth  | Description              |
| ------ | --------------------------- | ----- | ------------------------ |
| GET    | `/api/admin/drive/auth-url` | Admin | Get OAuth2 URL for Drive |
| GET    | `/api/admin/drive/callback` | Admin | OAuth2 callback handler  |
| GET    | `/api/admin/drive/status`   | Admin | Drive connection status  |

### Drive Health

**Router:** `admin_drive_health.py` | **Prefix:** `/api/admin/drive`

| Method | Path                      | Auth  | Description                |
| ------ | ------------------------- | ----- | -------------------------- |
| GET    | `/api/admin/drive/health` | Admin | Drive service health check |

### Drive Setup & Refresh

**Routers:** `admin_drive_setup.py`, `admin_drive_refresh.py`

| Method | Path                       | Auth  | Description          |
| ------ | -------------------------- | ----- | -------------------- |
| POST   | `/api/admin/drive/setup`   | Admin | Initial Drive setup  |
| POST   | `/api/admin/drive/refresh` | Admin | Refresh Drive tokens |

---

## 14. Integrations — Zoho

**Router:** `admin_zoho_auth.py` | **Prefix:** `/api/admin/zoho`

| Method | Path                       | Auth  | Description            |
| ------ | -------------------------- | ----- | ---------------------- |
| GET    | `/api/admin/zoho/auth-url` | Admin | Zoho OAuth2 URL        |
| GET    | `/api/admin/zoho/callback` | Admin | Zoho OAuth2 callback   |
| GET    | `/api/admin/zoho/status`   | Admin | Zoho connection status |

---

## 15. Channels — Telegram

**Router:** `telegram.py` + `telegram_webhook.py` | **Prefix:** `/api/telegram`

| Method | Path                               | Auth                        | Description                 |
| ------ | ---------------------------------- | --------------------------- | --------------------------- |
| POST   | `/api/telegram/webhook`            | **PUBLIC** (webhook secret) | Telegram bot webhook        |
| GET    | `/api/telegram/conversations`      | Required                    | List Telegram conversations |
| GET    | `/api/telegram/conversations/{id}` | Required                    | Get conversation messages   |

---

## 16. Channels — WhatsApp

**Router:** `whatsapp_chat.py` + `whatsapp_conversations.py` | **Prefix:** `/api/whatsapp`

| Method | Path                          | Auth                        | Description                 |
| ------ | ----------------------------- | --------------------------- | --------------------------- |
| POST   | `/api/whatsapp/webhook`       | **PUBLIC** (webhook verify) | WhatsApp webhook            |
| GET    | `/api/whatsapp/conversations` | Required                    | List WhatsApp conversations |
| POST   | `/api/whatsapp/send`          | Required                    | Send WhatsApp message       |

---

## 17. Channels — Instagram

**Router:** `instagram_chat.py` | **Prefix:** `/api/instagram`

| Method | Path                     | Auth       | Description          |
| ------ | ------------------------ | ---------- | -------------------- |
| POST   | `/api/instagram/webhook` | **PUBLIC** | Instagram webhook    |
| GET    | `/api/instagram/webhook` | **PUBLIC** | Webhook verification |

---

## 18. Channels — Twitter/X

**Router:** `twitter.py` | **Prefix:** `/api/twitter`

| Method | Path                   | Auth       | Description      |
| ------ | ---------------------- | ---------- | ---------------- |
| POST   | `/api/twitter/webhook` | **PUBLIC** | Twitter webhook  |
| GET    | `/api/twitter/webhook` | **PUBLIC** | CRC verification |

---

## 19. Voice

**Router:** `voice.py` | **Prefix:** `/api/voice`

| Method | Path                    | Auth     | Description              |
| ------ | ----------------------- | -------- | ------------------------ |
| POST   | `/api/voice/transcribe` | Required | Transcribe audio to text |
| POST   | `/api/voice/synthesize` | Required | Text to speech           |

---

## 20. Article Composer

**Router:** `article_composer.py` | **Prefix:** `/api/articles`

| Method | Path                    | Auth     | Description             |
| ------ | ----------------------- | -------- | ----------------------- |
| POST   | `/api/articles/compose` | Required | Compose article with AI |
| POST   | `/api/articles/publish` | Admin    | Publish article         |
| GET    | `/api/articles`         | Required | List articles           |
| GET    | `/api/articles/{id}`    | Required | Get article             |

---

## 21. Autonomous Execution

**Router:** `autonomous_execution.py` | **Prefix:** `/api/autonomous`

| Method | Path                                 | Auth     | Description           |
| ------ | ------------------------------------ | -------- | --------------------- |
| POST   | `/api/autonomous/plan`               | Required | Create execution plan |
| POST   | `/api/autonomous/execute`            | Required | Execute plan          |
| GET    | `/api/autonomous/plans`              | Required | List plans            |
| GET    | `/api/autonomous/plans/{id}`         | Required | Get plan status       |
| POST   | `/api/autonomous/plans/{id}/approve` | Required | Approve plan step     |

---

## 22. Workflow Analytics

**Router:** `workflow_analytics.py` | **Prefix:** `/api/analytics/workflows`

| Method | Path                              | Auth  | Description                  |
| ------ | --------------------------------- | ----- | ---------------------------- |
| GET    | `/api/analytics/workflows`        | Admin | Workflow execution analytics |
| GET    | `/api/analytics/workflows/trends` | Admin | Workflow trends              |

---

## 23. Health & System

**Router:** `health.py` | **Prefix:** `/health` | **All PUBLIC**

| Method | Path                     | Auth       | Description                        |
| ------ | ------------------------ | ---------- | ---------------------------------- |
| GET    | `/health`                | **PUBLIC** | Basic health (Fly.io probe)        |
| GET    | `/health/detailed`       | **PUBLIC** | Full service status breakdown      |
| GET    | `/health/ready`          | **PUBLIC** | Readiness probe (503 if not ready) |
| GET    | `/health/live`           | **PUBLIC** | Liveness probe (always 200)        |
| GET    | `/health/metrics/qdrant` | **PUBLIC** | Qdrant operation metrics           |
| GET    | `/health/kg-stats`       | **PUBLIC** | Knowledge Graph statistics         |

### Prometheus Metrics

| Method | Path       | Auth       | Description                 |
| ------ | ---------- | ---------- | --------------------------- |
| GET    | `/metrics` | **PUBLIC** | Prometheus metrics endpoint |

---

## 24. Test & Debug Endpoints

> These endpoints exist for development/debugging. Some may be disabled in production.

| Router                   | Prefix                    | Description                  |
| ------------------------ | ------------------------- | ---------------------------- |
| `test_drive.py`          | `/api/test/drive`         | Google Drive test operations |
| `test_drive_create.py`   | `/api/test/drive-create`  | Drive folder creation test   |
| `test_invoice.py`        | `/api/test/invoice`       | Invoice generation test      |
| `test_invoice_debug.py`  | `/api/test/invoice-debug` | Invoice debug info           |
| `test_list_practices.py` | `/api/test/practices`     | Practice listing test        |
| `test_update_client.py`  | `/api/test/update-client` | Client update test           |
| `test_zoho_status.py`    | `/api/test/zoho`          | Zoho integration test        |

---

## Public Endpoints Summary

All endpoints NOT requiring authentication:

| Path Pattern                       | Reason                       |
| ---------------------------------- | ---------------------------- |
| `/health*`                         | Infrastructure health probes |
| `/metrics`                         | Prometheus scraping          |
| `/api/v1/kbli-notebook/*`          | Public KBLI search for SEO   |
| `/api/agentic-rag/stream`          | Chat widget on public site   |
| `/api/agent/health`                | Agent health check           |
| `/api/telegram/webhook`            | Telegram bot callbacks       |
| `/api/whatsapp/webhook`            | WhatsApp bot callbacks       |
| `/api/instagram/webhook`           | Instagram bot callbacks      |
| `/api/twitter/webhook`             | Twitter bot callbacks        |
| `/docs`, `/redoc`, `/openapi.json` | API documentation (dev)      |

---

## Error Response Format

All errors follow this structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "request_id": "uuid-correlation-id"
}
```

**Common HTTP status codes:**

- `401` — Missing or invalid authentication
- `403` — Insufficient permissions (RBAC)
- `404` — Resource not found
- `429` — Rate limit exceeded
- `500` — Internal server error
- `503` — Service initializing or unavailable
