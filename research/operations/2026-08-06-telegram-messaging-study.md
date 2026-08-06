---
date: 2026-08-06
domain: operations
client_case: none — Zero's mandate 2026-08-06 ("va rivista tutta la messaggistica, va accorpata, inviata poche volte al giorno. Ma prima capire, studiando lo storico della messaggistica, cosa può essere auto healing direttamente")
adversarial_review: codex
sources:
  - LIVE SPOOL, Pro, measured this session — `/Users/nuzantara/.organism/tg_spool/archive/*.jsonl` + `archive-p0.jsonl`: 5202 events, 2026-07-07 → 2026-08-06 (29.5 days), 57 sources, 1525 at tier `p0`. Every record carries the `key` the gateway actually used, so the replays below use recorded keys and reconstruct nothing.
  - `scripts/tg_notify.py` — `key = dedup_key or sha1(condition_identity(...))`; the explicit key wins. `scripts/tg_digest_flush.py` — the only other spool consumer, builds its footer from `sum(count-1)`.
  - `scripts/log_size_watchdog.sh` — `THRESHOLD_BYTES=1048576`, per-file 6h cooldown state file, emits at tier **digest** with `--dedup-key "log-size:<path>"`; LaunchAgent `com.balizero.nuzantara.log-size-watchdog.plist`, `StartInterval=3600`
  - `infra/launchagents/wrappers/log-rotate-run.sh` (live copy `~/scripts/log-rotate-run.sh` sha256-identical to `origin/main` this session) — `THRESHOLD_MB=50`, `ERR_THRESHOLD_MB=10`, copy-truncate; LaunchAgent `com.nuzantara.log-rotate.daily`, `StartInterval=86400`, `runs=5`, `last exit code=0`
  - `apps/wa-mirror/bridge/session.ts` — emits at tier **digest** with `dedupKey: "wa-bridge:disconnected:<account>"`; `apps/wa-mirror/bridge/index.ts` — a terminal logout path that stops retrying and needs a human QR re-link
  - `scripts/sentinel_lib/alerter.py:97` — `dedup_key = md5(message)`, i.e. a key that moves with the counter inside the message
  - Pro filesystem this session: `~/logs` = 1.2 GB total (57 `*.err.log` at top level totalling ~47 MB; the balance is subdirectories and archives), 11 files above the 1 MB alert line at 1.1–7.1 MB, three with mtime frozen at 04/07, 21/07, 31/07
  - Adversarial review: `codex exec -m gpt-5.6-sol` at `xhigh`, 25 objections, run against the FIRST draft of this document. It refuted the draft's central claim. §8 records what survived and what did not.
---

# What the organism actually says, and what it could have fixed instead

Zero's instruction had an order in it: consolidate the messaging **but first understand,
from the history, what can auto-heal directly**. This is that study.

It is also a study that got its headline wrong on the first pass and had to be rebuilt. §8
records that honestly, because the failure is the most reusable thing in here.

## 0. Executive answer

The organism spools **176 events/day**, of which **51.6/day are sent immediately** at tier
`p0`. The reason it is loud is not a broken deduplicator. It is this:

> **A 6-hour window on a condition that is permanently true yields four messages a day,
> forever.** The window works perfectly and the channel is still unusable.

Everything below follows from that. The fix that shipped takes the whole channel from
**176 → 48 events/day** and `p0` from **51.6 → 28.6/day**, and the two largest producers from
~60 and ~49/day down to ~4 each. The rest is producer work, itemised in §7.

## 1. The corpus, and which code path each event takes

```
events   5202       window 29.5d (2026-07-07 → 2026-08-06)      176.1/day
p0       1525       51.6/day
sources    57
```

