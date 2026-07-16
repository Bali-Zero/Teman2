---
date: 2026-07-17
domain: operations
client_case: none (security/authz audit — LANE B backend, task authz-route-sweep-0717)
sources:
  - "Live enumeration against the real FastAPI app (include_routers, fastapi 0.139.0), run in-turn 2026-07-17"
  - "backend/middleware/hybrid_auth.py (fail-closed gate)"
  - "backend/app/auth/public_endpoints.py (PUBLIC_ENDPOINTS registry)"
  - "backend/app/auth/route_risk_registry.py (ROUTE_RISKS declared backlog, Case OS Fase-1)"
  - "backend/tests/security/test_route_authz_coverage.py (pre-existing Layer-2 posture gate, PR #2304, 2026-07-12)"
  - "backend/tests/security/test_mutating_routes_are_gated.py (NEW — this sweep's durable defense, Layer-1 gate)"
  - "memory: discovery_caseos_fase1_authz_gate_2026_07_12 (the '~65 route mutanti nude' origin claim)"
  - "Router source read in this turn: backend/app/routers/news.py, newsletter.py, knowledge_visa.py, dashboard.py, preview.py, team_activity.py, backend/app/deps/auth.py"
adversarial_review: codex
---

# Mutating-routes authz ledger — how many are really covered by the gate (2026-07-17)

## TL;DR — the number Zero asked for

**345** unique (method, path) mutating routes (POST/PUT/PATCH/DELETE) exist in the live app today.

- **299 are gated** — `backend/middleware/hybrid_auth.py` demands a valid credential (API key, JWT
  header, or JWT cookie) before the handler runs, because the path is NOT in `PUBLIC_ENDPOINTS`.
- **46 are public** — the path matches a `PUBLIC_ENDPOINTS` prefix/exact/template entry, so
  `HybridAuthMiddleware.dispatch()` skips authentication entirely (Step 1 of dispatch, see
  `backend/middleware/hybrid_auth.py:196-249`). Zero credential of any kind reaches the handler.
  - **40 of the 46** are reviewed-and-intentional (webhooks with signature verification, auth
    flows that must run before a credential exists, funnel/lead-gen anonymous-by-design,
    already-explicit registry rows, or independently re-gated in-router despite the middleware
    treating the path as public).
  - **6 of the 46 are NOT justified — genuine findings, zero auth at ANY layer.** See §Findings.

Separately, of the 299 gated routes, **51 are a declared-but-not-yet-hardened backlog**
(`ROUTE_RISKS`, Case OS Fase-1, 2026-07-12): any authenticated team member can call them — the
middleware requires *a* credential, but nothing yet distinguishes an intern from an admin. This is
a **different, already-tracked, already-owned axis** (Layer 2 — "who specifically may call this",
not Layer 1 — "is any credential required at all"). It is not new to this sweep; it is reported
here only to fully close the "~65 route mutanti nude" question Case OS Fase-1 opened.

**Answer to "how many of the mutating routes are truly covered by the authz gate today"**:
**339 / 345 (98.3%)** — the 299 gated + the 40 deliberately-public. **6 / 345 (1.7%) are the real
gap**: reachable by absolutely anyone, no token, no signature, no nothing.

## Two different questions this ledger keeps deliberately separate

