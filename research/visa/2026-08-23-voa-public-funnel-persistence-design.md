---
date: 2026-08-23
domain: visa
client_case: none
sources: 9
adversarial_review: codex
---

# GARUDA VOA public funnel — the persistence design the rebuild follows

## 0. What this is

Bali Zero's public VOA (Visa on Arrival) funnel at `https://balizero.com/visa/voa` was withdrawn
on 2026-08-21 by PR #4344 (commit `665bfd40d`). Zero has since ruled (2026-08-23, relayed via the
fleet mailbox to the S14 GARUDA-VOA lane) that **the mandate is to rebuild the public surfaces and
prove them live** — the old pages exist in git history, `665bfd40d` is the restore point. **Opening
sales to real clients stays a separate, explicit owner gate at the end of that work**; building and
proving live is not opening.

This document is not the rebuild. It is the persistence/PII design the rebuild must follow,
because the first design the conductor proposed for it was reviewed by two independent adversarial
seats and **both rejected it** — overturning a recommendation the owner had already approved. That
reversal, and what it converged on, is this document's actual content.

## 1. Verified current state (commands run this turn, not recalled)

```
$ curl -sI https://balizero.com/visa/voa
HTTP/2 404
cache-control: no-store, max-age=0
x-robots-tag: noindex, nofollow
x-matched-path: /visa/voa
x-pathname: /visa/voa
```

Sitemap: `curl -s https://balizero.com/sitemap.xml` and the alternate sitemap path return zero
`voa` rows (the two `visas/...` hits that do appear — `e-voa-electronic-visa-on-arrival-guide`,
`visa-free-vs-evoa-indonesia-comparison` — are unrelated evergreen content pages, not the funnel).

`git show 665bfd40d --stat` confirms the shape: `apps/mouth/src/app/visa/voa/page.tsx` (670 lines)
and `[hash]/page.tsx` (398 lines) were deleted; `apps/mouth/src/app/visa/voa/route.ts` and
`[hash]/route.ts` (20 lines each) were added in their place. Read directly, both are static 404
tombstones:

```ts
export function GET(): Response {
  return new Response("Not Found\n", { status: 404, headers: TOMBSTONE_HEADERS });
}
```

`TOMBSTONE_HEADERS` is `cache-control: no-store, max-age=0` + `x-robots-tag: noindex, nofollow`.
The `[hash]/route.ts` file carries one line worth keeping verbatim, because it states a boundary
this design leans on: *"Hashes are identifiers, never credentials."* — the same philosophy the
schema below was already built on before the withdrawal.

Backend-side, `garuda_voa` is still a registered router (`router_manifest.py:216`, gated by
`_is_garuda_flow_enabled`) but is absent from `public_endpoints.py` — it now requires auth. The
commit message trail (`git show 665bfd40d`) reads as a deliberate sequence: *"add stateless
owner-local synthetic preview" → "retire public routes" → "isolate stateless preview boundaries" →
"remove login database writes"* — consistent with a conscious pivot toward statelessness for the
*owner* preview, not evidence of what motivated retiring the *public* funnel specifically. No
commit message or linked doc states the reason. Nobody currently claims to have found one — the
2026-08-23 ruling above says explicitly the record behind #4344 "remains introvabile."

## 2. What the old public funnel actually persisted

`apps/backend-rag/backend/db/migrations_v2/261_garuda_voa_checks.sql` (2026-07-27) is the schema
the withdrawn funnel wrote to. Read in full, it is more careful than a naive "public form → PII
table" design: the migration's own header states the table was scoped, at build time, to hold
**only enum / date / boolean / ISO-code columns** — explicitly no name, no passport number, no
email, no phone — precisely so the unauthenticated route could exist at all. That constraint is
real and verified, not assumed.

What it does persist, one row per submission:

| Column | Type | Note |
|---|---|---|
| `hash` | `VARCHAR(20)` PK | 16-char URL-safe, public identifier in `/visa/voa/<hash>` |
| `nationality` | `VARCHAR(3)` | ISO-3 code |
| `entry_date` | `DATE` | |
| `passport_expiry_date` | `DATE` | |
| `voa_expiry_date` | `DATE` (nullable) | extension cases only |
| `decision` | `ACCEPT`/`DECLINE` | frozen at submission |
| `published_filing_deadline` | `DATE` | the one Safe Clock checkpoint ever shown |
| `price_idr` | `BIGINT` | |
| `view_count`, `share_count` | `INT` | |
| `created_at` | `TIMESTAMPTZ` | no default expiry |

No `TTL`, no purge, no consent field, no deletion endpoint. `view_count`/`share_count` are the only
mutable fields — everything else is append-only forever.

