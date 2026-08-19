---
date: 2026-08-19
domain: compliance
client_case: none
sources:
  - apps/mouth/src/proxy.ts (read this run)
  - apps/mouth/src/app/portal/(authenticated)/layout.tsx (read this run)
  - apps/mouth/src/app/(workspace)/layout.tsx (read this run)
  - live read-only GET probes against my.balizero.com / kita.balizero.com (run this run)
adversarial_review: codex
---

# CRM ↔ Portal — orchestrator live probes (iteration 1)

Scope: the operator↔client persona alternation across `kita.balizero.com` (workspace/CRM) and
`my.balizero.com` (client portal). Everything below was **reproduced this run**; each item carries
the command and its actual output, or the file:line opened. Items I checked and found **sound** are
recorded too — a clean check is a result.

## Structural ground (verified)

One Next.js app — `apps/mouth` — serves both personas. The domain router is
`apps/mouth/src/proxy.ts` (568 lines).

- `proxy.ts:78` — `const PORTAL_SESSION_COOKIE = "nz_access_token"`. This is the **same** httpOnly
  SSO cookie the operator workspace uses, scoped to `.balizero.com` and therefore sent to *both*
  domains. One token, two mutually-exclusive personas.
- `proxy.ts:157-159` — `hasPortalSession()` = `Boolean(request.cookies.get(PORTAL_SESSION_COOKIE)?.value)`.
- Operator role gate lives **client-side**: `(workspace)/layout.tsx` loads the profile, then
  `if (profile?.role === "client") window.location.replace(portal)`.
- Client gate lives **client-side**: `portal/(authenticated)/layout.tsx` runs a two-path auth
  (localStorage fast path, then cookie fallback via `api.portal.getProfile()`), behind a
  `setTimeout(checkAuth, 100)`.
- Route counts: 29 portal pages, 66 workspace pages, 37 API routes.

## F1 — The portal edge gate measures presence, never validity — REPRODUCED

```
curl -o /dev/null -w "%{http_code} %{redirect_url}" https://my.balizero.com/portal
  -> 307  https://my.balizero.com/portal/login-upgraded?redirect=%2Fportal

curl -o /dev/null -w "%{http_code}" -H "Cookie: nz_access_token=garbage" https://my.balizero.com/portal
  -> 200   <title>Client Portal | Bali Zero</title>   (43 129 bytes)
```

A cookie whose literal value is `garbage` passes the gate; no cookie does not. The differential is
the proof: the gate reads presence.

**Source of the cause.** The gate's own purpose is stated in the code (`proxy.ts`, portal block,
verbatim): *"Stop anonymous deep links before the client layout calls the profile API. Besides
avoiding a visible loading flash, this prevents the expected 401 from being reported as a browser
console error."* All three goals are defeated by a cookie that is **present but not valid**. The
first draft justified this as "the ordinary daily state of every returning client, since JWTs expire
while a cookie outlives them" — **that premise is backwards.** `cookie_auth.py` sets the cookie's
`max_age` from `settings.jwt_access_token_expire_hours` when no explicit lifetime is passed, so by
default the cookie and the JWT expire together. The branch demonstrated here is a cookie present and
not accepted; how often real clients land in it was never measured, and the severity argument that
rested on "every returning client" does not stand.
The guard therefore covers the case that rarely happens (no cookie at all) and fails open on the
case that always happens. It is not a data leak — the backend 401s every API route independently —
it is a guard whose protected population is close to empty in normal operation.

## F2 — Soft-404 on the portal domain — REPRODUCED

```
curl -w "%{http_code}" -H "Cookie: nz_access_token=garbage" https://my.balizero.com/portal/zzz-does-not-exist
  -> 200   <title>Page not found | Bali Zero</title>
```

A page that says "Page not found" is served with HTTP **200**. Any liveness probe, uptime monitor or
synthetic check that asks *"does it return 200?"* reads this as healthy. Same class as the scars
where a proxy signal is trusted over content.

