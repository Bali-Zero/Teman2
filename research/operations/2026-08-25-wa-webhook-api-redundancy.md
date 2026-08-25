---
date: 2026-08-25
domain: compliance
client_case: none — infrastructure availability of the client-facing WhatsApp channel
adversarial_review: kimi-k3 (2026-08-25, verdict FIX-FIRST(4) on draft 1 — findings applied below; §7 records what was confirmed, what was refuted, and what stays open)
sources:
  - "flyctl machines list -a nuzantara-rag (measured 2026-08-25)"
  - "flyctl releases -a nuzantara-rag --json (measured 2026-08-25 ~12:2xZ; 25-row page spanning 2026-08-24T08:54:20Z → 2026-08-25T09:53:55Z)"
  - "apps/backend-rag/fly.toml (read at 84200e014)"
  - "apps/backend-rag/backend/app/main_api.py::lifespan_light (re-read 2026-08-25)"
  - "apps/backend-rag/backend/app/main_rag.py + backend/app/setup/app_factory.py (re-read 2026-08-25)"
  - "apps/backend-rag/backend/app/routers/whatsapp_chat.py (re-read 2026-08-25)"
  - "apps/backend-rag/backend/services/integrations/wa_inbox_bot.py::_get_bot_generation_semaphore"
  - "https://developers.facebook.com/docs/graph-api/webhooks/getting-started (fetched 2026-08-25 — GENERIC Graph API Webhooks page, not WhatsApp-specific; see §2)"
---

# Should the `api` process group get a standby machine, like `drive`?

**Decision requested from Zero.** `fly.toml` is an off-limits file (CLAUDE.md §5) and this
changes the availability posture of the client-facing channel, so nothing here has been
applied. This document exists to price the choice, not to argue for one.

**Short answer: the exposure is real but it is LATENCY, not lost messages — and `api` is
not a drop-in for what was done to `drive`.** My recommendation is **C+D (do nothing to
`fly.toml`, batch the deploys), conditional on restoring the `subscribed_apps` diagnostic**,
with **option E (move the two SQLite databases to Postgres)** named as the cheapest real
cure if anyone ever wants the window gone.

> **Draft 1 was wrong about option B and this version says so.** A cross-family refuter
> (Kimi K3) returned FIX-FIRST on the first draft. Its strongest finding — that draft 1
> analysed option B against an architecture this repo does not have — was **confirmed by
> independent re-reading of the source**, not taken on the refuter's word. §7 keeps the
> full ledger, including the two places the refuter itself was wrong.

---

## 1. The exposure, measured

`flyctl machines list -a nuzantara-rag`, 2026-08-25:

| process group | machines | state | volume |
| --- | --- | --- | --- |
| `api` | **1** (`7817d92c4117d8`) | started, 1/1 checks | `vol_rnzwkm1m8leey98r` |
| `rag` | **1** (`1781e5eda03438`) | started | `vol_vde56p7dnjwwew34` |
| `drive` | **2** (`2874974fe6e158`, `48ee717b736948`) | one started, one stopped | none |

`fly.toml` binds the public HTTP service to `api` only (`[http_service] processes = ['api']`),
and `/webhook/whatsapp` is served by `api`. So a rolling deploy of `api` — with exactly one
machine — has a window in which Meta's POSTs reach nothing.

**Deploy cadence, cited rather than asserted.** `flyctl releases -a nuzantara-rag --json`
returns a **capped 25-row page**; that page spans `2026-08-24T08:54:20Z` (v4220) to
`2026-08-25T09:53:55Z` (v4244), i.e. **25.0 hours**. Because the page reaches *past* the
24-hour boundary, the count inside that boundary is complete and not a display artifact:
**24 releases (v4221…v4244, inclusive) in the 24 hours to 2026-08-25 09:54Z**, all with
status `complete`.

*(Draft 1 stated this number without the command or the derivation. That is exactly the
shape of the local scar W97 — a capped listing read as a total — and the refuter was right
to demand the citation even though the number survived it.)*

**Window duration: bounded by config, NOT measured, and draft 1's supporting anecdote is
withdrawn.** What is on record: `kill_timeout = 60`, health-check `grace_period = '60s'`,
plus image pull and boot. Draft 1 added "the repo has one recorded case of the 628 MB image
pull alone exceeding flyctl's default release wait" — **that claim is removed**: I could not
re-source it, and an unsourced "recorded" is worth less than nothing in a document whose
whole argument is that things must be measured.