| events | share | source | ev/key | tier |
|---:|---:|---|---:|---|
| 1798 | 34.6% | `log-size-watchdog` | 94.6 | digest |
| 1444 | 27.8% | `wa-mirror-bridge` | 60.2 | digest |
| 632 | 12.1% | `wa-attention` | 17.1 | p0 |
| 378 | 7.3% | `sentinel` | 1.5 | mixed |
| 243 | 4.7% | `dlq-autopilot` | 3.5 | mixed |
| 100 | 1.9% | `wr2-html-apply` | 1.4 | p0 |

`tg_notify` computes `key = dedup_key or sha1(condition_identity(source, text))` — **the
producer's key wins**. Split by the key actually recorded:

```
4847  (93.2%)  producer-supplied key   log-size-watchdog, wa-mirror-bridge, wa-attention, sentinel
 355  ( 6.8%)  derived key             dlq-autopilot, system-doctor, tech-orchestrator, compliance-ops
```

**This is the fact the first draft of this study got wrong**, and everything downstream of it
with it. See §8.

## 2. The deduplicator was not broken — that is the finding

Replaying a **flat 6h window over the recorded keys** reproduces the observed rate *exactly*:

```
observed                176.1/day        p0  51.6/day
flat 6h replay          176.1/day        p0  51.6/day     <- the control
```

Nothing collapses, because the archive already **is** the post-dedup output. The 6-hour window
was applied to every one of those 5202 events and let all of them through, because each was
the first sighting of its key in its own 6-hour bucket.

`log-size-watchdog` proves it at the finest grain: 1798 events over **19 stable keys**, and the
gap between two consecutive sends of the same key has **median 6.0h and minimum 6.00h — 0%
below six hours**. That is the fingerprint of a window doing its job with mechanical
precision, on nineteen conditions that were all simply *still true* the next time it looked.

So the defect was never "dedup doesn't fire". It was the **shape** of the rule: a flat window
treats the hundredth re-measurement of a month-old condition exactly like the first.

## 3. What shipped (#3668), and where it bites

**A persisting condition gets quieter, never louder.** Each further send of the same key mutes
it for the next rung of `6 / 24 / 72 / 168h`; silence past two windows means it resolved, so
the ladder restarts and the next occurrence is news again. A re-sent repeat carries
`(ripetuta N× nelle ultime Nh)`, because muting must never hide magnitude.

Replayed over the recorded keys:

| | events/day | p0/day |
|---|---:|---:|
| today | 176.1 | 51.6 |
| flat 6h (control — reproduces today exactly) | 176.1 | 51.6 |
| **ladder 6/24/72/168 — shipped** | **48.2** | **28.6** |

| source | now/day | after/day |
|---|---:|---:|
| `log-size-watchdog` | 60.9 | **4.2** |
| `wa-mirror-bridge` | 48.9 | **4.5** |
| `wa-attention` | 21.4 | **2.4** |
| `dlq-autopilot` | 8.2 | 5.4 |
| `sentinel` | 12.8 | **10.6** ← barely moves, see §4 |

The second shipped rule, **identity excludes measurements**, is honestly a small one: it is
the *fallback*, reached only by the 6.8% of events whose producer names no key. On those 355
events it collapses 167 raw identities to 35. It is worth having because a producer that names
nothing should get a sane default rather than a key that changes whenever a number does — and
because it is exactly what the producers in §4 should be passing instead of what they pass.

## 4. A producer key that MOVES is worse than no key at all

`sentinel` sets `dedup_key = md5(message)` — and its message contains the counter:

```
🔴 Sentinel | BLIND HEAL-LOOP: 16 TERMINAL job(s) parked in DLQ but ZERO healing
             actions for 99 consecutive cycles
```

168 BLIND HEAL-LOOP events produced **157 distinct keys**. Across all of sentinel: 378 events,
**255 keys — 1.5 events per key**. An explicit key that moves with the measurement does two
kinds of damage at once: it **bypasses** `condition_identity()` (explicit wins), and then it
**defeats every window**, because each re-measurement is a brand-new condition. That is why
the ladder only takes sentinel from 12.8 to 10.6/day.

