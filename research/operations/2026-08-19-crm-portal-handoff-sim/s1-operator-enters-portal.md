---
date: 2026-08-19
domain: compliance
client_case: none — internal architecture simulation, no single client engaged
sources:
  - apps/mouth/src/proxy.ts
  - apps/mouth/src/app/portal/(authenticated)/layout.tsx
  - apps/mouth/src/lib/api/portal/portal.api.ts
  - apps/mouth/src/lib/api/client.ts
  - apps/mouth/src/app/(workspace)/layout.tsx
  - apps/backend-rag/backend/app/routers/portal.py
  - apps/backend-rag/backend/middleware/hybrid_auth.py
  - apps/backend-rag/backend/app/utils/cookie_auth.py
  - apps/backend-rag/backend/app/core/config.py
  - apps/backend-rag/backend/app/routers/auth.py
  - live curl probes against my.balizero.com and nuzantara-rag.fly.dev (2026-08-19)
  - read-only Postgres query via mcp__postgres-nuzantara-local__query (2026-08-19)
adversarial_review: codex
---

# S1 — Operator enters the client portal (persona-alternation simulation)

## Scenario

An operator (a Bali Zero team member with a `kita.balizero.com` session — role
`admin`/`team`/whatever their `team_members.role` says, **never** `"client"`)
opens `https://my.balizero.com/portal` in the same browser. The SSO cookie
`nz_access_token` (httpOnly, `Domain=.balizero.com`) rides along automatically.
The question: what does the portal show them?

**Short answer: it depends on which operator.** For the ordinary case (any
team member whose email is not one of three hardcoded superuser addresses)
the answer is **(a) bounced to portal login** — but bounced by a client-side
catch-and-redirect, not by the edge gate, and not because anyone checked their
*role*. For exactly one specific superuser email, the answer is **(d) a
portal populated with data — that operator's own client-linked profile row**,
reached by an unrelated self-lookup fallback that nobody designed as a
"preview my own client view" feature. Both are downstream of the same root
belief: **the system treats "this identity is present/known" as a stand-in
for "this identity is authorized to see this content,"** at two independent
layers that don't know about each other.

---

## Step 1 — proxy.ts: the edge gate checks presence, not validity

`apps/mouth/src/proxy.ts:78`
```ts
const PORTAL_SESSION_COOKIE = "nz_access_token";
```

`apps/mouth/src/proxy.ts:157-159`
```ts
function hasPortalSession(request: NextRequest): boolean {
  return Boolean(request.cookies.get(PORTAL_SESSION_COOKIE)?.value);
}
```

`apps/mouth/src/proxy.ts:259-280` (portal-domain block):
```ts
if (isPortalDomain || enforceProdlikePortal) {
  if (isPortalPath(pathname)) {
    if (PORTAL_PUBLIC_PATHS.has(pathname) || hasPortalSession(request)) {
      return response;               // <-- pass through, no further check
    }
    ... redirect to /portal/login-upgraded ...
```

**Source of cause #1**: `hasPortalSession` is `Boolean(cookie?.value)` — it
does not decode the JWT, does not check expiry, does not check role, does not
check anything about *whose* cookie it is. Any non-empty cookie value passes.
Since the cookie is shared cross-subdomain (`Domain=.balizero.com`, set in
`apps/backend-rag/backend/app/utils/cookie_auth.py:80,100` via
`get_cookie_domain()` → `settings.cookie_domain`), the operator's real,
currently-valid `nz_access_token` from their `kita.balizero.com` session is
sent automatically and satisfies this check trivially. **The operator is
never bounced at the edge.** They reach the portal shell HTML.

I verified this live, without any real token (rule 2: synthetic junk value only):

```
$ curl -sS -o /dev/null -D - "https://my.balizero.com/portal"
HTTP/2 307
location: /portal/login-upgraded?redirect=%2Fportal
```

