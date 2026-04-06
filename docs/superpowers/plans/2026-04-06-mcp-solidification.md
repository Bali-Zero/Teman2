# MCP Server Solidification Plan

**Date:** 2026-04-06
**Machine:** Air (analysis) → Pro (implementation)
**Status:** FASE 4 ✅ — Validato da NB-1 Oracle con 5 correzioni integrate

---

## NB-1 Oracle Corrections (integrated)

1. **Naga → update `server_lite.py` EXCLUDED** — Antigravity 100-tool limit
2. **P3+P4 must ship together** — persistent HTTP needs retry because Fly.io `auto_stop` corrupts keep-alive sockets
3. **Dedup → content hash** not just client_id:channel — use `sha256(content)` pattern from `channel_optimizations.py`, add TTL eviction to avoid OOM
4. **Chain tests → mock-only** (confirmed) — integration tests live in backend-rag
5. **FATAL: `confirm=False` in chains** — chains run unattended via cron at 03:00. `confirm=True` would hang forever. Only use `confirm=True` for tools exposed to generative agents (Claude Code, Aider)

---

## Executive Summary

Studio profondo del server MCP (109 tool, 24 moduli, 8 chain, 10 prompt, 5 resource) ha rivelato **8 problemi** ranked per impatto produzione. Il server funziona per il day-to-day ma ha debiti tecnici nei workflow chain (notification spam, duplicati, zero test) e nell'infrastruttura (HTTP client per-request, resilience.py dead code).

**Costo totale fix:** ~6.5 ore | **Sprint 1:** ~2.5h (client-facing + infra) | **Sprint 2:** ~4h (fondamenta)

---

## Problems Found (ranked by production impact)

### TIER 1 — Bug attivi ora

| ID      | Problema                                                                 | Impatto                        | Effort |
| ------- | ------------------------------------------------------------------------ | ------------------------------ | ------ |
| **P0**  | `register_prime` duplicato in server.py (L112+118 import, L157+163 call) | Basso (overwrite identico)     | 5 min  |
| **P0b** | `naga.py` (3 tool) mai registrato in server.py                           | Medio (tool invisibili)        | 2 min  |
| **P8**  | `playwright` import a livello modulo in google_bridge.py L6              | Medio (crash startup se manca) | 2 min  |

### TIER 2 — Rischi latenti

| ID     | Problema                                                                       | Impatto                         | Effort |
| ------ | ------------------------------------------------------------------------------ | ------------------------------- | ------ |
| **P1** | Chain notification spam — no dedup, WhatsApp/email ripetuti ogni run           | **ALTO** (client blocca WA)     | 30 min |
| **P2** | 4/8 chain non idempotenti — creano duplicati se re-run                         | **ALTO** (record duplicati CRM) | 1h     |
| **P3** | HTTP client per-request — no connection pooling, TCP+TLS ogni chiamata         | Medio (3-7s overhead/chain)     | 15 min |
| **P4** | `resilience.py` dead code — retry+CB+irreversibility implementati ma mai usati | Medio (nessuna protezione)      | 45 min |

### TIER 3 — Qualità

| ID     | Problema                                                       | Impatto                        | Effort |
| ------ | -------------------------------------------------------------- | ------------------------------ | ------ |
| **P5** | 70% tool usa `_call()` che raise — errori generici per AI      | Medio (AI non recupera)        | 30 min |
| **P6** | 0% chain test coverage — il codice più rischioso non è testato | **ALTO** (no safety net)       | 3h     |
| **P7** | MCP test non in CI — 164 test solo locali                      | Medio (regressioni silenziose) | 15 min |

---

## Sprint 1 — Fix Client-Facing (~2h)

### S1.1: Fix P0 — Double prime registration + naga morto (5 min)

**File:** `server.py`

```python
# REMOVE duplicate (L117-118):
# --- Prime Nexus ---
# from nuzantara_mcp.tools.prime import register as register_prime

# REMOVE duplicate (L162-163):
# Prime Nexus geospatial intelligence
# register_prime(mcp, _call, _call_safe)

# ADD naga registration after federation (L115):
from nuzantara_mcp.tools.naga import register as register_naga

# ADD naga call after federation (L160):
register_naga(mcp, _call, _call_safe)
```

### S1.2: Fix P8 — Lazy playwright import (2 min)

**File:** `tools/google_bridge.py`

```python
# BEFORE (L6):
from playwright.async_api import async_playwright

# AFTER: move inside function body
async def upload_to_notebooklm(...):
    from playwright.async_api import async_playwright
    ...
```

### S1.3: Fix P3+P4 — Persistent HTTP client WITH retry (30 min)