The gateway cannot rescue this. `wr2-html-apply` (1.4 ev/key) and `dlq-autopilot` (3.5) have
the same shape. **The cure is at the producer**: pass a key naming the *condition*
(`sentinel:blind-heal-loop`), not a hash of the sentence describing it.

## 5. What can auto-heal directly — Zero's actual question

### 5.1 `log-size-watchdog` — 34.6% of traffic, and the alarm sits in a gap the cure cannot reach

The watchdog alarms on `~/logs/*.err.log` **above 1 MB** (hourly scan, 6h per-file cooldown,
digest tier). The rotator trims error logs **at 10 MB**, daily, by copy-truncate.

Above 10 MB the two agree. Between **1 and 10 MB** is a gap where a file is loud and eligible
for nothing. Every one of the 11 files currently over the alert line is in it:

```
7.1MB  06/08  wa-mirror-attention-classifier.err.log
6.7MB  06/08  intake-worker.launchd.err.log
5.8MB  06/08  intake-blob-retention.err.log
5.1MB  06/08  local-livekit-server.err.log
5.0MB  21/07  wa-dashboard-m1.err.log          <- frozen 16 days
4.5MB  06/08  wr2_supervisor.launchd.err.log
3.6MB  06/08  wa-mirror-attention-realtime.err.log
3.2MB  06/08  drive-intake-drain.err.log
2.5MB  31/07  flowkit.err.log                  <- frozen
2.0MB  04/07  wa-mirror-auto-promote.err.log   <- frozen
1.1MB  06/08  local-livekit-worker.err.log
```

Three of them are **not being written any more**. `wa-dashboard-m1.err.log` last changed on
21 July and sits at 5.0 MB: permanently above the alert line, permanently below the cure line,
never growing, never shrinking. It will be announced until someone deletes it by hand.

This gap was already found once. `log-rotate-run.sh` carries its own comment, dated 2026-07-20:

> `# 1-50MB dead zone — above the log-size-watchdog's 1MB alert line, below this rotator's`
> `# 50MB — so they never rotated and re-alerted every cycle (16 files, ...)`

Someone diagnosed it and closed it **half way**, from 1–50 MB down to 1–10 MB. The observed
population is 1–7 MB, so it is still entirely inside the remaining gap.

**Auto-heal, with its limit stated:** aligning the two thresholds (or having the watchdog
invoke the rotator) silences the *frozen* files permanently and the *live* ones until they
regrow. It rotates a symptom — the error-producing processes keep producing errors, and a
daily rotator against a live writer can be re-crossed before the next run. The honest framing
is that it converts a permanent alarm into a periodic one, and the frozen files into nothing.
It is not a substitute for reading why `wa-mirror-attention-classifier` writes 7 MB of stderr.

### 5.2 `wa-mirror-bridge` — 27.8%, and it recovers on its own

Pairing each disconnection with the next reconnection: **718 disconnections, 718 followed by a
reconnection**, median 1.0 min, 81% under 5 min, p90 25 min, max 358 min.

Stated precisely, because the method cannot support more: this is aggregate next-event
pairing, not per-incident tracking, and it is right-censored at both ends of the window. It
shows **no disconnection left the corpus unrecovered**; it does not prove no incident ever
needed a hand. The bridge does have a terminal logout path (`index.ts`) that stops retrying
and requires a human QR re-link — that one is `p0` and must **not** be suppressed.

**Auto-heal:** stop announcing the disconnection; announce the *failure to recover* past a
threshold. Roughly 10% of recoveries exceed 25 min, so ~72 incidents in 29.5 days would still
speak at a 25-minute line — that is a design choice about detection latency, not a number this
study can settle. What the study does establish is that the 81% resolving inside five minutes
are drowning the 358-minute tail, and today nobody can see the tail at all.

### 5.3 `sentinel` BLIND HEAL-LOOP — 168 announcements of one unhealed condition