```
$ curl -sS -o /dev/null -D - --cookie "nz_access_token=junk-not-a-real-jwt-12345" \
    "https://my.balizero.com/portal"
HTTP/2 200
x-matched-path: /portal
```

A syntactically meaningless cookie value flips the proxy from 307-redirect to
200-serve-the-page. This is a direct, reproduced confirmation that the edge
gate is a presence check, full stop — it never touches the JWT.

---

## Step 2 — portal layout.tsx: no localStorage on this origin, falls to cookie auth

`apps/mouth/src/app/portal/(authenticated)/layout.tsx:128-131` (the file's own
comment, confirmed accurate by the code that follows):
```
// Check authentication and load data
// Uses cookie-based auth check (not localStorage) for cross-domain SSO support.
// When user logs in on kita.balizero.com, the httpOnly cookie on .balizero.com
// is shared with my.balizero.com, but localStorage is NOT shared across subdomains.
```

`apps/mouth/src/lib/api/client.ts:35-38` — the API client's constructor reads
`localStorage` via `safeStorage.getItem("auth_token")`. `localStorage` is
strictly per-origin; the operator's browser has never visited
`my.balizero.com` before in this scenario, so this read returns `null` on
that origin regardless of what's stored on `kita.balizero.com`.

`layout.tsx:132-156` — `checkAuth()` first tries `api.getToken()` (the
localStorage fast path). It is `null`, so this whole branch (including the
`role === "partner"` redirect at `layout.tsx:141-144`) is skipped entirely —
**no client-side role check ever runs for this session**, because the only
place a role check happens here is inside that skipped branch.

`layout.tsx:158-195` — falls to the cookie-based path. `isPartnerPortal` is
`false` (path is `/portal`, not `/portal/partner`), so it calls:
```
const portalProfile = await api.portal.getProfile();   // layout.tsx:176
```

---

## Step 3 — the frontend API call

`apps/mouth/src/lib/api/portal/portal.api.ts:137-141`:
```ts
async getProfile(): Promise<PortalProfile> {
  const response = await this.client.request<PortalApiResponse<any>>(
    "/api/portal/profile",
    { method: "GET" },
  );
```

`apps/mouth/src/lib/api/client.ts:287,300` — the underlying `fetch` call sets
`credentials: "include"` unconditionally, so the shared httpOnly cookie rides
along even though no `Authorization` header exists (no localStorage token on
this origin, confirmed above). No `as_client` query param is appended either:
`client.ts:234-245` only appends `?as_client=<id>` when
`this.portalImpersonationClientId !== null`, and that field is itself seeded
from `localStorage.getItem("bz_portal_impersonation_v1")`
(`client.ts:49-56`) — also per-origin, also empty on a fresh `my.balizero.com`
visit. **The request that reaches the backend is a bare
`GET /api/portal/profile` with only the shared cookie as identity — no
explicit target client, no impersonation marker.**

---

## Step 4 — backend: HybridAuthMiddleware decodes the JWT honestly

`apps/backend-rag/backend/middleware/hybrid_auth.py:454-477` (Priority 3,
since no `Authorization` header and no API key are present):
```python
cookie_token = get_jwt_from_cookie(request)
...
jwt_user = await self.authenticate_jwt_token(cookie_token)
```

`hybrid_auth.py:487-524` (`authenticate_jwt_token`) — decodes the JWT with
`jwt.decode(..., settings.jwt_secret_key, ...)`, requires `exp`, checks
`is_session_revoked`, and returns:
```python
return {
    "id": payload.get("sub"),
    "email": payload.get("email"),
    "role": payload.get("role", "member"),
    ...
}
```
This is **the operator's real, currently-valid identity** — their real email,
their real role (`team_members.role`, set at login: `auth.py:479` /
`auth.py:732` copy `user["role"]` straight into the JWT payload). Nothing is
forged or stale here; the middleware is doing exactly what it should.
`hybrid_auth.py:316`: `request.state.user = auth_result`.