**NB-1 correction:** P3 and P4 must ship together. Fly.io `auto_stop` corrupts keep-alive sockets — persistent client without retry = `RemoteProtocolError`.

**File:** `server.py`

```python
# Replace per-request client with persistent singleton + retry
_http_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client

async def _call(endpoint, method="GET", json=None, params=None, timeout=None):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
        headers["X-API-Key"] = API_KEY
    client = _get_client()
    try:
        resp = await client.request(
            method=method, url=endpoint, json=json, params=params,
            headers=headers, timeout=timeout or TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.RemoteProtocolError, httpx.ReadError):
        # Stale connection after Fly.io auto_stop — force new client + retry once
        global _http_client
        if _http_client and not _http_client.is_closed:
            await _http_client.aclose()
        _http_client = None
        client = _get_client()
        resp = await client.request(
            method=method, url=endpoint, json=json, params=params,
            headers=headers, timeout=timeout or TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
```

### S1.4: Fix P1 — Notification dedup with content hash (30 min)

**NB-1 correction:** Use content hash, not just client_id:channel. Pattern from `channel_optimizations.py`. Add TTL eviction to prevent OOM.

**File:** `workflows/chains.py`

```python
# Add at top of file, after imports:
import time
import hashlib

# In-memory dedup with content hash — prevents OOM via LRU eviction
_notification_log: dict[str, float] = {}
_DEDUP_WINDOW = 86400  # 24 hours
_MAX_DEDUP_ENTRIES = 5000  # LRU cap to prevent OOM

def _should_notify(client_id: str | int, channel: str, content: str) -> bool:
    """Returns True if this exact message hasn't been sent to this client on this channel in 24h."""
    content_hash = hashlib.sha256(f"{client_id}:{channel}:{content}".encode()).hexdigest()[:16]
    now = time.time()
    # Evict stale entries (older than 48h) + LRU cap
    if len(_notification_log) > _MAX_DEDUP_ENTRIES:
        oldest = sorted(_notification_log.items(), key=lambda x: x[1])[:_MAX_DEDUP_ENTRIES // 2]
        for k, _ in oldest:
            del _notification_log[k]
    stale = [k for k, t in _notification_log.items() if now - t > _DEDUP_WINDOW * 2]
    for k in stale:
        del _notification_log[k]
    # Check dedup
    if content_hash in _notification_log and now - _notification_log[content_hash] < _DEDUP_WINDOW:
        return False
    _notification_log[content_hash] = now
    return True
```

Then wrap every WhatsApp/email/portal send in chains with:

```python
msg = f"URGENT: Your {doc_type} expires in {days} days..."
if _should_notify(client_id, "whatsapp", msg):
    await _call_safe("/api/whatsapp/send", ...)
```

### S1.5: Fix P2 — Idempotent chains (1h)

**chain_new_client_onboarding:** Add check-before-create:

```python
# Before creating client, check if email exists
existing = await _call_safe("/api/crm/clients/", params={"search": email, "limit": 1})
clients = existing.get("items") or existing.get("data") or []
if clients and isinstance(clients, list) and len(clients) > 0:
    client_id = clients[0].get("id")
    log.append({"step": "create_client", "status": "skipped", "detail": "client exists"})
else:
    # Create new client
    ...
```

**chain_journey_accelerator:** Add journey existence check:

```python
# Before creating journey, check if one exists for this client+type
existing = await _call_safe(f"/api/agents/journey/client/{client_id}")
journeys = existing if isinstance(existing, list) else existing.get("items", [])
has_same_type = any(j.get("journey_type") == journey_type for j in journeys if isinstance(j, dict))
if has_same_type:
    log.append({"step": "create_journey", "status": "skipped", "detail": "journey exists"})
else:
    # Create new journey
    ...
```

**chain_intel_pipeline:** Track composed articles:

```python
# Before composing, check if article already composed for this item
# Use staging item's source_url as dedup key
```

### S1.6: Fix P7 — MCP tests in CI (15 min)

**File:** `.github/workflows/tests.yml`

Add job:

```yaml
mcp-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install MCP dependencies
      run: |
        cd apps/nuzantara-mcp
        pip install -e ".[test]"
    - name: Run MCP tests
      run: |
        cd apps/nuzantara-mcp
        pytest tests/ -v --tb=short
```

---

## Sprint 2 — Fondamenta (~4.5h)

### S2.1: Fix P5 — Structured errors from \_call (30 min)

Option A (minimal): Keep `_call` as-is, add try/catch to the 15 most-used write tools.

Option B (systemic): Make `_call` return structured errors like `_call_safe`:

```python
async def _call(endpoint, method="GET", json=None, params=None, timeout=None):
    """Returns dict on success, raises on error (with structured message)."""
    try:
        ...
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        # Re-raise with actionable message
        raise Exception(f"{e.response.status_code}: {e.response.text[:200]}") from e
    except httpx.RequestError as e:
        raise Exception(f"Backend unreachable: {e}") from e
```

**Recommendation:** Option B — 30 min, all tools benefit, no tool code changes needed.

### S2.2: Fix P4 — Integrate resilience.py (45 min)

**NB-1 FATAL correction:** Chains run unattended via cron at 03:00. `confirm=True` would hang forever waiting for human input on stdio. **Chains MUST use `confirm=False`** (pre-approved by design). Only use `confirm=True` for tools exposed to generative agents.

Wire `call_with_retry` into chain write operations:

```python
from nuzantara_mcp.utils.resilience import call_with_retry

# In CHAINS (unattended, pre-approved):
await call_with_retry(_call_safe, "/api/whatsapp/send", method="POST", json=payload, confirm=False)

# In INTERACTIVE TOOLS (Claude Code, Aider):
await call_with_retry(_call_safe, "/api/whatsapp/send", method="POST", json=payload, confirm=True)
```

Also update `server_lite.py` EXCLUDED list to include naga tools (Antigravity 100-tool limit).

Only for write endpoints in chains. Read-only tools stay with plain `_call`.

### S2.3: Fix P6 — Chain test suite (3h)

Write 1 test per chain in `tests/test_chains.py`:

```python
@pytest.mark.asyncio
async def test_daily_ops_autopilot(mock_call_safe):
    mock_call_safe.side_effect = [
        {"items": [{"client_id": 1, "expiry_date": "2026-04-10", "severity": "critical"}]},  # expiry
        {"agents": [{"name": "main", "status": "active"}]},  # health
        {"items": []},  # intel
        {"data": {"total_hours": 40}},  # team hours
        {"completion_rate": 0.85},  # completion
        {},  # email send
        {},  # reflection save
    ]
    tools = _register_chains(mock_mcp, mock_call, mock_call_safe, 120)
    result = await tools["chain_daily_ops_autopilot"]()
    assert "reminders_sent" in str(result)
```

Priority: chains 2 (onboarding), 7 (compliance), 1 (daily ops), 3 (practice lifecycle).

---

## What NOT to Change

- **Tool descriptions:** well-written, AI selects correctly
- **Manual registration pattern:** explicit > magic
- **30s/120s timeouts:** adequate for Fly.io backend
- **server_lite.py exclusion list:** correct for Antigravity 100-tool limit
- **Tool count (109→112 with naga):** RBAC filtering reduces to 36-49 per role, acceptable
- **Chain NLM grounding:** optional, non-blocking, well-implemented

---

## Metriche Target Post-Solidificazione

| Metrica                  | Prima     | Dopo                                |
| ------------------------ | --------- | ----------------------------------- |
| Tool error handling      | 22%       | 100% (P5 fix)                       |
| Tool input validation    | 55%       | 55% (backend validates, acceptable) |
| Chain idempotency        | 50% (4/8) | 100% (P2 fix)                       |
| Chain notification dedup | 0%        | 100% (P1 fix)                       |
| Test coverage tool       | 48%       | 48% (no new tool tests needed)      |
| Test coverage chain      | 0%        | 100% (P6 fix)                       |
| Tests in CI              | No        | Yes (P7 fix)                        |
| HTTP connection pooling  | No        | Yes (P3 fix)                        |
| Resilience integration   | 0%        | Chain writes only (P4 fix)          |

---

## Implementation Order

```
DO NOW (9 min) ✅ DONE:
  P0  → remove double prime, register naga
  P0b → update server_lite.py EXCLUDED (naga)
  P8  → lazy playwright import

SPRINT 1 (~2.5h, same day):
  P3+P4 → persistent HTTP client WITH retry (NB-1: must ship together)
  P1    → notification dedup with content hash (NB-1: sha256 pattern)
  P2    → idempotent chains (check-before-create)
  P7    → MCP tests in CI

SPRINT 2 (~4h, next day):
  P5  → structured errors from _call
  P4b → wire resilience.py into chains (confirm=False! NB-1 FATAL)
  P6  → chain test suite, mock-only (NB-1: confirmed)
```

---

## Validation Required

Submit to NB-1 Oracle for validation:

1. Impatto su Claude Code e OpenClaw (109→112 tool)
2. Backward compatibility del persistent HTTP client
3. Dedup window 24h — giusto per tutti i use case?
4. Chain test strategy — mock-only vs integration?