**Why this still counts as personal data worth protecting, despite the migration's own "no PII
columns" framing**: nationality + entry date + passport expiry + a frozen accept/decline verdict is
travel data tied to one real, unnamed individual, reachable by anyone holding the hash. It is
narrower than name/passport-number/email/phone, and the 2026-07-27 design was right to keep those
four out — but "narrower PII surface" and "not personal data" are different claims, and the schema
comment makes the second one. This document does not correct that comment (out of scope — it
describes a retired table); it just does not repeat the stronger claim as if it were established.

## 3. What the conductor proposed first, and what happened to it

The conductor's initial design for the rebuild's result page was a **stateless signed token**: no
database row at all, the full assessment (nationality, dates, verdict, deadline, price) HMAC-signed
directly into the result URL. The owner approved it. The stated rationale was that this does not
*manage* the compliance question the withdrawn funnel raised — it makes the question disappear,
because there is no row for a purge policy, a consent flag, or a deletion request to act on.

Two independent adversarial seats then reviewed that approved design, on fresh context, with no
contact with each other.

**Both rejected it, and converged on the same replacement.**

### Kimi K3 — verdict

> "the URL leaks into Referer headers, browser history and sync, server/CDN/reverse-proxy access
> logs, analytics `page_location`, chat-app link-preview crawlers and caches, screenshots and
> clipboard managers" — **twelve ungoverned stores in place of one governed, auditable, deletable
> store.**

Kimi's core point: an HMAC gives *integrity* (the payload wasn't tampered with), never
*confidentiality* — anyone holding the URL reads nationality, travel dates, verdict, deadline and
price in clear, because nothing about a signature hides the signed content. Verbatim verdict:

> "the path-embedded signed token relocates personal data into logs and chat-app caches Bali Zero
> cannot govern while killing the analytics the funnel exists to produce."

Kimi also flagged, independent of the privacy argument, that the analytics loss is *"a product
trade, not a privacy freebie"* — losing per-visitor page views does not, by itself, buy any
compliance ground; it's a cost that happened to be paid alongside a design that didn't buy the
governance benefit it was meant to buy.

### Codex `gpt-5.6-sol` — verdict

Reached the same place independently: *"as specified, privacy is a wash, not an improvement."*
Bulk exposure through one queryable database table falls, but routine per-case replication moves
into chat previews, screenshot tools, and CDN/proxy logs — systems with **less** operator control
than a table Bali Zero already runs migrations against.

Codex's distinct and decisive addition is the **revocation argument**: once a token has reached a
chat, a screenshot, or a link-preview cache, the operator cannot delete or revoke that one result
without invalidating an entire signing key or policy version — which takes every other still-valid
result down with it. A governed row can be deleted by its own primary key; a signed token embedded
in the URL itself cannot be un-issued.

Its verdict: *"a minimal opaque-ID database row with automatic short retention, explicit notice,
deletion/revocation, and permanent coarse aggregates."*

### The thing neither design addressed

Both seats, independently, flagged the same gap: **the legacy pre-2026-08-21 rows in
`garuda_voa_checks` are the only personal data this funnel actually holds today**, and neither the
stateless-token design nor its replacement does anything about them by construction. Leaving them
read-only-forever (which is already true post-#4344 — the repository adapter is now hard-restricted
to reads, see §5) changes *mutation rights*, not *retention or exposure*. A retention design that
only governs rows written after the rebuild ships, while the pre-existing rows sit indefinitely, is
half a policy.

## 4. The ruled design

This is the spec the rebuild follows for the result-persistence layer.

1. **Minimal row behind an opaque random identifier** — ≥128 bits from a CSPRNG, never sequential,
   never derived from the payload. (The existing `hash` column — 16-char URL-safe, generated by
   `new_visa_hash()`, shared with `visa_checks` — already satisfies this; it does not need to
   change shape, only what governs its lifetime.)
2. **No personal data in the URL.** Result page stays `/visa/voa/<opaque-id>`; nationality, dates,
   verdict, and price never appear in path or query — this was already true of the pre-withdrawal
   design and must not regress with the stateless-token idea reintroducing it.
3. **Automatic retention, enforced by a fail-closed policy primitive — not a duration this document
   sets, and not a promise in a document.** Bali Zero already has a working precedent for exactly
   this shape of decision — the Visa Oracle engine's own retention system
   (`db/migrations_v2/264_visa_decision_retention_policy.sql`, `266_visa_retention_evidence.sql`,
   `268_visa_retention_binding_security_definer.sql`): a `visa_decision_retention_policies` table
   whose own COMMENT reads *"Zero-approved retention authority; activation requires a separated
   policy-writer owner/role"* and that is **fail-closed until Zero records an explicit duration,
   anchor, effective period, approver, and approval reference** — new inserts are rejected until a
   policy row exists, purge is exposed as a bounded database primitive with no invented cadence,
   and legal-hold transitions are tracked per-decision. This is the strongest property in the
   whole design, and it should lead, not follow: the rebuilt funnel is *structurally* unable to
   persist a single submission until Zero has signed off on retention — that beats any promise a
   document can make. The GARUDA rebuild should bind to this exact primitive (a new
   `approved_by`/`approval_reference` policy row scoped to `garuda_voa_checks`) rather than
   hand-roll a cron script that silently no-ops if misconfigured (cicatrix family #2 — exists ≠
   armed). **The retention duration itself is not this session's to set.** 90 days is offered below
   as this session's *proposed* value for that record — a number for Zero to approve or replace,
   never a ruled fact.