I confirmed the backend does reject a garbage token (i.e. this layer is not
also presence-only):

```
$ curl -sS -o /dev/null -D - --cookie "nz_access_token=junk-not-a-real-jwt-12345" \
    "https://nuzantara-rag.fly.dev/api/portal/profile"
HTTP/2 401
```

---

## Step 5 — `get_current_client`: the real branch point

`apps/backend-rag/backend/app/routers/portal.py:1092-1096`:
```python
@router.get("/profile")
async def get_profile(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
```

`get_current_client` (`portal.py:122-264`) is where identity actually gets
turned into a database row. `portal.py:93-94`:
```python
def _superuser_emails() -> frozenset[str]:
    return settings.admin_emails_set
```
`apps/backend-rag/backend/app/core/config.py:998-1022`: `admin_emails_set`
reads `ADMIN_EMAILS` env var; **when unset, falls back to a hardcoded
3-address set**:
```python
_ADMIN_EMAILS_FALLBACK: frozenset[str] = frozenset({
    "zero@balizero.com", "asya@balizero.com", "antonellosiano@balizero.com",
})
```
(I did not — and cannot from this sandbox — verify the live Fly `ADMIN_EMAILS`
secret; this fallback matches CLAUDE.md §13's CRM RBAC admin list verbatim,
which is corroborating but not proof of the live env var. Flagged INFERRED
where noted below.)

Two branches now exist, and they produce **different outcomes for different
operators**:

### Branch B — operator email NOT in `admin_emails_set` (the common case)

`portal.py:154,157,215-221`:
```python
is_superuser = user_email in _superuser_emails()
if is_superuser:
    ...
# ---- Normal client path ----
if user.get("role") != "client":
    raise HTTPException(status_code=403,
        detail="This endpoint is only accessible to clients")
```
Any operator whose real role is `admin`/`team`/anything but `"client"`, and
whose email isn't one of the 3 superuser addresses, gets a **403** here. This
is the majority of Bali Zero staff — CLAUDE.md's own team roster names people
like Subhi/Krisna/Dea/etc. who are not in the 3-address admin_emails set.
Note this 403 fires on **role alone** — it is the correct, intended gate, and
it works exactly as designed for this population.

### Branch A — operator email IS in `admin_emails_set` (3 addresses)

`portal.py:157-179`:
```python
if is_superuser:
    as_client_raw = request.query_params.get("as_client")
    if not as_client_raw:
        # Superuser without as_client → fall through to normal lookup so
        # zero@ can still see their own linked profile if any.
        async with db_pool.acquire() as conn:
            own = await conn.fetchrow(
                "SELECT id, email, full_name FROM clients WHERE LOWER(email) = LOWER($1)",
                user_email,
            )
        if own:
            return {"client_id": own["id"], ..., "impersonating": False}
        raise HTTPException(status_code=422,
            detail="Superuser: select a client via ?as_client=<id>")
```

Since Step 3 established the frontend never sends `as_client` on a first
visit, **every** superuser lands in this exact fallback. It does a raw
`WHERE LOWER(email) = LOWER($1)` lookup against the `clients` table using
**the superuser's own staff email** — a table built for paying clients, not
staff. Two outcomes, and I measured which superusers actually hit which one
(read-only, count/id only, no PII values per rule 3):

```sql
SELECT COUNT(*) AS n FROM clients
WHERE LOWER(email) IN ('zero@balizero.com','asya@balizero.com','antonellosiano@balizero.com');
-- n = 1
SELECT LOWER(email) AS matched_admin_email FROM clients
WHERE LOWER(email) IN ('zero@balizero.com','asya@balizero.com','antonellosiano@balizero.com');
-- matched_admin_email = zero@balizero.com
SELECT id AS client_id FROM clients WHERE LOWER(email) = 'zero@balizero.com';
-- client_id = 68
```

- **`asya@balizero.com`, `antonellosiano@balizero.com`** — no row in `clients`
  → `422 "Superuser: select a client via ?as_client=<id>"`.
