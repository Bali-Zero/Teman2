# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### ⚠️ STRUCTURAL: Test infrastructure mock != production stack (Sprint 1.B 2026-05-02, 3 hotfix in chain)

_Discovered: 2026-05-02 during Sprint 1.B Era Post-Agentica deploy — 3 hotfix
PRs (#423, #424) chained on the original PR #422 because tests were green
but live endpoints failed. Severity: P1 — every new endpoint addition is at risk._

**TRAUMA:** Sprint 1.B PR #422 added a new FastAPI router
`apps/backend-rag/backend/app/routers/channel_health.py` exposing
`GET /api/channels/{name}/health` for Cell-side heartbeat bridge. Unit tests
all green (4/4), but on prod:

1. **First curl** post-deploy → `401 {"detail":"Authentication required"}`. Cause:
   `HybridAuthMiddleware` blocks all `/api/*` paths not in `PUBLIC_ENDPOINTS` registry.
   Test `_build_app_with_db_pool()` mounted only the router, NOT the middleware
   stack, so auth was never exercised. Fixed by hotfix #423 — added 4 exact-match
   entries in `_INFRA` group of `apps/backend-rag/backend/app/auth/public_endpoints.py`.
2. **Second curl** post-deploy of #423 → `404 {"detail":"Not found"}`. Cause:
   the new router was added to `router_manifest.py` as `RouterEntry(name="channel_health", ...)`
   but `router_registration.py` uses **explicit imports**, not the manifest. The
   manifest is read by tests (`test_router_manifest.py`) but NOT by the runtime
   `include_routers()` and `include_light_routers()` functions. Fixed by hotfix
   #424 — added `from backend.app.routers import channel_health` (×2) and
   `api.include_router(channel_health.router)` (×2) in router_registration.py.
3. After deploy of #424, all 4 endpoints returned 200 + valid JSON.

The 3-PR chain (#422 → #423 → #424) cost ~2 hours of CI/deploy/curl cycles
that could have been avoided if the test infrastructure exercised the full
production stack (middleware + manifest-vs-registration drift).

**ANTIBODY (proposed but not yet implemented in code):**

1. **Integration test layer** — `apps/backend-rag/backend/tests/integration/test_endpoints_reachable.py`
   that mounts the full `main_api` (or `main`) FastAPI app via `create_app()`
   and `httpx.AsyncClient(app=app, base_url="http://test")`, then GETs every
   route returned by `app.routes`. For each path:
   - Expect 401 (if not in PUBLIC_ENDPOINTS) or 200/404/422 (if public).
   - Any new path that returns 404 → test fails.
   - Any new path with `health` in URL that returns 401 → flag as candidate
     for PUBLIC_ENDPOINTS review.

2. **Manifest-vs-registration parity test** — `backend/tests/setup/test_manifest_parity.py`:
   - Read `ROUTER_MANIFEST` from `router_manifest.py`.
   - Read `include_routers()` source via `inspect.getsource()` and grep for
     `include_router(<name>.router)` calls.
   - Assert every `RouterEntry(name=X)` with `process_groups` containing
     `_API` or `_BOTH` has a matching `api.include_router(X.router)` call
     in both `include_routers` AND `include_light_routers`.
   - Catches drift the moment a new manifest entry is added without the
     corresponding explicit imports.

3. **Public endpoint registry test extension** —
   `tests/test_public_endpoints_registry.py` already enforces "every registered
   path resolves to a mounted route". Add the inverse: every route with
   `/api/.*/health` or `/api/.*/heartbeat` pattern that is NOT in PUBLIC_ENDPOINTS
   triggers a test warning (not failure — some health endpoints are intentionally
   admin-only, like `/api/channels/health`). Reviewer must explicitly mark
   `# health-private: <reason>` in the route handler to silence the warning.

**GOTCHA:**

- The test mock `_build_app_with_db_pool()` in
  `backend/tests/unit/app/routers/test_channel_health.py` is the canonical
  pattern for new router unit tests. It is **intentionally minimal** — it
  does not mount middleware. That is correct for unit tests of router logic.
  The bug class is the *absence* of a complementary integration layer, not
  the unit test pattern itself.
- `router_manifest.py` has a SCAR comment at the top referring to PRs
  #54/#55/#60 ("registered routers only in include_routers() but not
  include_light_routers()"). Sprint 1.B Sprint 1.B PR #422 is a **regression**:
  same scar class, different surface. The manifest was created to "make this
  structurally impossible to repeat" — but only for the symmetric case of
  routers added to one include function but missed in the other. It does NOT
  catch routers added ONLY to the manifest with no include_router call at all.
- `HybridAuthMiddleware.__init__` logs `Public Endpoints: {len(self.public_endpoints)}`
  at FastAPI startup. After PR #423 the count went from N to N+4. The log line
  is grep-able as a sanity check after every public-endpoint PR — but only
  on Fly machines, not CI.
- Required CI checks (E2E + MCP + Frontend + Detect Secrets) did NOT catch
  any of the 3 issues. E2E Tests touches frontend only; backend route mounting
  drift is not exercised. Adding the 3 antibody tests above costs ~50ms each
  in CI, no infra needed.

Sprint timeline reference (Sprint 1.B Era Post-Agentica, 2026-05-02):
- 11:30 UTC PR #422 merged → deploy success → 401
- 12:50 UTC PR #423 (public_endpoints) merged → deploy success → 404
- 14:25 UTC PR #424 (router_registration) merged → deploy success → 200 ✅

Brainstorm artifacts: none yet (this entry is post-mortem). Future agents
implementing the antibody integration test should reference this scar as
a self-contained reproduction.

---

### ⚠️ STRUCTURAL: Untracked files lost when sibling automation switches branches mid-session (2026-04-29, twice in 9h)

_Discovered: 2026-04-29 21:42 WITA (incident #1, FASE 1+2 doc-recovery from
context) and 22:30 WITA (incident #2, W0-A `.py` file recovery from
`.git/objects` dangling blobs) · Partial mitigation: WIP-commit-every-10min
pattern (MOS lesson 2026-04-29) · Permanent fix: TBD, requires identifying
producer at the automation layer_

**TRAUMA:** Long-running Claude Code sessions (Opus 4.7 max effort, 1M
context, multi-hour) accumulate untracked work product (`.py` files,
`.yaml`, `.md` design docs) in the working tree before reaching a commit
threshold. Sibling processes — `nuz-sync` watchdog, parallel `claude`
sessions, possibly `agent-*` subagents launched with
`--dangerously-skip-permissions` — perform `git stash` + `git checkout
<other-branch>` + `git pull` sequences automatically, dropping untracked
files from the working tree.

`git stash` without `-u` does NOT stash untracked files. `git checkout
<branch>` allows the operation to proceed even when untracked files would
be silently dropped IF the target branch doesn't have those paths.
Result: file-loss is silent at the git level, observable only by
inspecting the working tree post-switch.

Same-day recurrence with two distinct producers makes this STRUCTURAL,
not a one-off:

| Incident | Time (WITA) | Producer | Lost |
|---|---|---|---|
| #1 | 21:42 | `nuz-sync` watchdog auto-pull | 2 untracked design docs (`00_design_intent.md` + `01_innervation_matrix.md`, ~17 KB combined). Recovered from in-context conversation buffer; NOT recoverable from `.git/objects` because never `git add`-ed before drop. |
| #2 | 22:30:03 | Parallel Claude session checking out `nbe/resend-fallback-team-templates` | 4 untracked `.py` files (~26 KB). Recovered from `.git/objects` dangling blobs because the file content had been hashed during a previous `git add` attempt before the hijack. |

Concrete forensic sequence for incident #2 (full timeline in commit
`7decc8187` `99b_status_2026_04_29_w0a_branch_hijack.md`):

| Time | Event |
|---|---|
| 22:14 | Session-A starts FASE 3 W0-A on `feature/innervation-2026-04-29`. |
| ~22:25 | Session-A writes 4 untracked `.py` files (~26 KB) + 18/18 tests passing. |
| 22:30:03 | Sibling claude session: `git stash` (tracked-only) + `git checkout main`. Tracked edits land in `stash@{0}` as `innervation-wip-pre-NBE`. |
| 22:30:06 | Same sibling: `git pull origin main --ff-only` + `git checkout nbe/resend-fallback-team-templates`. The 4 untracked `.py` files are silently dropped from working tree (target branch doesn't carry those paths). |
| ~22:31 | Session-A's next bash command runs into `cd: no such file` because `apps/cell` symlink resolution is now under a different branch's worktree shape. |
| 22:32 | Session-A diagnoses via `git reflog` + `git fsck --dangling --no-reflogs` and recovers all 4 files from `.git/objects` to `/tmp/innervation-recovery-20260429_223214/`. |
| 22:42 | Path B atomic restore + WIP commit `3980a1403` + push to origin in <30s window. |

**ANTIBODY (partial — permanent fix pending):**

1. **WIP-commit-every-10min policy** (MOS lesson saved 2026-04-29,
   importance 8): every long-running session SHOULD commit a "WIP
   checkpoint" to its feature branch every ~10 minutes whenever
   untracked files exist in the working tree. Committed objects are
   reachable from the branch ref, NOT subject to checkout silent-drop.
   Pattern (in shell, single atomic batch — NEVER as multiple separate
   commands):

   ```bash
   if git ls-files --others --exclude-standard | grep -q .; then
     git add -A apps/<scope>/  # scope-limited, NOT bare `git add -A`
     git commit -m "WIP(<scope>): checkpoint $(date +%H:%M) — work in progress"
     git push origin "$(git rev-parse --abbrev-ref HEAD)"
   fi
   ```

2. **Push within 30 seconds of commit**: protects the local commit
   against further hijack OR Pro disk-loss. Do not run any Write/Read
   tool calls between `git commit` and `git push origin`.

3. **Pre-session check `ps aux | grep claude | wc -l`**: counts
   concurrent Claude processes. If >2 (current session + the
   `~/scripts/claude-max-usage-watcher.py` cron tick), STOP and ask
   Zero which processes to kill before starting work. Concurrent
   sessions are the documented vector of the 22:30 hijack.

4. **Recovery procedure documented for next time**: dangling-blob
   extraction is reliable for content that has been `git add`-ed at
   least once OR written via tools that hash content into the
   object store. To recover any blob from this incident class:

   ```bash
   git fsck --dangling --no-reflogs 2>&1 | grep "dangling blob"
   for h in <hash>; do
     git cat-file -p "$h" > /tmp/recovery-$(date +%s)/<filename>
   done
   ```

   Same-hour recovery is reliable. After ~14 days, `git gc` may
   prune dangling blobs unrecoverably.

**ANTIBODY (TBD, requires investigation):**

- Identify which sibling process performed the 22:30 branch-switch.
  Suspects (per `ps aux` snapshot at 22:32):
  - PID 79949 (long-running Opus, 26 min CPU consumed since 13:19) —
    candidate #1. The session that wrote the FASE 1+2 docs is likely
    still resident.
  - PID 42807 (long-running, since 13:01) — candidate #2.
  - `agent-B-nba`, `agent-D-p02-fase2`, `agent-E-p05-fase2` (wave-2/wave-3
    team agents, `--dangerously-skip-permissions`) — any could have
    issued the checkout via filesystem MCP.
  - Bash background `until` loop watching deploy `410da34b` (PID 29764)
    is a poll, not a checkout actor.
- Until identified, the trigger condition cannot be eliminated.
- Future investigation directions: pre-checkout git hook that refuses
  to switch when untracked files exist AND the parent process is not
  the session that created them; mutex / lockfile on `feature/*`
  branches during long-session work.
- **Innervation Genoma exclusion (2026-04-30)**: `nuz-sync` is
  explicitly NOT enrolled in `apps/organism/organism/genome.yaml`
  despite being a critical Pro organ. Rationale: this scar identifies
  sibling automation as the most likely producer of branch-hijack
  incidents, and `nuz-sync` is the prime suspect for incident #1
  (auto-pull on git changes during long Claude sessions, fired inside
  its 5-min cron tick window at 21:42). If the Organism Supervisor
  were to auto-recover `nuz-sync`, a recovery loop during a
  hijack-in-progress could amplify the file-loss blast radius. Manual
  operator restart only until the producer is conclusively identified
  and isolated. Quarantine documented in PR W1.0 (`chore/innervation-w1-cleanup-2026-04-30`).

**GOTCHA:**

- `git stash list` shows incident #1's stash with descriptive label
  (`feature-innervation-temp-2026-04-29`) but does NOT contain the
  actually-lost design-doc files. The stash only saved tracked-but-dirty
  files (CLAUDE.md, lint, etc.) — the untracked design docs (`00`+`01`
  ~17KB) were dropped between the auto-stash and the checkout. **A stash
  whose label is "temp-<branch>" is not a guarantee that all WIP work
  for that branch is in it.** Always cross-check `git fsck --dangling`
  output against the stash patch before assuming "stash has my work".

- Recovery via `git fsck --dangling --no-reflogs` only works if the
  file content was hashed into `.git/objects` at some point. Files
  written to disk and never `git add`-ed do NOT have a blob there.
  Incident #1 design docs (00 + 01) had been written via the `Write`
  tool but were never `git add`-ed before the 21:42 stash-and-pull;
  they were unrecoverable from objects (had to be reconstructed from
  conversation context). Incident #2 `.py` files HAD been `git add`-ed
  during the in-progress test cycle, so blobs existed and recovery
  was clean.

- Recovery dirs in `/tmp/innervation-recovery-*` are volatile (cleared
  on macOS reboot). Always copy critical recovery artifacts into a
  committed branch within minutes, not hours. The Path B sequence in
  commit `3980a1403` is the canonical idempotent recipe.

- `nuz-sync watchdog` history (per `~/logs/nuz-sync/last-run` mtime
  1777473151 = 22:32:31 UTC) shows the watchdog ran AFTER the 22:30
  hijack — so it isn't the producer of incident #2. It IS likely the
  producer of incident #1 (21:42 was inside its 5-min cron tick
  window). Two different producers, same symptom = structural class.

- `_writer="pro"` field in `shared/escalations_pro.jsonl` confirms the
  hijack was a same-machine concurrent session, not Air→Pro federation.

Memory references: MOS records the 22:30 timeline as decision/discovery
2026-04-29 importance 9 ("Innervation Track C3 W0-A interrupted by
branch hijack — Path B executed, WIP commit 3980a1403 has 9 files / 1029
insertions / 18 tests passing, full forensics in 99b_status_*"). The
21:42 incident reference: `02_dispatch_resilience_log.md` § 6 in the
innervation FASE 1 docs.

---

### ✅ RESOLVED: Backend prod down — drive_poll_service called missing method on ServiceAccountDriveService (2026-04-29)

_Discovered: 2026-04-29 ~01:54Z (login flow 500 on kita.balizero.com) · Patched: same day, recovery 03:11Z, vaccination PR `ops/post-incident-vaccination-2026-04-29`_

**TRAUMA:** `apps/backend-rag/backend/services/crm/drive_poll_service.py`
called `await drive_service.get_file_metadata(...)` at lines 266 and 314 on
a `ServiceAccountDriveService` instance that did NOT implement that method.
Each Drive change event raised an unhandled `AttributeError`; the cron
runs every 5 minutes on Pro and the drive watch returned thousands of
changes after a recent backfill, so the event loop drowned in exceptions.
Result: FastAPI lifespan on the Fly.io `api` machine logged
`Logging configured` → `google-genai loaded` → `Middleware registered`
and never reached `Application startup complete`. Health check kept
timing out, the machine entered a restart loop (started 02:36Z), the Fly
proxy returned `no candidate` to upstream, login at
`https://kita.balizero.com/api/auth/login` returned 500 with body
`Unexpected end of JSON input`, all CRM endpoints unavailable.

Concrete sequence (mem 1865, 1867):

```
01:54Z  drive_poll_service starts flooding AttributeError on get_file_metadata
02:12Z  diagnosis: missing method on ServiceAccountDriveService
02:36Z  api machine d894e65bede478 enters restart loop (lifespan stuck)
02:42Z  hotfix #1: drive-poll cron disabled on Pro to stop the flood
02:47Z  hotfix #2: commit 720d54f5c adds get_file_metadata, deploy via CI
03:11Z  login flow recovered (POST /api/auth/login → 200 + JWT valid)
04:14Z  prevention: login healthcheck probe installed (mem 1870)
```

The 720d54f5c hotfix is the long-term fix. The cron stayed disabled
afterward as a precaution because the original test suite never
exercised the `drive_service.<method>` call path against the real
`ServiceAccountDriveService` class — only against mocks.

**ANTIBODY (3 layers):**

1. **PR-check time** —
   `apps/backend-rag/backend/tests/unit/services/crm/test_drive_poll_service_methods.py`
   parses `drive_poll_service.py` with `ast` and asserts that every method
   invoked on the local `drive_service` variable is implemented on
   `ServiceAccountDriveService`. The same test file pins
   `get_file_metadata` and the existing `get_start_page_token` /
   `list_changes_since` contract — any future rename or removal fails CI
   with a message that cites memory 1865 by id.
2. **Runtime detector (15 min cadence)** —
   `~/scripts/cron-agent-python/fly_watcher.py` `_lifespan_stuck_check`
   pulls the last 400 lines of `fly logs --no-tail` for `nuzantara-rag`
   and flags the *exact* failure signature (`Middleware registered`
   present + `Application startup complete` absent). Telegram alert is
   appended to the existing `_check_now` failure list, so the dedupe
   logic and 30-min cooldown apply automatically.
3. **Fleet-wide watchdog** —
   `~/scripts/fly-restart-loop-detector.sh` was authored on 2026-04-20
   but was never installed as a LaunchAgent until this incident.
   `~/Library/LaunchAgents/com.nuzantara.fly-restart-loop-detector.plist`
   now loads it every 15 minutes (`StartInterval: 900`); state file at
   `~/.agent/decisions/fly_restart_monitor.state.json`.

End-to-end probe (`~/scripts/login-healthcheck.sh`, mem 1870) sits on top
of all three: it fires on the *user* metric (POST `/api/auth/login` →
200 + JWT) and pages Telegram after 2 consecutive failures with a 2h
cooldown. Existence credentials at `~/.nuzantara-secrets.env`
(`HEALTHCHECK_PIN` + `HEALTHCHECK_EMAIL`).

**GOTCHA:**

- `_lifespan_stuck_check` fires only when a *recent* startup attempt is
  visible in the log buffer. After the machine has been healthy for
  hours the markers age out of the last 400 lines and the check returns
  `progress_seen=False, complete_seen=False` (silent OK). This is
  intentional — alerting on "no startup in last 400 lines" would be a
  false positive every steady-state run. The 15-min cadence is short
  enough that any real restart loop will be caught while at least one
  attempt is still in the buffer.
- The lifespan check skips silently (`ok=True, skipped=True`) when the
  `fly` CLI times out or fails — degrade-open is intentional. The
  `fly-restart-loop-detector.sh` LaunchAgent is the redundant signal in
  that case.
- The drive-poll cron on Pro
  (`*/5 * * * * /Users/nuzantara/scripts/openclaw-cron/drive-poll.sh`)
  is left commented out in crontab as `# DISABLED 2026-04-29 02:42`
  with restore instructions inline. Re-enable only after the contract
  test has been green for at least 48h (i.e. the hotfix has survived a
  full daily cycle including the indexing sweep at 00:30 WITA).
- The bug bypassed CI because `drive_poll_service` is reached only via
  cron at runtime, not through any HTTP endpoint exercised by the
  existing pytest suite. The new AST-based contract test does NOT need
  to import `drive_poll_service` (which would require Postgres, Drive
  credentials, and asyncpg pools) — it parses the source file as
  text. That's why it costs <50ms in CI and runs unconditionally.

Memories: 1865 (root cause), 1866 (resolved-update), 1867 (recovery
sequence), 1870 (login probe). Recovery commit: `720d54f5c`.

---

### ⚠️ STRUCTURAL: Backend `/health` masks `app.state.startup_failed` (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash · Severity: P0 · Workaround: TBD (intervention plan P0-0 in `docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-0_health_endpoint_classify.md`)_

**TRAUMA:** `apps/backend-rag/backend/app/setup/app_factory.py:114-118` catches RuntimeError from critical service initialization, sets `app.state.startup_failed=True`, and returns. `apps/backend-rag/backend/app/routers/health.py:48-55` defines `_check_startup_failed()` helper, but `health_check()` at lines 147-266 NEVER CALLS IT.

A backend with broken critical services keeps returning HTTP 200 from `/health`. **Fly auto-restart only fires on non-2xx**. So a deterministically-broken backend stays "healthy" forever — silent crash. The 2026-04-29 03:11Z incident (kita.balizero.com login broken, machine `d894e65bede478` "in restart loop") is exactly this pattern — could only be detected via downstream login probe.

**Compounding (BS-0b):** `apps/cell/cell/core/pulse.py` classifies green based on `reading.reachable and reading.status_code == 200` — Cell's own nervous system has the same blind spot.

**ANTIBODY (proposed):** P0-0 brainstorm — call `_check_startup_failed(request.app)` at top of `health_check()`, return 503; track `startup_started_at` in `app_factory.py` with 180s warmup deadline; `pulse.py` classify on body status field (`unhealthy/startup_failed/failed/down` → red, `degraded/initializing/warming` → yellow).

**GOTCHA:** Removing `raise` in `_init_critical_services` (graceful degradation per Symbiosis Law 4) is essential. Without it, uvicorn won't bind 8080. Warmup 180s assumes RAG cold-start ≤90-120s.

---

### ⚠️ STRUCTURAL: EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via NotebookLM NB-1 ground-truth · Severity: P0 · **Mitigated 2026-04-29 phase 1 via PR #342** (commit `0062090c4`); **phase 2 callsite refactor + DB triggers shipped 2026-04-29 in feat/p0-2-fase2-callsite-refactor** (Track C wave 3); per-handler ack + pruning cron remain for a future phase 3._

**TRAUMA:** `SYMBIOSIS.md` Law 4 promises "Redis Streams + consumer groups, if Redis is down ogni agente funziona in isolamento". Reality (per NB-1 source citations): EventBus uses **PostgreSQL LISTEN/NOTIFY**. See `apps/backend-rag/backend/services/events/__init__.py` PG_CHANNEL_MAP (`practice_changed`, `client_changed`, `compliance_alert`, `lkpm_ingest_completed`, `war_room_event`, `intel_event`, `cognitive_event`). Listener `_RECONNECT_DELAY_S = 5`.

When PG listener disconnects (5s window), every NOTIFY is **silently lost** — pg_notify is volatile, no queue. Symbiosis Law 4 promise is wrong twice: there's no Redis to be down, AND PG NOTIFY has no durability layer.

**ANTIBODY (phase 1, SHIPPED PR #342 2026-04-29):**

* New `events_outbox` table (migration 144, applied on prod 2026-04-29 10:30 UTC, `execution_time_ms=33`). `BIGINT GENERATED BY DEFAULT AS IDENTITY` PK, JSONB payload, partial indexes on `(created_at) WHERE consumed_at IS NULL` (fast replay) and `(consumed_at) WHERE consumed_at IS NOT NULL` (fast prune). Squawk lint cleared via per-statement `-- squawk-ignore: require-concurrent-index-creation` / `require-timeout-settings` directives — legitimate suppressions on a brand-new empty table where the warned-about lock contention cannot occur.
* New helper `apps/backend-rag/backend/services/events/outbox.py` exposes `publish` / `acknowledge` / `replay_unconsumed` / `prune_consumed` / `get_unconsumed_count` / `validate_channel`. `publish()` writes to outbox + fires `pg_notify($1, $2)` parameterised (NOT via `quote_ident($1)` — that produces a quoted identifier `"channel"` which is the SQL-identifier syntax, **wrong** for the `pg_notify(text, text)` function signature). `_outbox_id` is injected into the NOTIFY payload so consumers can ack idempotently. `replay_unconsumed()` re-dispatches to in-process handlers via caller-provided `dispatch_fn` and auto-acks on success.
* `EventBus._replay_outbox_on_reconnect` is invoked from `_connect_and_listen` after `add_listener` for each PG channel, before the keep-alive loop. Best-effort — a failure on any single channel is logged and the listener proceeds.
* 20 unit tests (16 `test_outbox.py` + 4 `test_event_bus_replay.py`) cover atomicity, `_outbox_id` injection, ack idempotency, replay ordering / max-age filter / continue-on-handler-error, channel-name validation, prune-only-consumed, EventBus reconnect-hook contract.

**Phase-1 limitation (documented):** `replay_unconsumed` auto-acks immediately after `dispatch_fn` returns. If the handler crashes mid-dispatch, the row is still marked consumed. Phase 2 introduces per-handler ack so handler crashes do NOT lose the event.

**ANTIBODY (phase 2, SHIPPED 2026-04-29 in feat/p0-2-fase2-callsite-refactor):**

* `EventBus.emit_pg` now delegates to `outbox.publish` (local import in `event_bus.py` to avoid circular package init), so any future Python caller of `emit_pg` automatically writes to `events_outbox` before the volatile `pg_notify` fires. The 8 KB payload-size warning is preserved, and the `db_pool=None` early-return path stays silent (no publish attempt). Behavior change is observable only to the listener-disconnect window: events that would have been silently dropped now land in `events_outbox` and are replayed by `_replay_outbox_on_reconnect` on the next listener reconnect.
* New SQL migration `db/migrations_v2/146_eventbus_triggers_use_outbox.sql` redefines six trigger functions (`notify_practice_change`, `notify_client_change`, `notify_compliance_alert`, `notify_war_room_event`, `notify_intel_event`, `notify_cognitive_event`) so each one builds the same JSONB payload as before (preserving consumer-visible keys exactly) and then runs `INSERT INTO events_outbox (channel, payload) VALUES (…) RETURNING id INTO outbox_id` followed by `pg_notify(channel, (payload || jsonb_build_object('_outbox_id', outbox_id))::text)` inside the original user transaction. The migration is wrapped in `CREATE OR REPLACE FUNCTION` so it is idempotent. Triggers themselves are NOT dropped — they keep pointing at the same function names. The `-- === ROLLBACK ===` section restores the pre-146 function bodies (still pg_notify-only, byte-identical to migrations 075/076/112/113/114).
* 12 new tests in `backend/tests/services/events/test_outbox_callsite_integration.py` cover: `emit_pg → outbox.publish` delegation, no-raw-pg_notify regression guard, payload round-trip without mutation, 8 KB warning preservation, `db_pool=None` no-op, 100-event disconnect-then-replay round-trip via the existing reconnect hook, `_replay` flag propagation, migration 146 file existence + every trigger-backed channel covered + `_outbox_id` injection per channel + rollback-marker present + out-of-scope channels (`wr2_status_change`, `partner.commission_changed`) NOT touched + war_room payload shape preserved (regex-tolerant).

**Phase-2 limitation (documented):** `replay_unconsumed` still auto-acks immediately after `dispatch_fn` returns, inheriting the phase-1 contract. If a handler returns successfully but silently drops the payload, the row is marked consumed and the event is gone. Per-handler ack moves to phase 3. Consumers must be idempotent on the `_outbox_id` key.

**Channels NOT in scope for phase 2:**

* `lkpm_ingest_completed` — no DB trigger; emitted by Python import scripts after bulk OSS receipt ingest. Those scripts already use `EventBus.emit_pg` (or could), so they pick up the new durable path automatically without a SQL migration.
* `wr2_status_change` (migration 138) — separate consumer (`wr2_supervisor.py` launchd daemon), not registered in `PG_CHANNEL_MAP`, the EventBus reconnect hook would never replay it. Left untouched intentionally; documented in the migration 146 header.
* `partner.commission_changed` (`services/crm/partners/events.py`) — dotted channel name fails `validate_channel` (`^[A-Za-z_][A-Za-z0-9_]{0,62}$` rejects `.`); also not in `PG_CHANNEL_MAP`. Out of scope; documented in the migration 146 header. If a future change registers it in PG_CHANNEL_MAP it must also be renamed to `partner_commission_changed` first.

**ANTIBODY (phase 3, pending future PR):** per-handler acknowledgment so a crashing handler does NOT lose events; pruning cron LaunchAgent on Pro calling `prune_consumed` daily (30-day retention).

**Decision (resolved 2026-04-29):** went with option (a) — keep PG LISTEN/NOTIFY + Outbox. SYMBIOSIS.md still says "Redis Streams"; that needs a doc update in a separate PR (low priority — code-as-truth wins). Migrating to Redis Streams (option b) was rejected as a major architectural change too risky for an audit fix.

**GOTCHA:**

- After phase 2: every PG_CHANNEL_MAP channel except `lkpm_ingest_completed` has a refactored DB trigger in migration 146 that writes to `events_outbox` BEFORE pg_notify. `lkpm_ingest_completed` has no DB trigger (Python emitter only) and now flows through the refactored `EventBus.emit_pg` instead. The four out-of-scope channels (`wr2_status_change`, `partner.commission_changed`, plus any channel not in PG_CHANNEL_MAP) remain volatile by design; see the channel list in the phase-2 ANTIBODY block above for the rationale.
- The trigger function in migration 146 wraps the INSERT INTO events_outbox + pg_notify in the SAME implicit transaction as the user's INSERT/UPDATE. If the user's transaction rolls back, both vanish (Postgres queues NOTIFY until COMMIT, and the outbox row stays invisible to other connections via MVCC). If the user's transaction commits but the listener is disconnected, the outbox row stays unconsumed and is replayed on listener reconnect.
- Consumers must be idempotent for replay safety. The replay path injects `_replay: True` and `_outbox_id` into the payload; consumers can dedup on the `_outbox_id` if they need at-most-once semantics. Phase 3 adds per-handler ack so a crashing handler does NOT auto-consume the event — until then, `replay_unconsumed` auto-acks on `dispatch_fn` return regardless.
- The legacy `_schema_versions` table on prod has only 6 rows (last entry `129_crm_guardian` from 2026-04-24). The active runner uses `schema_migrations` (88 rows, top entry `144_events_outbox`). **Future agents validating "did migration N apply?" must query `schema_migrations`, NOT `_schema_versions`** — querying the wrong table will return NOT_FOUND for every recent migration and look like a deploy failure.
- `pg_notify($1, $2)` with parameterised channel is injection-safe. Defense-in-depth: Python-side `validate_channel` regex `^[A-Za-z_][A-Za-z0-9_]{0,62}$` rejects suspect names early. Do NOT add `quote_ident($1)` — that produces SQL-identifier syntax wrong for the function arg.
- Pruning policy (events_outbox unbounded): still NOT enforced after phase 2. Phase 3 ships the cron. Until then, manually run `await prune_consumed(conn, older_than_days=30)` if monitoring shows table growth.
- Migration 146 must apply on the FRESHLY-DEPLOYED image (not the previous one) — same gotcha that caused the SQL v2 deploy-ordering scar (cf. `run-sql-v2-migrations-post-deploy` job in `fly-deploy.yml`). The job already covers SQL v2 migrations idempotently, so 146 will be picked up by the post-deploy step on first deploy after merge with no manual `workflow_dispatch` needed.

---

### ⚠️ STRUCTURAL: 53 LaunchAgents Pro, only 7 (13%) have KeepAlive=true (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: TBD (P0-3 mass plist audit)_

**TRAUMA:** `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`. Codex counted 53 project plist:
- 7/53 (13%) have `KeepAlive=true`
- 11/53 (21%) have NO KeepAlive directive at all
- 5/53 (9%) missing `EnvironmentVariables` (VADEMECUM §11 violation)
- 6/53 (11%) logging to `/tmp/` (lost on reboot, breaks Sentinel)

Critical daemons that should KeepAlive=true but don't include `com.cell.organism` (the actual organism cell), `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`. Cell's crisis-recovery hierarchy assumes daemon respawns within 10s — only works with KeepAlive=true.

**ANTIBODY (proposed):** P0-3 — `scripts/lint_launchagents.sh` + auto-patcher `scripts/patch_launchagents.sh --dry-run` + PreToolUse hook. Auto-classifies daemon-vs-cron based on `StartInterval`/`StartCalendarInterval` presence (cron) vs absence (daemon).

**GOTCHA:** `RunAtLoad=true + no schedule` is ambiguous (daemon-on-boot vs one-shot-on-load) — manual review. Each plist gets `.pre-vademecum-audit` backup before patching.

---

### ⚠️ STRUCTURAL: SQL v2 migrations duplicate numbers `129_*` and `130_*` (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: rename non-applied duplicate (P0-7)_

**TRAUMA:** `apps/backend-rag/backend/db/migrations_v2/` has TWO migration files sharing number `129` and TWO sharing `130`. Runner (`backend/db/migration_manager.py`) tracks via `migration_number` column in `_schema_versions` — duplicates cause undefined apply order and silent corruption risk.

**ANTIBODY (proposed):** P0-7 — compare contents + git history, identify which is in `_schema_versions` (applied), rename the not-applied to next-available number. CI guardrail `lint-migration-numbers.yml` prevents regression. Migration runner asserts uniqueness in `discover_migrations()`.

**GOTCHA:** If both have been applied (unlikely): Zero handoff. Renaming changes file hash but not SQL content — apply order must be re-verified.

---

### ⚠️ STRUCTURAL: Unknown agent overwrites loaded LaunchAgent plist files with their own JSON dump (2026-04-29)

_Discovered: 2026-04-29 ~15:30Z during P0-3 audit · Severity: P0 · Status: Recovery automated, root cause UNKNOWN — escalation HIGH in `shared/escalations_pro.jsonl`_

**TRAUMA:** At `2026-04-29 15:09:15-17 WITA` an unidentified process truncated **51 of 54** project plist files in `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`, replacing each plist XML with a tiny JSON fragment that is the value of *one* of the plist's own keys — typically `StartCalendarInterval` (e.g. `{"Hour":1,"Minute":0}`, 21 bytes) or `EnvironmentVariables` (e.g. `{"GH_TOKEN":"...","FIREWORKS_API_KEY":"...","HOME":"/Users/nuzantara",...}`, ~145-313 bytes). At `2026-04-29 16:05:18` the *same event repeated*: 50 plist re-corrupted (all but the 3 freshly-canary-tested ones) within a single second window. **Cycle ~56 minutes between waves.**

The signature exactly matches `plutil -convert json -o "$plist" -- "$plist"` or equivalent (`subprocess.run(["plutil","-extract","<key>","json"], stdout=open("$plist","w"))`) — a "read one key, write back the value as JSON, but truncate the file first because of `>` redirect" pattern. Grep across `~/scripts ~/Desktop/nuzantara ~/.cron-agent-python ~/.openclaw ~/.claude ~/.agent` for `plutil.*-convert`, `plutil.*>` redirects, `Library/LaunchAgents.*write_text`, etc., turned up **zero matches** — the producer is not a versioned shell/python script with a literal plutil invocation. Sentinel (`nuzantara-sentinel.py`, runs at 16:05), automap-watchdog (60s cycle, runs `automap_autofix.py`), launchagent-state-bridge.py (300s), zombie-hunter (60s), and system_doctor.py (4h) were all checked — all read launchctl but write only to `~/.agent/decisions/state/*.json`, not to plist files.

**Critical observation:** a canary plist NOT loaded in launchd (`com.balizero.canary-final`, file present, never bootstrapped) was NEVER corrupted across two waves. **The producer enumerates services *currently in `launchctl list`* and writes per-label.**

The on-disk corruption was masked for hours because launchd had loaded the *real* config at boot — `launchctl print gui/$(id -u)/<label>` still returned the full config from memory, so production behavior was unaffected. **Reboot would have lost 51 services**, including critical daemons (`com.cell.organism`, `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`, all WR2 producers) and CRON jobs (`com.balizero.intel.nightly`, `com.balizero.indexing-sweep.daily`, login-healthcheck, fly-restart-loop-detector).

**Secrets leaked into world-readable (mode 0644) plist files** during the event:
- `com.balizero.post-publish-poller.plist` → `GH_TOKEN` (`ghp_iZ4V…`, 40 chars), `FIREWORKS_API_KEY` (`fw_GXzCU…`, 25 chars), `SCRAPER_API_KEY` (`internal-…`, 20 chars)
- `com.balizero.post-publish-webhook.plist` → `POST_PUBLISH_SECRET` (26 chars)
- `com.cell.organism.plist` → `GOOGLE_API_KEY` (`AIzaSy…`), `CELL_TELEGRAM_BOT_TOKEN`, `FLY_API_TOKEN` (FlyV1, 687 chars), `CELL_DATABASE_URL` (postgres password embedded)
- `com.nuzantara.dlq-autopilot.plist` + `com.nuzantara.sentinel.plist` → `TELEGRAM_BOT_TOKEN` (shared bot, same as `cell.organism`)

Backups of the corrupt blobs are kept in `~/p0-3-recovery/plist_corrupt_backup/` for forensic analysis. Rotation plan in `~/p0-3-recovery/secrets_rotation_plan.md` (manual approval required per secret class).

**ANTIBODY (recovery, automated):**

The `~/p0-3-recovery/reconstruct_plist.py` script parses `launchctl print gui/501/<label>` output (which has the in-memory config in launchd's text format) and emits a valid plist XML using `plistlib.dump`. Each output is validated with `plutil -lint` before it is moved into `~/Library/LaunchAgents/`. **Atomic mv preserves the live launchd state** — no `launchctl unload`/`load` needed; the next boot picks up the rebuilt plist while the running process is unaffected. End-to-end recovery for 53/54 plist takes ~30s on Pro and produces zero service flap (verified via PID snapshot diff).

The 1 unrecoverable plist (`com.nuzantara.qwen-code-review.plist`) was never loaded in launchd, has no fallback in `~/Desktop/nuzantara/infra/launchagents/`, and is not referenced by anything currently running — the corrupt 22-byte file was moved to `~/p0-3-recovery/com.nuzantara.qwen-code-review.plist.removed`.

**ANTIBODY (prevention — partial, producer still UNKNOWN):**

The producer of the corruption has not been identified, but two preventive layers are now in place (2026-04-29 18:50 WITA):

1. **Filesystem hardening** — all 54 project plist were chmod'd read-only:
   - 5 plist with leaked secrets (`com.cell.organism`, `com.balizero.post-publish-poller`, `com.balizero.post-publish-webhook`, `com.nuzantara.dlq-autopilot`, `com.nuzantara.sentinel`) → `0400` (owner read only, no world read, no write at all). Stops both *write* and *read by other users*.
   - 49 remaining plist → `0444` (world read OK, no write). Stops only *write*.
   - Verified: 54/54 still plutil-lint OK, `launchctl load/unload` still works, `> "$plist"` redirect now fails with `Permission denied`. To legitimately edit a plist: `chmod u+w "$plist"`, edit, restore mode.
   - Memory ID 1879 has the operational note.

2. **fs_usage audit** active since 19:33 WITA (PID 10080, capture log `~/p0-3-recovery/fs_usage_trap/capture-20260429-193348.log`) — captures any future `WrData`/`O_TRUNC`/`truncate` on project plist with PID + parent PID. To inspect: `grep -E "WrData|O_TRUNC|truncate" ~/p0-3-recovery/fs_usage_trap/capture-*.log`. To stop: `sudo pkill -f "fs_usage -w -f filesys"`.

The originally-suspected **56-minute recurrence cycle was refuted** — by 18:44 WITA (>3.5 h after the 16:05 second wave) no third wave had fired, even before chmod was applied. Most likely scenario: the writer was a one-shot AI agent action (Antigravity/Cline/parallel Claude Code session via filesystem MCP), not a recurring daemon.

If recovery is ever needed again: `python3 ~/p0-3-recovery/reconstruct_plist.py && for src in ~/p0-3-recovery/plist_reconstructed/com.*.plist; do chmod u+w "$HOME/Library/LaunchAgents/$(basename "$src")" 2>/dev/null; install -m 0444 "$src" ~/Library/LaunchAgents/; done` (note the `chmod u+w` step required because of the new hardening).

The original P0-3 audit (mass `KeepAlive=true` enforcement on the 54 plist) remains **paused**: the lint+patch scripts (`scripts/lint_launchagents.sh`, `scripts/patch_launchagents.sh`) need a `chmod u+w` step before patching now. Resumption tracked separately.

**GOTCHA:**

- The producer enumerates **launchd-loaded services only**. A new plist that has never been bootstrapped is left untouched — useful as a canary, useless as production state.
- `plutil -lint` on a corrupted plist returns 1 (failure) but launchd still serves the cached XML from boot. Don't equate "plutil-lint OK" with "service running properly".
- Most-likely remaining candidates (none ruled out): (a) a parallel AI-agent session (Antigravity/Cline/Codex/Gemini/Claude Code subagent) issued the lethal command via filesystem MCP without logging to terminal history — supported by Antigravity network activity at 15:09:05–13 (10 s before corruption); (b) a not-yet-discovered binary running with `plutil -convert -o file file` semantics; (c) launchd-internal race triggered by simultaneous `launchctl list` from many processes. The originally-noted 56-min cycle hypothesis is now **refuted** (no third wave fired by 18:44 WITA, even before hardening).
- The P0-3 lint script is conservatively read-only — only uses `plutil -extract <key> raw 2>/dev/null` redirecting STDERR. The patch script uses `plutil -insert/-replace` directly on the file (in-place, atomic). NEITHER produces the corruption signature.
- After chmod hardening, any future recovery / `patch_launchagents.sh --apply` MUST `chmod u+w` the plist first — otherwise `plutil -insert/-replace` will fail silently with `Operation not permitted`. The lint script (read-only) is unaffected.
- Cross-LLM brainstorm artifacts: `/tmp/kakuro-S4-final-brainstorms/{codex,deepseek,gemini,notebooklm}.md` — DeepSeek's analysis is the most useful (Codex hit auth fail, Gemini hit rate-limit, NotebookLM CLI error).

---

### ✅ RESOLVED: Atlas migrate-lint paywalled in v0.38 — pivoted to Squawk (2026-04-26)

_Discovered: 2026-04-26 during sprint 1 PR #306 CI run · Patched: same day via pivot to `sbdchd/squawk-action@v2`_

**TRAUMA:** PR #306 sprint 1 originally adopted `ariga/atlas-action/migrate/lint@v1`
to lint Postgres migrations at PR-check time. The action installed Atlas at
`latest`, which on 2025-10-30 became v0.38 — the release that **moved
`migrate lint` behind a paid Atlas Pro tier**. CI failed with:

```
Abort: Starting with v0.38, 'atlas migrate lint' is available only to Atlas Pro users.
```

The error surfaced in the very first PR run, not at planning time — the
brainstorm artifacts (`docs/brainstorms/2026-04-26-oss-injections/03_atlas_*.md`)
recommended Atlas without flagging the v0.38 paywall because it was newer
than their training cutoff.

**ANTIBODY:** Pivoted to **Squawk** (`sbdchd/squawk-action@v2`, MIT, OSS,
~600K monthly downloads, Postgres-specific). Same value prop — destructive-op
detection at PR-check time — without the paywall risk. Implementation in
[`.github/workflows/migration-lint.yml`](../../.github/workflows/migration-lint.yml).

The runtime rollback-marker validation in `migration_manager.py` (which caught
PR #302) stays as-is and is **complementary** to Squawk: it validates the
`-- === ROLLBACK ===` marker presence at deploy time; Squawk validates DDL
safety at PR time. Two checks, two phases, two different bug classes.

**GOTCHA:**

- Atlas's older versions (≤v0.37) still have `migrate lint` for free, but
  pinning a specific old version of an actively-developed CLI is a maintenance
  trap — every minor release means re-evaluating whether to upgrade. Squawk
  has no such pressure.
- The Squawk ignore syntax is per-statement, not per-file:
  `-- squawk-ignore: ban-drop-column` on the line immediately preceding the
  offending statement. (Not `-- atlas:nolint` as some older docs say.)
- Squawk uses GitHub annotations for violations, not job log lines. Read them
  via `gh api repos/<org>/<repo>/check-runs/<job-id>/annotations` if you need
  to script around them.
- The `--latest 1` flag from the Atlas plan does not apply to Squawk — Squawk
  always lints whatever files you pass it. Our workflow uses `git diff` to
  compute the changed migrations against the PR base.

Brainstorm artifacts (with the original Atlas reasoning, kept for posterity):
`docs/brainstorms/2026-04-26-oss-injections/03_atlas_*.md`. Final design with
Squawk: [`docs/oss-injections-2026-04-26.md`](../../docs/oss-injections-2026-04-26.md).

---

### ✅ RESOLVED: SQL v2 migrations apply on OLD image, not the freshly-built one (2026-04-26 → 2026-04-29)

_Discovered: 2026-04-26 deploy of PR #307 (migration 139 `intel_radar_findings`) · Workaround: `workflow_dispatch` re-trigger after merge · Patched: 2026-04-29 via PR #336 + #339 + #340, verified in fly-deploy run 25097928856 (commit `711cd6066`) which applied 30 migrations on fresh image including canary 141, with `applied_count=30` notice in workflow log_

**TRAUMA:** `.github/workflows/fly-deploy.yml` runs jobs in this order:

1. `pre-deploy-gate` (validation)
2. `run-migrations` — `flyctl ssh console --app nuzantara-rag --command "python -m backend.db.migrate apply-all"`
3. `deploy` — `flyctl deploy --strategy rolling`
4. `run-python-migrations` (post-deploy, idempotent — but only for `apply_migration_NNN.py`, NOT SQL v2)
5. `post-deploy-health`

The `flyctl ssh console` in step 2 connects to the **currently running container** — i.e. the image from the PREVIOUS deploy. Any new file in `apps/backend-rag/backend/db/migrations_v2/NNN_*.sql` introduced by the same PR is NOT yet visible to the running app, because the build hasn't happened yet (step 3). The migration runner walks `migrations_v2/` on the OLD filesystem, doesn't find the new SQL file, applies 0 new migrations.

The new SQL only lands in the image at step 3. By then, `run-migrations` has already finished. The workflow **never re-runs** the SQL v2 runner against the new image.

**Concrete symptom from PR #307:**

```
Run DB migrations on Fly.io / Run DB migrations via flyctl console
  ...
  Migration 138_wr2_status_notify already applied, skipping
  ✅ Applied: 26 migrations          ← was 26 before, still 26 after — no 139
  - Migration 138                     ← stops at 138
```

Then on the manual `workflow_dispatch` re-trigger (run 24959168929), with the new image already serving:

```
Run DB migrations on Fly.io / Run DB migrations via flyctl console
  ...
  Applying migration 139_intel_radar_findings to nuzantara-postgres.flycast:5432/nuzantara_rag
  ✅ Applied: 27 migrations          ← +1 = the new one
  - Migration 139
```

The `run-python-migrations` post-deploy step exists for exactly this class of problem, but it only handles `backend/migrations/apply_migration_NNN.py` (Python wrappers), not SQL files in `migrations_v2/`. Two distinct migration systems with different deploy-time semantics.

**ANTIBODY (workaround for now):**

After merging a PR that adds a new `migrations_v2/NNN_*.sql` file:

1. Wait for the auto-triggered fly-deploy (push event) to complete normally — image gets built and rolled out.
2. Verify in the run logs that `Applied:` count is unchanged (proof the new SQL wasn't picked up).
3. Manually re-trigger the workflow:

   ```bash
   gh workflow run "Deploy Backend to Fly.io" --ref main
   ```

4. Verify in the new run logs that the migration applied (`Applying migration NNN_*.sql ...` followed by an incremented `Applied:` count).
5. Health check is automatic.

**Permanent fix (TODO, separate PR):** add a step after `deploy` that re-runs the SQL v2 migration runner against the freshly-deployed image. Pseudo-code:

```yaml
run-sql-v2-migrations-post-deploy:
  needs: deploy
  steps:
    - name: Wait for new image
      run: <existing wait-loop>
    - name: Re-run SQL v2 migrations on new image
      run: |
        flyctl ssh console --app nuzantara-rag \
          --command "/bin/sh -c 'cd /app && python -m backend.db.migrate apply-all'"
```

Idempotent (the runner skips already-applied migrations via `_schema_versions` table), so the no-op cost on deploys without new migrations is one extra `flyctl ssh` round-trip (~5-10s).

**GOTCHA:**

- Path filter on the workflow (`paths: apps/backend-rag/**` + `.github/workflows/fly-deploy.yml`) means a PR that touches **only** `migrations_v2/` files outside backend-rag will NOT trigger any deploy at all — manual `workflow_dispatch` is the only path. (Not our case for §A — we also touched the test file under backend-rag, so the auto-deploy did fire.)
- The `run-python-migrations` step's wait-loop checks for `apply_migration_119.py` as the "new image is live" sentinel. If 119 is ever removed from the codebase, that loop breaks silently. Defensive: pick a sentinel from a recent migration, not one that could be deprecated.
- `python -m backend.db.migrate apply-all` is the same command both pre and post — only the container filesystem differs. Don't try to "fix" by adding `--force` or path overrides; the runner is correct, the deploy ordering is the issue.
- This caveat does NOT affect Python-style migrations (`backend/migrations/apply_migration_NNN.py`) — those are handled by the existing `run-python-migrations` post-deploy job. SQL v2 is the gap.

**Why we discovered it on PR #307 specifically:** prior SQL v2 migrations (e.g. 138 `wr2_status_notify`) had a follow-up commit on the same day that re-triggered the workflow on a new push, masking the issue. PR #307 was a clean single-deploy, exposing the gap.

**RESOLUTION (2026-04-29, P0-4 zero-crash audit):** PR #336 added job
`run-sql-v2-migrations-post-deploy` after `deploy`, with two follow-up
hotfixes that landed lessons worth keeping:

- **PR #339** — sentinel must filter `config.metadata.fly_process_group == "api"`. The
  app has two process groups (`api`, `rag`); they share the image tag at
  deploy time but have different installed Python packages. Without the
  filter, the sentinel could pick a `rag`-group machine and crash with
  `ModuleNotFoundError: asyncpg` (run 25095416132). The pre-deploy
  `run-migrations` job omits `--machine` and flyctl auto-routes — once we
  pin via `--machine`, that auto-routing is gone.
- **PR #340** — do NOT add `PYTHONPATH=.` to the post-deploy command. The
  Fly image has its `sys.path` configured at build time; `PYTHONPATH=.`
  shadows site-packages on this image and asyncpg disappears even on the
  api group (run 25096530075). Keep the post-deploy `--command`
  byte-identical to the pre-deploy one. The kakuro-S2 prompt template
  suggested `PYTHONPATH=.` by analogy with the local-dev golden rule
  "No Root Execution: PYTHONPATH=. python -m backend.module" — that rule
  is for local dev, not Fly containers.

Verified in fly-deploy run 25097928856 (commit `711cd6066`): job applied
30 migrations on the fresh image including canary 141 with
`applied_count=30` notice. Telegram alert fired but got 401 Unauthorized
— **separate cicatrix to track**: bot token rotation needed for
`TELEGRAM_BOT_TOKEN` secret. Migration itself succeeded; alert loss is
recoverable (workflow notice in run logs).

**NEW GOTCHA (post-resolution):** Future agents adding any new
`flyctl ssh console --machine` step must (a) filter machines by
`fly_process_group` to the group that has the package they need, and
(b) NOT prefix the inner command with `PYTHONPATH=.` unless they have
verified empirically that it does NOT shadow site-packages on the
target image. Defensive default: copy the existing pre-deploy
`run-migrations` command character-for-character.

---

### ✅ RESOLVED: Deploy crash before health check went unalerted (Air A3, 2026-04-18)

_Discovered: 2026-04-18 audit (CRIT-3) · Patched: 2026-04-18 via `devops/deploy-rollback-hardening`_

**TRAUMA:** In `.github/workflows/fly-deploy.yml`, the `post-deploy-health` job
chained `needs: deploy`. Its rollback + Telegram notification steps used
`if: failure() && steps.health_check.outputs.healthy == 'false'`. If `deploy`
itself crashed (flyctl error, network failure, image build fail, timeout) *before*
any machine was swapped, GitHub Actions marked `post-deploy-health` as
**skipped** (not failed) due to upstream-dependency failure — so neither the
rollback nor the Telegram alert fired. The previous release kept serving
traffic (no new bits had shipped), but Zero had no visibility that the deploy
had aborted.

**ANTIBODY:** New sibling job `deploy-failure-alert` (see fly-deploy.yml):

```yaml
needs: [run-migrations, deploy]
if: |
  always() &&
  (needs.run-migrations.result == 'failure' || needs.deploy.result == 'failure')
```

It runs when *either* `run-migrations` or `deploy` fails, distinguishes the
failing stage in the Telegram message, and deliberately does **not** issue a
rollback (no new release exists to roll back from). Includes a link to the GH
run for quick triage.

**GOTCHA:**

- The `if:` must use `always()` — without it, GitHub skips the job because its
  upstream deps failed. With `always()`, the inner expression then decides
  whether to fire.
- Do NOT collapse this into `post-deploy-health`: the two cases need *different*
  behavior (rollback vs. no rollback) and GitHub's skipped-vs-failed semantics
  only let one of them see an upstream failure cleanly.
- `pre-deploy-gate` failures are still handled by the gate's own Telegram step;
  if the gate fails, `run-migrations` and `deploy` are marked *skipped* (not
  failure), so `deploy-failure-alert` correctly stays silent — no duplicate
  alert.

---

### ✅ RESOLVED: Dockerfile cell-core missing (PR #56 → PR #62 → monorepo workspace promotion)

_Discovered: 2026-04-15 · Patched: 2026-04-16 via PR #62 · Fully resolved: 2026-04-17 via cell-core-workspace PR_

**HISTORY:**

1. **PR #56** (commit `31ec067b8`) fixed the `from cell_core import ...`
   ImportError in CI (`tests.yml`, `fly-deploy.yml` pre-deploy gate) by adding
   `pip install -e ../../packages/cell-core`. It did NOT touch
   `apps/backend-rag/Dockerfile`. Consequence: the deployed image still lacked
   `cell-core`, making `/api/skill/*`, `/api/experience/*`, and
   `/api/metabolic/*` run in degraded mode (fake empty responses, or 503 for
   metabolic).
2. **PR #62 / #74** (commit `cdd6610a8`) moved the Fly build context to the
   monorepo root and added `COPY packages/cell-core` + a separate
   `pip install -e /app/packages/cell-core` line to the Dockerfile. Deployed
   image regained cell-core, but the editable install was now declared in
   three places (Dockerfile, tests.yml, fly-deploy.yml) — drift-prone.
3. **This PR** promotes cell-core to a proper monorepo workspace dependency:
   declared exactly once, in `apps/backend-rag/requirements{,-prod}.txt`, as
   `-e ../../packages/cell-core`. Dockerfile builder stage now runs
   `pip install -r requirements-prod.txt` from `WORKDIR /app/apps/backend-rag`
   so the relative path resolves to the already-COPYed
   `/app/packages/cell-core`. CI workflows drop their redundant install step.

**ANTIBODY:** Single source of truth — the requirements file. Any new app
that wants cell-core adds the same `-e …/packages/cell-core` line to its
own requirements; no special-casing in Dockerfile/CI. `packages/cell-core/pyproject.toml`
ships `[tool.setuptools.packages.find]` so the wheel build is deterministic
(submodules included, tests excluded — verified via `python -m build`).

**GOTCHA:** Local `docker build` still must run from the repo root
(`docker build -f apps/backend-rag/Dockerfile .`). The relative
`-e ../../packages/cell-core` in requirements ONLY works when `pip install -r`
is invoked with CWD == `apps/backend-rag/`; running pip from repo root with
`pip install -r apps/backend-rag/requirements.txt` will fail to find the
package. CI workflows `cd apps/backend-rag` before installing; the Dockerfile
uses `WORKDIR /app/apps/backend-rag` for the same reason.
