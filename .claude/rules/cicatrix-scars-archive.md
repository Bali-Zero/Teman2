# cicatrix-scars-archive.md

Resolved scars archived from `cicatrix-scars.md` to keep the active file under the 40k-char auto-load threshold.
Each entry retains its full TRAUMA / ANTIBODY / GOTCHA context — grep-able, git-tracked, just not auto-loaded per session.
Restore by appending an entry back to `cicatrix-scars.md` if it relapses into a STRUCTURAL pattern.

---

### ✅ RESOLVED: Consiglio v1 mata-garuda prototype quarantined permanently (2026-05-06 / confirmed 2026-05-12)

_Quarantined 2026-05-06 PR #468 · Confirmed permanent via SYMBIOSIS gap-closure loop NLM review 2026-05-12 PR #588_

**TRAUMA:** The multi-LLM deliberation prototype in `apps/mata-garuda/council/` (Sprint reference PR #68 2026-04-16) never produced a single deliberation: `council.db` was never created on either Pro or Mini, no log entries match "council", the weekly LaunchAgent was meant for Air (decommissioned 2026-05-05 before any cron landed), and `shared/escalations.json` (one of two intended Council inputs) stayed empty from creation through quarantine.

**ANTIBODY:** Code moved to `apps/mata-garuda/.disabled-2026-05-06/council/` following the `.disabled-YYYY-MM-DD/` convention used for `apps/backend-rag/backend/channels/.disabled-2026-04-30/` (Twitter/Slack/gchat). Kept self-contained at moment of quarantine: no production imports of `mata_garuda.council` existed. Files moved (preserves git history via `git mv`):

```
apps/mata-garuda/mata_garuda/council/        → .disabled-2026-05-06/council/
apps/mata-garuda/tests/council/              → .disabled-2026-05-06/tests-council/
apps/mata-garuda/scripts/council_weekly.py   → .disabled-2026-05-06/council_weekly.py
shared/escalations.json                      → .disabled-2026-05-06/escalations.json
```

**GOTCHA:** The LIVE Consiglio v1 implementation continues at `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` (Gate-6 invariant: every final claim has ≥3/4 LLMs agreeing, 4 members Claude+Gemini+DeepSeek+NotebookLM, read-only, feeds Task 20 playbook synthesis writing `08_playbook.md` + `09_wr2_weights.json`). Companion file `apps/organism/organism/supervisor/consiglio_gate.py` is the supervisor's Gate integrator. The mata-garuda quarantined prototype and the backend-RAG live impl are DIFFERENT designs:

| Aspect | Quarantined prototype | Live impl |
|---|---|---|
| Location | `apps/mata-garuda/.disabled-2026-05-06/council/` | `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` |
| Cadence | Weekly cron LaunchAgent | Synchronous gate-6 invariant in FastAPI context |
| Members | 4-LLM moderator (different impl) | Claude+Gemini+DeepSeek+NotebookLM |
| Persistence | SQLite `council.db` | None (read-only) |
| Trigger | Weekly cron (meant for Air) | Task 20 driver call |
| Status | DORMANT (no historical deliberations) | LIVE (production playbook synthesis) |

PR #468 correctly quarantined only the prototype. SYMBIOSIS gap-closure loop 2026-05-12 Step 4 initially recommended "KILL all Consiglio" based on incomplete analysis (only checked the quarantined directory); NB-1 review caught the live impl and the KILL was REVOKED. See `research/symbiosis/2026-05-12-consiglio-v1-live-vs-quarantined-divergence.md` for the full decision matrix.

**Future agents**: when evaluating any "kill X" decision, grep the ENTIRE `apps/` tree for the entity name, not just the quarantined location. The mata-garuda+backend-rag duplicate-entity pattern is structural in Nuzantara (cf. `apps/cell/` legacy vs `packages/cell-core/` canonical observatory implementations).

---

### ✅ RESOLVED: OpenClaw MCP child apparent mortality = test artifact (2026-05-02)

_Discovered: 2026-05-02 during deep test del bot @Balizerobot dopo realignment workspace prompt. **Non è un bug strutturale** — è artefatto del test pattern._

**TRAUMA:** Tool call MCP (`nuzantara-rag__chat_kbli`, `__ask_legal`, `__search_service_pricing`) fallivano in modo intermittente con:

```
[tools] nuzantara-rag__<tool> failed: MCP error -32000: Connection closed
[tools] nuzantara-rag__<tool> failed: Not connected
```

Sembrava che il child stdio (`nuzantara-mcp-server.py`, FastMCP 3.2.4) morisse silenziosamente fra una query e l'altra. `pgrep -P $(pgrep -f openclaw-gateway)` ritornava periodicamente 0 children quando il gateway era ancora up. Il pattern era: **prima query OK → seconda query "Not connected" → restart gateway → ricomincia il ciclo**.

**Root cause** (tracciato leggendo `~/.openclaw/lib/node_modules/openclaw/dist/`):

1. OpenClaw mantiene il MCP runtime **per-session lane** (`SESSION_MCP_RUNTIME_MANAGER` in `pi-embedded-iRgRpYxO.js`). Ogni sessionId UUID ha il proprio child stdio MCP.
2. Quando una **nuova session** rimpiazza una previous sotto lo stesso `sessionKey`, `reply-B8i7ZpFD.js:2611` chiama `disposeSessionMcpRuntime(previousSessionEntry.sessionId)`.
3. Disposal → `disposeSession()` (line 1329) → `session.client.close() + session.transport.close()` → SIGPIPE al child Python.
4. La query DOPO trovava 0 children e ritornava `Connection closed` / `Not connected`.

**Trigger del bug nel test setup**: usare `--session-id "fresh-$(date +%s%N)"` ad ogni invocation `openclaw agent` per "forzare reload del system prompt". Logic in `agent-command-BfFD6VqT.js:859-860`:

```js
const sessionId = opts.sessionId?.trim() || (fresh ? sessionEntry?.sessionId : void 0) || crypto.randomUUID();
const isNewSession = !fresh && !opts.sessionId;
```

Con `--session-id` SEMPRE nuovo e nessuna entry matchante in store → `isNewSession=true` → previous lane disposed → child killed.

**Production NON impattato:** il bot @Balizerobot riceve da `chat_id` 8764530025 (Zero) o altri stabili → sessionKey `agent:telegram-codex:main` deterministico → sessionId stabile per giorni. Il pattern non si manifesta in produzione.

**ANTIBODY:**

1. **Documentazione test pattern** in `~/.openclaw/workspace/MCP_INTEGRATION.md` sezione Troubleshooting (cf. realignment 2026-05-02). Pattern corretto:
   ```bash
   # RIGHT — riusa default sessionKey
   openclaw agent --agent telegram-codex --message "..."

   # RIGHT — sessionKey deterministico via E.164
   openclaw agent --agent telegram-codex --to +6281234567890 --message "..."

   # WRONG — kills previous lane ogni call
   openclaw agent --session-id "fresh-$(date +%s%N)" ...
   ```

2. **Watchdog LaunchAgent** `com.nuzantara.openclaw-children-watchdog` (5min interval, 30min cooldown, 2min grace post-restart). Alerta Telegram a Zero (chat_id 1125336968) se gateway è up MA 0 children con sessions attive in 24h. Implementazione `~/scripts/openclaw-children-watchdog.sh`. State `~/.agent/decisions/state/openclaw_children_watchdog.state`. Log `~/logs/openclaw-children-watchdog.log`.

3. **MOS lesson** salvata in `lessons.md` 2026-05-02 + memorie discovery (importance 8) + fact (importance 7).

**GOTCHA:**

- Il pattern "tool funziona la prima volta, poi falla" può sembrare race condition o bug stdio. È invece il design **per-session lifecycle** che si scontra col test setup.
- 3 children attesi è il default normale (uno per agent: `main`, `telegram-codex`, `coder`). Non 1.
- Sandbox prune `idleHours: 24` può comunque dispose un child legittimo se il bot Telegram resta inattivo per >24h. Improbabile in production reale, ma possibile durante manutenzioni lunghe.
- `launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway` rispawna correttamente il gateway. Children vengono ricreati lazy al primo tool call dopo il restart.
- I file `~/.openclaw/lib/node_modules/openclaw/dist/*.js` sono il riferimento di codice sorgente per debug — non bundle minified, leggibili.

**Lesson trasversale (cf. lessons.md 2026-05-02):** prima di cercare un bug strutturale in un sistema in production, verifica che il test setup non lo stia generando artificialmente. "Il sistema funziona ma i miei test falliscono" è il segnale di un'asymmetry nel setup di test, non di un bug.

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

<!-- ARCHIVED 2026-05-25 sweep: 8 RESOLVED/INFO scars pre-2026-05-18 -->

### ⚠️ STRUCTURAL: GDRIVE_COMPANIES_FOLDER_ID phantom + wa-mirror bypasses POST /api/clients (2026-05-21)

_Discovered: 2026-05-21 02:50 WITA during user request "ogni nuovo cliente kita.balizero deve avere folder Drive auto" · Severity: P1 · Fix shipped on branch `fix/drive-folder-auto-create-hardening-2026-05-21` (commit `1a3824b39`): secret rotated + 14 orphans backfilled + startup validation + Sentry capture + new `POST /api/crm/clients/{id}/ensure-drive-folder` endpoint for wa-mirror service-to-service calls · Reconciliation cron deferred_

**TRAUMA:** Two compounding bugs left ~30+ clients without Drive folder despite the auto-creation feature being live since 2026-02:

1. **`GDRIVE_COMPANIES_FOLDER_ID` pointed to a ghost folder.** The Fly secret had value `1PGRBCSzXc8T3LYqEB1-hucBaH2YW77Av` — folder never existed (or was deleted long ago). Every `client_type='company'` creation triggered `ServiceAccountDriveService.create_client_folder` → `files.create(parents=[ghost_id])` → `404 File not found` → exception swallowed by `BackgroundTask` try/except → API returned 201 to the client, silently no folder. No alert, no Sentry (or PII-redacted), no metric. ~30 company clients orfani in DB.
2. **`wa-mirror-auto-promote-leads.py` and `wa-mirror-dash` bypass the API router.** Both do `INSERT INTO clients (...) created_by='wa-mirror-auto-promote'` directly via asyncpg, never call `POST /api/clients`, so `create_client_folder` BackgroundTask is never scheduled. 5/7 recent orphans were wa-mirror leads.

Empirical scope last-60d (2026-05-21 audit):
| created_by | drive/total |
|---|---|
| `wa-mirror-*` | 0/5 (100% miss) |
| UI (`zero@`, `adit@`, `krisna@`, `ari.firda@`) on `company` | 0/7 (100% miss — phantom secret) |
| UI on `individual` | OK (parent `Individual_CRM` valid) |
| `system-import` (legacy) | 0/16 — fuori scope |

**ANTIBODY (shipped 2026-05-21 — commit `1a3824b39`):**

1. **Secret rotation** — `fly secrets set GDRIVE_COMPANIES_FOLDER_ID=1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW -a nuzantara-rag` → punta ora a `BALI ZERO/CRM/Company_CRM`, deployed + machine restart verified.
2. **Backfill** — `/tmp/backfill_drive_folders_v2.py` (run inside Fly api machine `7847d95ce257d8`): re-runs `ServiceAccountDriveService.create_client_folder` for clients with `google_drive_folder_id IS NULL`. 14 clients backfillati (7 individual + 7 company post-rotation). Tutti hanno 6 sottocartelle top-level in `client_drive_subfolders` table.
3. **Startup validation** — `ServiceAccountDriveService.__init__` ora chiama `_validate_configured_folders()` che fa un `files.get()` su ciascuno dei 3 parent ID (`GOOGLE_DRIVE_ROOT_FOLDER_ID`, `GDRIVE_INDIVIDUALS_FOLDER_ID`, `GDRIVE_COMPANIES_FOLDER_ID`). Log ERROR a boot se 404/trashed/inaccessibile — visibilità immediata di future rotation a ID malformati.
4. **Sentry capture** — `BackgroundTask` Drive ora avvolto in `_create_drive_folder_with_observability` (crm_clients.py): `sentry_sdk.capture_exception` con tag `subsystem=drive_folder_create` e `client_type`. PII già redacted via `sentry_config.py:_before_send` (scar 2026-04-21). Silent failure → P2 ticket.
5. **Service-to-service endpoint** — `POST /api/crm/clients/{id}/ensure-drive-folder` (idempotente: returns `{"created": false}` se già esiste). Auth via JWT user OR `X-Internal-Key` header (settings `wa_mirror_internal_key`). `~/scripts/wa-mirror-auto-promote-leads.py` aggiornato per chiamare l'endpoint dopo INSERT con key letta da `~/.wa-mirror.env`. 6 unit test coprono route registration, idempotency, create-when-missing, 404 on missing client.

**ANTIBODY (deferred):**

- **Periodic reconciliation cron.** Daily job: `SELECT count(*) FROM clients WHERE google_drive_folder_id IS NULL AND deleted_at IS NULL AND created_at > NOW() - INTERVAL '7 days'` → if > 0 → Telegram alert. Catches future regressions in <24h instead of being discovered only when user asks "perché manca?". Non shipped — opzione (b) outbox event-driven preferita ma scope creep.
- **25 storici orfani** (16 `system-import` + 9 `created_by IS NULL`) deliberatamente fuori scope. Da fare con script targeted se/quando emergono in workflow.

**GOTCHA:**

- Per la rotation: `fly secrets set` mette in `staged`, MUST poi `fly secrets deploy` per applicare alle machines. `fly secrets set --stage` lascia esplicito che è staged; senza `--stage` Fly fa restart automatico (anche più veloce).
- L'errore 404 di Drive sembra "permanent" ma in realtà se la cartella esiste ma il service account non è stato condiviso, l'errore è IDENTICO (`File not found`). Modo per distinguere: prova `files.get(supportsAllDrives=true)` impersonando user con accesso (es. `zero@balizero.com`) vs senza DWD.
- `ServiceAccountDriveService` su Fly usa `Domain-wide delegation` impersonando `zero@balizero.com` (vedi log `"✅ Using Domain-wide delegation, impersonating: zero@balizero.com"`). Quindi le folder devono essere accessibili a `zero@balizero.com` (non al SA email diretto). La nuova `Company_CRM` lo è perché è dentro `BALI ZERO/CRM` di proprietà di Zero.
- `Individual_CRM` esiste sotto `BALI ZERO/CRM` parent `1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl` ed è correttamente referenziato dal secret. La gerarchia attesa è `BALI ZERO/CRM/{Individual_CRM,Company_CRM,Archive_CRM}` — verificato listing 2026-05-21.
- Esistono 39 active orphans totali (14 backfillati + 16 `system-import` + 9 `created_by IS NULL`). I 25 storici NON sono nello scope di questo fix.

---

### ⚠️ STRUCTURAL: Intel Lake routing prefix-blind for subdomains (2026-05-20)

_Discovered: 2026-05-20 03:00 WITA durante Phase A audit · Patched PR-B1a `feat/intel-lake-2stage-routing-2026-05-20` · Severity: P1_

**TRAUMA:** Phase A audit ha trovato che **90% intel_items finivano in `needs_review`** invece di essere classificati. Producer scraper inviava `source_domain="kompas.com"` o `tempo.co` ma le rules in `intel_lake_router.py` matchavano solo TLD diretto, non sotto-dominii (es. `nasional.kompas.com` → unmatched). Effetto: la coda `needs_review` cresceva quotidianamente di ~50 items/day, router silently skipping. Compounding: SSOT JSON (`~/scripts/intel-lake-routing-rules.json`) deviava dal Python backend (`_RULES` in `intel_lake_router.py`) — Pro-local router cron usava JSON, Fly backend usava Python. 4-LLM panel verdict (Gemini + Codex 3/3 convergent): rules troppo restrittive, non un bug pipeline.

**ANTIBODY (shipped feat/intel-lake-2stage-routing-2026-05-20):**

1. **2-stage routing**: domain match (con `_SUBDOMAIN_PREFIX = r"(?:[a-z0-9-]+\.)*"` regex tollerante) → keyword content match → classifica. `_PRESS_GENERAL_RE` apre la lista press, ma deve poi ottenere un match in `_PRESS_REGULATORY_KEYWORDS` (visa/kitas/pajak/pmk/kbli/...) per andare a `nb-intel/press`. Gov rules restano STRICT (security: non vuoi `nasional.kompas-fake.com` che si dichiari `kemenkumham.go.id`).
2. **Shadow mode**: env `INTEL_LAKE_ROUTING_SHADOW=1` → calcola classifica ma non muta DB. Permette A/B test live.
3. **SSOT reconciliation**: `~/scripts/intel-lake-routing-rules.json` _meta.version bumped to 2, `synced_from_backend_at = 2026-05-20`. Nota corretta: in-process router IS attivo, `DISABLE_BACKGROUND_WORKERS` NON è settato in prod.
4. **`backfill_needs_review(dry_run=True)`** helper: ri-classifica retroattivamente la coda `needs_review` con le nuove rules. Default dry_run per safety. 49/49 unit test pass.

**GOTCHA:**

- `_PRESS_GENERAL_RE` deve mai includere `.go.id` o `kemenkumham/*` — quelli sono gov authoritative, lì TLD strict. Mix-up = fake gov authority bypass.
- `_SUBDOMAIN_PREFIX` regex usa `(?:...)` non-capturing — non rompere `re.match(_PRESS_GENERAL_RE, domain).group(0)` (non c'è group, usa `.group(0)`).
- Backfill cron NON è attivo automaticamente — solo invocato manualmente da Antonello via `python -m backend.services.intel.intel_lake_router --backfill`.

---

### ✅ RESOLVED: outbox-drain stderr noise (2026-05-20)

_Discovered: 2026-05-13 audit `~/logs/intel-lake-outbox-drain.err` 841KB · **RESOLVED** PR-B2 2026-05-20 `chore/outbox-drain-log-routing-2026-05-20`_

**TRAUMA:** `/Users/nuzantara/scripts/intel-lake-outbox-drain.py` usava `logging.basicConfig` default che routa ogni livello a stderr. `.err` log cresceva indefinitamente (~841KB in 7 giorni) con INFO routinari "idle (pending=N delivered=M)" che Pro launchd cattura come "stderr → errore". Effetto: false-alarm fatigue, vero WARN/ERROR sepolti.

**ANTIBODY (shipped):**

Split-stream handlers: `_stdout_handler` filtra `< WARNING` (INFO/DEBUG → stdout `.log`), `_stderr_handler` filtra `>= WARNING` (WARN/ERROR → stderr `.err`). Stesso formatter, root logger ha entrambi handlers.

```python
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.DEBUG)
_stdout_handler.addFilter(lambda r: r.levelno < logging.WARNING)
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.WARNING)
```

**GOTCHA:** se aggiungi un nuovo handler (es: Sentry), va aggiunto a `logging.root.handlers = [...]` esplicito, non basta `addHandler`. Il root logger `.handlers = []` riscrive l'intera lista.

---

### ⚠️ STRUCTURAL: WR2 master template requires verified richtext slot count (2026-05-10 → architecturally bypassed 2026-05-13)

_Discovered: 2026-05-10 02:53 WITA · Patched via `chore/wr2-pipeline-hardening-2026-05-10` · **Architecturally bypassed 2026-05-13 via `feat/wr2-canva-pdf-render-2026-05-13`** (ReportLab→Tigris→Canva import, no master template required) · Severity: P0 (defanged)_

**RESOLUTION (2026-05-13):** New rendering pipeline: PDF generated server-side via ReportLab (`wr2_canva_pdf_render.py`, 12 layout families), uploaded to Tigris S3, imported into Canva via `import-design-from-url` MCP → no richtext slots needed.

| Design ID     | Status                    | Reason                               |
| ------------- | ------------------------- | ------------------------------------ |
| `DAHE6lx1lf8` | DECOMMISSIONED 2026-05-08 | Original master, obsolete            |
| `DAHJLYRn_3E` | KEPT AS FAILURE EXAMPLE   | Only 2 usable pages (PR #565 failed) |
| `DAHJEkWpkzY` | UNUSED IN NEW FLOW        | Was the 2026-05-10 "fix" master      |

**Production cron disabled 2026-05-13**: kill switch `system_settings.wr2_canva_renderer_enabled='false'` + `launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer`. Plist preserved on disk for reload after orchestrator refactor. Queue: 0 pending, 20 rendered + 15 rejected.

**Plist resurrection 2026-05-15 → PURGED 2026-05-19 (4-LLM panel decision)**: someone (sibling agent / re-bootstrap) re-loaded `com.balizero.wr2.canva-renderer.plist` despite the 2026-05-13 bootout. From 2026-05-15 20:07 to 2026-05-19 10:04: 1122 traceback in `wr2_canva_apply.error.log` (4.1 MB), every 5min `socket.gaierror: [Errno 8] nodename nor servname provided` on `DATABASE_URL=postgres://...flycast` (Fly internal hostname, irrisolvibile da Pro). The DB kill-switch was correctly OFF the whole time but the script crashed on `asyncpg.connect()` BEFORE reading it (gaierror happens in `_connect_addr` socket.getaddrinfo call, never reaches the kill-switch SELECT). Panel synthesis 2026-05-19 (Gemini + DeepSeek + Codex 3/3 convergent, doc: `research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md`): purge plist + archive script + add `launchd_cicatrix_lint.sh` pre-push hook (Wave 2 Codex unique). The "preserved for reload" stance was wrong — preserving on disk under `~/Library/LaunchAgents/` IS the attack surface for sibling-agent resurrection. Correct posture: physical move to `.disabled-YYYY-MM-DD/` directory + script archival under `scripts/.disabled-YYYY-MM-DD/`.

New `canva_renderer_v2` package (~1000 LOC, 9 modules). T1-T13 commits on `feat/wr2-canva-pdf-render-2026-05-13`, 47/47 unit tests passing. Key modules: migration 170 lease columns, `_telegram.py`, `_schema_adapter.py`, `_pdf_pipeline.py`, `_tigris.py`, `_token_storage.py` (HMAC+flock), `_canva_mcp.py` (mcp SDK 1.27.0), `_pg.py` asyncpg, `_telemetry.py`, orchestrator, entrypoint, bootstrap+watchdogs, 3 launchd plists. Deploy via `docs/runbooks/wr2-orchestrator-pdf-render-runbook.md`.

**TRAUMA:** PR #565 promoted `DAHJLYRn_3E` as new master without verifying its shape. Design only had richtext slots on pages 2-3; renderer emits ops for pages 1+4-11. Phase A live-mapping detected 19/22 ops (86%) would drop → `template_mismatch`. Phase 0 had already wiped 3 elements. CI checks (E2E+MCP) were green — they tested python code, NOT the live template shape.

**ANTIBODY (shipped `chore/wr2-pipeline-hardening-2026-05-10`):**

1. **Pre-flight validator** `scripts/wr2_validate_master.py` — exits non-zero if design missing, <11 usable pages, or <18 richtext elements (filter: `width >= 30`). Run before any commit bumping `TEMPLATE_DESIGN_ID`.
2. **Unit-test contract** `test_template_design_id_format` asserts constant matches `^DAH[A-Za-z0-9_-]{8}$`.
3. **Docstring header** on `TEMPLATE_DESIGN_ID` lists verification checklist.

**GOTCHA:**

- Phase 0 wipes master BEFORE Phase A detects mismatch — a wrong design ID means someone else's design gets blanked. Validator catches this pre-wipe; run it before every `TEMPLATE_DESIGN_ID` change.
- `start-editing-transaction` returns ALL richtext elements; renderer + validator both filter `width >= 30`. Change threshold in one → must change both (no programmatic link).
- `DAHJLYRn_3E` is kept in Canva (not trashed) as canonical failure example.
- Future template promotions: prefer designs that are verified clones of a working master.

---

### ⚠️ STRUCTURAL: WR2 canva-apply path coupling between deploy worktree and main repo (2026-05-10)

_Discovered: 2026-05-10 03:50 WITA · Severity: P0 · Workaround SHIPPED in `chore/wr2-pipeline-hardening-2026-05-10`: skill reads `WR2_OUTPUT_ROOT` env var; production plist exports canonical path so deploy worktree and main repo align._

**TRAUMA:** Production cron runs `wr2_canva_desktop_apply.py` from deploy worktree `/Users/nuzantara/Desktop/nuzantara-deploy`; writes `canva_pending.json` there. The `/canva-apply` skill was hardcoded to read from the main repo path. Result: skill read a stale/absent file and silently timed out polling.

Temporary fix was a runtime symlink (fragile: destroyed by `git worktree remove`; invisible without `ls -la`).

**ANTIBODY (shipped):**

1. Skill reads `WR2_OUTPUT_ROOT` env var (fallback: legacy main-repo path). Plist exports `WR2_OUTPUT_ROOT` matching the writer side. Symlink no longer needed.
2. Snapshot copy at `infra/claude-skills/canva-apply.md` with CI drift check.
3. **Long-term TODO**: move output dir to `~/var/wr2/output/canva/` (out of git tree entirely).

**GOTCHA:**

- `WR2_OUTPUT_ROOT` must NOT have trailing slash. Plist value is normalized (skill strips on read).
- `wr2_canva_desktop_apply.py` reads `WR2_REPO_ROOT` (different var — repo root for venv+imports vs output dir). Don't conflate.
- Local skill at `~/.claude/skills/canva-apply.md` is NOT in git by default; iterate locally → commit to `infra/claude-skills/`.

---

### ✅ RESOLVED: LegalIngestionService bypasses OpenAI 300k token batch limit (2026-05-10 → resolved post-2026-05-10)

_Discovered: 2026-05-10 ~15:00 WITA · **RESOLVED** (verified 2026-05-17 by reading `backend/core/embeddings.py`) · Move to archive at next cleanup._

**RESOLUTION:** `EmbeddingsGenerator.generate_embeddings_batch()` now implements two-level batching (lines 409-509 of `embeddings.py`):

- Level 1: item batches of max 50 texts
- Level 2: `_split_by_token_budget()` splits each item batch into sub-batches ≤200k tokens
- `_embed_batch()` propagates exceptions instead of swallowing (cicatrix comment at line 374-382)
- `_truncate_oversized_input()` handles single inputs >8192 tokens

3 affected documents (Permenkumham 22/2023, 11/2024, Permen ATR/BPN 18/2021) need re-ingest against `legal_unified_hybrid_hybrid` — they were 0 chunks before the fix shipped.

---
### ⚠️ STRUCTURAL: NLM feeder split-brain — base_worker redis-cli has no host arg, prod has two local Redis instances (2026-05-06)

_Discovered: 2026-05-06 22:00 WITA · Patched same day, branch `fix/nlm-feeder-resurrect-2026-05-06` · Severity: P0_

**TRAUMA:** `apps/mata-garuda/mata_garuda/workers/base_worker.py` called `redis-cli` with no `-h`/`-p` flags → always hit `127.0.0.1`. After 2026-05-02 Modo B reorg, sentinel moved to Mini but feeder stayed on Pro. Pro Redis `garuda:alerts`: 258 entries, frozen since 2026-05-05. Mini Redis: fresh. Feeder consumed Pro's stale stream for ~36h; logs showed `processed=0, fed=0` — misread as "no new items". Compounding: 2 `sqlite3.OperationalError: disk I/O error` per 106 runs (WAL not enabled on `KnowledgeBase.__init__`).

Before fix (22:30 WITA): NB-INTEL-Immigration 61 sources, last updated 2026-05-04. After fix (23:00 WITA): +61 total sources across all 5 NB-INTEL notebooks.

**ANTIBODY (shipped):**

1. `base_worker.redis_cmd` reads `GARUDA_REDIS_HOST` + `GARUDA_REDIS_PORT` env vars; prepends `-h $host` to every redis-cli call. Unset → localhost (backward compat).
2. `KnowledgeBase.__init__` enables WAL + `synchronous=NORMAL` — lock contention waits on busy_timeout instead of crashing.
3. 9 new tests (`test_redis_host_override.py` + `test_knowledge_resilience.py`).
4. Mini Redis: `bind 127.0.0.1 ::1 100.93.236.6`, `protected-mode no`. Backup at `/opt/homebrew/etc/redis.conf.pre-tailscale-bind-2026-05-06`.
5. Pro plist gains `GARUDA_REDIS_HOST=100.93.236.6` in `EnvironmentVariables`. Reloaded via `launchctl bootout + bootstrap`.

**GOTCHA:**

- `redis-cli` does NOT honor `GARUDA_REDIS_HOST` — env var is ONLY for the Python wrapper. Debug: use `redis-cli -h $host` explicitly; verify via `INFO server | grep run_id` (Pro and Mini each have unique `run_id`).
- Env-var override only takes effect after `fix/nlm-feeder-resurrect-2026-05-06` merges to main; until then, hourly cron still reads Pro localhost.
- Future cross-host consumers MUST set `GARUDA_REDIS_HOST=100.93.236.6` — no auto-discovery.
- 753 nlm_fed dedup entries from pre-patch Pro era remain in `data/knowledge.db`. Overlapping URLs skipped on first cycle (visible as `skipped=N`) — correct, not a bug.
- `getcwd: cannot access parent directories` errors in launchd logs are RED HERRING from zsh `-l` startup; feeder works fine. Out of scope.

---
### ✅ RESOLVED: Backend `/health` masks `app.state.startup_failed` (2026-04-29 → resolved 2026-04-29)

_Discovered: 2026-04-29 audit zero-crash · Resolved: 2026-04-29 commit `2a3256758` PR #337 · Severity: P0 (defanged)_

**RESOLUTION (2026-04-29):** Commit `2a3256758` (`fix(p0-0): /health 503 on startup_failed + Cell pulse semantic classify (#337)`) ships the proposed antibody verbatim. `apps/backend-rag/backend/app/routers/health.py:249` now calls `_check_startup_failed(request.app)` at the TOP of `health_check()` (before any other branch) and returns HTTP 503 with `status="unhealthy"` when `app.state.startup_failed=True`. A second guard at `health.py:270` (`_check_warmup_timeout`) flips to 503 when startup is still incomplete past `STARTUP_WARMUP_DEADLINE_S` (default 180s, env-overridable). Fly.io auto-restart fires correctly on the non-2xx response. Pulse classification (`apps/cell/cell/core/pulse.py`) updated in same commit to classify on body `status` field (`unhealthy/startup_failed/failed/down` → red; `degraded/initializing/warming` → yellow), closing BS-0b.

**ANTIBODY (shipped, code excerpt `health.py:242-249`):**

```python
# P0-0: surface app.state.startup_failed as HTTP 503 BEFORE any other branch.
# _check_startup_failed already exists (lines 48-55); the bug fixed here
# is that health_check never called it, so a deterministically-broken
# backend reported HTTP 200 + status='healthy' indefinitely. Fly.io
# auto-restart only fires on non-2xx, so without 503 the machine never
# recycles. See cicatrix STRUCTURAL 2026-04-29 'Backend /health masks
# app.state.startup_failed'.
startup_err = _check_startup_failed(request.app)
```

**TRAUMA (historical):** `app_factory.py:114-118` catches RuntimeError from critical service init, sets `app.state.startup_failed=True`, returns. `health.py:48-55` defined `_check_startup_failed()` helper but `health_check()` at lines 147-266 NEVER CALLED IT. A broken backend returned HTTP 200 from `/health` forever — Fly auto-restart only fires on non-2xx. The 2026-04-29 03:11Z incident (login broken, machine in restart loop) was exactly this pattern.

**Compounding (BS-0b, also resolved):** `apps/cell/cell/core/pulse.py` classified green on `status_code == 200` — same blind spot, addressed in same PR.

**GOTCHA:** Do NOT `raise` in `_init_critical_services` (graceful degradation per Symbiosis Law 4) — without it uvicorn won't bind 8080. Warmup 180s assumes RAG cold-start ≤90-120s; tune via `STARTUP_WARMUP_DEADLINE_S` env if Qdrant retry loop or embedding load runs longer. Fly.io health-check `grace_period` is capped at 60s — this deadline is the app-level guard after boot starts.

---

