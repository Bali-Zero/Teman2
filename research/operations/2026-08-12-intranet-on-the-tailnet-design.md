---
date: 2026-08-12
domain: operations
client_case: none (internal infrastructure)
adversarial_review: codex
sources:
  - live measurement, nuzantara-rag (Fly) — anonymous HTTP probes, status + size only
  - live measurement, Pro (100.107.22.111) — listener table, process cwd, uptime
  - live measurement, Postgres prod via nuzantara_readonly — aggregate counts only
  - apps/backend-rag/backend/middleware/hybrid_auth.py (public-endpoint bypass)
  - apps/backend-rag/backend/app/auth/public_endpoints.py (registry, 75 entries)
  - apps/backend-rag/backend/app/intake_review_reader.py (shared-secret RBAC)
  - apps/backend-rag/backend/app/modules/identity/router.py (login response shape)
  - apps/mouth/src/middleware.ts (hostname fences, workspace gate)
  - infra/tailscale/policy.hujson (tag:team-device initiates nothing)
  - research/operations/2026-07-17-mutating-routes-authz-ledger.md (prior audit)
discovered_by: session (M5), multi-seat design pass + grounded workflow
---

# An intranet on the tailnet: what to build, and what the question turned out to be

## Why this document exists

The question asked was "could we build an intranet?" — after the narrower one,
"what is having the team inside the tailnet actually for?". The answer is yes,
and the design below is deliberately small, because measuring the two sides of
the trade turned the question into a different one.

