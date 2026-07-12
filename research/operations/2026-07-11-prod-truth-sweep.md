---
date: 2026-07-11
domain: compliance
client_case: none
adversarial_review: gpt-5.5
sources:
  - https://nuzantara-rag.fly.dev (live prod probes)
  - https://balizero.com/kbli-explorer (live prod probes)
  - git log / gh pr view (PR #2163, #2164, #2189)
  - apps/backend-rag/backend/app/setup/service_initializer.py:1061-1066
  - apps/team-agent/mcp-wrapper/config/roles.yaml
  - apps/nuzantara-mcp/nuzantara_mcp/auth.py
  - apps/nuzantara-mcp/nuzantara_mcp/workflows/heartbeat.py
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
| #2189 (6d045e1, merged 2026-07-09) | Qdrant retry-with-backoff, re-ingest completed | Commit message is proof-of-work only ("hit one timeout at batch 180/1559, retried successfully, completed all 1559 points with correct final verification counts") — this sweep did NOT independently re-run `verify_collection()` or query the Qdrant collection's point count directly. Live corroboration retained: non-exact semantic query (`restaurant catering food service`) returns a healthy differentiated score gradient (0.379→0.318→0.290→0.288→0.262→…→0.232), NOT the flat ~0.20 plateau that would indicate a stale/degraded index | **PARTIALLY CORROBORATED** — retrieval quality on non-exact queries is consistent with a healthy re-ingested index, but full cardinality (1,559/1,559 points) and the retry execution itself are supported only by the commit message, not independently re-verified this sweep |

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
| 200 | 24 | Correct — public health/status/news/oracle-health/wa-dashboard-health surface. The 24 route **paths and status codes** were manually reviewed and match an expected public/health-check profile by name; **response bodies were not inspected for PII/CRM content** — this is a scope-appropriate check, not a body-level leakage audit |
| 422 | 7 | Correct — required query params omitted by design of my probe (e.g. `kbli-notebook/search` needs `?query=`, `prime/v2/*` need body/query params) |
| 403 | 2 | Correct — `/webhook/instagram`, `/webhook/whatsapp` reject unsigned requests (no valid webhook signature sent) |
| 307 | 1 | Correct — `/api/integrations/zoho/callback` OAuth redirect |
| 000→200 | 2 | **False alarm, my probe error** — `/api/prime/zones-geojson` (19s, heavy GeoJSON) and `/api/v1/kbli-notebook/llm-health` (7.3s) both exceeded my initial 8s timeout; retried at 30s timeout → both 200 |
| **5xx** | **0** | **Clean, scoped** |

**Scope of the "0/195 5xx" claim (corrected):** this is 0/195 on the static (no path-param)
GET surface probed *unauthenticated*. Of the 195, 159 (81%) never reached authenticated/
protected route logic at all — they were stopped at the global 401 auth wall before any
handler code ran, so this sweep proves nothing about 5xx behavior past authentication for
those 159 routes. Only the 24 `200` + 7 `422` + 2 `403` + 1 `307` + 2 timeout-then-`200`
routes (36 total) actually exercised handler logic and are covered by the "clean" verdict.
Additionally, 65 path-parameterized GET routes and all non-GET (POST/PUT/PATCH/DELETE)
routes were excluded entirely — not counted in the 195 and not probed by this sweep.
**Corrected verdict: 0/36 routes that executed past the auth wall returned 5xx; the auth-
walled 159 are reachable-but-unverified-past-auth, not clean-by-this-sweep.**

No persona-escalation (superuser/team/portal-client synthetic sessions) was performed —
building real synthetic sessions (create+auth+cleanup per the
`discovery_crm_portal_live_e2e_synthetic_2026_07_08` pattern) for 195 routes was out of
the 2h time-box. If a deeper 3-persona pass is wanted, scope it to the 159 auth-walled
routes (unverified past auth) plus the ~36 non-401 routes above plus the 65 path-
parameterized GET routes not swept here (need real/synthetic IDs).

Full raw sweep: `/tmp/sweep_results.tsv` (not committed — reproducible from
`/tmp/get_routes.txt`, itself reproducible via the route-enumeration one-liner above).

## 3. Known-opens — resolved, not bugs

### `GET /api/generals/activity` → 404
**Verdict: 404 confirmed, but the "zero callers" claim in the original pass was WRONG —
there IS a live caller.** `service_initializer.py:1061-1066` documents that "The Generals
(CodingGeneral, IntelligenceGeneral) were removed 2026-04-03" — the `backend/generals/`
directory never existed as live code inside `apps/backend-rag/backend/`; their
responsibilities were absorbed by Core Guardian V3 (external) and the Intel Pipeline
(Chain 4). That grep was correctly scoped to `apps/backend-rag/backend/` only, and it is
true that nothing THERE calls this route.

However, a **different app in the same monorepo does call it**:
`apps/nuzantara-mcp/nuzantara_mcp/workflows/heartbeat.py:32` —

```python
activity_task = _call_safe("/api/generals/activity", params={"hours": 24})
...
snapshot = {
    "critical_alerts": _safe(alerts, "critical_alerts"),
    "recent_activity": _safe(activity, "recent_activity"),  # line 49
    ...
}
```

This is the `lam_grounding_snapshot` MCP tool — documented as "call this first at the
start of any session" for LAM startup grounding. Every invocation of that tool fires a
request at the dead `/api/generals/activity` route, gets a 404 wrapped as
`{"error": True, "detail": ...}` by `_call_safe`'s exception handling, and silently
populates `recent_activity` with an error object instead of real activity data. The
2026-07-08 memory that flagged "breaks the LAM grounding snapshot `recent_activity`
section" was RIGHT — this sweep's original close-as-non-issue was based on an
incompletely-scoped grep (backend-rag only) and should not have been treated as a full
trace.

**Corrected status: OPEN FOLLOW-UP, not closed.** The route itself doesn't need to come
back — but `lam_grounding_snapshot`'s `recent_activity` section is silently degraded on
every call. Fix options: (1) point `heartbeat.py:32` at whatever DOES track recent agent
activity now (Core Guardian V3 / Intel Pipeline Chain 4, per the same service_initializer
comment), or (2) remove the `recent_activity` field from the snapshot contract if no
replacement exists. Flagging as **LEDGER-DELTA** — a real, live, low-severity bug (silent
degraded field, not a crash), owner: whoever next touches `nuzantara_mcp/workflows/`.

### MCP `get_client_timeline` / `get_client_compliance` — "over-restrictive role gate"
**Verdict: today's mapping matches by observation, but the original "drift is impossible"
claim is FALSE as a statement about runtime enforcement — corrected below.**

`apps/nuzantara_mcp/auth.py` (real path — the report's original `nuzantara_mcp/auth.py`
was missing the `apps/` prefix) implements TWO independent mechanisms that are easy to
conflate:

1. **`roles_for(tool_name)`** (`auth.py:133-146`) — an audit/sanity-check helper that DOES
   read live from `ROLE_TAXONOMY`, itself loaded from `roles.yaml` once at import time
   (`auth.py:124`). This is the piece the module docstring means by "so drift is
   impossible" — and that claim is true, but only for code that actually calls
   `roles_for()`.
2. **`require_role(*allowed_roles)`** (`auth.py:149-185`) — the actual enforcement
   decorator applied to every MCP tool. It takes **hardcoded string-literal role names
   at the call site** and checks only `caller in allowed_roles` (`auth.py:168`). It never
   calls `roles_for()` and never reads `ROLE_TAXONOMY` at all.

Verified today's values match exactly:
- `get_client_timeline`: `roles.yaml:12` lists it ONLY under `visa_specialist`. Decorator
  `@require_role("visa_specialist")` at `crm.py:231` matches.
- `get_client_compliance`: `roles.yaml:34` lists it ONLY under `tax_consultant`. Decorator
  `@require_role("tax_consultant")` at `compliance.py:83` matches.
- Neither tool appears in `company_setup`'s tool list (`roles.yaml:40-57`).

**But this is an exact match TODAY, verified by inspection, not a structural guarantee.**
Because `require_role()`'s allowed-roles tuple is a hardcoded literal independent of
`ROLE_TAXONOMY`, editing `roles.yaml` alone — e.g. adding `get_client_timeline` under
`company_setup` — would NOT change what `crm.py:231` enforces; the decorator would still
deny `company_setup` callers, silently diverging from the YAML that's supposed to be the
single source of truth. Conversely, editing the decorator's role tuple without touching
`roles.yaml` creates the same silent divergence in the other direction. **Drift is
possible; there is no tripwire (test or runtime check) that fails when the decorator
literal and the YAML entry disagree.**

The underlying product conclusion is unchanged: `company_setup` is correctly excluded
from both reads today, and this remains a legitimate least-privilege design, not a bug to
fix blind. What changes is the framing — this is "exact-match verified today, no
structural enforcement of that match," not "drift is impossible." Flagging as
**LEDGER-DELTA**: (1) the RBAC-scope product question from the original pass still stands
(owner: Zero, business call), and (2) a new, smaller follow-up — a test that asserts every
`@require_role(...)` literal in `apps/nuzantara-mcp/nuzantara_mcp/tools/*.py` is consistent
with `roles_for()` for that tool name, so future edits to either side get caught instead of
silently diverging.

## 4. What was NOT done (time-box)

- No 3-persona synthetic-client walk of the full portal/CRM surface — the unauthenticated
  sweep gave a clean signal only on the 36 routes that executed past the auth wall (see
  §2 correction: 159/195 routes never reached protected handler logic in this sweep), and
  a full synthetic create→walk→cleanup cycle per persona would have consumed the
  remaining budget without a specific signal pointing at a broken surface. The
  `discovery_crm_portal_live_e2e_synthetic_2026_07_08` memory already ran a comparable
  pass on 2026-07-08 with 0 500s found (2 MCP contract bugs fixed then, PR #2179) — but
  that pass is not a substitute for probing THIS week's 159 auth-walled routes.
- 65 path-parameterized GET routes (need real or synthetic IDs) not probed.
- `apps/mouth`/Vercel-side confirmation that #2164's data-file change actually reached the
  live `kbli-gold-all.json` artifact was not verified (fenced: mouth is Subhi's lane per
  CLAUDE.md §13, and S4's fences explicitly exclude `apps/mouth` edits — but a *read-only*
  live-content check would have been in scope; flagging as unchecked).
- Independent re-verification of #2189's Qdrant point count (`verify_collection()` output
  or a direct collection-count query) was not performed this sweep — see §1 correction.

## Owner / next step

- `apps/mouth` Vercel deploy confirmation for #2164 → owner: whoever next touches mouth
  lane (Subhi/coordinator), 5-minute check: fetch a live gold-purged code from
  `balizero.com/kbli/<one-of-the-11-purged-codes>` and confirm the purged
  `expert_legal`/`tkaInfo` fields are actually gone client-side.
- `roles.yaml` `company_setup` scope question (timeline/compliance reads) → owner: Zero,
  business call on RBAC scope, not a code bug.
- `require_role()`/`roles_for()` consistency test (no tripwire today, drift possible) →
  owner: whoever next touches `apps/nuzantara-mcp/nuzantara_mcp/auth.py` or its tool
  decorators.
- `lam_grounding_snapshot`'s `recent_activity` field silently degraded by the dead
  `/api/generals/activity` route (`heartbeat.py:32`) → owner: whoever next touches
  `apps/nuzantara-mcp/nuzantara_mcp/workflows/heartbeat.py`; either repoint to the real
  activity source (Core Guardian V3 / Intel Pipeline Chain 4) or drop the field.
- Independent Qdrant point-count re-verification for #2189 → owner: whoever next touches
  the KBLI reindex lane, 2-minute check via `verify_collection()` or a direct count query
  against `kbli_2025_final_hybrid`.

## Adversarial review

Seat: gpt-5.5 (Codex CLI, fresh context, read-only sandbox) — 2026-07-12.
Verdict as returned: **REFUTED** (5 findings).

1. "Generals 404 has zero callers" → **CONFIRMED as a real finding.** `heartbeat.py:32`
   calls `/api/generals/activity` and assigns the result to `recent_activity` in
   `lam_grounding_snapshot`. Corrected in §3 (was: closed as non-issue; now: open
   follow-up, silently degraded field).
2. "0/195 5xx, surface-wide clean" → **CONFIRMED as overreach.** 159/195 routes were
   stopped at the 401 auth wall before executing protected logic; 65 path-parameterized
   GET routes and all non-GET routes were excluded. Corrected in §2 (scoped to the 36
   routes that actually executed handler logic).
3. "#2189 re-ingested all 1,559 points, proven live" → **CONFIRMED as unsupported.**
   Evidence retained was a commit message plus one non-exact query gradient; neither
   proves full cardinality or that the retry logic executed. Corrected in §1 (downgraded
   to "partially corroborated").
4. "RBAC drift is impossible" → **CONFIRMED as false.** `require_role()` (the actual
   enforcement decorator) uses hardcoded role literals and never reads `ROLE_TAXONOMY`;
   only the separate `roles_for()` audit helper is YAML-live. Today's values match by
   inspection, but there is no tripwire against future divergence. Corrected in §3
   (reworded to "exact-match verified today, no structural enforcement").
5. "24 public endpoints zero PII/CRM leakage" → **CONFIRMED as unsupported.** Retained
   evidence was paths and status codes only; response bodies were never inspected.
   Corrected in §2 (scoped to "reviewed by path/status, not a body-level leakage audit").