One structural point draft 1 missed, and it makes the window unavoidable rather than
incidental: `api` runs **one** machine with a volume attached, and §3(a) establishes that a
Fly volume attaches to exactly one machine at a time. There is therefore no deploy strategy
— canary, blue-green — that can bring a second `api` up alongside the first while the volume
is where it is. The gap is a property of the topology, not of the strategy flag. *(How Fly
sequences the replacement internally I have not measured; see §6.)*

## 2. What that window actually costs — and it is less than it looks

Meta's Webhooks documentation (fetched 2026-08-25):

> "If any update sent to your server fails, we will retry immediately, then try a few more
> times with decreasing frequency over the next 36 hours."
> "Unacknowledged responses will be dropped after 36 hours."

So a deploy window of minutes does **not** lose client messages. It delays them.

**Two honest limits on that sentence, both raised by the refuter and both upheld:**

1. **The source is the GENERIC Graph API Webhooks page, not a WhatsApp Cloud API page.**
   Everything here assumes WhatsApp inherits the platform-wide retry policy. That is the
   normal reading, but it is an inheritance assumption, not a WhatsApp-specific citation.
2. **"Decreasing frequency" cuts against the comfortable reading.** If Meta's *immediate*
   retry also lands inside the window — entirely plausible when the window is minutes —
   the next attempt arrives on a decaying schedule, and the delay can exceed the window by
   a wide margin. "Nothing is lost" survives; "the delay is roughly the window" does not.

**Removed from draft 1:** a comparison against a "~990 s p90 inbound→outbound" figure. It
was uncited, and it was also the wrong instrument — steady-state latency while the service
is *up* says nothing about additive delay while it is *down*. The argument does not need it.