## F3 — Unknown paths on the operator domain render a public-styled article page — REPRODUCED, scoped

```
curl -w "%{http_code}" -H "Cookie: nz_access_token=garbage" https://kita.balizero.com/zzz-does-not-exist
  -> 200   <title>Zzz-does-not-exist Insights | Bali Zero</title>
```

An unknown path on the **internal** domain falls through to the `(blog)/[category]` catch-all and
renders a public-styled page titled with the typo, capitalised. `proxy.ts` names this exact symptom
twice in its own comments and cures it — but by **enumeration**: `RETIRED_APP_ROUTES` and
`APP_SUBDOMAIN_ROUTE_MAP` list the known-bad paths. Any path not on those lists still falls through.
The instances were cured; the fall-through that generates them was not.

**Scope, honestly.** SEO is defended — the response carries `x-robots-tag: noindex, nofollow` and a
`<meta name="robots" content="noindex">`. This is an operator-experience and monitoring defect, not
an indexing leak.

**Challenged, then re-measured — and the challenge made the finding sharper.** An adversarial review
objected that this finding contradicts the current source: `(blog)/[category]/page.tsx:40` and
`layout.tsx:137` both call `notFound()` for an unknown category, and `layout.test.tsx:53` is a
`guilt:`-prefixed test asserting exactly that. That objection is correct about the repository. It is
wrong about production, and the difference is the point.

Re-probed live, defeating the CDN with paths never requested before — the first probe had returned
`x-vercel-cache: HIT`, so it could not settle anything:

```
GET https://kita.balizero.com/qqq-mai-sondato-prima-8819   -> 200  x-vercel-cache: MISS
    <title>Qqq-mai-sondato-prima-8819 Insights | Bali Zero</title>
GET https://kita.balizero.com/zzz.dotted.path.test         -> 200  x-vercel-cache: MISS
    <title>Zzz.dotted.path.test Insights | Bali Zero</title>
```

Two different path shapes, both a genuine cache MISS, both still rendering the capitalised-typo
article page. **So the guard exists, is covered by a passing test, and does not participate in
production.** Whether the deployed build predates it or the route shape never reaches it is not
established here and is worth its own look — but the finding stands as written about live
behaviour, and it has become an instance of this investigation's own meta-pattern rather than a
counter-example to it: a control whose existence and whose test both read as protection, while the
surface it protects behaves as though it were absent. It was found only because a reviewer said the
finding was wrong.

## F4 — Real workspace routes are NOT affected — CHECKED, SOUND (self-correction)

My first reading of `kita.balizero.com/dashboard` (HTTP 200, public marketing `<title>`) suggested
operators were being served marketing content. Measuring the **body** instead of the title refutes
that: `/dashboard`, `/clients`, `/inbox` all contain the `workspace` marker and a `Loading` state,
and contain **zero** marketing markers (`Get in touch`, `Our Services`, `Book a consultation` all 0).
They serve the workspace shell, which then bounces client-side. The public title was root metadata
leaking, not marketing content. F3 applies only to paths that do not exist.

## F5 — 65 of 66 workspace pages wear the public identity — REPRODUCED

```
find "(workspace)" -name page.tsx                                  -> 66
grep -rl "export const metadata\|generateMetadata" "(workspace)"   ->  1
```

One workspace page declares its own metadata. The other 65 inherit the root layout's title, so the
operator's browser tabs, history entries and bookmarks for the internal CRM all read
*"Bali Zero | Visa, Business & Immigration…"* — the marketing identity. `/inbox` is the one exception
(`<title>Inbox — Kita | Bali Zero</title>`), which proves the mechanism rather than the intent.

**Source of the cause.** `(workspace)/layout.tsx` is `"use client"`, and a client component cannot
export `metadata`; per-route metadata therefore has to be added deliberately to each page, and was
added once.