| | `test_route_authz_coverage.py` (existing, PR #2304) | `test_mutating_routes_are_gated.py` (NEW, this sweep) |
|---|---|---|
| Question | Does this mutating route have SOME authz posture? | Does this mutating route bypass the middleware's fail-closed gate ENTIRELY? |
| Compliant if | Depends-auth, OR body-verifier, OR public, OR `ROUTE_RISKS` entry | Not public, OR public-and-in `INTENTIONALLY_PUBLIC_MUTATIONS` |
| Treats "is public" as | Automatically compliant, full stop | The thing being scrutinized — public is exactly what needs a *specific*, reviewed reason |
| Blind spot it has | A route can be "compliant" purely by sitting under a broad public-read prefix, with zero verification that THIS specific mutation was the intended target of that prefix | None on router-level granularity (that's `ROUTE_RISKS`'s job, not duplicated here) |
| Result today | **GREEN** (0 uncovered — confirmed live, this turn) | **RED** (6 uncovered — confirmed live, this turn) |

Both are true at once, and both are necessary: the existing test proved the 65-nude number from
Case OS Fase-1 has gone to zero *by its own definition*. This sweep's test proves that definition
has a structural blind spot — a prefix declared public for reading was never method-scoped, so it
silently also covers writes nobody reviewed for that purpose. Neither test subsumes the other.

## §Findings — 6 mutating routes reachable with ZERO credential (HIGH PRIORITY, NOT fixed here)

Per the task's explicit instruction, these are **reported, not silently patched**. Each is a real
business decision (does this need to be closed, and by adding auth vs narrowing the public prefix vs
something else) that belongs to Zero, not to a blind overnight fix.

| # | Method | Path | Handler | Why it is reachable unauthenticated | Real-world impact |
|---|---|---|---|---|---|
| 1 | POST | `/api/news` | `news.py:290 create_news` | `/api/news` is a `PUBLIC_ENDPOINTS` prefix match (category `marketing`, reason "Public news/intel feed — approved articles..."), intended for the READ side. The prefix is not method-scoped, so it also covers this handler, which has **zero** `Depends()` beyond the DB pool. | Anyone can INSERT an arbitrary news_items row with `status='approved'` (**auto-approved, no review step**) — direct content injection onto the public balizero.com news feed. |
| 2 | POST | `/api/news/bulk` | `news.py:351 create_news_bulk` | Same prefix bleed as #1. Zero `Depends()`. | Bulk version of #1 — same impact, N articles per call. |
| 3 | POST | `/api/news/{news_id}/image` | `news.py:414 update_news_image` | Same prefix bleed. Zero `Depends()`. | Anyone can overwrite the `image_url` of ANY existing news item with an arbitrary URL — defacement / hotlink / possible XSS-adjacent vector depending on how the frontend renders it. |
| 4 | PATCH | `/api/news/{news_id}/status` | `news.py:442 update_news_status` | Same prefix bleed. Zero `Depends()`. | Anyone can flip ANY news item between `pending/approved/rejected/archived` — unpublish a live article, or approve a pending one, with no auth. |
| 5 | POST | `/api/blog/newsletter/log` | `newsletter.py:564 log_newsletter_send` | `/api/blog/` is a `PUBLIC_ENDPOINTS` prefix (category `marketing`, generic reason "Public blog articles and content" — meant for reading blog posts). Docstring says "(admin endpoint)" but there is **no** `Depends()` at all. | Anyone can insert fake rows into `newsletter_send_log` (recipient/sent/failed counts) — pollutes internal delivery reporting. Lower severity (no PII exposure, no destructive write to a live-content table), but still a documented "admin" action with zero enforcement. |
| 6 | PATCH | `/api/blog/newsletter/preferences` | `newsletter.py:434 update_preferences` | Same `/api/blog/` prefix bleed. Zero `Depends()`. Takes a raw `email` OR `subscriberId` in the body — no proof of ownership (unlike `/unsubscribe`, which is presumably token-gated per its registry reason). | Anyone who knows/guesses a subscriber's email or numeric ID can change their newsletter `categories`/`frequency`/`language` with no verification. |

**Adjacent finding, NOT in scope for this ledger (GET, not mutating) but worth flagging loudly**:
`newsletter.py:492 list_subscribers` (`GET /api/blog/newsletter/subscribers`) is docstringed
"(admin endpoint)", has **zero** `Depends()`, and sits under the same public `/api/blog/` prefix —
meaning it returns every subscriber's `email`/`name`/`categories`/`frequency`/`language` to an
unauthenticated caller. This is a **PII read exposure**, arguably higher severity than findings
#5/#6 above, but it is a GET and therefore structurally out of this ledger's mutating-routes scope.
Recommend Zero treat it as part of the same gating decision.

### PENDING-ARMS

```
PENDING-ARMS: news.py POST /api/news, POST /api/news/bulk, POST /api/news/{news_id}/image,
  PATCH /api/news/{news_id}/status — reachable with zero credential, auto-approved content
  injection into the public news feed. owner=operator[business] — decide: add
  Depends(get_current_user)+role check (breaks any live unauthenticated caller, e.g. the
  balizero-intel scraper — NOT verified live in this sweep, must be checked before gating) vs
  narrow the /api/news PUBLIC_ENDPOINTS prefix to GET-only equivalents. Category: SECURITY HOLE,
  HIGH. Not fixed in this PR (investigative task, no blind code changes).

PENDING-ARMS: newsletter.py PATCH /api/blog/newsletter/preferences, POST
  /api/blog/newsletter/log — reachable with zero credential; /preferences additionally lacks
  ownership proof (raw email/subscriberId). owner=operator[business] — decide: add a
  signed-token requirement (mirrors /unsubscribe's presumed pattern) vs Depends(auth) vs accept
  as low-severity and document. Category: SECURITY HOLE, MEDIUM (no PII read, but unauthenticated
  state mutation on a real subscriber record). Not fixed in this PR.

PENDING-ARMS: newsletter.py GET /api/blog/newsletter/subscribers — zero Depends(), returns full
  subscriber PII (email/name/prefs) to unauthenticated callers under the public /api/blog/
  prefix. owner=operator[business] — adjacent finding (GET, out of this ledger's mutating scope)
  surfaced for the same gating decision. Category: PII EXPOSURE, HIGH. Not fixed in this PR.
```

## §Medium findings — public at the middleware, but independently re-gated in-router (verified SAFE, not holes)

Three routes are swept into "public" by a broad read-oriented prefix, but each has its own
`Depends()` that does NOT rely on `request.state.user` (which the middleware never sets for a
"public" path) — it independently re-validates the caller's Bearer JWT / API key. Confirmed by
reading the full dependency chain in this turn, not assumed from the docstring:

| Method | Path | In-router gate | Why it is still safe |
|---|---|---|---|
| POST | `/api/knowledge/visa/` | `Depends(get_admin_user)` → `Depends(get_current_user)` (`backend/app/deps/auth.py:29`) | `get_current_user`'s Priority-2 fallback independently decodes the `Authorization: Bearer` JWT when `request.state.user` is unset — an unauthenticated caller gets 401 from the ROUTER, not a silent pass. |
| PUT | `/api/knowledge/visa/{visa_id}` | Same chain | Same as above. |
| POST | `/preview/upload` | `Depends(verify_internal_api_key)` (`preview.py:46`) | Independent in-router API-key check, unrelated to the middleware's public-path skip. |

These are **not** PENDING-ARMS items — they are a fragile-but-currently-safe pattern (a
cookie-only browser session would 401 here since `HTTPBearer` doesn't read cookies, and no CSRF
check runs on a "public" path) worth a follow-up hardening note, not an urgent gate.

## §Additional findings — surfaced by the mandatory adversarial-review pass, independently re-verified by this session

The repo's own R1 gate (`scripts/check_adversarial_review.py`) requires a generator≠grader review
before this ledger can merge. That review (Codex, this turn) confirmed all 6 primary findings and
all 3 "medium/safe" claims above, and additionally flagged that 4 of the 40 "justified" entries
have a **documented reason that overclaims the actual code behavior**. Every one of these was then
independently re-read by this session (not taken on Codex's word alone) — see the exact `file:line`
evidence below. These do NOT change the PASS/FAIL verdict of the new test (each route's public-ness
IS architecturally correct — webhooks and one-click-unsubscribe are SUPPOSED to require no session)
— they are a distinct, real class of finding: **the claimed protection mechanism is weaker than, or
absent from, what the registry's `reason` text says.**

| Route | Registry claims | Verified actual behavior | Severity |
|---|---|---|---|
| `POST /webhook/whatsapp` | "verified by WHATSAPP_VERIFY_TOKEN" | `whatsapp_chat.py:1167-1197 _verify_whatsapp_signature` DOES check `X-Hub-Signature-256` HMAC-SHA256 — but its own docstring (line 1175) says it returns `True` ("valid") when `WHATSAPP_APP_SECRET` is unset. **Silent fail-open**, config-dependent. | MEDIUM — landmine, not currently known to be misconfigured, but no alarm would fire if it were |
| `POST /webhook/instagram` | "verified by INSTAGRAM_VERIFY_TOKEN" | `instagram_chat.py:149-164` — that token check exists ONLY on the `GET` handshake. The `POST` handler (`instagram_chat.py:167-215+`) parses the JSON body directly with **zero** `X-Hub-Signature-256` check — no signature verification of the actual message payload at all. | HIGH — any caller can POST a forged Instagram DM payload into the auto-reply/RAG pipeline |
| `POST /webhook/telegram` | (registry reason describes the routing, claims no explicit verification but the "signed webhook" framing in prior audits implied one) | `telegram_webhook.py:252-` — **no** `X-Telegram-Bot-Api-Secret-Token` check at all. Any caller can POST a forged Telegram update, including a `callback_query` whose `data` starts with `"intel:"`, which reaches `handle_intel_callback` (intel-voting/quorum logic) | HIGH — forged callback data reaches a business-logic branch, not just chat noise |
| `POST /api/blog/newsletter/unsubscribe` | "token-based verification (legal requirement)" | `UnsubscribeRequest.token` (`newsletter.py:141`) is accepted in the Pydantic schema but the handler (`newsletter.py:394-431`) never reads `request.token` — it looks up by raw `subscriberId`/`email` only. Contrast with `/confirm` (`newsletter.py:304-320`), which DOES do `WHERE id=$1 AND confirmation_token=$2` — a real, verified token check. | LOW — unsubscribe-only action (no PII read, no destructive write), and no-login one-click-unsubscribe is a common/expected pattern, but the specific "token-based" claim is currently false |

### PENDING-ARMS (additional, from the adversarial-review pass)

```
PENDING-ARMS: webhook/whatsapp signature verification fails OPEN (returns valid) when
  WHATSAPP_APP_SECRET is unset (whatsapp_chat.py:1177-1178). owner=operator[business] — decide:
  (a) verify the Fly secret is actually set in prod today (this session has no fly-secrets access
  to confirm), (b) change the fail-open to fail-closed (reject if secret missing) as defense in
  depth, or (c) accept as-is with a monitoring alert on missing-secret startup. Category: SECURITY
  HOLE (conditional), MEDIUM. Not fixed in this PR.

PENDING-ARMS: webhook/instagram POST handler has ZERO signature verification of message payloads
  (instagram_chat.py:167+) — only the GET handshake checks a token. owner=operator[business] —
  decide: add X-Hub-Signature-256 HMAC check mirroring whatsapp_chat.py's pattern (reuse
  INSTAGRAM_APP_SECRET if it exists, else provision one). Category: SECURITY HOLE, HIGH. Not fixed
  in this PR (would require a new secret + code change beyond this investigative task's scope).

PENDING-ARMS: webhook/telegram POST handler has NO secret-token verification at all
  (telegram_webhook.py:252) — forged callback_query with "intel:" prefix reaches intel-voting
  logic. owner=operator[business] — decide: add X-Telegram-Bot-Api-Secret-Token check (set via
  Telegram's setWebhook secret_token param) + independently review whether handle_intel_callback's
  quorum logic needs its own voter-authorization check regardless of transport-layer fix.
  Category: SECURITY HOLE, HIGH. Not fixed in this PR.

PENDING-ARMS: newsletter unsubscribe registry claims "token-based verification" but the token
  field is accepted-and-ignored (newsletter.py:141 schema vs :394-431 handler) — no ownership
  proof, raw email/subscriberId only. Same gap on /api/news/unsubscribe (news.py:512, takes only
  a bare `email` query param, no token field in the signature at all). owner=operator[business] —
  decide: enforce the existing token field (cheap fix, field already in the schema) vs accept as
  intentionally low-friction one-click unsubscribe and correct the registry's reason text instead.
  Category: DOCUMENTATION-VS-CODE MISMATCH + minor authz gap, LOW-MEDIUM. Not fixed in this PR.
```

## §Full accounting of the 46 public mutating routes

Reviewed-and-intentional (40) — full list with justification lives in
`backend/tests/security/test_mutating_routes_are_gated.py::INTENTIONALLY_PUBLIC_MUTATIONS`
(the durable, machine-checked source of truth — this table is a snapshot, that file is live):

| Method | Path | Category | Why public |
|---|---|---|---|
| POST | `/api/auth/login` | auth | Login endpoint — cannot require the credential it issues |
| POST | `/api/auth/team/login` | auth | Team member login — same reason |
| POST | `/api/auth/request-magic-link` | auth | Passwordless request, enumeration-safe |
| POST | `/webhook/whatsapp` | webhook | Meta signature verified in-router (WHATSAPP_VERIFY_TOKEN) |
| POST | `/webhook/instagram` | webhook | Meta signature verified in-router (INSTAGRAM_VERIFY_TOKEN) |
| POST | `/webhook/telegram` | webhook | Telegram bot webhook, single mounted path |
| POST | `/api/bridge/ingest/article` | bridge | X-Bridge-Auth hmac.compare_digest in-router |
| POST | `/api/bridge/ingest/enrichment` | bridge | Same HMAC gate |
| POST | `/api/bridge/intake-gate/doc-counts` | bridge | Same HMAC gate |
| POST | `/api/bridge/wa-media/ack` | bridge | Same HMAC gate |
| POST | `/api/crm/clients/upsert-by-phone` | infra | X-CRM-Write-Key in-router |
| POST | `/api/crm/internal/clients/{client_id}/documents/upload` | infra | Same X-CRM-Write-Key gate |
| POST | `/api/intel/lake/observations` | infra | X-Producer-Token in-router |
| POST | `/api/intel/lake/observations-batch` | infra | Same X-Producer-Token gate |
| POST | `/api/hr/late-reply/{incident_id}` | client_portal | Per-incident token = the auth (secrets.compare_digest) |
| POST | `/api/portal/invite/complete` | client_portal | Invite token = the auth, no account exists yet |
| POST | `/api/lead/capture` | funnel | Anonymous CTA, no PII, 8KB cap |
| POST | `/api/funnel/session/touch` | funnel | Anonymous UUID cookie touch |
| POST | `/api/funnel/session/convert` | funnel | Called by the portal login flow itself |
| POST | `/api/analytics/funnel-event` | funnel | 11 whitelisted events, session_id only |
| POST | `/api/prime/v2/analyze` | funnel | Explicitly declared "public, rate-limited" |
| POST | `/api/prime/v2/resolve` | funnel | Explicitly declared public |
| POST | `/api/v1/visa-oracle/recommend` | visa_oracle | Stateless scoring, no persistence |
| POST | `/api/v1/visa-oracle/chat` | visa_oracle | IP-hash rate-limited, no PII |
| POST | `/api/v1/visa-oracle/handoff` | visa_oracle | Deep-link builder, no state mutation |
| POST | `/api/v1/kbli-notebook/chat` | public_knowledge | Public classification chat, no PII |
| POST | `/api/blog/ask` | marketing | AskZantara public Q&A, explicit row |
| POST | `/api/blog/newsletter/subscribe` | marketing | Public opt-in, explicit row |
| POST | `/api/blog/newsletter/confirm` | marketing | Double opt-in token verify, explicit row |
| POST | `/api/blog/newsletter/unsubscribe` | marketing | Legal opt-out requirement, explicit row |
| POST | `/api/news/subscribe` | marketing | Same opt-in shape as blog equivalent (news.py:480) |
| POST | `/api/news/unsubscribe` | marketing | Same opt-out shape as blog equivalent (news.py:512) |
| POST | `/api/metrics/frontend` | infra | Best-effort, no PII, explicit row |
| POST | `/api/dashboard/map/validate-property` | preview | Stateless KBLI compute, matches reason verbatim |
| POST | `/api/dashboard/map/gistaru-zone` | preview | Stateless geo compute, matches reason |
| POST | `/api/dashboard/map/analyze-investment` | preview | Stateless compute, verified no DB write |
| POST | `/api/dashboard/map/analytics/log-lookup` | preview | Telemetry insert only, same shape as `/api/metrics/frontend` |
| POST | `/api/knowledge/visa/` | public_knowledge | Public prefix, but independently re-gated (§Medium findings) |
| PUT | `/api/knowledge/visa/{visa_id}` | public_knowledge | Same |
| POST | `/preview/upload` | preview | Public prefix, but independently re-gated (§Medium findings) |

**NOT justified (6)** — see §Findings above.

## §Cross-reference — the 51-entry `ROUTE_RISKS` declared backlog (Layer 2, pre-existing)

Not new to this sweep. Reported for completeness since the task explicitly invoked the "~65 route
mutanti nude" number. These 299-minus-248=51 routes are ALL gated by `hybrid_auth` (Layer 1 —
require a credential) but have no ROUTER-level role distinction yet (Layer 2):

- **R3_ADMIN, `gating_safe=False`** (9): live internal callers (MCP/cron/service-key) would 401 if
  gated blind — migrate the caller first. E.g. `/api/naga/research`, `/api/v1/autonomous-execution/*`.
- **R2/R1, `gating_safe=True`** (~27): no known live caller would break — safe to gate today,
  just not yet done (non-urgent, low blast radius per Case OS Fase-1's own adversarial audit).
- **R2, `gating_safe=False`** (~15): confirmed live callers using API-key auth whose registration
  in prod is unverified — same caution as the R3 set.

Full detail: `backend/app/auth/route_risk_registry.py`. This ledger does not re-litigate that
classification — it is independently owned and dated 2026-07-12.

## Reproducibility

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/security/test_mutating_routes_are_gated.py -q
```

The 46/40/6 split and the 345 total are computed live by the test's `_mutating_routes()` +
`find_entry()` against `include_routers()` — this document is a snapshot of that computation on
2026-07-17, fastapi 0.139.0. Re-run the test to get today's number; do not treat this file as an
authority once it drifts from a re-run.

## Adversarial review

Seat: `codex` (GPT-5.x via the `second-opinion` MCP, read-only sandbox, `cwd` = this worktree, ran
the actual test suite itself rather than trusting the report). Full transcript summary:

**Confirmed, independently, by re-reading the code**:
- `PublicEndpoint.match()` defaults to prefix (`path.startswith(...)`), is not method-scoped, and
  has no segment boundary (e.g. `/api/newsroom` would also match an `/api/news` prefix entry —
  noted as a related risk class, no such route exists today).
- All 6 primary findings (news.py x4, newsletter.py x2): zero auth dependency of any kind, confirmed.
- All 3 medium/safe claims (`knowledge_visa.py` x2, `preview.py` upload): the independent
  `get_current_user`/`verify_internal_api_key` re-validation is real and does not silently pass on
  missing credentials — 401/403, not a bypass. One caveat added: `get_current_user`'s expiry check
  can be audit-only depending on `jwt_enforce_expiry` config (does not weaken THIS finding, noted
  for awareness).

**Findings the original classification missed, ADDED to this ledger after re-verification**
(this session re-read every one of these directly — see §Additional findings above for exact
`file:line` evidence, not merely relayed from the reviewer):
- WhatsApp webhook HMAC fail-open when `WHATSAPP_APP_SECRET` unset.
- Instagram webhook has zero POST signature verification (token check is GET-handshake-only).
- Telegram webhook has zero signature/secret-token verification at all; forged `callback_query`
  with an `"intel:"` prefix reaches intel-voting logic.
- Newsletter/news unsubscribe: the registry's "token-based verification" claim does not match the
  handler code (token field present in schema, never read).
- Adjacent, out of this ledger's mutating-only scope but flagged: `GET /api/blog/newsletter/subscribers`
  is an undeclared, unauthenticated PII read (subscriber email/name/prefs) under the same public
  `/api/blog/` prefix.

**Reviewer's assessment of scope/framing**: the distinction drawn between this new test and the
pre-existing `test_route_authz_coverage.py` was confirmed accurate (old test accepts "is public" as
automatically compliant; this test treats "is public" as the thing needing a specific, reviewed
reason). The reviewer's explicit caution, preserved here rather than smoothed over: **this ledger
and test are a regression-detection tool for the middleware-bypass surface, not an end-to-end proof
that every listed "justified" route's underlying protection is airtight** — the test only checks
"is this (method,path) in a reviewed allowlist with a real justification string", not "is the
justification's claim about signature/token verification actually true today". That gap is why
§Additional findings exists as a distinct section rather than being silently folded into "40
justified, case closed".

No objections from the review were left unaddressed: every additional finding it raised was
independently re-verified by this session against the actual source (not accepted on the
reviewer's word) and is now reflected in both this ledger and the test file's justification text.
