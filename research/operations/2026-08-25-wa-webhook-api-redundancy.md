---
date: 2026-08-25
domain: compliance
client_case: none — infrastructure availability of the client-facing WhatsApp channel
sources:
  - "flyctl machines list -a nuzantara-rag (measured 2026-08-25)"
  - "apps/backend-rag/fly.toml (read at 84200e014)"
  - "apps/backend-rag/backend/app/main_api.py::lifespan_light"
  - "apps/backend-rag/backend/services/integrations/wa_inbox_bot.py::_get_bot_generation_semaphore"
  - "https://developers.facebook.com/docs/graph-api/webhooks/getting-started (fetched 2026-08-25)"
---

# Should the `api` process group get a standby machine, like `drive`?

**Decision requested from Zero.** `fly.toml` is an off-limits file (CLAUDE.md §5) and this
changes the availability posture of the client-facing channel, so nothing here has been
applied. This document exists to price the choice, not to argue for one.

**Short answer: the exposure is real but it is LATENCY, not lost messages — and `api` is
not a drop-in for what was done to `drive`.** My recommendation is option C (do nothing to
`fly.toml`), for reasons that are measured below rather than assumed.

---

## 1. The exposure, measured

`flyctl machines list -a nuzantara-rag`, 2026-08-25:

| process group | machines | state | volume |
| --- | --- | --- | --- |
| `api` | **1** (`7817d92c4117d8`) | started, 1/1 checks | `vol_rnzwkm1m8leey98r` |
| `rag` | 1 (`1781e5eda03438`) | started | `vol_vde56p7dnjwwew34` |
| `drive` | **2** (`2874974fe6e158`, `48ee717b736948`) | one started, one stopped | none |

`fly.toml` binds the public HTTP service to `api` only (`[http_service] processes = ['api']`),
and `/webhook/whatsapp` is served by `api`. So a rolling deploy of `api` — with exactly one
machine — has a window in which Meta's POSTs reach nothing.

The window is not something I measured directly (it cannot be reconstructed after the fact);
what is on record is its shape: `kill_timeout = 60`, health-check `grace_period = '60s'`,
plus image pull and boot. The repo has one recorded case of the 628 MB image pull alone
exceeding flyctl's default release wait. Order of minutes, not seconds.

Deploy frequency is not hypothetical either: **24 releases between v4221 and v4244 in the
24 hours to 2026-08-25 10:00Z.**

## 2. What that window actually costs — and it is less than it looks

Meta's own documentation (fetched 2026-08-25):

> "If any update sent to your server fails, we will retry immediately, then try a few more
> times with decreasing frequency over the next 36 hours."
> "Unacknowledged responses will be dropped after 36 hours."

So a deploy window of minutes does **not** lose client messages. It delays them until a
retry lands. The cost is response latency on a channel whose measured p90 inbound→outbound
was already ~990 s during the only week this bot has carried real load.