## F6 — Cross-persona path redirects are permanent-status but revalidated — CHECKED, SOUND

Every non-`/portal` path on the portal domain 301s to the public domain, and portal paths on the app
domain 301 to the portal domain:

```
my.balizero.com/dashboard        -> 301 -> https://balizero.com/dashboard
kita.balizero.com/portal/matters -> 301 -> https://my.balizero.com/portal/matters
```

A permanent redirect that a browser caches would be a durable trap — a client who mistypes once
keeps the detour after the route is fixed. **It is not one:** both responses carry
`cache-control: public, max-age=0, must-revalidate`. Checked and clean; recorded so the next session
does not re-raise it.

## F7 — Shared path vocabulary across personas — REPRODUCED (consequence pending)

Both personas own routes with the same suffix: `/process`, `/process/[id]`, `/lkpm`, `/lkpm/submit`,
`/settings/notifications`, `/profile`. Live crossings:

```
my.balizero.com/process     -> 301 -> balizero.com/process     -> 200 kita.balizero.com/process
my.balizero.com/lkpm        -> 301 -> balizero.com/lkpm        -> 200 balizero.com/lkpm
my.balizero.com/clients     -> 301 -> balizero.com/clients     -> 200 kita.balizero.com/clients
                              (NOT shared vocabulary — see correction below)
```

A path typed or pasted on the wrong domain does a three-surface round trip (portal → public → app)
and lands on a surface the sender did not intend.

**Corrected by a third seat.** A cross-family reviewer (Kimi K3, independent of the two Codex runs)
checked the claimed shared paths one by one and found that **four of the five hold and `/clients`
does not**: the portal's authenticated routes are `companies`, `company`, `billing`, `chat`,
`family`, `lkpm`, `matters`, `messages`, `partner` — there is no `/clients` among them. Re-measured
directly against `apps/mouth/src/app/portal/(authenticated)/` and confirmed.

The redirect chain itself is real and was reproduced; what was wrong is the label. `/clients` is not
a collision between two vocabularies, it is a path **only kita owns**, which the portal domain still
forwards to. That is arguably the more interesting half — the round trip does not require both
personas to claim the name — but it is a different claim from the one the section made, and the
section made it on an example that does not support it. Neither Codex pass caught this; it took a
seat from a third family reading the route list rather than the argument. Whether `/process/45` on kita and
`/portal/process/45` denote the *same record* is delegated to the S5/S6 simulation lanes; if they
do, an operator pasting their own address bar to a client sends them to a page that will bounce
them, and if they do not, the same number means two different things on the two surfaces.

## Meta-pattern (provisional, iteration 1)

Every item above is the same decision made in four places: **the boundary judges a cheap proxy, and
the real identity check is deferred to the browser, after render.** Cookie *presence* stands in for
session validity; path *shape* stands in for route existence; HTTP *200* stands in for "the page
exists"; the root layout's *public* identity stands in for the operator's. The system is
correct-after-render — it shows something first and fixes it a moment later — and every snag in the
persona alternation is a moment of that window being visible to the wrong person.

This is provisional: it is the orchestrator's reading of its own probes, and it has not yet faced
the cross-family refutation lanes.

## Not a finding — checked and sound

- Backend authorisation is independent and holds: every API route returns 401 without a valid token,
  including a garbage cookie. No data was reachable in any probe above.
- The 401 on API routes is a **catch-all**: `/api/definitely-not-a-real-route-xyz123` also returns
  401, so a 401 proves nothing about route existence. Recorded because my own first probe misread
  it as route discovery.
- SEO defence on the internal domain is in place (`x-robots-tag: noindex, nofollow`).

## Method note

All probes were read-only `GET`, unauthenticated, using a synthetic cookie value. No write of any
kind was issued against either production surface, and no client PII appears in this file.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (OpenAI family, effort medium, read-only sandbox), run on the file
directly and instructed to default to "the claim is defective". Nine objections raised; none were
withdrawn on re-reading, and the four listed here narrow claims in the text above. They are recorded
rather than silently edited, because the pattern they share is the finding.