The design was produced by three independent proposals judged along three
lenses (operational, security, labor), with the conductor overriding four of the
judges' verdicts where the evidence contradicted them. It was then refuted as a
whole by a cross-family seat — see [Adversarial review](#adversarial-review),
which changed sixteen of its claims and moved one phase.

**The finding that reframed everything is not architectural.** Measured on the
production CRM: **107 of 822 practices carry a renewal date and 715 do not**;
**none of the 107 dated ones falls within the next 60 days**; `missing_documents`
is empty on **all 822**; **248 of 1,244 active clients have no Drive folder**; and
**32 of 124 open practices have gone untouched for 30+ days**.

Two honest caveats on that paragraph, because it carries the whole plan. A
renewal pipeline **exists and is unusable as a queue** — 107 dated rows is not
zero, and "none within 60 days" could also be seasonality or expired dates
excluded by the query rather than an empty future. And **`missing_documents`
empty on all 822 has two readings** — the field is never populated, or every
practice genuinely lacks nothing — and this document did not establish which.
Settling that is the first task of Phase 1, not an assumption inside it.

What survives the caveats is enough: a CRM in which 87% of practices have no
renewal date cannot answer "what expires this month", and an intranet placed over
that state would be a UI on top of an unanswered question.

## The thesis

**One door, on one dedicated port, into one machine.** Behind it goes only what
cannot be hosted: the sovereign-data surfaces (intake OCR documents, the raw
WhatsApp mirror) that must not leave Pro, and the internal tools whose only
missing part is a login. Everything the team touches hourly stays exactly where
it is, on Vercel and Fly.

*(Precision the first draft lacked: "client PII must not leave Pro" is not true
of the CRM as a whole — its data plane is on Fly, and the client-detail endpoint
serves passport numbers from there. The sovereign set is the intake/mirror
surfaces, named above.)*

The bet is asymmetric. Both sides were measured, but **not in the same unit**,
and the comparison is weaker than the first draft implied:

| side | what was measured | unit |
|---|---|---|
| the tailnet room | 11 `review_pending` intake items · 38 drafted carousels in one queue · 4 tools bound to loopback | instantaneous inventory |
| the hosted floor | 14 of 24 staff rows with a login in the last 7 days, 17 in 30 | observed people per window |

Inventory does not measure demand and a login does not measure frequency, so this
table establishes an order of magnitude, not a ratio. The four loopback tools
are **not reachable from another host**; whether anyone uses them locally or over
a tunnel was not measured, so "nobody can reach them" was withdrawn.

And the host we would be moving onto: **15 reboots in 54.3 days** (mean 3.9 days;
one 51 minutes before the survey), **91% disk**, **1.73 GiB free RAM at the time
of reading**. Those are boot events, not characterised downtime — and this
document also lists *why Pro reboots* as unknown, so it cannot claim the move
"would subtract value". The defensible statement: **moving a daily-use workspace
there would add an availability risk whose size we have not measured**, onto a
host that reboots roughly weekly for reasons nobody has diagnosed. That is
sufficient reason not to do it, and it is a smaller claim.

## The four overrides

**The door goes on its own port — but not on the port-first proposal's design.**
Tailscale ACLs are host:port and cannot express paths. The first draft concluded
that port separation is therefore "the only mechanism that can fence a laptop
from `/term → ttyd -W zsh`". That was wrong as stated, and the refuter was right:
**it is the only fence expressible as a pure host:port network rule.** Removing
the Serve route, or authorising in the application, or Tailscale Grants with
app capabilities, are other mechanisms — we simply are not relying on them, and
the route removal is in fact a second control we *do* apply ("nothing on `:443`"
below). A port number is one line to graft; the guard repairs the winning
proposal carries are not.

**No tier that authenticates nobody.** One proposal's front door
"AUTHENTICATES NOBODY, by design", admitting tools on the CI-checked criterion
"holds zero client rows". That criterion measures **confidentiality** while the
risk on those tools is **authority and attribution**: one mutates editorial
state and shells out via `subprocess`; another is a control plane. A tailnet node
*is* an authenticated principal — it is simply not a **person**, and it carries no
attribution. (The first draft also said device access is "revocable only by
untagging a laptop"; that is false — device removal, an ACL edit and user
revocation all exist. The real objection is attribution, not revocability.)

**Phase order reversed.** The winning proposal opened with a 3–4 day ops board
for an audience of two, gated on a console action, and deferred a 1–2 day fix
that stops staff clicking sidebar links that 404. The renewal-pipeline finding
above becomes Phase 1 instead.

**The cookie mechanics force a local login — and the first draft's version of it
does not work.** `nz_access_token` is httponly on a `.balizero.com` cookie domain
and the access token lives one hour, so a page served from
`nuzantara.tail461666.ts.net` will **never** receive the team's existing session:
JavaScript cannot read it and a top-level navigation cannot carry a bearer
header. This was scored against one proposal while hitting the winner's own
intake-review phase identically — neither noticed.

The constraint is real: a second issuer against a divergent roster (**31 rows on
Pro, 24 on Fly**) signing with the shared `JWT_SECRET_KEY` would turn the
sovereign path into a back door to the public API. But the proposed cure — "mint
a local-origin cookie under a separate signing key and a distinct audience" — is
**incomplete, and would not work as written**. Verified in this session:

- `apps/backend-rag/backend/app/intake_review_reader.py:14` states the reader
  uses the **same `HybridAuthMiddleware` + `JWT_SECRET_KEY`** "so RBAC is
  byte-identical to Fly". A cookie signed under a *different* key is therefore
  **rejected by the tenant**. The design needs an explicit
  **identity-translation contract** between door and tenant — a signed internal
  header, mTLS, or a modified verifier — plus anti-spoofing on it. That contract
  does not exist yet and is the door's central unfinished piece.
- `apps/backend-rag/backend/app/modules/identity/router.py` returns
  `token=token` **in the login response body** and sets a cookie upstream. The
  door must be *required* to discard the upstream body token, `Set-Cookie` and
  CSRF token before answering the browser. Otherwise the barrier between the
  local issuer and the public API holds only by accident of implementation.
- A `aud` claim is not a control until the local verifier is **required** to
  check algorithm, issuer and expected audience. As written, the separation
  rested on the distinct key alone.

**Declared cost, unchanged:** new logins on the tailnet require Fly to be
reachable. Law 6 offline operation is **partial in v1** — existing sessions
survive a disconnection, new ones do not. **And that cost has a consequence the
first draft missed:** if sessions survive Fly being unreachable, then disabling a
user on Fly **cannot** invalidate them. Per-user revocation and a maximum session
TTL are therefore **prerequisites of the door**, not a later phase — see the
build order, where they moved.

## Build order

| phase | what | estimate |
|---|---|---|
| **0** | The three removals — the price of admission | half a day |
| **1** | The floor: settle the `missing_documents` semantics, then "my week" + the hostname fence | 5–7 days |
| **2** | The voice: a heartbeat read route that does not live on Pro | 1–2 days |
| **3** | **Prereqs for the door**: enrollment, one narrow ACL accept for the new port with its deny tests, per-user revocation, max session TTL, the offboarding runbook half | 2–3 days |
| **4** | The door + its identity-translation contract + its first tenant (one queue, one named human) | 5–7 days |
| **5** | The board, read-only, audience of two — stated plainly | 2–3 days |
| **6** | The PII transport: intake reader off Cloudflare onto the door | 2–3 days + a parallel week |
| **7** | A second OCR home — gated on physical facts, never on M5 | 2 days |

Two orderings are load-bearing and both came from the refutation. **Revocation
precedes the door**, for the reason above. And **enrollment plus the ACL accept
precede it too**, because `infra/tailscale/policy.hujson:80-81` says in its own
comment that there is "deliberately NO rule with `tag:team-device` as src, so it
can initiate nothing inside the tailnet" — so *every* phase behind the door needs
that grant, not only the PII transport. The first draft said enrollment was
required only at the last one.

**Phase 0 delivers nothing a human touches, and that is not dressed up.** It is
three interventions, not two: the public geo endpoint (**done**, below), the
WhatsApp dashboard bind (**open**), and Qdrant `:6333` — off the tailnet bind or
given a key (**open**). It must not be sequenced behind any design.

**Phase 1 is the whole point:** a "my week" page whose every empty count is a
named hole. The behavioural bet — that rendering *"you have N practices with no
renewal date"* is what gets the column filled — is a **hypothesis, not a
result**; it needs a named owner, a target and an exit criterion, and the human
backfill work is explicitly **outside** the 5–7 day engineering estimate:
`operator[business]`. Plus the fence: the zantara hostname restricted to `/`,
`/chat`, `/login`, `/api` by copying the portal-domain fence that already exists
in the same middleware file, and the workspace gate moved off the client-side
profile check so ten staff shells stop answering 200 anonymously. **The zantara
hole was found by measuring one host — the other five are unmeasured, not clean.**

## What we deliberately do not build

- **Not moving kita / my / prime / zantara inside.** Four hostname views of one
  Vercel deployment; the data plane stays on the public Fly backend anyway, so
  the exposure bought back is page shells, not client data.
- **No shared API key for any internal tool.** A key mapped to `role=admin` is
  synthesised into an identity no human owns and **satisfies the CRM admin
  check** (`is_crm_admin` accepts `role in ("admin", ...)`), defeating even the
  strictest row scoping in the repo.
- **Nothing mounted on `:443`, and ttyd is not re-armed.** "It 502s today" is an
  accident of a reboot, not a control — but removing the route *is* one, and it
  is the second fence referred to above.
- **The tailnet is never the SOLE authorization, and never a human-identity
  decision**, and never an Art. 56 transfer basis. (The first draft said "never
  an authorization decision", which contradicts a design that uses tailnet policy
  to authorize source, host and port.) No internal assistant over client
  conversations — that is the obvious next feature and precisely what would
  widen the known-open chat-PII gap.
- **No local staff assistant.** Its own proposal text certifies it would answer
  worse than what staff can already reach, on a host with 1.73 GiB free RAM
  behind a 23.4 GiB resident model.
- **No Postgres replication to Mini** (10–15 days, gated on physical facts nobody
  can measure). Note the corrected reasoning: the **11-item queue depth justifies
  deprioritising the UI, not the database resilience strategy** — resilience is
  decided by a written RPO and a rehearsed restore, which is the one thing we do
  extract, detached from replication and not requiring Mini to be alive.
- **No self-hosted mail/calendar/documents**, no rebuild of
  `knowledge.balizero.com` (live, staff-gated, source deleted from the repo — so
  "moving it inside" means rewriting it), **no Grafana** (29 config files, zero
  exporters running), **no ninth authorization allowlist**.

## What becomes load-bearing

1. **Pro** — for document review and the tool shelf. It already is; the design
   rule is that we only serve things a Pro outage already darkens. But the PII
   transport phase removes the Cloudflare fallback, which is why the parallel
   week is not optional.
2. **The door** — the most privileged network position in the house. As a
   loopback-reaching process it could otherwise dial `:18795`, `:5432`, `:6379`,
   `:6333`, `:7790`, `:3333`, `:18789`, `:11434`. Dedicated UID that does not own
   `~/.nuzantara-secrets.env`, strict `enum→(host,port)` map, no user-controlled
   host or port, no redirect following, no forwarding of client-supplied
   `Host`/`X-Forwarded-*`. **Stated limit:** that map constrains SSRF *through
   the intended path*; it does not contain a **compromised process**, which can
   open sockets directly. Containing that needs OS-level isolation or egress
   control, or authentication on each upstream — none of which this design has.
3. **Tailscale itself** — a coordination-plane outage does not break established
   tunnels but does break new device handshakes; node-key expiry becomes an
   availability risk to manage consciously, never to silently disable.
4. **The shared `JWT_SECRET_KEY`** — a routine rotation becomes a fleet-wide
   logout event, hence a fingerprint check in `/healthz` instead of letting a
   mismatch present as an intermittent logout loop.

## Who loses reach, and when

- **Phase 0:** the tailnet-reachable WhatsApp dashboard and the open Qdrant stop
  answering from M5. The first draft asserted the owner is "the only current
  user" of both — **withdrawn**: no access log was consulted, and node ownership
  is not usage evidence. What is known is that the team is not yet enrolled, so
  the population of possible users today is the owner's own devices plus
  whatever reaches Pro's LAN.
- **The fence:** anyone with a bookmarked staff route on `zantara.balizero.com`
  gets redirected.
- **The door:** `pro:3333` (NEXUS OSINT) is written into the deny tests, which
  defers any plan to give the team OSINT access.
- **After the PII transport's parallel week:** an unenrolled device cannot review
  intake. Note this is not "the one task requiring enrollment" — every phase
  behind the door requires it, per the ACL fact above.
- **The largest loss is not schedulable here:** repairing `can_view_all_clients()`
  narrows the unified inbox, the wa-mirror message list, the action queue and the
  DLQ purge for everyone who uses them. *(How many people that is, and for how
  long, is not established: the measured denominators are 24 staff rows, 17 with
  a login in 30 days, 14 in 7 — "sixteen laptops" is a plan, not a measurement,
  and no measurement shows all of them used those four surfaces for months.)*
  Held out of Phase 0 on purpose. It lands only with a read-policy ruling, a
  written comms line, and an admin override — **and if it lands unannounced it
  will be the reason the intranet is remembered badly, or worse, the reason
  someone reverts the predicate and restores the silent disarm permanently.**

## What is not yet known — stated, not papered over

- **The value of `OCR_ALLOW_CLOUD_VISION`** — a set, write-only Fly secret.
  `OLLAMA_URL` is unset there and the image installs no Ollama, so on Fly every
  OCR call reaches the gate and one unreadable boolean decides whether a staff
  passport upload is refused or forwarded to Google. Settle it by posting a
  **synthetic non-PII image** to the preview endpoint and reading the answer.
  Do not design either branch first.
- **The semantics of `missing_documents`** — empty on all 822 rows means either
  "never populated" or "nothing missing anywhere". Phase 1 settles it before
  building on it.
- **Whether Tailscale Serve gives the door any identity.** Two readings
  conflict: one measured `Tailscale-User-Login` present and verified for a
  user-owned device; another found no such symbol in the installed 1.98.10
  binary. The refuter offered a reconciliation — that Serve adds the header for
  user-owned devices and not for tagged ones — which would make both readings
  correct and would also mean the header is absent for exactly the devices this
  design enrolls. **That reconciliation was not verified against the installed
  binary in this session and must not be cited as fact.** Nothing in this design
  depends on the header, and the door strips the prefix inbound.
- **Whether the `:443` control plane enforces its token on action endpoints**,
  and whether Qdrant `:6333` is write-capable from the tailnet. Both probed
  GET-only.
- **Mini, entirely** — listeners, model roster, and above all whether it is on a
  genuinely separate power circuit and upstream ISP. The two endpoint readings
  taken are in different /24s, so it is not even stable, and a second router on
  the same mains is indistinguishable from here. `operator[physical]`.
- **What the team actually uses for mail, calendar and documents.** Three live
  sidebar links 404. This is a question for the humans and **it matters more
  than anything in this plan.**
- Also open: whether the other five hostnames leak the workspace the way zantara
  does; which project serves `knowledge.balizero.com`; whether the 20 kita
  workspace routes are working tools or scaffold (this materially changes how
  much intranet already exists); whether `assigned_to` holds emails or names in
  production (**21 measured rows are non-email — rows, not necessarily 21
  people, and a lockout is inferred, not proven: it needs a join on distinct
  assignees against the active roster and the effective policy**); what the
  Cloudflare Access policy behind the 403s actually is; how many production API
  keys carry `role=admin`; whether the `:8443` Funnel is the live Meta webhook or
  only the reply bridge; and **why Pro reboots** — 15 boots, zero panic files,
  empty shutdown-cause log.

## The one decision that is not the session's

**The read policy.** `CLAUDE.md` §13 says a team member sees only `assigned_to`
rows; the code documents the opposite for client read as deliberate, and the
detail endpoint returns **passport numbers and dates of birth to any team member
for any of 1,244 clients**. An intranet's entire value is making that one click
closer, which is exactly why it must not be accelerated before the ruling.
Legge 5.

## Phase 0, as executed

Half of Phase 0 shipped the same day this document was written, because it was a
live leak and not a design question:

**`GET /api/dashboard/map/clients/geo` answered an anonymous request from the
public internet with HTTP 200 and 500 active-client rows** (66,229 bytes; keys
per row `address, email, full_name, id, phone, status`). The cause was a
**prefix** entry `/api/dashboard/map/` in `PUBLIC_ENDPOINTS`: the auth middleware
treats a registry match as *skip auth entirely*, so all 7 routes on that router
inherited a zero-credential bypass.

Two things about why it survived every gate are worth more than the fix:

1. `test_route_authz_coverage.py` accepts membership in `PUBLIC_ENDPOINTS` as a
   valid authorization posture — so **the blanket prefix WAS the four POSTs'
   declared posture**. The guard was satisfied by the very thing that was the
   vulnerability. Measured: that gate passes on `main` and only goes red once the
   prefix is removed.
2. The 2026-07-17 mutating-routes audit **read this exact router** and justified
   its POSTs one by one — but its scope was *mutating methods*, so the GET
   carrying the client book was invisible to an audit that read the file it lives
   in. **The scope was the METHOD, not the DATA.**

Shipped as three halves (prefix removed with per-route replacements; principal +
ownership filter; the write route de-published and its body-supplied `user_email`
replaced by the principal), mutation-verified 3/3.

**Still open from Phase 0, deliberately not done unilaterally:**

- The WhatsApp dashboard (`apps/wa-dashboard-m1/server.cjs`) defaults `HOST` to
  `0.0.0.0` — verified live, `http://100.107.22.111:7790/` answers **HTTP 200,
  125,724 bytes with no caller authentication** (its 19 auth-shaped references
  are all deeplink/lead tokens and a DB session table; none authenticates the
  caller). The one-line fix removes the owner's own reach and, as far as anyone
  has *measured*, nobody else's — so it is his call, and it becomes urgent the
  hour the laptops are enrolled, which is itself gated on him.
- Qdrant `:6333`.

## Adversarial review

Seat: **Codex (`gpt-5.6-sol`, xhigh)**, read-only, instructed to refute rather
than comment, and pointed **at this document's own sentences** — not at the three
proposals it merged. That framing was the point: the earlier rounds all hit the
proposals, and a synthesis is read as the safe part of the work, which is exactly
how a correction ships a new false claim (superscar #6 / W113).

It returned 24 objections, 23 rated REAL. **Sixteen changed this document**, and
one of them moved a phase. The substantive ones, and what they did:

| objection | effect |
|---|---|
| "no renewal pipeline" — 107 dated rows prove one exists, incompletely | rewritten as 107-of-822, plus the seasonality caveat |
| `missing_documents` empty has two readings and the doc never settled which | promoted to an explicit unknown and the first task of Phase 1 |
| "14 of 24 logged in within 7 days" became "14 daily users" | every occurrence corrected to the measured window |
| the Pro conclusion leans on reboots whose cause the doc calls unknown | claim narrowed to an unmeasured availability risk |
| "4 loopback tools nobody can reach" — a bind proves reachability, not use | withdrawn |
| "port separation is the ONLY mechanism that can fence a path" | corrected: the only *host:port network rule*; other mechanisms named |
| "revocable only by untagging" | false — corrected; the real objection is attribution |
| "the tailnet is never an authorization decision" contradicts the design | corrected to "never the sole authorization, never a human identity" |
| the local cookie under a separate key would be **rejected** by the tenant | **verified at `intake_review_reader.py:14`** — identity-translation contract added as the door's central open piece |
| the upstream login returns a Fly token in the body + `Set-Cookie` | **verified in `identity/router.py`** — discarding them made an explicit requirement |
| an `aud` claim is not a control until the verifier is required to check it | added |
| sessions surviving Fly ⇒ Fly-side disable cannot revoke them | **revocation + max TTL moved BEFORE the door** |
| the enum map does not contain a compromised process | limit stated in the load-bearing section |
| "the two removals" while the doc describes three | corrected to three; Qdrant kept in the open list |
| "the one task requiring enrollment" | **verified at `policy.hujson:80-81`** — every phase behind the door needs the grant |
| 11 queue items used to decide database resilience | reasoning corrected; RPO decides resilience |
| "he is the only current user" | withdrawn — no access log was consulted |
| "21 non-email rows ⇒ those consultants are locked out" | rows ≠ people; lockout marked inferred |
| "sixteen people, months of habits" | denominators reconciled and labelled |
| "is what will get the column filled" | labelled a hypothesis, with owner and exit criterion |

Three of the refuter's own claims were checked against the repo in the same
session before being adopted (`intake_review_reader.py`, `identity/router.py`,
`policy.hujson`) — all three accurate. One was **not** adopted as fact: its
vendor-documentation reconciliation of the `Tailscale-User-Login` contradiction
is recorded as an unverified hypothesis, because the doc page was not read in
that session and a refuter hallucinates too (W65).

Not adopted, with reasons: the objection that comparing the two sides is
invalid — the units genuinely differ, so the table was relabelled rather than
removed, since an order-of-magnitude gap is still the finding; and the objection
to "an intranet over empty columns is a dashboard over nothing", which is now
defended by the 87%-undated figure rather than by "no pipeline".