- **`zero@balizero.com`** — **one row exists**, `clients.id = 68` → the
  endpoint returns **`200`** with that row's data, no error, no impersonation
  flag set (`"impersonating": False` — this path is not even logged by
  `_log_impersonation`, `portal.py:97-119`, which only fires on the
  explicit `as_client` branch at `portal.py:199-205`).

`portal.py:1108-1165` (`get_profile` body) then runs the SELECT keyed on
`client["client_id"]` (68) and returns real, shaped fields:
`full_name, email, phone, whatsapp, nationality, passport_number,
passport_expiry, date_of_birth, gender, address, member_since, assigned_to`
— field **names** only, per rule 3 I did not read the values.

I also checked (counts only) whether this client row carries any of the
content the rest of the portal renders:
```sql
SELECT
  (SELECT COUNT(*) FROM practices WHERE client_id = 68) AS practices_n,
  (SELECT COUNT(*) FROM documents WHERE client_id = 68) AS documents_n,
  (SELECT COUNT(*) FROM portal_messages WHERE client_id = 68) AS messages_n;
-- practices_n=0, documents_n=0, messages_n=0
```
So `/dashboard`, `/visa`, `/documents`, `/messages` — every other route on
`portal.py` also gated by the same `get_current_client` dependency — would
return successful-but-empty payloads for this client_id. Only `/profile` (and
the header greeting, which reads `portalProfile.fullName`/`.email`) shows
populated, real fields.

---

## Step 6 — back at the frontend: what the operator actually sees

`apps/mouth/src/lib/api/client.ts:320-357` — a **global** 401 handler exists
that clears the token and hard-redirects. It only fires on exactly `401`.

`client.ts:373-403` — every other non-2xx (403, 422, 500…) is thrown as a
plain `ApiError` with `.statusCode` set, with **no special handling** — it is
just an exception.

`apps/mouth/src/app/portal/(authenticated)/layout.tsx:160-195` — the cookie
path wraps the whole thing in one `try { ... } catch { /* redirect to login */ }`
(`layout.tsx:190-195`) that does not branch on status code at all (unlike the
localStorage-path's careful `error.statusCode === 401` check at
`layout.tsx:149`). **Any** thrown error — 403 from Branch B, 422 from the
two empty-lookup superusers in Branch A — is swallowed identically and ends
at `router.replace(portalLoginHref(...))`. The 200 from `zero@balizero.com`'s
Branch-A hit is the only outcome that does **not** throw, so it is the only
one that renders the portal shell instead of redirecting.

---

## Answer to the framing question

- **(a) bounced to portal login** — for every operator whose email is not
  `zero@balizero.com`. This includes the two other superuser addresses
  (`asya@`, `antonellosiano@`) — they get bounced too, just via a 422 instead
  of a 403, an implementation detail invisible to the user, who just sees a
  spinner and then the login page.
- **(d) a portal populated with data** — only for `zero@balizero.com`
  specifically, today. The data shown is **that operator's own client-linked
  row** (client_id 68) — a self-view, not another named client's data — but
  it is real personal-info-shaped content (name/email/phone/passport fields
  if populated) served through the **client-facing portal chrome**, reached
  with zero explicit consent step, zero `as_client` selection, and zero audit
  log entry (the audit call only exists on the explicit-impersonation branch).
  The rest of the portal (dashboard/visa/documents/messages) is empty because
  that client row has no linked practices.

No branch produces (b) a dedicated error page or (c) a genuinely empty-but-
rendered portal shell with no identity resolved — every non-200 response is
funneled through the same `catch {}` into a full redirect before any content
paints.

---

## Source of cause (not the symptom)

Two code locations, **one belief in common**:

1. **`proxy.ts:157-159` (`hasPortalSession`)** treats *cookie presence* as
   sufficient to let a request reach the portal shell and its client-side
   auth logic. It was written this way on purpose — real validation is
   deferred to the API layer — but it means the edge gate contributes zero
   identity information: it cannot distinguish "no session" from "someone
   else's valid session" from "an operator's valid session." Reproduced live.

