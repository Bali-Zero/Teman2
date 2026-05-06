# SYMBIOSIS W2 — KG → Pro MCP Tool (Bridge A) Design Spec

**Date:** 2026-05-07
**Status:** Approved by Zero (2026-05-06)
**Worktree:** `.worktrees/symbiosis-W2/`
**Branch:** `feat/symbiosis-W2-kg-zantara-bridge-2026-05-07`
**Scope:** Bridge A only. Bridge B (Fly→Mini for end-user Zantara) is a future, separate PR.

## 1. Goal

Expose the `mata-garuda` SQLite Knowledge Graph (Mini, `~/.agent/mata-garuda/kg.db`,
**409 entities + 1549 relations + 622 observations** verified 2026-05-06) as a
local MCP tool callable by Pro-side organs (Claude Code stdio, OpenClaw,
Cowork). Result: when an internal investigation asks *"who/what does the
mata-garuda KG know about Imigrasi?"* the caller gets entity metadata,
neighbour names, and source URLs back. **No OSINT raw content leaves
mata-garuda.**

## 2. Non-Goals

- **Not** exposing this tool to Fly.io / Vercel / cloud / frontend. The HTTP
  surface binds Tailscale interface only on Mini.
- **Not** giving end-user Zantara on Fly access — that's Bridge B, scoped
  separately (would need Tailscale subnet router + reverse proxy auth).
- **Not** writing into the KG. This bridge is read-only.
- **Not** semantic / vector search. Substring + exact-name lookup only.

## 3. Doctrine Justification

**SYMBIOSIS.md Pilastro 3 Condivisione** allows operative knowledge sharing
between organs: *"le skill e gli insight condivisi contengono conoscenza
operativa, mai dati OSINT"*. The identity of an entity *mentioned* in the
KG is operative knowledge; the raw article body is OSINT.

**Override of `apps/mata-garuda/CLAUDE.md` §1 OSINT-blindato** is added in
the same PR as a new §1.4 "Eccezione Pillar 3 SYMBIOSIS — KG metadata
sharing" with verbatim text approved by Zero (see Task 2 in plan). The
doctrine commit lands BEFORE any code commit.

## 4. Architecture