1. **BLOCKER, accepted.** "*a cookie that is present but expired … the ordinary daily state of every
   returning client*" — the probe sent the literal string `garbage`, not an expired JWT. That
   demonstrates the *unauthenticated-with-a-cookie* branch; it does not establish frequency, cookie
   lifetime, or that this is the ordinary state of any client, let alone every one. Read the claim as
   scoped to the branch demonstrated.
2. **BLOCKER, accepted.** "*covers the case that rarely happens … fails open on the case that always
   happens*" — rarely/always are population claims and no session telemetry was collected. The
   behavioural difference between the two branches stands; the traffic distribution does not.
3. **BLOCKER, accepted.** "*The other 65 inherit the root layout's title*" — a `find` count plus a
   grep for exported metadata does not establish the runtime title of 65 routes; metadata can come
   from a layout or template. This needed a route manifest or HTTP sampling and got neither.
4. **BLOCKER, accepted.** "*both responses carry `cache-control: public, max-age=0,
   must-revalidate`*" therefore the 301 "is not a trap" — `must-revalidate` constrains reuse after
   staleness; it is not a guarantee that no browser retains a 301. The headers are reported
   correctly, the absolute conclusion drawn from them is not supported.

Also raised and accepted as over-broad wording rather than wrong findings: "any liveness probe …
reads this as healthy" (many monitors assert on body or final URL), "any path not on those lists
still falls through" (one synthesised path proves that path), and "every API route returns 401"
(the probes cannot cover *every* route). The section framing all four items as "the same decision
made in four places" is a narrative generalisation — cookie validity, route resolution, HTTP
semantics and metadata are distinct mechanisms.

### Third seat, and one thing its agreement does not buy

**Kimi K3** (Moonshot, flat subscription) reviewed this file on fresh context, with repo read access
and its own live `curl` against both production hosts — independent of the two Codex passes.

| Claim | Kimi verdict | How |
|---|---|---|
| F1 — cookie-presence-only portal gate | CONFIRMED | re-read `hasPortalSession()`, re-ran both curls: no cookie → `307`, junk cookie → `200` |
| F2 — soft-404 on `/portal` | CONFIRMED | `GET /portal/zzz-does-not-exist-xyz` → `200`, body contains "not found" |
| F3 — unknown kita path renders a public article shell | CONFIRMED | its own curl, `x-robots-tag: noindex, nofollow`, slug-built title |
| F5 — 65/66 workspace pages inherit the public title | "CONFIRMED" — see below | re-ran `find … page.tsx` → 66 and `grep -rl "export const metadata\|generateMetadata"` → 1 |
| F7 — shared path vocabulary | PARTIALLY CONFIRMED | 4 of 5 hold; `/clients` does not (corrected above) |

**F5's confirmation is worth less than it looks, and saying so is the point.** Codex's objection to
F5 was not that the counts are wrong — it was that a file count plus a grep for exported metadata
does not establish the *runtime* title of 65 routes, because metadata can arrive from a layout or a
template. Kimi then re-ran the same two commands and got the same two numbers (66 and 1, which I
also re-measured myself: identical). That is a second seat reproducing the **method**, not answering
the objection to it.

Two independent families agreeing tells you nothing about a defect that lives in the method both of
them used. This organism already has a scar for exactly that shape — same-family agreement
certifying seven false-clean results out of eight, because the agreement measured transcription
fidelity rather than truth. Cross-family does not immunise you against it; **method-diversity is the
property that matters, and it is not the same property as seat-diversity.** F5 therefore stands as a
claim about the source tree, where the evidence is direct, and remains unproven as a claim about
what 65 routes actually render — which would take an HTTP sample or a route manifest, and got
neither, twice, from two different families.
