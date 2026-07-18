# S03 Phase 2 — JWT expiry enforcement: activation audit + GO checklist

> Author: Kimi (Air-M5 session), 2026-07-18 · Status: **AWAITING OPERATOR GO** (Legge 5 — prod auth posture is an operator decision)
> Scope: audit of `jwt_enforce_expiry` readiness. **No prod change has been made by this report.**

## 1. Current state (verified on disk this turn)

| Item | Value | Location |
|---|---|---|
| Flag | `jwt_enforce_expiry: bool = False` — "S03: Phase 1 audit mode, flip to True for Phase 2" | `apps/backend-rag/backend/app/core/config.py:501` |
| Env override | `JWT_ENFORCE_EXPIRY=true` (pydantic-settings, no code change needed) | same |
| Token lifetime | `jwt_access_token_expire_hours = 1` (already reduced from 24h) | `config.py:500` |
| Revocation | `enable_token_revocation: bool = False` (S03-S2, Redis-backed; **not implemented** in sync dep path nor middleware) | `config.py:503` |
| Refresh flow | `POST /api/auth/refresh` exists | `backend/app/routers/auth.py:690` |

Enforcement points that read the flag **live** (5 call-sites, all consistent — verified by grep):

1. `backend/middleware/hybrid_auth.py:473` — header JWT
2. `backend/middleware/hybrid_auth.py:517` — cookie JWT (`nz_access_token`, CSRF-validated)
3. `backend/app/deps/auth.py:70` — sync dep path (Phase 1 audit branch at :103 logs expired tokens, accepts them)
4. `backend/app/auth/validation.py:61` — token validation helper
5. `backend/app/routers/websocket.py:93` — WebSocket auth

## 2. Why this matters (risk statement)

With `verify_exp=False`, a JWT's 1h lifetime is **cosmetic**: any token — leaked from a log, a transcript, a stolen cookie — remains valid **forever** (until `JWT_SECRET_KEY` rotates). The S03 hardening (1h tokens) buys nothing while expiry is not verified. Phase 1 audit mode was correct for measurement; it is not a safe steady state.

## 3. Blast radius of flipping to `true`

Clients presenting an **expired** token will receive 401 and must refresh/re-authenticate:

- **Web/portal cookie sessions** (`nz_access_token`): users re-auth via SSO/magic-link (migration 237). Impact: UX friction only, by design.
- **Header-JWT API clients** (MCP tools, scripts): must call `/api/auth/refresh` or re-login. Any script holding a **static, long-dead token** breaks loudly — this is the intended detection.
- **Service keys** (`X-API-Key`, `X-Internal-Key`, `X-Debug-Key`): **unaffected** (separate auth path in HybridAuthMiddleware).
- **WebSocket clients**: reconnect with fresh token.

**Open measurement gap:** Phase 1 has been logging expired-token usage since S03 (audit branch `deps/auth.py:103`). Before flipping, quantify: `fly logs -a nuzantara-rag | grep -i "expired"` over ≥7 days (run on Pro). If daily expired-token traffic is near-zero, the flip is low-risk. If a loud consumer appears, fix that consumer first (it is running on a dead token *right now* — a finding in itself).

## 4. GO checklist (operator)

1. [ ] Measure expired-token audit volume (≥7 days, Pro `fly logs` or Sentry).
2. [ ] Verify `/api/auth/refresh` works from a real client (portal + one MCP session).
3. [ ] Flip: `fly secrets set JWT_ENFORCE_EXPIRY=true -a nuzantara-rag` (Fly restarts machines — pick a low-traffic window; no deploy needed).
4. [ ] Monitor 30 min: 401 rate, Sentry auth errors, WA/IG/Telegram channel health (channels use API keys — should be untouched).
5. [ ] Rollback path (instant): `fly secrets unset JWT_ENFORCE_EXPIRY -a nuzantara-rag`.

## 5. Follow-ups (separate strikes, not blocking)

- **Token revocation (S03-S2):** `enable_token_revocation` is flag-off and architecturally unwired in the sync dep path. Without it, a *valid unexpired* token cannot be killed. Recommend implementation after Phase 2 lands.
- **Secret rotation drill:** `JWT_SECRET_KEY` has never (to my knowledge) been rotated; with expiry enforced, rotation becomes the remaining kill-switch. Document the drill.

## 6. What this report did NOT do

- Did not flip the flag (Legge 5).
- Did not touch `hybrid_auth.py` / `deps/auth.py` — plumbing is already correct and consistent; the only change needed is operational (Fly secret).