2. **`portal.py:157-179` (superuser fallback in `get_current_client`)**
   treats *"this email exists as a row in the `clients` table"* as
   sufficient authorization to view that row through the client portal —
   with no distinction between "an admin explicitly chose to impersonate
   this client" (which the code elsewhere audits, at `portal.py:199-205`)
   and "an admin's own staff email happens to coincide with a client
   record." It was written as a convenience ("so zero@ can still see their
   own linked profile if any") but the mechanism it uses — bare email
   equality against a table of a different population (clients, not staff)
   — is presence-of-a-row, not proof that this view was intended.

Both bugs are instances of the same underlying decision: **the system
repeatedly substitutes "is this identity known/present somewhere" for "is
this identity authorized for this specific view,"** once at the edge
(cookie exists) and once in the backend (email exists in an unrelated
table). Neither individually is catastrophic — the edge gate is cheap-and-
defers-on-purpose, and the backend gate does correctly wall off the other
two superusers and every ordinary operator — but the second one is live,
unaudited, and currently fires for the one email that matters most
(`zero@balizero.com`, the account named throughout this repo's own
CLAUDE.md as the primary admin/owner identity).

## What I did not verify (explicitly out of scope / could not verify)

- The live value of the `ADMIN_EMAILS` Fly secret for `nuzantara-rag` — I
  read only the fallback in `config.py`; I did not query Fly secrets (out of
  scope for a read-only code+DB simulation, and not a `*.balizero.com` GET
  probe). If `ADMIN_EMAILS` is set to something broader in prod, Branch A
  applies to more than 3 emails, and this specific self-lookup collision
  would need re-checking against whichever emails are actually configured.
- I did not attempt any request with a real/forged valid JWT (rule 2
  forbids it) — every backend-auth claim above is traced from the decode
  logic in code, corroborated by the two live 401s for a syntactically
  invalid token, not reproduced end-to-end with a genuine session.
- I did not check whether `zero@balizero.com`'s `clients.id = 68` row is a
  deliberate seed/test fixture or an artifact of some historical onboarding
  flow — that provenance question is orthogonal to the mechanism finding
  above and would need a separate, non-code investigation.

## Adversarial review

Two passes, in this order, and the chain matters more than the verdict.

**Pass 1 — same-family.** A Sonnet lane re-opened every file:line cited here and re-ran every probe,
producing `s1-operator-enters-portal.refutation.md`. Its own cross-family seat (`qwen`) timed out
twice and it correctly recorded that as *unavailable* rather than inventing agreement. So pass 1 was
Sonnet grading Sonnet — the precise weakness this organism has already been bitten by, and it is why
pass 2 exists.

**Pass 2 — cross-family: Codex `gpt-5.6-terra`**, run twice independently (once by this session, once
by a separate lane) on fresh context. Objections against the claims in *this* file:

1. **Real defect.** "*no impersonation flag and no audit entry*" — the absence of an
   impersonation-specific audit call does not establish the absence of auditing; `update_profile()`
   can still create `notification_alerts` / `portal_messages` rows. The narrow claim (no
   *impersonation* audit event) holds; the broad one does not.
2. **Overstated.** Calling the severity "high" — self-access to the admin's own client row is not
   cross-tenant access or horizontal privilege escalation. This file's own text already concedes
   most of that, and the heading should match the body.
3. **Structural, and the most important of the three.** Re-running the commands a finding cites can
   falsify its *citations*; it cannot validate the *causal and severity conclusions* drawn from
   them. Both reviewers reached this independently. Read every verdict in the refutation file at
   that strength: source review plus unauthenticated curl, never an authenticated request through
   the branch in question.

Nothing here was withdrawn. The findings are recorded as measured, with the ceiling on what the
method can establish stated rather than implied.
