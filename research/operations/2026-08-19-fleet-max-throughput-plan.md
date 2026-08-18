---
date: 2026-08-19
domain: operations
client_case: N/A — internal fleet governance (max-throughput session layout, 3 machines + cloud)
sources: 7
discovered_by: session (worktree .worktrees/ops-army-throughput, mandate Zero 2026-08-19 "massiccio attacco di sessioni ben modulate sulle 3 macchine e se serve anche con metodi cloud")
adversarial_review: codex
---

# Fleet max-throughput plan — sessions across M5/Pro/Mini + cloud, modulated

**Mandate (Zero, 2026-08-19, verbatim fragments)**: "analizza le sessioni
ongoing e pianifica un massiccio attacco di sessioni ben modulate sulle 3
macchine e se serve anche con metodi cloud … voglio categoricamente che
Jules, Codex Spark, [Gemini] Spark lavorino no stop h24 … dobbiamo essere
costantemente in movimento specialmente nell'usare llm di poco costo …
sempre la dashboard con i consumi così gli orchestratori sanno come muoversi,
ma che non sia un limite".

Sibling ruling shipped the same session (PR #4326): final-review gear split —
Fable 5 reviews Gear-3/large features only; Gear 1-2 close on Opus 5.

## 1. Measured state (2026-08-19 02:30-03:20 WITA, live probes this session)

| Node | Live sessions/lanes | Finding |
| --- | --- | --- |
| M5 | 1 interactive Fable session; 5 task worktrees (bot lanes); no tmux server | Command deck healthy; collector unarmed |
| Pro | 1 interactive claude; army-spark LIVE (2h tick) but **queue empty since 2026-08-17 04:13** (~22 empty ticks); army-jules LIVE, key in Keychain since 18/8, **queue empty since 15/8**; ~19 residual `codex mcp-server` processes | The H24 lanes exist and tick — they are **starved**, not broken (famiglia #2: "devono LAVORARE, non solo esistere") |
| Mini | only `ollama serve`; load ~3.3; no agent lanes at all | **Biggest untapped capacity in the fleet** |
| Dashboard | `scripts/usage/` collector existed since 2026-08-09, **armed nowhere** (README's own PENDING-ARMS note still true 10 days later) | W81 textbook |

Meta-diagnosis: the constraint on "no stop h24" was never engine capacity —
it is **feeding**. Every starving surface above starves because nothing makes
queue-feeding a standing duty.

## 2. The attack layout (lane map per node + cloud)

**M5 — command deck (interactive)**
- 1-2 conductor sessions (Opus 5 default; Fable only when a Gear-3 arc needs
  the gate). Twin strategic sessions per the `workflow` skill when a mandate
  is wide (disjoint lanes, ledger handoff).
- Sonnet-5 subagent fan-outs for harness-native BUILD units only; everything
  batch/iterative routes to workhorse doors (TP1 Qwen/DeepSeek-flash, GLM
  z.ai, agy) per MODEL_ROSTER §Throughput doctrine (section added by PR
  #4326, armed in the merge queue at write time — until it lands, the
  binding source is the workhorse-first memory ruling of 2026-08-15).
- Qwen Code CLI seat lives ONLY here — Pro/Mini reach it via `ssh air`.
- seat-usage collector: armed at this arc's ship step (installer in this PR;
  proof = a snapshot written BY LAUNCHD, never a hand-run of the collector).

**Pro — H24 workhorse**
- army-spark: fed 9 read-only census tasks this PR. Pace measured on
  COMPLETED REPORTS, not attempts (the run-count state files count
  invocations before success/failure splits — Codex finding #8): 5 reports
  in the 3 observed days (15-17/8) ≈ 1.7/day → 9 tasks ≈ 5-6 days of food.
  Refill duty = every conductor session's CLEAN stage.
- army-jules: 1 anchored task this PR; sessions add anchored tasks as they
  scope them (queue contract unchanged: no speculative seeding).
- Existing cron fleet + WR2/WR3 lanes unchanged.
- seat-usage collector: armed at this arc's ship step (same installer, same
  launchd-driven proof).
- Lane liveness measured this session via launchctl + lane logs; the
  roster's "not yet SSOT" caveats on #4179/#4180 were stale and are
  corrected by PR #4326 (Codex finding #4).
- Hygiene finding for a future sweep: ~19 residual `codex mcp-server`
  processes accumulated (bounded memory each, but they are session litter).

**Mini — the idle giant (proposal, next PR)**
- `army-local` lane: spark_lane-pattern standing lane running **flat/local
  seats** (claude-glm z.ai for compact reviews; agy flash for width; Ollama
  qwen3.5 for classification) on its own repo-side queue — read-only
  analyses like the spark queue, zero Anthropic quota. Mini is the H24
  server by design and today runs nothing but Ollama.
- TP1 heavy batches scheduled in the night-50% discount window run from
  Mini (`ssh mini` or launchd), keeping M5/Pro interactive-responsive.
- Status: PENDING-ARMS line (needs its own lane script + tests — not
  improvised in this PR).

**Cloud — the fourth machine**
- **Jules** (Google async implementer): fed by `infra/army/jules-queue/`;
  works while the Macs sleep; harvest lane already live.
- **Codex Spark bucket**: consumed by army-spark H24 (idle weekly bucket →
  read-only analysis).
- **Claude scheduled routine** (claude.ai cloud session): 1/day fleet-recon
  at 05:03 WITA — sweeps open PRs for red/`cancelled` required checks (W118:
  a cancelled required is invisible to failure sweeps) + army queue depth,
  produces a repair plan. **Attempted this session via the remote-trigger
  API: creation is BLOCKED on a missing cloud `environment_id`** (the API
  requires `ccr.environment_id`, and no cloud environment exists yet for
  this account — a one-time claude.ai/code setup). PENDING-ARMS line filed;
  the routine body/prompt is ready in the ledger entry. Deliberately ONE
  routine — cloud sessions spend Anthropic quota, which is the orchestration
  tier, not the batch tier.
- **Claude Cowork**: deep-work artifact sessions (the consumption dashboard
  itself was born in a Cowork session, 2026-08-09) — used on demand, not
  scheduled.
- **Gemini Spark**: GATED, NOT ARMED (study #4213 + 2026-08-15 repo-lane
  study): not a repo worker, not schedulable by a session — H24 only via
  GUI-verified Gmail/Docs/folder standing schedules, no PII/secrets, no
  unsupervised use. Activation is GUI-only → §Solo-operatore.
- **Kimi Desktop/Swarm**: operator-driven massive sweeps; K3 CLI stays
  surgical-only (quota lesson 2026-08-15).

## 3. Modulation rules (how "massiccio" stays "sereno")

1. **Workhorse-first, intensified** (MODEL_ROSTER §Throughput doctrine, PR
   #4326): Alibaba TP1 + Gemini doors are the default implementer/batch tier
   **respecting per-seat status** — `deepseek-v4-flash-0731` and
   `qwen3.7-plus` are ARMED (measured mileage); `qwen3.6-flash`/`3.7-max`
   stay PROBATION (never load-bearing alone) until they earn measured calls.
   FLEET_TOPOLOGY's `builder_primary` chain still lists Sonnet first for
   harness-native units — the intensification narrows WHICH units go
   Anthropic, it does not delete that chain. Anthropic seats =
   orchestration, judgment, gates. Consiglieri (Fable · Sol xhigh+ · K3 ·
   Qwen 3.8 Max) = "il meno possibile".
2. **Gear-split review** (ruling 2026-08-19): Fable only on Gear-3; Opus 5
   closes Gear 1-2. Protects the weekly Fable allowance for what needs it.
3. **Dashboard informs, never limits** (Zero verbatim): orchestrators read
   `~/.agent/cost-ledger/seat_usage_snapshot.json` +
   `~/.agent/seat-usage/console_quota_snapshot.json` to pick the
   least-loaded door. A hot seat means "use another door", never "stop".
4. **Night window**: TP1 heavy batches in the night hours, exploiting the
   console-visible "Night 50% Off" label on qwen3.8-max — the console does
   NOT publish the window's hours (Codex finding #7: the 22:50 UTC+8
   timestamp in FLEET_TOPOLOGY was a one-off quota-reset reading, not a
   recurring discount window) — probe the console label before scheduling.
5. **Queue-floor duty**: a lane ticking on an empty queue is a starved lane.
   Feeding spark (and anchored jules tasks) belongs to every conductor
   session's CLEAN stage — written into MODEL_ROSTER by PR #4326, and the
   starvation itself stays visible in each lane's daily digest.
6. **Fire-and-sleep**: no session busy-waits a lane, CI, or an external LLM;
   background + wakeup, cache-aware polling (≤270s or 1200s+).

## 4. §Meta-pattern

One defective belief generated every finding here: **"installed = working"**
(famiglia #2 at fleet scale). The army lanes were declared "LIVE" on 15/8 and
were live — and starving 48h later, because existence had a guardian
(launchctl, digests) while THROUGHPUT had none. The same belief left the
consumption collector unarmed for 10 days (its own README said so) and Mini
idle since its lean-down. The cure shipped by this arc is to make feeding and
measuring first-class: queues filled as a standing CLEAN duty, the collector
arming shipped with a LAUNCHD-driven artifact-freshness verify (the daemon
must write the snapshot — a hand-run of the collector proves nothing, Codex
finding #5), and the doctrine text (MODEL_ROSTER, PR #4326) naming
starvation as the failure mode to watch.

## 5. §Solo-operatore

- Gemini Spark schedule activation (GUI-only, consumer account) — shortlist
  from #4213 already delivered.
- Kimi Desktop / K3 Swarm sweeps (desktop app, operator-driven).
- TP1 add-on purchases if the rolling quota ever binds (spend = Legge 5).
- `codex login` re-auth on Pro acct2 if the 401 class returns.

## Adversarial review

Reviewed by Codex (GPT-5.6, `codex exec --sandbox read-only`, 2026-08-19,
235k tokens) with an explicit refute mandate over this doc + both queue
dirs + the SSOT files in the same tree. **10 material findings**, all
disposed in this same commit:

- **#1/#2/#4 (sequencing)**: the doc cited MODEL_ROSTER §Throughput
  doctrine and gear-split text that live in sibling PR #4326, not yet on
  main → every such citation now names #4326 and its armed-in-queue state.
- **#3 (SSOT inversion)**: the workhorse tier now respects per-seat
  ARMED/PROBATION status and no longer reads as deleting FLEET_TOPOLOGY's
  `builder_primary` chain (a 1-line pointer was added to that chain in this
  PR instead).
- **#5 (false "armed")**: collector claims rewritten to ship-step future
  tense, and the installer's proof was strengthened — it now passes only on
  a LAUNCHD-written snapshot (kickstart + mtime-advance poll), never a
  hand-run of the collector.
- **#6 (Gemini Spark)**: re-labeled GATED NOT ARMED with the study's gates
  named. **#7 (invented discount hours)**: the 22:50 figure was a one-off
  quota-reset reading — replaced with "probe the console label".
- **#8 (attempts ≠ throughput)**: pace re-derived from completed reports
  (5 in 3 days ≈ 1.7/day), not run-counts.
- **#9 (false premise in a queue task)**: the TG dedup census task was
  rewritten premise-free — it must measure `tg_notify.py`'s real
  window/pruning semantics first, then judge keys against those.
- **#10 (pre-existing doc defect found by the review)**: the spark-queue
  README described a `done-list.txt` contract the runner never implemented
  — corrected in this PR against the code (attempts.jsonl, sha-keyed,
  never-attempted cohort first, quarantine at 2 failures; each semantic
  re-verified directly at spark_lane.sh:292-305, not taken from the
  refuter's word).

Residual risk accepted: Codex could not reach Pro (its sandbox is
machine-local), so Pro-side liveness claims rest on this session's own ssh
probes; and the 1.7/day pace is measured from 3 days of history.
