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