**This still corrects the framing the mandate was written on** ("ogni deploy ≈2-3 min di
webhook morto") — the window is real, the message loss is not.

⚠️ **One thing this does NOT rule out.** Persistent delivery failure is also how Meta
disables a webhook subscription. The 24-day silence of 2026-07-30 → 2026-08-23 is still
unexplained, and `GET /{WABA}/subscribed_apps` answers `500 {"code":1,"error_subcode":99}`
reproducibly. I am NOT claiming deploy churn caused that — there is no evidence linking
them, and the retry window is 36 h against an outage of 24 days. It is named here because
**it is the reason the recommendation in §5 carries a condition.**

## 3. Why `api` is not a drop-in for what was done to `drive`

`drive` was scaled to two machines cheaply because it has **no mount and no public
service** (`fly.toml`: `drive = "python -m backend.workers.drive_poll_worker"`). `api`
differs in three ways, each verified in this repo:

**(a) `api` owns a volume with two SQLite databases.** `fly.toml` mounts
`nuzantara_api_data` at `/data` for `processes = ['api']`, and the env sets
`EXPERIENCE_DB_PATH=/data/experience.db` and `METABOLIC_DB_PATH=/data/organism_metrics.db`.
A Fly volume attaches to exactly one machine, so a second `api` machine gets its **own**
volume. The writers (`app/routers/experience.py`, `app/routers/metabolic_health.py`) would
then be writing two divergent databases that never reconcile, with each request landing on
whichever machine the proxy picked. That is superscar #10 (active-active split-brain) by
construction, not by accident.

**(b) `api`'s lifespan spawns singleton-shaped background work.** `main_api.py::lifespan_light`
starts the notification scheduler (`main_api.py:139-142`) and `WA_OUTBOX_WORKERS` (default 2)
WhatsApp outbox scheduler loops (`main_api.py:161-167`). Two machines means both run twice.
The outbox worker is explicitly built for K concurrent workers — per-thread advisory lock,
claim-token fencing, burst coalescing — so it is the half that is probably fine. The
notification scheduler's behaviour under two instances is **unverified**, and I am not going
to assume it.

**(c) The WhatsApp admission gate is per-process, so it would silently double.**
`wa_inbox_bot._get_bot_generation_semaphore` is a module-level singleton bounding
in-flight RAG calls to `WA_BOT_MAX_CONCURRENT_GENERATIONS` (default 3) **per api process**.
Two machines = up to 6 concurrent generations aimed at a `rag` group that is still **one**
machine. *(Weight correction: with `--workers 1` on `api` this is a one-env-var re-tune, not
design work. Draft 1 listed it alongside the volume split-brain as if they cost the same.
They do not — (a) is the expensive one.)*

## 3bis. Where the reply actually happens — the fact draft 1 got wrong

This is the correction that changes an option's verdict, so it is stated with its evidence:

- **The reply is generated inside `api`, not handed off.** `/webhook/whatsapp` persists to
  `inbound_webhooks`, ACKs 200, and schedules generation via FastAPI `BackgroundTasks`
  (`whatsapp_chat.py:1614`, `:1622`) — a task that runs **in the `api` process itself**.
- **`WebhookProcessor` — the recovery drain — runs in `rag`, not `api`.** It is constructed
  and started only in `app_factory.py:311-322`. `main_rag.py:32,48` uses that factory's
  lifespan; `main_api.py:225` uses `lifespan_light`, which never mentions it. `grep -n
  WebhookProcessor backend/app/main_api.py` returns nothing.

Consequence: during an `api` deploy, **no reply is generated by anyone**, and the recovery
drain that would catch up afterwards lives in a process group that is *also* a single
machine with a volume.

## 4. The options, with what each costs

**A — second `api` machine.** Removes the deploy window. Requires resolving (a), (b) and
(c) first: move the two SQLite DBs off the volume, verify the notification scheduler under
two instances, re-tune the admission semaphore. Real work, and it makes `rag` the next
single point of failure.

**B — split the webhook into its own tiny process group.** ⚠️ **Draft 1 recommended this as
"the architecturally clean answer". That recommendation is WITHDRAWN.** Per §3bis, a
stateless `webhook` group would ACK Meta instantly and then generate **no replies** during
an `api` deploy — client-visible latency identical to doing nothing. What it buys is
avoiding Meta retries, which §2 spends a page establishing are free. B is a fix aimed at
the half of the problem that was not costing anything. It becomes interesting only if the
generation path moves with it, at which point it *is* option A wearing a different name.

**C — do nothing to `fly.toml`.** Accept a minutes-long window per deploy, on the evidence
that Meta retries for 36 h and nothing is lost. Cost: delayed replies during deploys, on a
channel not yet publicly promoted. Spends nothing.

**D — reduce how OFTEN the window opens** (compatible with C): batch deploys rather than
shipping 24 releases a day, and prefer deploying outside Bali business hours
(`WA_BOT_BUSINESS_START`/`END`, 08:00–20:00 WITA, is already the sentinel's own definition
of when silence matters). *(Draft 1 titled this "reduce the window" — inaccurate: batching
changes the window's FREQUENCY, nothing here shortens the window itself. Per §1, on a
single machine with a volume, nothing can.)*

**E — move `experience.db` and `organism_metrics.db` to Postgres.** *(Added on the
refuter's finding; draft 1 buried this as a sub-clause of A.)* This repo is already a
Postgres shop — `inbound_webhooks` goes through asyncpg. These two SQLite files are the
**only** thing making `api` stateful. Moving them: (i) removes the mount, which is what made
`drive` cheap to scale; (ii) turns A from a three-problem project into a `fly scale count`
plus the (b)/(c) checks; (iii) removes the volume as a host-failure recovery SPOF, which
matters independently of deploys. It is the one option that is worth doing on its own merits
even if the answer to this whole question is "leave it alone".

## 5. Recommendation

**C, with D, conditional on restoring the `subscribed_apps` diagnostic** — and **E queued
as the cure to reach for** if the answer ever becomes "make it redundant".

The condition is not decoration. §2 names Meta-side subscription disabling as the failure
mode that a dead webhook could eventually cause, and `GET /{WABA}/subscribed_apps` currently
returns a reproducible 500 — meaning we **cannot read our own subscription state**. Choosing
to spend nothing is defensible; choosing to spend nothing *while blind to the one failure
mode you just documented* is not. Restore the diagnostic, then C is a real decision rather
than an absence of one.

Revisit trigger: the bot goes public, **or** the cadence stays this high once real traffic
exists. *(These two partly cancel — if D works, cadence drops and the second trigger never
fires. That is acceptable: D working IS the mitigation.)*

The reason not to reach for A now is not cost. It is that (a) trades a latency problem for
a silent-data-divergence problem, and this repo's own scar ledger says which of those two is
discovered later and hurts more. E is how you buy A without buying (a).

## 6. What is NOT established here

- **The actual duration of the deploy window.** Bounded by config, never measured. The probe
  that would settle it: poll `GET /webhook/whatsapp` (the GET handshake, which needs no
  signature) once a second across a deploy and record the non-200 span.
- **How Fly sequences a single-machine-with-volume replacement internally.** §1 asserts only
  what follows from single-attach plus count=1 — that no strategy overlaps the machines. The
  exact stop/attach/boot ordering is not measured here, and the refuter's confident version
  of this claim was deliberately not adopted.
- Whether the notification scheduler is safe active-active.
- Whether WhatsApp Cloud API inherits the generic Graph API retry policy verbatim (§2).
- Whether any inbound message has ever actually been delayed by a deploy. `inbound_webhooks`
  records what arrived, not what was retried, so our side cannot see it. Meta's Webhooks
  delivery diagnostics in Business Manager can (`operator[gui]`).
- **Deploy-time abandonment of in-flight replies.** Given §3bis, a SIGTERM mid-`BackgroundTask`
  kills a generation already under way. Whether `lifespan_light` shutdown drains those tasks
  is unverified. Raised by the refuter; left open rather than guessed.
- **There is no standing alarm on any of this.** No check watches "`api` health != 1/1", and
  §6's probe is manual. Noted, not built — building it is a different concern and a
  different PR.

## 7. Adversarial-review ledger (Kimi K3, 2026-08-25 — verdict FIX-FIRST(4))

Generator ≠ grader: the refuter ran on fresh context against the worktree. Recorded in full
because a review whose misses go unrecorded is indistinguishable from one that never ran.

**Confirmed by independent re-reading, and fixed:**

| # | Finding | Verification I ran |
| --- | --- | --- |
| 1 | Option B analysed against an architecture that does not exist | `grep -n WebhookProcessor backend/app/main_api.py` → empty; `app_factory.py:311-322` is the only construction site; `main_rag.py:32,48` uses that lifespan, `main_api.py:225` uses `lifespan_light`; `whatsapp_chat.py:1614,1622` are `background_tasks.add_task`. **B withdrawn** (§4, §3bis) |
| 2 | The window is structural (single volume + count=1), not merely unmeasured | Follows from §3(a) + the measured machine count. Adopted in a **narrower** form than the refuter's — see §6 |
| 3a | "~990 s p90" uncited | Could not re-source → **deleted**, and the argument rebuilt without it |
| 3b | "628 MB image pull" uncited | Could not re-source → **deleted** |
| 4 | Meta retry source is generic Graph API, not WhatsApp-specific; "decreasing frequency" undercuts the framing | Both **upheld and stated** in §2 |
| 6 | The standalone "SQLite → Postgres" option was buried | Promoted to **option E** |
| 7 | C recommended while the `subscribed_apps` diagnostic is broken | **C is now conditional** (§5) |
| 8 | §4-D mis-titled; §3(c) over-weighted | Both **corrected in place** |

**Where the refuter was itself wrong** (recorded so nobody re-derives it — the refuter
hallucinates too, scar family #6):

- **On the release count.** It objected that "v4244 − v4221 = 23 version numbers; '24
  releases' requires an inclusivity assumption." The inclusive count of v4221…v4244 is
  `4244 − 4221 + 1 = 24`; the arithmetic objection is simply wrong. Its *other* point on the
  same claim — that version arithmetic is not a release count, because failed releases
  consume numbers — was right, and §1 now counts actual `complete` rows instead.
- **On finding 5 ("internal contradiction on whether there is traffic").** Not a
  contradiction: "carried real load" describes a past week and "not yet publicly promoted"
  describes the current posture. The sentence that made it look contradictory was the
  uncited p90, which is gone for a different reason.

**Left open, deliberately:** its suggestion that `kill_timeout` etc. are "red herrings as
bounds" — they bound the drain, not the total gap; both statements are true and the
distinction did not change any option's verdict.