**This corrects the framing the mandate was written on** ("ogni deploy ≈2-3 min di webhook
morto") — the window is real, the loss is not.

⚠️ **One thing this does NOT rule out, and it should be checked before anyone relaxes.**
Persistent delivery failure is also how Meta disables a webhook subscription. The 24-day
silence of 2026-07-30 → 2026-08-23 is still unexplained, and
`GET /{WABA}/subscribed_apps` answers `500 {"code":1,"error_subcode":99}` reproducibly.
I am NOT claiming deploy churn caused that — I have no evidence linking them, and the
retry window is 36 h against an outage of 24 days. It is named here only so that "Meta
retries, therefore the window is harmless" is not read as broader than it is.

## 3. Why `api` is not a drop-in for what was done to `drive`

`drive` was scaled to two machines cheaply because it has **no mount and no public
service**. `api` differs in three ways, each verified in this repo, and each is a reason a
second `api` machine is a design change rather than a `fly scale count` :

**(a) `api` owns a volume with two SQLite databases.** `fly.toml` mounts
`nuzantara_api_data` at `/data` for `processes = ['api']`, and the env sets
`EXPERIENCE_DB_PATH=/data/experience.db` and `METABOLIC_DB_PATH=/data/organism_metrics.db`.
A Fly volume attaches to exactly one machine, so a second `api` machine gets its **own**
volume. The writers (`app/routers/experience.py`, `app/routers/metabolic_health.py`) would
then be writing two divergent databases that never reconcile, with each request landing on
whichever machine the proxy picked. That is superscar #10 (active-active split-brain) by
construction, not by accident.

**(b) `api`'s lifespan spawns singleton-shaped background work.** `main_api.py::lifespan_light`
starts the notification scheduler and `WA_OUTBOX_WORKERS` (default 2) WhatsApp outbox
scheduler loops. Two machines means both run twice. The outbox worker is explicitly built
for K concurrent workers — per-thread advisory lock, claim-token fencing, burst
coalescing — so it is the half that is probably fine. The notification scheduler's
behaviour under two instances is **unverified**, and I am not going to assume it.

**(c) The WhatsApp admission gate is per-process, so it would silently double.**
`wa_inbox_bot._get_bot_generation_semaphore` is a module-level singleton bounding
in-flight RAG calls to `WA_BOT_MAX_CONCURRENT_GENERATIONS` (default 3) **per api process**.
Two machines = up to 6 concurrent generations aimed at a `rag` group that is still **one**
machine. The knob would then no longer mean what its name says, and the pressure lands on
the component that was not made redundant.

## 4. The options, with what each costs

**A — second `api` machine.** Removes the deploy window. Requires resolving (a), (b) and
(c) first: move the two SQLite DBs off the volume or accept per-machine divergence; verify
the notification scheduler under two instances; re-tune the admission semaphore against a
single-machine `rag`. Real work, and it makes `rag` the next single point of failure.

**B — split the webhook into its own tiny process group.** A `webhook` group with no
mount, no schedulers, two machines, serving only verify → persist → hand off. This is the
architecturally clean answer, because the webhook handler genuinely is stateless: it
verifies the HMAC, writes `inbound_webhooks`, and the existing `WebhookProcessor` drains
anything the fast path misses. It costs a new process group, a route split in the Fly
service config, and its own deploy story.

**C — do nothing to `fly.toml`.** Accept a minutes-long window per deploy, on the evidence
that Meta retries for 36 h and nothing is lost. Cost: delayed replies during deploys, on a
channel that is not yet public. This is the option that spends nothing on a problem whose
measured consequence is latency.

**D — reduce the window instead of the exposure** (compatible with C): batch deploys rather
than shipping 24 releases a day, and prefer deploying outside Bali business hours
(`WA_BOT_BUSINESS_START`/`END`, 08:00–20:00 WITA, is already the sentinel's own definition
of when silence matters).

## 5. Recommendation

**C, with D**, until one of these is true: the bot goes public, or the deploy cadence stays
this high once real traffic exists. B is the right shape if the answer ever becomes "make
it redundant" — A buys the same availability while creating a split-brain that has bitten
this organism before.

The reason not to reach for A now is not cost. It is that (a) trades a latency problem for
a silent-data-divergence problem, and this repo's own scar ledger says which of those two
is discovered later and hurts more.

## 6. What is NOT established here

- The actual duration of the deploy window. Bounded by config, never measured. The probe
  that would settle it: poll `GET /webhook/whatsapp` (the GET handshake, which needs no
  signature) once a second across a deploy and record the non-200 span.
- Whether the notification scheduler is safe active-active.
- Whether any inbound message has ever actually been delayed by a deploy. `inbound_webhooks`
  records what arrived, not what was retried, so our side cannot see it. Meta's Webhooks
  delivery diagnostics in Business Manager can (`operator[gui]`).
