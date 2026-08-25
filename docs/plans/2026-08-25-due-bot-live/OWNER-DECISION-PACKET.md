# OWNER DECISION PACKET — I DUE BOT switchboard (lane B7)

> MANDATE.md: "nothing here blocks the build, everything ships dark, and the owner is to be
> presented **a single decision packet** — never a set of unwatched ledger lines." This is that
> packet. Every item states: what to do concretely, what it unblocks, what happens if it is
> never done, and how to reverse it if it goes wrong. Items are independent — none blocks
> another, and none blocks the build (B1-B6 can all reach "tested green, shipped dark" with
> zero owner action).
>
> Two items (2 and 4) carry a CORRECTION to how MANDATE.md originally described them — verified
> live against production during this packet's drafting, not assumed from the mandate text. Read
> those two sections in full before acting; the mandate's one-line switchboard row understates
> or misstates the current reality in both cases.

## Item 1 — Second WA number + WABA "Bali Zero Operations"

**Concretely**: acquire a second SIM/eSIM (a phone number distinct from the public
+62 821-3465-159), register it as a WhatsApp Business number under a NEW WhatsApp Business
Account named "Bali Zero Operations" in Meta Business Manager
(business.facebook.com → WhatsApp Manager → Add phone number → verify via SMS/call), and note
down the resulting `phone_number_id` and WABA id — B3/B5 need both to configure the team-bot
webhook subscription once they land.