The same condition, roughly every 4 hours, for a month. Announcing it 168 times did not heal
it. **Repetition is not escalation.**

Meanwhile `dlq-autopilot` reported `🧹 DLQ corpse-sweep: drained N recovered job(s)` 32 times,
and `dropbox_intake` was escalated to Claude Code 33 times and declared `🛑 TERMINAL` 33 times.
These are not necessarily contradictory — the autopilot may be draining *recovered* jobs while
different *terminal* ones stay parked. But nothing in the channel lets a reader tell, and that
is itself the defect: two organs narrate the same DLQ for 29 days in terms that cannot be
reconciled without opening the database. Resolving it needs job IDs on both sides, and is on
the ledger, not in this diff.

### 5.4 `wa-attention` — 632 events, and not an alarm at all

560 of them are `🚨 HIGH attention`. "A client is waiting for a reply" is a **product signal**,
not a fault. It shares a channel with disk pressure and dead crons because there has only ever
been one channel.

## 6. `p0` is mostly not `p0`

Of the 1525 immediate-tier messages, the large majority arrive on a fixed cadence — 24 source
labels whose inter-event gaps cluster on 4h, 6h, 8h, 24h or 48h. Urgency is a property of the
**condition**, never of the **schedule**; a report that was going to arrive at 06:00 whether or
not anything happened is not urgent by virtue of arriving at 06:00.

Two cautions, both raised by the adversarial pass and both correct:

- **A scheduled checker can still discover something urgent** (a failed backup, an expired
  credential). Demoting a whole *source* assumes it emits one severity class. It does not: the
  same `sentinel` label carries both the timer digest and the CRITICAL path. Re-tiering must be
  **per message class**, not per source label — this is why §7 lists it as producer work rather
  than a config sweep.
- Three of the 24 labels (`wa-attention` ~0h, `dlq-autopilot` ~0h, `wr2-html-apply` 0.3h) do
  not fit a timer cadence at all; they are high-frequency event streams that the gap-clustering
  heuristic mislabels. They need §4 and §5.4 treatment, not re-tiering.

Also worth noting: `run_multimodal` / `cron:run_multimodal` and `run_nb2_pipeline` /
`cron:run_nb2_pipeline` appear as four source labels for what look like two jobs. Confirming
they *are* the same producer needs the call sites; if they are, any per-source policy must
treat each pair as one or it will be written twice and enforced once.

## 7. The rules this establishes

1. **A condition announces itself when it is born, not while it lasts.** A flat window on a
   permanent condition is a metronome set to the window length. Repetition is not escalation.
2. **A key that moves with a measurement is worse than no key**, because it silently opts out
   of every collapse mechanism downstream.
3. **Announce the failure, not the process.** An organ that recovers on its own should speak
   only when recovery fails.
4. **An alarm must name a condition some organ can act on.** If the alarm line and the cure
   line do not overlap on the observed population, the alarm is decoration.
5. **A report on a timer is not urgent** — but severity is a property of the *message*, not of
   the *producer*, so never demote a whole source.

## Adversarial review

**Seat:** `codex exec -m gpt-5.6-sol -c model_reasoning_effort=xhigh --sandbox read-only`,
run against the **first draft** of this document, generator ≠ grader. **25 objections raised.**
It refuted the draft's central claim; the document was rebuilt from re-measured data rather
than patched.

**Objections adopted (the draft was wrong):**

1. *"`sha1(source|text[:160])` was the key"* — **refuted.** It was the *fallback*:
   `key = dedup_key or sha1(...)`. `log-size-watchdog` passes `log-size:<path>`, `wa-mirror`
   passes `wa-bridge:disconnected:<account>`, `sentinel` passes `md5(message)`. Verified at all
   three call sites. **93.2% of events carry a producer key.**