4. **Explicit notice and acknowledgement at submit**: what is stored, why, for how long, how to
   delete it. Not present in the withdrawn funnel — no consent field existed on the table at all.
5. **Self-service deletion from the result page** — no email round-trip. This is what the
   revocation argument (§3, Codex) requires structurally: deletion must operate on the row's own
   primary key, which is exactly why the stateless-token design failed this requirement by
   construction (nothing to delete a key *from*).
6. **Coarse aggregates survive the purge**: counts by month × decision × nationality × decline-code.
   No dates, no per-visitor identifier. This is the funnel's demand evidence — once the row is
   gone this aggregate is not personal data, because it cannot be traced back to one visit.
7. **Result-route headers**: `Cache-Control: no-store, private`, `Referrer-Policy: no-referrer`,
   `X-Robots-Tag: noindex, nofollow, noarchive`; excluded from the sitemap. Partially already true
   of the tombstone routes today (`no-store, max-age=0` + `noindex, nofollow`) — the rebuild's real
   result page needs the full set, including `Referrer-Policy: no-referrer`, which the tombstone
   doesn't need and doesn't have.
8. **Abuse posture**: per-source rate limit on the creator POST; count preview-bot GETs separately
   from human views rather than calling every GET a "view". Verified gap: neither
   `apps/backend-rag/backend/app/routers/garuda_voa.py` nor `services/garuda_flow/` currently
   contains any rate-limit logic (`grep -rl rate_limit` returns nothing) — this is new work, not a
   regression to fix.
9. **Legacy rows — measure, then propose, do NOT execute.** See §5. Deleting data is irreversible;
   this document proposes, the owner disposes.

## 5. Legacy-row measurement — UNMEASURED

This session attempted the read-only Postgres MCP (`mcp__postgres-nuzantara__query`, per
CLAUDE.md §10) to get a real count and date range for the pre-withdrawal rows in
`garuda_voa_checks`. It is **not reachable from this session**, verified three independent ways
rather than assumed from one:

- `.mcp.json` at repo root: only `nuzantara-knowledge` is registered.
- `~/.claude.json` (user-level MCP config): only `advanced-seo-mcp` is registered.
- `claude mcp list`: 20 servers checked, `postgres-nuzantara` is not among them.

**The legacy-row count and date range are UNMEASURED.** No number is estimated and none is inferred
from code (the schema in §2 tells us the shape of a row, not how many exist or when they were
written). Whoever runs the actual retention/purge work — on a session where
`mcp__postgres-nuzantara__query` is connected, per CLAUDE.md this is expected on Pro — should run
it first:

```sql
SELECT count(*), min(created_at), max(created_at) FROM garuda_voa_checks;
```

Report **counts and dates only** — a row's contents (nationality, decision, dates for any
individual row) must never appear in a report, log, or memory entry per the repo's PII boundary.

### Proposed action on legacy rows (proposal only — not executed here)

Given the fail-closed retention primitive (§4.3) and the schema-verified `created_at` column (§2),
the following disposition is proposed for Zero's decision once the count/range above is known —
this document does not execute it, and it deliberately does not key off any fixed number of days:
it keys off the policy row Zero has not yet created.

- **Once a `garuda_voa_checks` policy row exists** (§4.3 — `approved_by` + `approval_reference` +
  a Zero-chosen `retention_interval`, 90 days being this session's proposed starting value, not a
  ruled one): rows older than the *recorded* `retention_interval`, measured from the recorded
  anchor, fall out under it. Nothing here hardens 90 — or any other number — into the disposition
  logic; the policy row is the single source of truth once it exists.
- **Until that policy row exists**: the legacy set sits exactly where §4.3's fail-closed design
  says data must sit absent an approved policy — untouched, not purged, not aggregated. This
  section is not proposing an exception to the primitive for legacy rows; it is proposing that
  Zero's policy decision, once made, apply to them too rather than only to rows written after the
  rebuild ships (the "half a policy" gap both adversarial seats flagged, §3).