```
┌──────────────────────────── Mini (100.93.236.6) ───────────────────────────┐
│                                                                             │
│  ~/.agent/mata-garuda/kg.db  (SQLite, 409e/1549r/622o)                      │
│           ▲ read-only                                                       │
│           │                                                                 │
│  apps/mata-garuda/mata_garuda/api/kg_query.py  (stdlib http.server)         │
│           │                                                                 │
│           bind 100.93.236.6:8990 (Tailscale interface only,                 │
│           NOT 0.0.0.0, NOT 127.0.0.1)                                       │
│                                                                             │
│  ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist (KeepAlive=true)  │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ HTTP/1.1 over Tailscale
                                  │ (no TLS — tailnet WireGuard provides)
                                  ▼
┌─────────────────────────────── Pro (Nuzantara) ────────────────────────────┐
│                                                                             │
│  apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py                         │
│  - register(mcp, _call, _call_safe) per existing pattern                    │
│  - 3 tools: kg_intel_search, kg_intel_entity, kg_intel_health               │
│  - httpx.AsyncClient base_url=http://100.93.236.6:8990, timeout=3s          │
│  - On Tailscale flap: return {"error": "intelligence layer unavailable"}    │
│                                                                             │
│  Consumers (stdio MCP): Claude Code, OpenClaw, Cowork                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. Mini-side HTTP API

Implementation: `apps/mata-garuda/mata_garuda/api/kg_query.py`. Uses
`http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler` from stdlib —
**no new runtime dependency** (mata-garuda §1.3 stack-minimale rule:
runtime deps are pydantic-only).

### Bind address

`KG_API_BIND` env var, defaults to `100.93.236.6` (Mini's Tailscale v4).
The plist sets it explicitly. **Hardcoded refusal** to bind `0.0.0.0` —
the server checks the bind string at startup and exits non-zero if it
matches `0.0.0.0`, `::`, or any non-loopback non-tailnet address. (For
local CI tests we bind `127.0.0.1`, which is allowed; the production
guardrail rejects only the wildcard binds.)

### Endpoints

#### `GET /health`

```json
{
  "ok": true,
  "kg_path": "/Users/nuzantara/.agent/mata-garuda/kg.db",
  "entities_count": 409,
  "relations_count": 1549,
  "observations_count": 622,
  "schema_ok": true
}
```

`schema_ok=false` if any of the three tables is missing — fail-soft, the
server still starts (Legge 4 graceful degradation).

#### `GET /kg/search?q={substring}&limit={int}`

Returns up to `limit` (default 20, hard-capped at 100) entities whose
`canonical_name` matches the substring case-insensitively.

```json
{
  "query": "imigrasi",
  "limit": 20,
  "results": [
    {
      "name": "Direktorat Jenderal Imigrasi",
      "type": "organizations",
      "source_count": 17,
      "last_seen": "2026-04-30T12:14:09+00:00"
    },
    ...
  ]
}
```

**Forbidden in response:** observation values, evidence URLs, neighbours.
Search is a hit-list only; detail comes from `/kg/entity/...`.

#### `GET /kg/entity/{name}?type={persons|organizations|locations|laws|topics}`

```json
{
  "name": "Direktorat Jenderal Imigrasi",
  "type": "organizations",
  "source_count": 17,
  "first_seen": "2026-03-12T08:11:02+00:00",
  "last_seen": "2026-04-30T12:14:09+00:00",
  "neighbor_names": [
    {"name": "KITAS Investor", "type": "topics",  "predicate": "regulates",   "confidence": 0.78},
    {"name": "Permenkumham 22/2023", "type": "laws", "predicate": "issued_by", "confidence": 0.85}
  ],
  "observation_count": 11,
  "observations": [
    {"observed_at": "2026-04-30T12:14:09+00:00", "source_url": "https://imigrasi.go.id/2026/04/30/announcement"},
    {"observed_at": "2026-04-21T03:00:00+00:00", "source_url": "https://kemenkumham.go.id/news/12345"}
  ]
}
```

`type` query param is **required** because `(type, canonical_name)` is the
KG's UNIQUE constraint — names are not globally unique.

`name` is URL-decoded (path component); special chars allowed except `/`
(rejected by the routing regex).

`neighbor_names` is hard-capped at 50 (predicate/confidence sorted, highest
first). Existing `KnowledgeGraph.neighbors()` already orders this way.

`observations` list contains only `observed_at` + `source_url`. The `value`
field of `kg_observations` (which can contain headline/body excerpts —
OSINT raw — see kg_sqlite.py:99) is **never returned**. `observation_count`
gives the total including filtered ones.

### Forbidden in any payload

- `observation.value` (may contain title/snippet OSINT body)
- `evidence_url` from `kg_relations` (it points at the source article, but
  per Zero's payload spec only `observation.source_url` is returned —
  evidence_url is treated as OSINT until explicit broader allowance)
- Anything from `aliases_json` (alias-set is OSINT-derived; would let a
  consumer infer source articles by reverse-search)
- Any field named `content`, `title`, `body`, `excerpt`, `summary`
- `field` (the literal column name from `kg_observations.field` — its
  value is the OSINT field-tag like `headline`/`mention`, suppressed
  defense-in-depth)

A unit test enforces this by asserting that JSON-encoded responses contain
none of the forbidden keys at any depth.

### Error responses

All errors return JSON `{"error": "<code>", "detail": "<human msg>"}` with
a 4xx/5xx status. Codes: `bad_request`, `not_found`, `entity_not_found`,
`internal_error`, `kg_unavailable`.

### Concurrency / SQLite

Single `KnowledgeGraph` instance per worker thread; SQLite WAL mode is
already enabled in `kg_sqlite.py:53`. Each handler opens a short-lived
read-only connection (`sqlite3.connect("file:...?mode=ro", uri=True)`) so
the writer (`kg_linker.py`) never blocks on us.

### Logging

Standard `logging` to `~/logs/mata-garuda-kg-api.log`. Audit-line per
request: `level=INFO, ts, remote_addr, method, path, query (truncated 80c),
status, duration_ms`. **Body never logged.**

## 6. LaunchAgent (Mini-side daemon)

`~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist`

- `KeepAlive=true` (per VADEMECUM §11 + cicatrix structural-3 rule)
- `RunAtLoad=true`
- `EnvironmentVariables`: `KG_API_BIND=100.93.236.6`, `KG_API_PORT=8990`
- `StandardOutPath=$HOME/logs/mata-garuda-kg-api.log`
- `StandardErrorPath=$HOME/logs/mata-garuda-kg-api.err`
- `ProgramArguments`: `["/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/.venv/bin/python", "-m", "mata_garuda.api.kg_query"]`
- File mode `0444` (per cicatrix structural-3, plist tampering trap)
- No `ANTHROPIC_API_KEY` — the bridge runs zero LLM calls (mata-garuda §1.0).

Bridge script (`~/scripts/mata-garuda-kg-api.sh`) is the launchd entry
point so we keep the venv-python pattern from `~/scripts/mata-garuda-watcher.sh`
(TCC-bypass via adhoc-signed binary). The plist points at the bridge,
the bridge `exec`s `$VENV_PY -m mata_garuda.api.kg_query`.

## 7. Pro-side MCP tool

`apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py`. Same `register(mcp,
_call, _call_safe)` shape as `tools/intel.py:8`. Three tools:

```
kg_intel_search(query: str, limit: int = 20) -> dict
kg_intel_entity(name: str, entity_type: str) -> dict
kg_intel_health() -> dict
```

### HTTP client

Module-level singleton `httpx.AsyncClient(base_url="http://100.93.236.6:8990",
timeout=3.0)`, env-overridable via `MATA_GARUDA_KG_BASE_URL`. Same
stale-connection retry pattern as `server.py:85` (Mini reboots / Tailscale
flap). On `httpx.ConnectError` / `TimeoutException`, return:

```json
{"error": "kg_unavailable", "detail": "Mata Garuda KG bridge unreachable (Tailscale flap or daemon down)"}
```

— a regular dict with `error` set, NOT a raised exception. AI consumers
can branch on the field.

### Auth gating

Decorate with `@require_role("admin")` (existing `nuzantara_mcp.auth`
helper). Per Zero: this tool is admin-only because the consumer pool is
internal investigators, not Bali Zero clients. If the role taxonomy ever
adds an `intel_analyst` role, switch to that.

### Citation output

Tool docstring documents that AI consumers MUST cite `observation.source_url`
when they relay any KG fact downstream. Citation format is the consumer's
problem — this tool just returns the URL list.

## 8. Test plan

### Mini-side (TDD against `kg_query.py`)

`apps/mata-garuda/tests/api/test_kg_query.py` (new). Uses `pytest` +
`http.client` against an in-process server bound to `127.0.0.1:0` (random
free port) with a fixture `kg_db_with_seed_data` that creates a temp
SQLite KG and inserts 3 entities + 2 relations + 4 observations.

Tests:

| ID | Behaviour |
|----|-----------|
| T1 | `/health` returns `ok=true` + correct counts when KG is seeded |
| T2 | `/health` returns `schema_ok=false` if a table is dropped (fail-soft) |
| T3 | `/kg/search?q=imigrasi` returns substring matches, capped at limit |
| T4 | `/kg/search?q=` (empty) returns 400 bad_request |
| T5 | `/kg/search?limit=999` is hard-capped at 100 in response |
| T6 | `/kg/entity/Imigrasi?type=organizations` returns full record minus forbidden fields |
| T7 | `/kg/entity/Imigrasi?type=` returns 400 bad_request (type required) |
| T8 | `/kg/entity/Unknown?type=persons` returns 404 entity_not_found |
| T9 | Response body contains NONE of `value`, `evidence_url`, `aliases_json`, `aliases`, `content`, `title`, `body`, `excerpt`, `summary`, `field` (deep walk) |
| T10 | Server refuses to bind `0.0.0.0` (startup-time guardrail) |
| T11 | Concurrent reads don't deadlock (10 threads × 50 requests, all 200) |
| T12 | Path traversal `/kg/entity/..%2Fetc%2Fpasswd?type=persons` is rejected (400 bad_request) |

### Pro-side (TDD against `kg_intel.py`)

`apps/nuzantara-mcp/tests/test_tools_kg_intel.py` (new). Uses `pytest-asyncio`
+ `httpx.MockTransport` per existing `test_http_helpers.py` pattern.

Tests:

| ID | Behaviour |
|----|-----------|
| P1 | `kg_intel_search("imigrasi")` returns dict with `results` list |
| P2 | `kg_intel_entity("X", "organizations")` returns parsed entity record |
| P3 | `kg_intel_health()` returns counts |
| P4 | On `httpx.ConnectError`, returns `{"error": "kg_unavailable", ...}` (no raise) |
| P5 | On `httpx.TimeoutException`, returns `{"error": "kg_unavailable", ...}` |
| P6 | On HTTP 404, returns `{"error": "entity_not_found", ...}` |
| P7 | Tool decorators include `@require_role("admin")` |
| P8 | Module imports successfully (server-imports regression test) |

## 9. Tri-LLM Review

Pre-merge requirement. Threshold relaxed to **≥2/3 explicit approvals**
(per Wave-2 Pro 2026-04-29 capacity-exhaustion pattern, MOS lesson).

Stack:

1. **DeepSeek R1** (paid API, ~$0.01) — architectural review, single-point-of-failure check.
2. **NotebookLM NB-1** — backend-rag MCP architecture ground-truth (only if `mcp__notebooklm-mcp__*` server is wired; otherwise skip and note in PR body).
3. **Codex / Gemini 3.1 Pro** — opportunistic; skip if quota exhausted.

PR body must include the three review excerpts (or quota-exhausted
notes), key concerns flagged, and how each was addressed (or explicitly
deferred with reason).

## 10. Latency Benchmark

Required in PR body: 100 calls of `/kg/search?q=imigrasi` from Pro to Mini
via Tailscale. Report p50/p95/p99 in milliseconds. **Pass threshold: p99 <
800ms.** Run with `apps/mata-garuda/scripts/bench_kg_api.py` (new
single-file script — uses stdlib `urllib` to avoid adding a benchmarking
dep).

## 11. Security Checklist (PR body)

- [ ] Mini server refuses `0.0.0.0` bind (T10)
- [ ] No OSINT body fields in any response (T9)
- [ ] Tool returns graceful degradation dict on flap, never raises (P4/P5)
- [ ] Tool decorated `@require_role("admin")` (P7)
- [ ] Plist file mode `0444`, secrets file separate
- [ ] Daemon log does NOT log request bodies, only path+query+status
- [ ] Path traversal rejected (T12)
- [ ] `~/.agent/mata-garuda/kg.db` opened read-only (`mode=ro` URI)
- [ ] Tailscale auth = the only network gate (no app-level token; the
      daemon trusts whoever can reach it on tailnet, which is Pro+Mini
      only per `reference_tailnet_topology.md`)

## 12. Files to Create / Modify

### New files (Mini-side, in monorepo)

- `apps/mata-garuda/mata_garuda/api/__init__.py`
- `apps/mata-garuda/mata_garuda/api/kg_query.py`
- `apps/mata-garuda/tests/api/__init__.py`
- `apps/mata-garuda/tests/api/test_kg_query.py`
- `apps/mata-garuda/scripts/bench_kg_api.py`
- `infra/launchagents/com.matagaruda.kg-query-api.plist`
  (canonical copy in repo; deployed copy in `~/Library/LaunchAgents/` is
  installed via the existing `infra/launchagents/install.sh` pattern)
- `scripts/mata-garuda-kg-api.sh` (bridge for launchd, mirrors
  `mata-garuda-watcher.sh`)

### New files (Pro-side, in monorepo)

- `apps/nuzantara-mcp/nuzantara_mcp/tools/kg_intel.py`
- `apps/nuzantara-mcp/tests/test_tools_kg_intel.py`

### Modified files

- `apps/mata-garuda/CLAUDE.md` — append §1.4 doctrine exception (Zero's
  approved verbatim text, in commit 1)
- `apps/nuzantara-mcp/nuzantara_mcp/server.py` — add 2 lines: import
  `register as register_kg_intel`, call `register_kg_intel(mcp, _call,
  _call_safe)` (in commit 5 with the tool itself)

### NOT modified

- `apps/mata-garuda/mata_garuda/runtime/kg_sqlite.py` — read-only consumer
- `apps/backend-rag/**` — Bridge B is out of scope
- `fly.toml` — out of scope

## 13. Commit Sequence

The PR has 6 logical commits:

1. **`docs(mata-garuda): add §1.4 SYMBIOSIS Pillar 3 doctrine exception for KG metadata sharing`**
   — Zero's approved verbatim §1.4 in `apps/mata-garuda/CLAUDE.md`. ZERO code change. Establishes legitimacy before any export-shaped code lands.

2. **`feat(mata-garuda): add kg_query HTTP API (Mini-side, Tailscale-only bind)`**
   — `kg_query.py` + `tests/api/test_kg_query.py` + bench script. Tests T1-T12 all green.

3. **`feat(mata-garuda): launchd plist + bridge script for kg-query-api daemon`**
   — Plist + bridge. Manual install instructions in commit body. Plist mode 0444.

4. **`feat(nuzantara-mcp): add kg_intel tool (3 tools, role=admin)`**
   — `kg_intel.py` + `tests/test_tools_kg_intel.py`. Tests P1-P8 all green. NOT yet wired in `server.py`.

5. **`feat(nuzantara-mcp): wire kg_intel into MCP server registration`**
   — 2-line patch on `server.py` + assertion test in `test_server_imports.py` covering registration.

6. **`docs(symbiosis): add W2 design + plan + post-merge ops notes`**
   — Spec + plan + a short `docs/symbiosis/W2-kg-bridge-runbook.md` covering install/restart/logs/manual-test for Mini daemon. Also contains the latency benchmark output and tri-LLM review excerpts.

## 14. Open Questions / Risks

1. **Tailscale bind reliability** — Tailscale's IP can change after `tailscale logout/login`. Mitigation: daemon binds the configured IP and exits if `getaddrinfo` for `100.93.236.6` doesn't match a local interface; LaunchAgent restarts → it re-checks → operator notices. Alternative `tailscale ip` pre-flight in bridge script if needed.
2. **kg.db corruption during read-only access** — Read-only URI mode prevents writer-side damage, but if writer (`kg_linker.py`) updates schema, our `schema_ok` check must not fail loudly. Test T2 covers fail-soft.
3. **Mini reboot during long Pro session** — `kg_intel.health()` returning `kg_unavailable` is the canonical way for the Pro caller to know. No watchdog needed in scope.
4. **NB-1 query auth** — if `mcp__notebooklm-mcp__*` is not loaded in this conversation's tool set, NB-1 review is skipped. The 2/3 relaxed threshold accommodates this.
5. **Future Bridge B** — when Fly needs access, options are: (a) Tailscale subnet router on Mini exposing 8990 to Fly (heavy infra); (b) backend-rag adds an internal endpoint that proxies to Mini (still requires Fly→Mini reachability). Decision deferred.

---

End of design spec. Implementation follows in
`docs/superpowers/plans/2026-05-07-symbiosis-w2-kg-mcp-bridge.md`.