2. *"the window never once applied"* — **refuted.** The archive is post-dedup output; the
   flat-6h control reproduces the live rate exactly. Rewritten as §2, which is now the study's
   strongest evidence.
3. *"2791 → 362 conditions"* — **refuted as scoped.** That replayed the fallback over all 5202
   events. On the 355 events that actually take it: **167 → 35**.
4. *"51.6 → 15.9/day"* — **corrected to 28.6/day**, replayed over recorded keys.
5. *"6 sources >80% of days carry 87%"* — **refuted.** The table showed top-6 by volume, a
   different set (`wr2-html-apply` is 20/31 = 64.5%). The two sets are no longer conflated.
6. *"the alarm line and the cure line do not overlap"* — **narrowed.** They overlap above
   10 MB; the gap is 1–10 MB. §5.1 says so.
7. *"invoke the rotator and it is healed"* — **limited.** Copy-truncate against a live writer
   regrows; a daily rotator can be re-crossed before its next run. §5.1 now states that this
   converts a permanent alarm into a periodic one and silences only the frozen files.
8. *"1.2 GB that nothing is trimming"* — **refuted.** The 11 alarmed files total ~47 MB; the
   balance is subdirectories and archives with their own retention.
9. *"718/718 ⇒ self-healing at 100%"* — **method stated instead.** Aggregate next-event
   pairing, right-censored at both window edges. The terminal-logout `p0` path is now called
   out as one that must never be suppressed.
10. *"p90 25 min, so a handful remain"* — **refuted.** ~10% of 718 ≈ 72 incidents exceed it.
11. *"one of the two organs is wrong"* (sentinel vs dlq-autopilot) — **downgraded.** Both can
    be true of different jobs; the defect is that the channel cannot distinguish them.
12. *"re-tier 24 sources"* — **refuted as written.** A source is not a severity class; the same
    `sentinel` label carries the timer digest and the CRITICAL path. §6 re-tiers message
    classes.
13. *"a report on a timer is never urgent"* — **narrowed.** A scheduled checker can discover an
    urgent condition; the schedule sets observation time, not severity.
14. *"1423 of 1444 events are round-trip halves"* — **arithmetic wrong** (718 pairs = 1436).
    Claim removed.
15. *"it teaches everyone to ignore the channel"* / *"the noise was hiding it"* — **removed.**
    No acknowledgment or response-time data exists; this measured frequency, not attention.
16. *"`run_multimodal` and `cron:run_multimodal` are the same job"* — **downgraded** to "look
    like", with the evidence that would settle it named.

**Objections raised and NOT adopted, with reasons:**

- *"the p90 threshold is a non-sequitur, give an SLO"* — correct that a percentile does not
  pick a threshold, but no recovery SLO exists to derive one from. Recorded in §5.2 as an open
  design choice about detection latency, not silently converted into a number.
- *"eight control checks cannot establish corpus-wide collision safety"* — true, and a full
  labelled collision audit is disproportionate for a fallback that 6.8% of events reach. The
  scope limit is stated in §3 instead of being papered over.
- *"the census program is not committed, so the replay is not auditable"* — fair; the replay
  logic is stated precisely enough to re-derive (recorded `key`, ladder rungs, restart rule)
  and the inputs are the live spool, which cannot be committed. Noted as a real limitation.
- *"'not one has ever been eligible for rotation' is a snapshot"* — correct; the sentence now
  describes the present population rather than all history.
- *"111 emissions exceeds the 6h cooldown over 17 days"* — the 111 count spans the full 29.5-day
  window, not the post-20-July period. The claim that conflated them was dropped.

**Objection I raised against myself, after the review:** while rewriting, this document
asserted `355 → 118` for the fallback replay. Measured: **167 → 35**. See §8.

## 8. How this study was wrong, and what caught it

The first draft's headline was: *"the dedup key was raw text, so every repeat hashed anew and
the window never once applied — 5202 events presented as 2791 distinct conditions."*