- **Either way**: no notice was ever given to the visitors who generated these rows (the withdrawn
  funnel had no consent field, §2), so there is no consent to honor or withdraw — this is a
  straightforward "this data should not have accumulated without a retention limit, and the fix is
  to apply one retroactively," not a request-driven deletion. That framing, and the actual
  execution, is Zero's call — flagged here, not decided here.

## 6. Adversarial review

Two independent seats reviewed the conductor's approved stateless-signed-token design, on fresh
context, without contact with each other or foreknowledge of each other's brief.

| Seat | Verdict on the approved design | Core argument | Convergent replacement |
|---|---|---|---|
| Kimi K3 | REJECTED | HMAC gives integrity, never confidentiality; the URL is copied into ≥12 ungoverned stores (Referer, history/sync, CDN/proxy logs, analytics `page_location`, link-preview crawlers/caches, screenshots, clipboard managers) that replace one governed, deletable table | Opaque-ID row, governed store |
| Codex `gpt-5.6-sol` | REJECTED | "Privacy is a wash, not an improvement" — bulk DB exposure falls, per-case replication into less-controlled systems rises; decisive: a signed token embedded in a URL that has already propagated **cannot be individually revoked** without invalidating a whole key/policy | Minimal opaque-ID row, short automatic retention, explicit notice, deletion/revocation, coarse aggregates |

**Both seats overturned a recommendation the owner had already approved.** That is the spine of
this document, not a footnote: the conductor's own design — reasoned, deliberate, approved — did
not survive independent adversarial review, and the design that replaced it (§4) is not the
conductor's; it is the two refuters' converged verdict. Neither seat had visibility into the
other's brief or output when it reached its conclusion — the convergence is independent, not
coordinated.

Both seats also independently surfaced the legacy-row gap (§3, §5) that neither the original design
nor its replacement addresses by construction — that finding survives into this document as an
open, unmeasured item rather than a resolved one.

**A second, smaller reversal, on this same document.** The first draft of §4.3 stated "automatic
retention: 90 days" as part of the ruled design — a number this document's own directing brief
had stated as settled, reproduced here without independently checking it. It was wrong for the
same class of reason as the token design: the `visa_decision_retention_policies` primitive that
same draft cited in the very next sentence is built, explicitly, to refuse exactly that — a
duration set by anyone other than Zero, recorded with an `approved_by` and `approval_reference`.
The two claims sat in the same paragraph and contradicted each other; grounding the retention
mechanism in a real repo precedent (found while writing §4.3, not assumed) is what surfaced the
contradiction. Corrected in this revision: §4.3 now leads with the fail-closed property instead of
the number, and §5's disposition keys off the recorded policy rather than off 90. Two reversals in
one document, both caught by checking a claim against something verifiable rather than accepting
it because it had already been approved upstream.

## 7. Open items for whoever picks up the rebuild

- Legacy-row count/date range: UNMEASURED (§5) — needs a session with `postgres-nuzantara` MCP
  connected.
- No record of the actual reason behind #4344's public-funnel withdrawal has been found by any
  lane that has looked (this session, the 2026-08-23 S14 audit at
  `research/visa/2026-08-23-voa-product-regulatory-and-engine-audit.md`, or Zero's own ruling
  text). If one surfaces mid-rebuild and it is a compliance reason rather than a priority/resourcing
  one, the ruling above already says: stop, go back to Zero before republishing.
- This document does not implement §4 — no migration, no route, no purge job was written in this
  PR. It is the spec the S14 GARUDA-VOA rebuild lane should build against.

## Sources

1. `curl -sI https://balizero.com/visa/voa` — run this turn, HTTP 404 verified live.
2. `curl -s https://balizero.com/sitemap.xml` (+ alternate sitemap path) — run this turn, zero
   `voa` rows.
3. `git show 665bfd40d --stat` — run this turn, full commit shape.
4. `apps/mouth/src/app/visa/voa/route.ts` + `[hash]/route.ts` — read in full this turn.
5. `apps/backend-rag/backend/db/migrations_v2/261_garuda_voa_checks.sql` — read in full this turn.
6. `apps/backend-rag/backend/services/garuda_flow/repository.py` — read in full this turn (confirms
   read-only historical adapter, no archive-write capability).
7. `apps/backend-rag/backend/db/migrations_v2/264_visa_decision_retention_policy.sql` (+ 266, 268)
   — read this turn, cited as reusable precedent.
8. `apps/backend-rag/backend/app/setup/router_manifest.py:216` + `public_endpoints.py` (grep,
   confirms `garuda_voa` is registered but not public) — checked this turn.
9. Team-lead brief for this document, relaying: the conductor's approved stateless-token design;
   Kimi K3's independent verdict; Codex `gpt-5.6-sol`'s independent verdict; Zero's 2026-08-23
   ruling ("Riapri il funnel pubblico") relayed via the fleet mailbox to the S14 GARUDA-VOA lane.