**Unblocks**: team-bot live traffic. The team bot must not share the client bot's WABA/number —
separate identity resolution (F7), separate rate limits, separate audit namespace (go-live
checklist §5.5: "Both bots have separate WABAs/phone-number IDs, webhook secrets, access tokens,
audit namespaces, and kill switches").

**If never done**: B3 (team-bot runtime) and B4 (inference plant) ship fully built and tested
against synthetic fixtures with zero owner action required — this genuinely does not block the
build. It blocks only the FIRST real message a staff member could ever send.

**Reversal**: none needed. A WABA/number can be deleted or left dormant in Meta Business Manager
with no other system depending on it until item 7's `TEAM_BOT_INGRESS_ENABLED` rung is flipped.

**While you're in Business Manager anyway**: the 2026-08-24 measurement of the EXISTING client-bot
WABA found a second app, "Business Agent" (id `1143680903703001`), subscribed to it alongside
ours — benign or not couldn't be determined from the API. Worth a look while you're there for
item 1; unrelated to the new WABA you're creating.

## Item 2 — Webhook signature enforcement (WhatsApp + Instagram) — CORRECTED

**MANDATE.md's own text carries a false premise on this item** — a frozen document being wrong
about the world, not merely stale, and worth stating plainly rather than quietly working around:
its framing ("`WHATSAPP_APP_SECRET` fetched from Meta into Fly secrets — client bot fail-open
scar") describes a state that was already wrong before this mandate was written, and the fix for
the REAL gap (Instagram, below) has since merged. This is written down explicitly so a later
reader does not need to re-run the curl themselves to discover the mandate is wrong here. Three
separate corrections, verified directly against the merged code at integration-branch tip
`6f336a822` (not assumed from the mandate text):

**1. `WHATSAPP_APP_SECRET` was never actually missing.** Live-checked twice — 2026-08-24 by a
prior session, and again just now during this packet's drafting:
`curl -X POST https://nuzantara-rag.fly.dev/webhook/whatsapp` with an unsigned body returns
**HTTP 401**, not a silent accept. The mandate's "fail-open" framing traces to a 2026-08-23
finding that a next-day investigation corrected: "UNSET" came from a truncated
`fly secrets list | head -20` (215 total rows), not from the secret's actual absence — the same
shape of bug as cicatrix family #2's **W97** ("display-cap `[:40]` letto come completo"): a
paged/truncated listing misread as the complete set. Named here so the next reader recognizes
the shape instead of rediscovering it.

**2. Instagram, not WhatsApp, was the real live gap — and it is now closed in code.** Verified
live before the merge: an unsigned POST to `/webhook/instagram` returned **HTTP 200** (no check
at all beyond the GET handshake token). The merge (`b0cf8d087` + follow-ups, landed at
`6f336a822`) adds `_verify_instagram_signature` calling the same shared `verify_meta_hmac`
primitive WhatsApp already used, reading a **new, separate** setting —
**`instagram_app_secret`** (env var `INSTAGRAM_APP_SECRET`) — NOT the WhatsApp secret reused.
Each surface keeps its own secret.

**3. One shared flag governs BOTH surfaces' fail-open/fail-closed behavior — this is the actual
"one-value flip".** `META_WEBHOOK_REQUIRE_SIGNATURE` (bool, **default `False`**) is the single
knob: when `False` (today's default, unchanged by the merge), a missing secret on either surface
skips verification — but now LOUDLY, with a warning log naming exactly which secret is missing
and both remediation options. When `True`, a missing secret on EITHER surface makes that
surface's webhook reject with 401 instead. **The flag is shared; the secrets are not** — flipping
the flag to `True` before `INSTAGRAM_APP_SECRET` exists does not silently no-op, it starts
rejecting real Instagram traffic; and since the flag is shared, flipping it also starts enforcing
WhatsApp more strictly against any FUTURE accidental removal of `WHATSAPP_APP_SECRET`.

**What you actually need to do** — one real action, plus a confirmation:

1. **Verify `INSTAGRAM_APP_SECRET` exists as a Fly secret AND is the correct, current one** —
   the only step this item actually requires of you, and it needs doing carefully:
   - **Absent is safe** — `META_WEBHOOK_REQUIRE_SIGNATURE` stays `False` by default, so Instagram
     simply continues the pre-merge fail-open behavior (now with a loud warning) until you act.
   - **Present-but-stale is an outage on deploy** — if `INSTAGRAM_APP_SECRET` exists but is
     wrong/rotated AND `META_WEBHOOK_REQUIRE_SIGNATURE` is (or becomes) `True`, every real
     Instagram webhook starts 401ing the instant that combination is live. **Check the value, not
     just presence**: `fly secrets list -a nuzantara-rag | grep -i instagram` for existence, then
     confirm the value against Meta Business Manager → the Instagram-linked app's Basic
     settings → App Secret (Show) before trusting it. As of this packet, nothing in the repo
     references `INSTAGRAM_APP_SECRET` as a provisioned Fly secret — this genuinely has not been
     done yet, not merely unverified.
2. **Decide when to flip `META_WEBHOOK_REQUIRE_SIGNATURE` to `True`** — only after step 1 is
   confirmed. Until then, leave it at its shipped default (`False`); the merge itself changes
   nothing about production behavior beyond the new warning logs.

**Unblocks**: real signature enforcement on Instagram (WhatsApp already had it, per correction 1)
— without it, anyone who found the Instagram webhook URL could inject forged inbound messages
the backend would accept and process as genuine client messages.

**If never done**: Instagram stays fail-open exactly as it was, now with a warning log instead of
silence — a visible, not a hidden, gap. If step 1 is skipped and step 2 is done anyway (flipping
the flag before verifying the secret), the risk flips to an active outage instead.

**Reversal**: `fly secrets unset INSTAGRAM_APP_SECRET` or set `META_WEBHOOK_REQUIRE_SIGNATURE`
back to `false` — Fly restarts the affected machines automatically on a secrets/config change,
no manual redeploy step.

## Item 3 — Test message from your phone to the public WA number

**Concretely**: from your own phone, send an ordinary WhatsApp message to +62 821-3465-159.

**Why this, and only this, can answer the question**: a 2026-08-24 measurement checked every
API-observable signal between Meta and the backend for the number's 24-day silence (since
2026-07-30 01:23:58Z) and found all of them green — token valid, WABA approved, phone number
`CONNECTED`/`GREEN`, `messages` subscription present in `/{app}/subscriptions`, our webhook
correctly rejecting an unsigned POST with 401 (proving both transport and signature correctness),
zero code regression in the relevant window. The one thing left standing, `GET
/{WABA}/subscribed_apps` answering `500` reproducibly, is not conclusive alone. **No further API
query can distinguish "the subscription is silently broken" from "24 days really were zero real
inbound traffic."** Only a real message from a real phone can: a row appearing in
`inbound_webhooks` within seconds confirms the pipeline is alive and clients simply stopped
writing (a demand problem, not a technical one); nothing appearing means the `messages`
subscription is gone at Meta's end and needs restoring from Business Manager.

**Unblocks**: confirms/refutes the 24-day-silence cure — i.e., tells the whole team whether the
client-bot's WhatsApp surface has a live transport problem to fix, or whether the real work is
demand-side (why did 24 days of zero traffic happen, separately from the RAG/CRM-side defects
the same investigation found: 94 answers discarded on an expired 24h Meta customer-care window,
never told to the client).

**If never done**: the 24-day silence stays an open question with no further instrument able to
close it — every subsequent finding downstream of this (containment rate, resolution rate,
whether Gemini's spine is healthy) is measuring a channel whose basic liveness is still unproven.

**Reversal**: none — sending a message has no destructive effect; it is the test itself.

## Item 4 — Codex seat OAuth logins on the broker Macs — CORRECTED

**Concretely**: on each Mac hosting a codex broker daemon seat, run `codex login` under that
seat's dedicated unprivileged macOS identity (e.g. `sudo -u zantara-codex-seat1 -i`, then `codex
login`, completing the browser OAuth flow), then verify with `codex exec --sandbox read-only
"ping"` returning exit 0.

**What changed since the mandate was written — and it is more unsettled than a completed fix**:
B2a's first attempt at telling AUTH_DEAD apart from QUOTA (matching stderr text against two word
lists) was **refuted, not merely revised** — a cross-family refuter found 12 reproduced findings,
traced to one design defect: a single real stderr string can legitimately match both classes at
once ("token has expired; refresh failed with 429 too many requests" reads as both), matching
spans a whole multi-line blob instead of one record, and ordinary prose can't be reliably
classified by vocabulary at all. Read
`docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md` for the full account —
its own words on when this may be trusted: **"This stays dark until a REAL codex exec quota
event and a REAL policy block have been observed and their exact stderr recorded here... no
caller may take an irreversible action on it"** until then. That has not happened yet.

**What IS already reliable, and what this item's alerts mean today**: `AUTH_DEAD` itself rests
on a different, pre-existing, empirically-anchored pattern (already tested against one real
observed case) — unaffected by the refutation above. So: an alert citing `AUTH_DEAD` today means
what it always meant, and `codex login` is the correct response. An alert citing `QUOTA` is
currently built on the still-unarmed classifier — treat it as a signal worth investigating, not
yet as confident grounds to conclude "this definitely wasn't an auth problem." One further,
solid distinction this packet adds: `cli_version_mismatch` is `wa_codex_daemon.py`'s own
**pre-existing, deterministic** version-pin guard (unrelated to the contested stderr classifier)
— if you see this specifically, the fix is restoring or re-approving the pinned CLI version, and
`codex login` does nothing for it either.

**Unblocks**: B2 arming — the codex broker leg cannot execute a single real generation without a
live-authenticated seat. B2's code itself (daemon, error split, tripwires, schema, promotion
machinery) ships fully built and tested against the fake broker (B6a) with zero owner action;
this item only blocks REAL execution, never the build.

**If never done**: the codex leg ships dark and fully tested against the fake broker, but never
executes a real generation — Gemini remains the sole active brain indefinitely, which is exactly
the mandate's own staged default ("Gemini ... is the working spine today").

**Reversal**: none needed — an unauthenticated seat is inert by construction (the daemon
requires a live auth check before it will claim a job at all).

## Item 5 — Gemini billing auto-reload + alert

**Concretely**: in Google Cloud Console → Billing → the project backing the Gemini API key the
client bot uses → Budgets & alerts, confirm auto-reload is enabled (no silent hard cap that would
402 every request), and set a budget alert threshold (e.g. 80%) notifying you by email/Telegram.

**Unblocks**: client-bot spine reliability. Gemini is not just the primary brain — per the Sol
§2.4 degradation ladder, it is ALSO the fallback of last resort for nearly every codex-leg
failure mode. A Gemini billing outage does not degrade one leg; it takes down the entire client
bot, both brains at once.

**If never done**: the same standing risk that predates this mandate persists — a hard billing
cap could 402 every Gemini call with no advance warning, and because Gemini is also the
fallback, `fallback_provider_failure_ratio` (the tripwire meant to catch exactly this) would only
fire once it was already happening in production.

**Reversal**: none — this is a monitoring/limit configuration only, safe to adjust at any time.

## Item 6 — Team roster: WA numbers → user_id enrollment

**Concretely**: compile a roster (name, verified WhatsApp number, existing system `user_id`) for
the ~10 Bali Zero staff who will use the team bot, cross-checked against the team roster (memory
`reference_bali_zero_team.md`) — **verify each number personally**, since F7's fail-closed design
means an unverified/wrong number never reaches the model at all (fixed refusal copy). The actual
data-entry step depends on B3 shipping the enrollment table/CLI — this item can be PREPARED
(compiling and verifying the roster) now; entering it is gated on B3 landing.

**Unblocks**: F7's identity table. Without it, every inbound message to the team bot is from an
"unknown" number and gets the fixed refusal copy — the bot is live-capable but useless to 100%
of staff until this is populated.

**If never done**: the team bot answers nobody — F7's fail-closed default, which is the SAFE
default, not a broken one. This is a "does not block the build" item that only blocks USE.

**Reversal**: removing or disabling one staff member's enrollment is a single-row deactivation —
granular, no wider blast radius (F7 already scopes per-number).

## Item 7 — Ignition (both promotion orders, verbatim, with what each rung proves)

Both ladders are already frozen in the mandate/research capture; what follows states explicitly
what is PROVEN at each rung before the next — the thing MANDATE.md's one-line table doesn't spell
out and the team lead asked this packet to carry.

### Client bot — `synthetic probe → shadow against recorded fixtures → production shadow, no

send → owner-only allowlist → 5% eligible WA traffic → 25% → one surface at a time` (Sol §2.5)

1. **Synthetic probe**: proves the pipeline runs end-to-end without error. Zero live exposure.
2. **Shadow against recorded fixtures**: proves gate/engine behavior matches expectation on KNOWN
   inputs (B6 goldens). Still zero live traffic.
3. **Production shadow, no send**: proves the engine behaves correctly on REAL live inbound
   traffic's actual distribution — the thing goldens can't fully capture. Nobody receives an
   answer yet.
4. **Owner-only allowlist**: proves a real send path works end-to-end (webhook → gate → ALLOW →
   actual Meta/portal send) against the lowest-stakes possible recipient — catches integration
   bugs before any client is exposed.
5. **5% eligible WA traffic**: proves the system holds up under a small slice of real, unscreened
   client traffic and real handoff/escalation behavior with actual clients.
6. **25%**: proves the above holds at higher concurrency — this is where Kimi's refutation
   specifically warned the codex leg's latency can start to collapse (FC1: "not at scale, but at
   the SECOND simultaneous conversation").
7. **One surface at a time**: proves each surface's own quirks (IG DM formatting, portal auth,
   KBLI domain-restriction) independently before compounding surfaces together.

### Team bot — `ingress/audit → shadow intent/tool selection → fixed replies to owner →

allowlisted staff, read tools → R2 writes → R3 practice open → automatic failover` (research
§5.5)

1. **Ingress/audit only**: proves the webhook receives, HMAC-verifies, and durably logs real Meta
   traffic with zero model/tool involvement — the lowest-risk "is the pipe connected" proof.
2. **Shadow intent/tool selection**: proves the model correctly SELECTS the right tool for real
   staff messages without ever calling one (dry-run) — catches Kimi's FM2 (wrong-tool-selection,
   the highest-frequency failure after argument hallucination) before any tool executes for real.
3. **Fixed replies to owner**: proves a full round-trip reply can be sent to a real WhatsApp
   thread, scoped to the single lowest-stakes recipient.
4. **Allowlisted staff, read tools**: proves R0/R1 reads work against REAL CRM data for a small
   vetted group, and that RBAC (`assigned_to` scoping) holds under real usage — before any write
   capability exists at all.
5. **R2 writes**: proves the confirmation state machine (F6) correctly gates a real mutation
   end-to-end, idempotency holds under real retries, and audit logging captures every step —
   still only the lower-risk mutation tier.
6. **R3 practice open**: proves the highest-risk single mutation (committing a server-stored
   preview, never mutable free-text) works safely through the full preview→confirm→commit dance
   under real usage.
7. **Automatic failover**: proves the Mini→Pro mechanism (leader-epoch CAS, WABA callback
   override) holds not just synthetically (already required as a gate before this rung, F9) but
   that Meta's REAL retry semantics behave as the staging drill predicted. Gated explicitly:
   "AUTO-failover stays DARK until a staging-WABA drill proves Meta's retry semantics" — this
   rung does not open on schedule, it opens on that drill passing.

## Item 8 — Model Studio API key for `qwen3.7-flash` (~$3.4/month) — NEW, directive #1

**What it is.** Directive #1 reserves a slot for `qwen3.7-flash` via a Model Studio API key,
entering as the team bot's primary brain when you authorise it. Until then the primary is
`qwen3.7-plus` through the TP1 door, which is already armed and needs nothing from you.

**Why it is on this switchboard and not in a lane.** It is a **paid per-token API key**, and
the standing rule is that any paid per-token API outside the pre-authorised set needs your
explicit yes — never installed autonomously "to test". The directive already gates it
correctly; this item exists so the gate has a place to be answered rather than sitting
implicit in a paragraph.

**What you are actually deciding.** Whether ~$3.4/month buys enough over `qwen3.7-plus` to be
worth a new credential and a new billing surface. Nobody has measured the two against each
other on our traffic, so **there is no evidence here yet** — this item is deliberately not
asking you to decide today. It is asking you to know it exists, so that a lane never quietly
arms it.

**Cost of saying no:** none. The chain runs on TP1 as directive #1 specifies.

---

## Item 9 — One sentence on the PII boundary for per-member memory — NEW, directive #1

**What it is.** Directive #1 adds three-layer per-member memory, and its episodic layer has to
resolve anaphora — _"and for the other client?"_ — which requires storing enough to
disambiguate one client from another across turns.

**The tension, stated plainly.** You granted this lane a derogation for **processing**
(documents whose client consent is already collected). The Law 2 **output** frontier is
unchanged: no cleartext PII in any persisted memory, log, report, metric label or shared
artifact. A per-member memory is, structurally, a persistence layer for facts about clients.
`client_id` plus a practice reference is almost certainly sufficient for anaphora and stays
inside the frontier.

**Why you and not us.** "Almost certainly" is the orchestrator estimating your risk appetite.
The lane has been told to build inside the frontier and to **report rather than relax** if it
finds a layer that cannot do its job under it. What is missing is one sentence from you fixing
where the line sits, so three lanes do not each re-derive it slightly differently and the
loosest reading wins by accident.

**What a yes looks like:** a sentence naming what episodic memory may persist about a client.
**Cost of not answering:** the lane builds to the strictest reading — `client_id` and hashes
only — which may make some proactivity weaker than you wanted, and you will hear about it as a
capability report rather than as a leak.

---

## Item 10 — Four duplicate keys in the client-facing price list — NEW, found 2026-08-25

**What it is.** `bali_zero_official_prices_2026.json` names four services twice, with
different prices each time. It is the entire monthly tax product line:

| key            | basic (without LKPM & Annual) | bundled (including them) | spread     |
| -------------- | ----------------------------- | ------------------------ | ---------- |
| `Tier 0-50`    | 1.800.000 – 2.000.000 IDR     | 2.500.000 IDR            | up to 700k |
| `Tier 50-100`  | 2.500.000 – 3.000.000 IDR     | 3.500.000 IDR            | up to 1.0M |
| `Tier 100-200` | 3.500.000 – 4.500.000 IDR     | 4.500.000 IDR            | up to 1.0M |
| `Tier 200+`    | 5.000.000 IDR                 | 6.500.000 IDR            | 1.5M       |

Census run over the live catalogue: 109 service keys, 4 of them duplicated, all four in
`tax_accounting`, all four with a different price on each side. So this is not an edge
case — it is _every_ monthly-tax price the bot could quote.

**What does NOT need you.** The bot path is being closed in code (lane B1d): the pricing
snapshot gets keys that are unique by construction, so a claim naming `Tier 0-50` can no
longer bind to whichever of the two amounts happens to be indexed. That fix needs no
decision from you and is in flight.

**What might.** The ambiguity is not only the bot's. The list is client-facing, and a human
reading it has exactly the same problem: two rows called `Tier 0-50`, 700k apart, where the
distinguishing fact ("without" vs "including LKPM & Annual") lives only in the long name.
Quote the basic price to a bundled client and Bali Zero absorbs the difference; quote the
bundled price to a basic client and the client is overcharged. That has presumably already
happened at least once, by a person, without a bot involved.

**Why you and not us.** Renaming a service in a client-facing price list is a commercial
decision — what customers see something called, and whether an already-quoted client now
reads a different word. The lane was explicitly forbidden from touching the data for that
reason.

**What a yes looks like:** disambiguated keys in the source list (e.g. `Tier 0-50 (basic)`
/ `Tier 0-50 (bundled)`), which also makes the code fix simpler rather than redundant.
**Cost of not answering:** none for the bot, which is being fixed regardless. The residual
risk stays where it already is — on humans reading the list.

---

## Item 11 — one of v1's declared tools has no backend at all — NEW, found 2026-08-25

**What it is.** Directive #1 §3 put **deadlines & compliance, with proactive reminders**, inside
v1 as domain 3. A reconciliation of all ten frozen team-bot tools against the live backend found
that `create_reminder` is **ABSENT**: no `reminders` table, no model, no route anywhere in
`backend-rag/backend`. Verified by search, not inferred from a doc.

**What DOES exist, so the gap is narrower than it sounds.** The proactive half is live and
running: `routers/cron_notifiers.py` (visa-expiry, LKPM deadlines, compliance forecast, …),
driven by GitHub Actions cron into Fly, each endpoint behind its own `system_settings` kill
switch. That machinery _sends_ deadline alerts today. And `TeamMyDeadlinesTool` already answers
"what is due for MY clients", filtered by `assigned_to`.

**What is missing** is the ad-hoc direction: a staff member telling the bot _"remind me about
this practice on the 14th"_. Nothing can store that.

**The decision.** Two honest options, and it is yours because it changes what v1 means:

- **Build the surface** — a `reminders` table plus a create/list route, with the same
  `assigned_to` scoping the rest of the CRM enforces. Real work, and it adds a persistence
  surface that will hold client-linked rows (so it inherits item 9's PII boundary question).
- **Drop `create_reminder` from v1** — the bot answers deadline questions and the existing cron
  keeps sending proactive alerts, but a staff member cannot ask it to remember something new.
  Costs nothing and narrows the product.

**What does NOT need you:** nothing is blocked meanwhile. The other nine tools are unaffected,
and the orchestrator's standing ruling is that a tool with no backing route is not a tool — so
`create_reminder` stays out of v1 by default until you say otherwise. This item exists so that
default is a decision you made rather than one discovered by whoever wires R1.

---

## See also

- **Kill criterion**: `MANDATE.md` (new section, this lane's addition) — the measured conditions
  under which a leg should be reverted rather than iterated on.
- **Kill switches**: `ops/KILL-SWITCHES.md` — the single-gesture off for every plane.
- **Tripwires**: `ops/TRIPWIRES.md` — what fires automatically, business vs technical.
- **Packet templates**: `ops/packets/` — the two evidence-gated packets this switchboard's items
  2 and 4's underlying tripwires can produce later (quota-wall stage-2, Funnel pivot).
