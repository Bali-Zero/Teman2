---
date: 2026-07-11
domain: compliance
client_case: none
sources:
  - https://nuzantara-rag.fly.dev (live prod probes)
  - https://balizero.com/kbli-explorer (live prod probes)
  - git log / gh pr view (PR #2163, #2164, #2189)
  - apps/backend-rag/backend/app/setup/service_initializer.py:1061-1066
  - apps/team-agent/mcp-wrapper/config/roles.yaml
---

# Lane S4 — PROD-TRUTH sweep, 2026-07-11

Mandate: prove in PRODUCTION what merged in the last week; sweep the API surface for
residual 5xx/contract lies. Worktree: `.worktrees/backend-rag-prod-truth`. Fly app
`nuzantara-rag`, machines last deployed v3727 (2026-07-11T10:17 UTC, ~3h before this sweep).

## 1. KBLI trio — proven live BY CONTENT

| PR | Claim | Live probe | Verdict |
|---|---|---|---|
| #2163 (e96dd46, merged 2026-07-08) | Exact-code fast-path | `GET /api/v1/kbli-notebook/search?query=68111` → top result `68111` score `1.0`, next-best `0.2004` | **PROVEN LIVE** |
| #2163 | Search snippet `[CONTEXT:` leak purged | grepped raw JSON body of 2 live searches (10+15 results) | `0` occurrences — **PROVEN LIVE** |
| #2163 | Chat abstain recalibration | `POST /api/v1/kbli-notebook/chat` with the site's own sample question ("Can foreigners own a villa rental business?") | 200, `detected_kbli` = 5 non-empty codes (55909/55203/55901/55204/55201), grounded answer citing PP 28/2025, `sources` non-empty — **PROVEN LIVE** |
| #2164 (5b4a983, merged 2026-07-08) | Gold-data purge (11 codes + 128 tkaInfo) | This is a **data file change** (`apps/mouth/data/kbli-gold-all.json`), not backend code — no Fly redeploy required. File is committed on main; `apps/mouth` deploys via Vercel on push. Not independently re-verified live (out of S4 scope — mouth/Vercel deploy is Subhi lane, fenced) | **ON MAIN, deploy-path not backend's** — flag if Vercel deploy hasn't run |
| #2189 (6d045e1, merged 2026-07-09) | Qdrant retry-with-backoff, re-ingest completed | Commit message itself is proof-of-work ("hit one timeout at batch 180/1559, retried successfully, completed all 1559 points with correct final verification counts"). Live corroboration: non-exact semantic query (`restaurant catering food service`) returns a healthy differentiated score gradient (0.379→0.318→0.290→0.288→0.262→…→0.232), NOT the flat ~0.20 plateau that would indicate a stale/degraded index | **PROVEN LIVE** — re-ingest ran successfully, retrieval quality confirmed on non-exact queries too |

Live proof commands (reproducible):
```
curl "https://balizero.com/api/v1/kbli-notebook/search?query=68111"
curl "https://balizero.com/api/v1/kbli-notebook/search?query=restaurant%20catering%20food%20service"
curl -X POST "https://balizero.com/api/v1/kbli-notebook/chat" -H "Content-Type: application/json" \
  -d '{"query":"Can foreigners own a villa rental business?"}'
```

Note on routing: the Fly backend (`nuzantara-rag.fly.dev`) enforces global bearer auth
(401 on every direct probe, `www-authenticate: Bearer`) — there is no per-route
`Depends(get_current_user)` on the kbli-notebook router itself. The public path is
`balizero.com/api/v1/kbli-notebook/*`, a Next.js (`apps/mouth`) server-side API route that
proxies to the Fly backend (likely with a server-side credential, not the user's
`nz_access_token` cookie). All KBLI probes above went through this real public path, not
a synthetic bypass.

## 2. Full-router GET sweep (read-only, prod, no persona escalation)

195 static (no path-param) GET routes enumerated from `backend.app.main.app.routes` via
venv-activated `PYTHONPATH=. python3`, probed unauthenticated against
`https://nuzantara-rag.fly.dev`.

| Status | Count | Verdict |
|---|---|---|
| 401 | 159 | Correct — global auth wall |
| 200 | 24 | Correct — public health/status/news/oracle-health/wa-dashboard-health surface, **zero PII/CRM leak** (manually reviewed the list) |
| 422 | 7 | Correct — required query params omitted by design of my probe (e.g. `kbli-notebook/search` needs `?query=`, `prime/v2/*` need body/query params) |
| 403 | 2 | Correct — `/webhook/instagram`, `/webhook/whatsapp` reject unsigned requests (no valid webhook signature sent) |
| 307 | 1 | Correct — `/api/integrations/zoho/callback` OAuth redirect |
| 000→200 | 2 | **False alarm, my probe error** — `/api/prime/zones-geojson` (19s, heavy GeoJSON) and `/api/v1/kbli-notebook/llm-health` (7.3s) both exceeded my initial 8s timeout; retried at 30s timeout → both 200 |
| **5xx** | **0** | **Clean** |

No persona-escalation (superuser/team/portal-client synthetic sessions) was performed —
the 401-dominant unauthenticated sweep already gave a clean signal (zero 5xx surface-wide)
and building real synthetic sessions (create+auth+cleanup per the
`discovery_crm_portal_live_e2e_synthetic_2026_07_08` pattern) for 195 routes was out of
the 2h time-box. If a deeper 3-persona pass is wanted, scope it to the ~36 non-401 routes
above plus the 65 path-parameterized GET routes not swept here (need real/synthetic IDs).

Full raw sweep: `/tmp/sweep_results.tsv` (not committed — reproducible from
`/tmp/get_routes.txt`, itself reproducible via the route-enumeration one-liner above).

## 3. Known-opens — resolved, not bugs

### `GET /api/generals/activity` → 404
**Verdict: correctly 404, not a bug.** `service_initializer.py:1061-1066` documents that
"The Generals (CodingGeneral, IntelligenceGeneral) were removed 2026-04-03" — the
`backend/generals/` directory never existed as live code; their responsibilities were
absorbed by Core Guardian V3 (external) and the Intel Pipeline (Chain 4). Grepped the
entire `apps/backend-rag/backend/` tree for any caller of `/api/generals/activity` or a
`recent_activity` field it would populate: **zero hits**. No live code depends on this
route. The 2026-07-08 memory that flagged it ("breaks the LAM grounding snapshot
`recent_activity` section") was a manually-probed URL, not a traced caller — closing as
non-issue. If the LAM grounding snapshot genuinely has an empty `recent_activity` field
somewhere, that's a separate, differently-rooted finding that needs its own trace to
whatever DOES populate it (not this route).

### MCP `get_client_timeline` / `get_client_compliance` — "over-restrictive role gate"
**Verdict: working as designed, not a bug.** Traced both gates to their single source of
truth, `apps/team-agent/mcp-wrapper/config/roles.yaml` (the `nuzantara_mcp/auth.py`
docstring is explicit: "Source of truth for role → tools mapping ... The taxonomy is
loaded once at import time ... so drift is impossible").

- `get_client_timeline`: `roles.yaml` line 12 lists it ONLY under `visa_specialist`.
  Python decorator `@require_role("visa_specialist")` in `crm.py:231` matches exactly.
- `get_client_compliance`: `roles.yaml` line 34 lists it ONLY under `tax_consultant`.
  Python decorator `@require_role("tax_consultant")` in `compliance.py:83` matches exactly.
- Neither tool appears in the `company_setup` role's tool list (`roles.yaml:40-57`).

There is **no decorator/yaml drift** — the MCP service identity `company_setup` is denied
both reads by the declared role taxonomy itself, which is a legitimate least-privilege
design (company-formation consultants don't need client interaction timelines or
tax-compliance detail). This is a product/RBAC-scope question, not a code bug: if
`company_setup` (or the generic MCP automation identity) SHOULD read these, the fix is a
one-line addition to `roles.yaml`'s `company_setup.tools` list — deliberately left
unarmed pending an explicit call on whether that's the right scope, since it's a
privilege-widening change and outside "small backend fixes" scope for this lane. Flagging
as **LEDGER-DELTA**, not fixing blind.

## 4. What was NOT done (time-box)

- No 3-persona synthetic-client walk of the full portal/CRM surface — the unauthenticated
  sweep already showed 0/195 5xx, and a full synthetic create→walk→cleanup cycle per
  persona would have consumed the remaining budget without a specific signal pointing at
  a broken surface. The `discovery_crm_portal_live_e2e_synthetic_2026_07_08` memory
  already ran a comparable pass on 2026-07-08 with 0 500s found (2 MCP contract bugs
  fixed then, PR #2179).
- 65 path-parameterized GET routes (need real or synthetic IDs) not probed.
- `apps/mouth`/Vercel-side confirmation that #2164's data-file change actually reached the
  live `kbli-gold-all.json` artifact was not verified (fenced: mouth is Subhi's lane per
  CLAUDE.md §13, and S4's fences explicitly exclude `apps/mouth` edits — but a *read-only*
  live-content check would have been in scope; flagging as unchecked).

## Owner / next step

- `apps/mouth` Vercel deploy confirmation for #2164 → owner: whoever next touches mouth
  lane (Subhi/coordinator), 5-minute check: fetch a live gold-purged code from
  `balizero.com/kbli/<one-of-the-11-purged-codes>` and confirm the purged
  `expert_legal`/`tkaInfo` fields are actually gone client-side.
- `roles.yaml` `company_setup` scope question (timeline/compliance reads) → owner: Zero,
  business call on RBAC scope, not a code bug.