That is **false**, and it was the load-bearing claim. `key = dedup_key or sha1(...)`: the
producer's key wins, and **93.2% of events carry one**. The 2791 figure came from replaying the
raw fallback over *all* events — a code path 93% of them never take. Built on it were: "dedup
was decorative", "51.6 → 15.9/day", and a re-tiering benefit that assumed producers whose
traffic is not even `p0`.

An adversarial pass (`codex -m gpt-5.6-sol` at `xhigh`, generator ≠ grader) returned 25
objections against that draft and led with exactly this one, citing the three call sites. Every
number in the present version was then re-measured from the recorded `key` field — and the
corrected picture is *better*: the flat-6h control reproducing the live rate to the decimal is
much stronger evidence for the ladder than a broken-deduplicator story would have been.

What the objections changed, concretely: the central mechanism (§2), the effect size (28.6/day,
not 15.9), the identity rule's scope (6.8% of traffic, not all of it), the §5.1 auto-heal
(limits now stated: rotation without fixing the writers is symptomatic), the §5.2 claim (method
and its censoring stated; the terminal-logout `p0` path excluded), the §5.3 contradiction
(downgraded to "cannot be reconciled from the channel"), the §6 re-tiering (per message class,
not per source), and the removal of two unsupported claims — that the volume "teaches everyone
to ignore the channel" (never measured: no acknowledgment or response-time data exists) and
that 1.2 GB of `~/logs` "is untrimmed" (the 11 alarmed files are ~47 MB; the rest is
subdirectories and archives with their own retention).

Three lessons, in the order they hurt:

- **A fallback is not the path.** Before claiming what a code path does to a corpus, check how
  many events take it. `x or y` means `y` is the minority case by construction.
- **The refuter earns the next round, it does not end it.** Objections 4–6 were right and the
  study is better for them; several others (the "1423 vs 1436" arithmetic, the "1–10 MB not
  1–50 MB" correction) were also right. Some were not adopted — the p90 threshold objection
  asks for an SLO that does not exist, and is recorded as an open design choice rather than a
  defect. Adopting an objection uncritically is the same failure as ignoring it.
- **The correction is itself an unverified claim** (W113). While rewriting, this document
  asserted "355 → 118 conditions" for the fallback replay. The measured value is **167 → 35**.
  That sentence was written *in the act of fixing another sentence*, which is precisely the
  place nobody looks.

## 9. Ledger

**Shipped** — #3668: the escalating mute ladder with death-detection and a declared suppression
count; identity-excludes-measurements as the no-key fallback; `TG_DEDUP_HOURS` preserved as the
first rung; both `tg_notify` test files armed in `tg-gateway.yml` (they ran in no workflow
before — `scripts/tests/ sweep` is `continue-on-error` and gates nothing).

**Open, in order of size**

| what | owner | size |
|---|---|---|
| `sentinel`, `wr2-html-apply`, `dlq-autopilot`: replace `md5(message)` keys with condition keys (§4) | session | unlocks the ladder for ~12/day it cannot currently touch |
| Align `log_size_watchdog.sh` with the rotator, or have it invoke it (§5.1) | session | 34.6% of traffic; frozen files silenced permanently |
| `wa-mirror-bridge`: announce failure-to-recover, not disconnection (§5.2) | session | 27.8% |
| Re-tier timer-driven message *classes* `p0` → `digest` (§6) | session | the bulk of the residual 28.6 p0/day |
| Delete the three frozen `~/logs` files nothing will ever trim (§5.1) | session | disk + permanent alarms |
| `sentinel` vs `dlq-autopilot` narrate the same DLQ irreconcilably (§5.3) | session | correctness, not volume |
| `wa-attention` onto its own surface (§5.4) | session | 12.1% |
| `drive-token-watchdog` has been failing identically for 25 days | session | — |
| Rotate the `@Balizerobot` token via @BotFather — it is in 25 commits of a public repo | `operator[credential]` | security |
