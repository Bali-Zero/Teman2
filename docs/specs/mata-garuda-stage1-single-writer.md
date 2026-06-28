# SPEC — Mata Garuda Stage 1: single-writer / split-brain cure

> Status: **REV 2 — post 3-LLM panel** (2026-06-29). NO code until Zero gives G1.
> Derives from: `research/operations/2026-06-28-mata-garuda-mythos-tac.md` §5 Stage 1.
> Scar families addressed: #10 (active-active split-brain), #2 (esiste≠armato), #8 (network-flap).

## PANEL VERDICTS (3 heterogeneous models, asymmetric roles — CLAUDE.md §6)

| Panelist     | Model           | Verdict              | Load-bearing finding                                                                                                                                                                                                                   |
| ------------ | --------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Red-team     | Gemini 3.x      | **NO-GO** (on REV 1) | PG-lock absurd → use Redis-lock; canonical must be H24 node; Tailscale flap drops one-shot crons; pointing 2 hosts at 1 Redis RE-introduces temporal overlap → mutex mandatory; snapshot rdb before cutover                            |
| Constructive | DeepSeek V4 Pro | **GO-WITH-FIXES**    | drop layer 3c entirely; fold heartbeat into Stage 1; canonical-going-forward (no back-merge) + rdb archive; assign organs per-host via plist `Disabled`                                                                                |
| Feasibility  | Codex GPT-5.5   | **GO-WITH-FIXES**    | claims (a)(c)(d) TRUE; claim (b) **FALSE as written** — mata_garuda ALREADY has PG access (`scripts/mata_garuda_invalidation_sweep.py:55` asyncpg) though the stream workers don't; "wired to no cron" confirmed (no deployable plist) |

**Convergence (≥2 models independently):** remove PG-advisory-lock from the primary design ·
canonical-going-forward + rdb snapshot · fold the minimal heartbeat · fix redis-cli path ·
mutex (if any) belongs on Redis, not PG.

**Gate W65 correction (my own on-disk re-verification — even the panel hallucinates):**

- Red-team AND DeepSeek both assumed "canonical = Mini because Pro sleeps". **FALSE** —
  CLAUDE.md:16 says **Pro = "workhorse H24 (176 daemon)"**; it is **M5** that sleeps (CLAUDE.md:15).
  So BOTH Pro and Mini are H24. Their _rule_ (canonical on an H24 node) stands; their _choice_
  (Mini) rests on a false premise. **Pro remains the stronger candidate** (H24 + all producers +
  the existing PG sweeper already live there). G1 is still Zero's call, but the panel's
  Mini-lean should be discounted.
- Codex's claim-(b) correction is accepted: PG is NOT a brand-new dependency for the app
  (the sweeper uses asyncpg already) — but it IS new for gap_consumer/nlm_feeder specifically.
  This weakens, but doesn't revive, the case for a PG lock: the panel still prefers no-lock.

## 0. Problem (grounded on disk 2026-06-28/29, not from memory)

Mata Garuda is a set of cron singletons spread across Pro + Mini with **no single
authoritative writer**:

- `base_worker.py:24-37` routes every `redis-cli` call to `GARUDA_REDIS_HOST` (or 127.0.0.1
  if unset). **GARUDA_REDIS_HOST is unset in every plist** → each host's cron talks to its
  OWN local Redis.
- Producers write Pro Redis; `sentinel.daily` writes Mini Redis; `nlm_feeder` reads whatever
  host it's pointed at → silently misses the other host's items (the W16 split-brain, 4337+
  items missed historically).
- `check_redis_split_brain.py` exists but is **wired to no cron AND is itself unrunnable**
  (`redis-cli` not in PATH in the non-login shell — verified live on Pro 2026-06-29). The
  watchdog of the split-brain is itself unarmed (#2).
- **Mata Garuda has zero Postgres access today** (grep: no psycopg/asyncpg/DATABASE_URL in
  the package). Any DB-based lock introduces a NEW dependency.

## 1. The honest tension this spec must resolve FIRST

The TAC §5 proposed `pg_try_advisory_lock` for single-writer. Grounding revealed a problem:

- `pg_advisory_lock` is **session-scoped** (`migration_manager.py:328-334`): the lock lives
  only as long as the holding connection. It auto-releases when the process exits.
- Mata Garuda singletons are **one-shot cron jobs** (run → process → exit), NOT long-running
  daemons. A lock acquired at start and released at exit only protects against _temporal
  overlap_ (two runs at the same instant) — which is NOT the actual failure.
- The actual failure is **logical divergence**: cron on Pro and cron on Mini run at
  _different_ times, each against a _different_ Redis, and the union is never reconciled.
  A mutex does not fix two-sources-of-truth; it only serialises concurrent access to one.

**Conclusion: a pure advisory-lock is the WRONG primary cure for THIS bug.** It is necessary
but not sufficient. The real cure is **declaring ONE Redis as canonical** and making every
consumer read it. The lock is a secondary guard against accidental double-run.

This tension is the central thing the panel must pressure-test.

## 2. Goal

Exactly one authoritative Redis instance for the `garuda:*` streams, every producer AND
consumer agreeing on it, with a cheap guard against accidental concurrent runs and an
end-to-end liveness signal that tells the truth (rows-processed, not exit-code).

Non-goal: durable-execution migration (DBOS), Neo4j, reviving the meta-agent — all explicitly
deferred (TAC §5 Stage 5/6).

## 3. Design — three layers, smallest-first

### 3a. Canonical-host declaration (the REAL split-brain cure) — MANDATORY

- Introduce one config constant `GARUDA_CANONICAL_REDIS` (host:port) read by `base_worker.py`
  as the default when `GARUDA_REDIS_HOST` is unset, replacing the silent 127.0.0.1 fallback.
- Decision required (panel + Zero): **which host is canonical** — Pro (where producers +
  intel_scraper live) or Mini (server H24). Evidence leans Pro (producers are there; Mini's
  only producer is sentinel.daily/RSS which can be pointed at Pro). Mini-as-canonical would
  require moving producers.
- Every `com.matagaruda*.plist` gets `GARUDA_REDIS_HOST=<canonical>` set explicitly. No plist
  relies on the implicit localhost default ever again.
- The non-canonical host's mata_garuda crons either (i) point at the canonical Redis over
  Tailscale, or (ii) are disabled on that host. Declarative `assigned_node` per organ.

_Falsifiable metric:_ `check_redis_split_brain.py` (once runnable) reports drift <1h for 7
consecutive days. Currently it cannot even run → fixing that is part of this layer.

### 3b. Make the detector runnable + wired — MANDATORY

- Fix `REDIS_CLI = "redis-cli"` (`base_worker.py:21`) to resolve an absolute path
  (`shutil.which` with a fallback list incl. `/opt/homebrew/bin/redis-cli`), so cron/non-login
  shells don't silently fail. This is the #2 fix: the watchdog must actually run.
- Wire `check_redis_split_brain.py` to a cron (e.g. hourly) on the canonical host, emitting to
  the organism alert channel (the receptor from PR #1805/#1808), NOT to Zero's Telegram.

_Falsifiable metric:_ the detector cron produces a real result row each hour; a deliberately
induced 2h drift fires an organism alert within one cycle.

### 3c. Concurrency guard — RESOLVED: NO LOCK now (panel 3/3)

**Panel verdict: drop the advisory-lock entirely from Stage 1.** With organs assigned to exactly
one host (3a + the `Disabled` plist key) and launchd's own single-instance-per-label guarantee,
concurrent double-run is not a real failure mode. Both DeepSeek and Codex judge a PG lock as
unnecessary complexity; the red-team calls a cross-host `flock` useless (separate filesystems).

- **Decision:** ship NO lock. Keep a documented escape hatch: IF a double-run is ever observed,
  add a Redis `SET <key> <run_id> NX EX <ttl>` guard on the canonical Redis (reuse the existing
  Redis-mutex pattern at `apps/organism/organism/supervisor/mutex.py` / `scripts/agent_lease.py`
  — NOT a new PG dependency). The mutex, if ever needed, lives on Redis (the single source of
  truth), per red-team #1.

### 3d. End-to-end heartbeat — RESOLVED: FOLD INTO STAGE 1 (panel 2/2)

- Each singleton writes `{organ, ts, status, rows_processed, run_id}` at END of real work — to the
  SAME `~/.organism/last_seen/` channel the receptor already reads, so the status-aware detector
  (PR #1808) surfaces a green-but-dead gap_consumer (95%-unacked) as `unhealthy`.
- **Codex caveat (accepted):** `scripts/lib/heartbeat.py` writes only `ts/status/note` — for the
  `{rows_processed, run_id}` metadata use the metadata-capable emitter
  (`apps/cell/cell/utils/organ_emitter.py:40`) OR extend the helper. Do not silently lose the
  metadata schema (superscar #9 — two sidecar formats already exist).
- **Decision:** fold in; it is the cheapest validation instrument for the 7-day metric window.

## 4. Scope / blast radius

- Files touched: `base_worker.py` (host default + REDIS_CLI path), the 12-13
  `com.matagaruda*.plist` (add GARUDA_REDIS_HOST), `check_redis_split_brain.py` (cron wiring),
  optionally gap_consumer/nlm_feeder (lock + heartbeat).
- Hot-zone: LaunchAgent plists + cross-host shared-state → AUTONOMOUS_OPS L2, PR + Zero merge.
- PII: none in stream metadata touched here; OSINT payloads stay Pro-local (Law 2 unaffected).
- Reversibility: all changes are config/guard; revert = unset GARUDA_REDIS_HOST + drop lock.

## 5. Decision gates (go/no-go)

- **G1 (Zero) — OPEN:** which host is canonical (Pro vs Mini). Blocks 3a. Panel leaned Mini on a
  false premise (Pro is H24, not asleep); my recommendation is **Pro** (H24 + producers + PG
  sweeper already there). Still Zero's strategic call.
- **G2 (panel) — RESOLVED:** NO lock now; Redis-mutex escape hatch only if double-run observed.
- **G3 (panel) — RESOLVED:** fold minimal heartbeat into Stage 1.
- **G4 (empirical):** detector exits 0 for 7 consecutive days post-change → split-brain cured.

## 5b. Panel-added safety gates (REV 2)

- **rdb snapshot before cutover** (red-team #6 + DeepSeek): `bgsave` + archive the non-canonical
  Redis `.rdb` BEFORE rewriting any plist, so the 37-day fork is recoverable. MANDATORY.
- **retry on remote Redis calls** (red-team #4, superscar #8): once consumers cross Tailscale, a
  blip must not silently drop a one-shot cron's work — wrap `redis_cmd` in bounded retry/backoff.
- **redis-cli abs path** (red-team #5 + DeepSeek): `shutil.which("redis-cli")` + fallback list, so
  cron/non-login shells stop failing mutely (the watchdog-unarmed bug, verified live).
- **SPOF disclosure** (DeepSeek e): document that one canonical Redis = if it's unreachable, ALL
  crons stop. Accepted trade-off vs silent split-brain corruption; replication is a later stage.

## 6. What this spec deliberately does NOT do

- No DBOS / durable-execution (Stage 5, NO-GO by default).
- No reconciliation/merge of the two DIVERGED Redis histories — we pick a canonical going
  forward; back-merging 37 days of divergence is a separate operator decision (is the stale
  data even worth recovering?).
- No change to embedding model, no Neo4j, no meta-agent revival.

## 7. Open questions for the 4-LLM panel

1. Is the canonical-host declaration (3a) the correct PRIMARY cure, or is there a better
   split-brain fix for one-shot crons across 2 hosts that we're missing?
2. advisory-lock (new PG dep) vs flock (no dep) vs nothing — for one-shot crons, what actually
   prevents the real failure?
3. Should we back-merge the 37-day Redis divergence or declare canonical-going-forward and
   drop the stale fork? (data-loss judgment)
4. Any failure mode introduced by pointing both hosts' consumers at one Redis over Tailscale
   (network-flap #8 — does a Tailscale blip now starve BOTH hosts instead of one)?
