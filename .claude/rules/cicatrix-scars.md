# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### 🚨 P0 SECURITY: `apps/cell/.env` holds prod superuser password in cleartext, readable by plain `cat` (2026-06-03)

_Discovered: 2026-06-03 ~20:30 WITA during the organism TAC (read-only diagnosis), when `ssh pro 'cat ~/Desktop/nuzantara/apps/cell/.env'` printed the secret into the session transcript · Severity: **P0 SECURITY** · Status: **REPORTED — rotation + chmod deferred to deliberate operator decision (Antonello)**_

**TRAUMA:** While hunting for Cell's health-check URL, a `cat` of `apps/cell/.env` returned `CELL_DATABASE_URL` and `EVENTBUS_DATABASE_URL` with the **`backend_rag_v2` Postgres password in cleartext**. `backend_rag_v2` is the **superuser** role (per W38 scar, `rolsuper=t`) — so that single string is full production-DB compromise (DROP DATABASE, ALTER SYSTEM, COPY FROM PROGRAM = RCE on DB host). The secret is now in this session's transcript. Two problems compound:

1. The `.env` is readable by a plain `cat` over ssh with no friction → permissions too open (not `0600`).
2. The DB password lives in cleartext in a dotfile on disk (same class as the 2026-04-29 plist-secret-leak and the 2026-05-21 "postgres password in 32 files" P0).

**ANTIBODY (NOT executed — operator decision):**

1. **Rotate** the `backend_rag_v2` password (it's already slated for NOSUPERUSER demotion in W38 spec — rotate + demote together). Update the Fly secret `DATABASE_URL` + every local `.env` (`apps/cell/.env`, `apps/backend-rag/.env`, EventBus consumers) atomically, else half the organism loses DB.
2. **`chmod 600 apps/cell/.env`** on Pro (and audit all `apps/*/.env` for mode > 600) — reduces read surface to owner only.
3. **Stop printing env with secrets into transcripts**: diagnosis must read config via code (`core/config.py` defaults) + logs + DB, NEVER `cat .env`. A single `cat` of a secret-bearing dotfile leaks it irreversibly into the conversation log.

**GOTCHA:**

- Rotation is NOT a solo `ALTER ROLE ... PASSWORD` — it cascades to Fly secret + N local `.env` files + any cron wrapper that sources them. Coordinate as one atomic change in a low-traffic window (same window as W38 demotion).
- The secret is in THIS transcript regardless of rotation — if the transcript is synced anywhere (Drive mirror, logs), it carries the live credential until rotated. Rotation is the only true remediation; `chmod` only stops _future_ reads.
- Orthogonal to W38 (which minimizes blast radius _if_ the secret leaks). This scar is "the secret leaks trivially". Both layer: rotate (this) + demote NOSUPERUSER (W38) = leaked-secret becomes both fresh-invalid AND low-privilege.
- Family: 2026-04-29 plist world-readable secrets, 2026-05-21 P0 postgres password in 32 files. Recurring class: **prod credentials in cleartext on the Pro filesystem**, reachable by any process/agent with read access.

**Reference**: discovered during `research/operations/2026-06-03-organism-tac.md` (organism TAC). Related: W38 (`backend_rag_v2` rolsuper demotion spec), archived 2026-05-21 P0 postgres-password-leak. NO secret value recorded in this scar by design.

---

### ⚠️ STRUCTURAL: W62 — Agent worktree broker TTL=60min violated 34× by 6 abandoned ops fan-out (2026-05-28)

_Discovered: 2026-05-28 09:00 WITA by general-purpose subagent during orchestrator wave-c-ops-triage · Severity: P2 (storage waste, sibling-race surface area increase) · Status: **REPORTED, no enforcement fix yet (broker has no auto-cleanup)**_

**TRAUMA:** 6 worktrees under `.worktrees/ops-*` created during a parallel fan-out wave at 2026-05-26 14:00-14:23 UTC (PIDs 30081/34063/37516/41062/41637/63354 different agents). Each was supposed to TTL out at 60min per `scripts/agent_start.py` broker default. By the time orchestrator audit ran 2026-05-28 (34+ hours later), all 6 were still on disk:

- `ops-wa-doc-req-worker-e2`
- `ops-whatsapp-privacy-audit-worker-i`
- `ops-worker-f-immigration-lifecycle`
- `ops-worker-g-tax-payment-signals-wa`
- `ops-worker-h-followup-risk`
- `ops-worker-j-case-windows`

Each had 3-5 "dirty" files (verified by triage agent: all were pure formatting noise — Black/Prettier reformat + timestamp `Generated UTC:` lines in summary md). ZERO unique commits vs `origin/feat/wr2-c5a-pilot-and-p1-structural-fixes-2026-05-26` (PR #891). The fan-out was 100% subsumed by PR #891 (34 commit ahead of main).

**Why TTL was violated**:

- `scripts/agent_start.py --cleanup` is **opt-in** — must be invoked manually. There's no cron LaunchAgent that runs `--cleanup` periodically.
- Spawning agent didn't call `--release <task-id>` at exit (subagents don't have the broker concept exposed in their context).
- The 6 worktrees had `.agent-task.json` metadata with `created_at` timestamps but no enforcement consumer reads them.

**ANTIBODY (proposed, NOT yet shipped):**

1. **Add LaunchAgent `com.nuzantara.agent-worktree-cleanup.daily`** (or hourly): invokes `python scripts/agent_start.py --cleanup` automatically. Skip worktrees with dirty files > some threshold OR with very recent mtime (<10min, active session).

2. **Add hook in `scripts/agent_start.py` to detect orphan**: at every `--list` invocation, surface worktrees older than 2× TTL as WARN. Operator sees warning in interactive session.

3. **Broker-aware spawn convention**: subagent SDK should provide a `register_worktree_for_cleanup()` callback. Or simpler: orchestrator (when dispatching subagent) registers task-id in broker, broker auto-cleans at agent exit notification.

4. **CI test**: `tests/integration/test_no_stale_worktrees.py` — fails CI if `.worktrees/` has entries with mtime > 24h. Forces hygiene at PR time.

**TACTICAL MITIGATION applied 2026-05-28 09:15 WITA** (no fix shipped):

- All 6 worktrees + branches manually droppato by orchestrator (verified non-blocking — content was in PR #891).
- 1 nested worktree bug (W63) discovered concurrently and fixed.

**GOTCHA:**

- The `--cleanup` flag in `agent_start.py` is WIP-safe: it does NOT remove worktrees with uncommitted changes. So even if cron ran, the 6 ops worktrees would have stayed (each had pseudo-dirty formatting noise). The fix needs to be smarter than "TTL expired = drop".
- Subagents spawned via the Agent tool create worktrees under `.claude/worktrees/agent-<id>/` (different path) and are auto-cleaned by the harness. The broker TTL violation specifically applies to the user-facing `.worktrees/` path used for manual or scripted lane spawns.
- Sibling-race surface area grows with stale worktrees: each adds a checkout that another session may accidentally `cd` into and commit on. W59 ANTIBODY (BRANCH_EXPECTED hook) covers commit-time but not directory-context confusion.
- The 6 stale worktrees contributed to the W59 incident family (sibling automation operating on shared trees). Cleanup is part of W59 long-term ANTIBODY.

**Reference**:

- Investigation: `/tmp/wave-c-ops-triage-2026-05-28.md` (124 righe, general-purpose subagent)
- Cleanup commands executed: orchestrator session 2026-05-28 09:15 WITA (12 `git worktree remove --force` + 6 `git branch -D`)
- Family: closes part of W59 (sibling-race), opens new structural debt for broker enforcement
- Related: `docs/runbooks/agent-worktree-broker.md`, `research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`

---

### ⚠️ STRUCTURAL: `agent-library-evolver` weekly cron checkout `program/base` su REPO_ROOT condiviso con `wr2-deploy-puller` — 32h broken silent (2026-05-25)

_Discovered: 2026-05-25 ~03:40 WITA via GEN-5 disambiguation test "sto avendo problemi con il deploy" · Resolved 2026-05-25 04:13 WITA via stash + checkout deploy/main + pull origin/main (50 commits) · Severity: P0 (cron 32h broken) · Status: **RECOVERED** — root design issue worktree-sharing pending operator decision_

**TRAUMA:** Due LaunchAgent autonomi condividevano lo stesso `~/Desktop/nuzantara-deploy/` worktree:

- `com.balizero.agent-library-evolver.weekly.plist` (Sunday 03:00 WITA) — Voyager-style skill library evolution che fa `git checkout program/base` per checkpoint proprio output (`agent-library/.claude/program.yaml`)
- `com.balizero.wr2.deploy-puller` (hourly) — git pull `origin/main` per refresh WR2 cron logic

Cronologia 2026-05-24:

1. **03:00:46**: evolver crea commit `7902ac05d "Create program: base"` su nuovo branch `program/base` (1 commit ahead di `deploy/main`, file `agent-library/.claude/program.yaml` 59 lines)
2. **03:43+**: wr2-deploy-puller cron tick → `git branch --show-current` ritorna `program/base` → exit 1 `ERROR: deploy worktree on branch=program/base, expected deploy/main`
3. **Cooldown alert suppression** (W55 retry pattern correttamente comportandosi) → ogni ora cron fallisce + suppressed → operator NON vede alert
4. **32 ore di drift**: WR2 cron logic merged a `main` (50 commit) NON propagato al worktree → WR2 Canva renderer + topic selector + draft generator runnano vecchio codice

Compounding: 4 file WR2 (`scripts/wr2_draft_generator.py`, `scripts/wr2_topic_selector.py` + 2 test) dirty mai-committed sul worktree (probabilmente artefatto debug sibling-session pre-checkout `program/base`).

Discovery via GEN-5 test scenario "sto avendo problemi con il deploy" prompt vago: Claude ha letto `~/logs/wr2-deploy-pull.log` + identificato pattern `branch=program/base, expected deploy/main` ripetuto da 32h. Antonello non aveva ricevuto alert (suppression attiva).

**ANTIBODY (immediate recovery shipped):**

1. **`git stash push -u`** dei 4 file WR2 dirty con messaggio `wr2-rescue-pre-checkout-2026-05-25` (preservata in stash@{0} per recovery se serve)
2. **`git checkout deploy/main`** + **`git pull --ff-only origin main`** (50 commit) → worktree a `f6ba657f1` (head main)
3. **Kickstart wr2.deploy-puller** → `runs=62 last exit code=0` `[wr2-deploy-pull] OK: already up-to-date (f6ba657f1)` ✓
4. Branch `program/base` PRESERVED (evolver lo userà al prossimo Sunday 03:00 — non eliminare)

**ANTIBODY (design issue, pending operator decision):**

3 opzioni per disaccoppiare evolver dal worktree WR2:

- **Opzione A**: dedicate worktree separato per evolver (`~/Desktop/nuzantara-evolver/`) — plist evolver REPO_ROOT punta lì
- **Opzione B**: evolver fa `git worktree add /tmp/evolver-$$` ad-hoc + cleanup post-run (no persistent state)
- **Opzione C**: deploy-puller skip silently se branch `program/*` (whitelist `evolver-managed-branches`) + alert solo se altro branch wrong

Opzione A è la più chiara (zero magic), B è più ergonomic (auto-cleanup), C è zero-friction ma maschera classi di errore future. Decision pending Antonello.

**GOTCHA:**

- **Suppression NON è bug — è feature W55 working as designed**. Il problema è che la suppression presume "operator vedrà alert in dashboard" — ma se NON c'è dashboard separato per cooldown-suppressed alerts, l'operator scopre il problema solo quando qualcosa di visibile rompe (qui: WR2 produzione cron stale). Future improvement: weekly digest "alert suppressed by cooldown last 7 days" via Telegram.
- **Worktree-sharing è anti-pattern noto** ma cicatrix W50/W51/W52 era diverso (HOME-fork drift su `~/scripts/`). Questa è prima istanza di "due cron LaunchAgent condividono `git checkout` state sul medesimo worktree". Generalizza: ogni LaunchAgent autonomo che fa `git checkout` deve avere worktree dedicato O usare `git worktree add` ad-hoc.
- **Recovery side-effect**: pull origin/main ha portato 50 commit incluso lavoro WA copilot di altre sessioni (mig 200 schema, mig 201 audit, S1.3 identity resolver). NON è regressione — è semplicemente catch-up post-drift. Verificare che WR2 cron logic non sia stato refactored in modi incompatibili durante questi 50 commit (review log `git log a4394c9b1..f6ba657f1 -- scripts/wr2_*` opzionale).
- **`git pull --ff-only origin deploy/main` fail con `fatal: couldn't find remote ref deploy/main`** perché `deploy/main` è SOLO local branch — il remote ha `origin/main`. Branch `deploy/main` locale traccia `origin/main` (verify via `git rev-parse --abbrev-ref @{u}` = `origin/main`). Pattern: in questo repo `deploy/main` è alias locale per "main destinato al deploy", non remote branch.
- **wr2-deploy-pull.sh ha logica robust**: dopo il `fatal` exit comunque scrive `[wr2-deploy-pull] OK: already up-to-date (f6ba657f1)` perché controlla `git rev-parse HEAD` vs `origin/main` come second-pass check. Architettura difensiva preservata.
- **Family** scar: ⚠️ STRUCTURAL deploy-path coordination (W50/W51/W52/PR #63 manifest drift + ora questa). Tutte caratterizzate da "due cron/sistemi credono di avere world-state diverso, drift silenzioso fino a sintomo visibile".

**Reference**: ~/logs/wr2-deploy-pull.log (32h trail di ERROR + suppressed). LaunchAgent `~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist` + `com.balizero.wr2.deploy-puller`. Runner `~/Desktop/nuzantara-deploy/scripts/agent-library-evolver-run.sh`. Stash preserved: `stash@{0}` su `program/base` con label `wr2-rescue-pre-checkout-2026-05-25`. Sister scar: W50/W51/W52 family (deploy-path desync, diversa surface).

---

### 🚨 PENDING APPROVAL (P1 SECURITY): `backend_rag_v2` Postgres role has `rolsuper=t` — demotion spec drafted, awaiting Antonello sign-off (W38, 2026-05-23)

_Discovered: 2026-05-23 ~04:30 WITA by T3.2 read-only `fly ssh console` investigation (closed in cicatrix below). Spec drafted: 2026-05-23 ~07:45 WITA W38 audit · Severity: **P1 SECURITY** · Status: **DRAFT SPEC — NOT EXECUTED — awaiting Antonello approval for any production write**_

**TRAUMA:** The application role `backend_rag_v2` (used by every backend service via Fly secret `DATABASE_URL`) has `rolsuper=t` — FULL PostgreSQL superuser. If the app is compromised (SQLi, dependency takeover, leaked secret, container escape), the attacker has: `DROP DATABASE`, `ALTER SYSTEM`, `CREATE ROLE`, `pg_terminate_backend()` on any session, `COPY ... FROM PROGRAM` (RCE on DB host), `pg_read_server_files`, `pg_write_server_files`, and the ability to read/modify `pg_hba.conf`. Eight superuser roles total exist in the DB (`backend_rag_v2`, `backend_ts_user`, `flypgadmin`, `nuzantara_memory`, `nuzantara_rag`, `postgres`, `repmgr`, `zantara_rag_user`); `backend_rag_v2` is the only one actively used by app code and the only one reachable via leakable application secret.

W38 read-only empirical audit (via `fly ssh console -a nuzantara-rag` → asyncpg as `backend_rag_v2`, 12 queries against `pg_roles`, `pg_stat_activity`, `pg_extension`, `pg_namespace`, `pg_tables`, etc.) confirmed:

1. **`rolsuper=t` is STILL the live state** (not stale memory). Plus `rolinherit=t`, `rolconnlimit=-1`, `rolvaliduntil=null`.
2. **No legitimate runtime use** for superuser by application code paths:
   - 30/30 sampled `pg_stat_activity` queries are routine CRUD (UPDATE wa-mirror, SELECT events_outbox, SELECT 1)
   - 227 of 239 public tables are OWNED by `backend_rag_v2` → OWNER role already grants ALL on those
   - 12 non-owned tables have explicit grants from migration 156 + T3.2 cascade (244 entries × 7 privileges)
3. **Only TWO real ceilings after demotion**:
   - `CREATE EXTENSION` on non-trusted extensions (postgis, pg_stat_statements) — 6/8 existing migration calls hit IF NOT EXISTS no-ops; new migrations would fail
   - `pg_ls_waldir()` requires `pg_monitor` role — already documented as needed in `health_monitor.py:280-291`
4. **Olympus pulse cron** DROP/CREATE partitions on owned `olympus_heartbeats` parent → OWNER preserves capability post-demotion
5. **codebase grep** found ZERO uses of `CREATE ROLE`, `ALTER SYSTEM`, `pg_hba`, `COPY … FROM PROGRAM`, `CREATE LANGUAGE` — no legitimate superuser dependency

**ANTIBODY (DRAFTED, NOT EXECUTED — spec file: `research/operations/specs/W38-backend-rag-v2-nosuperuser.md`):**

3-stage plan, fully reversible via single `ALTER ROLE backend_rag_v2 SUPERUSER` rollback:

- **Stage A** (pre-flight, no prod change): empirical CREATE TABLE smoke on throwaway role + `pg_signal_backend` usage grep + Olympus partition rotation verification
- **Stage B** (code + secret prep, ~20min, no DB demotion yet): patch `migration_manager.py` to prefer `ADMIN_DATABASE_URL` (with `flypgadmin` DSN) over `DATABASE_URL`; add Fly secret `ADMIN_DATABASE_URL`; `GRANT pg_monitor TO backend_rag_v2` (idempotent); deploy
- **Stage C** (the actual demotion, ~5min + 24h observation window): `ALTER ROLE backend_rag_v2 NOSUPERUSER` during Sunday 03:00-05:00 WITA low-traffic window; immediate verification via `/health` + `mcp__nuzantara-mcp__check_health` + `list_clients limit=1`; 24h Cell organism telegram alert + audit-launchd-daily delta observation

Audit snapshot: `research/operations/audits/2026-05-23-w38-backend-rag-v2-rolsuper-audit.json` (604 lines JSON).

**GOTCHA:**

- **DO NOT EXECUTE `ALTER ROLE backend_rag_v2 NOSUPERUSER` without explicit Antonello approval.** W38 deliberately stopped at spec drafting per task constraint.
- **6/8 existing `CREATE EXTENSION` calls in migrations are idempotent no-ops** because the extensions are already installed; new migrations adding a non-trusted extension (e.g., a hypothetical `pg_hint_plan` or `postgis_topology`) would fail. The Stage B `ADMIN_DATABASE_URL` split is what unblocks future schema work without re-elevating the app role.
- **OWNER ≠ SUPER**: post-demotion, `backend_rag_v2` retains ALL on its 227 owned tables via OWNER grant. The 12 non-owned tables (e.g., partitioned children, mata_garuda tables) need verification that explicit grants cover them all. Migration 156 + T3.2 cascade already cover 244 of 244.
- **`pg_monitor` membership is mandatory** for the demotion to be transparent — `health_monitor.py:288` calls `pg_ls_waldir()` which needs it. Without the GRANT, WAL monitoring silently disables (already-handled with try/except + WARN log per code, but loses visibility).
- **The other 7 superuser roles** (`zantara_rag_user`, `nuzantara_memory`, `nuzantara_rag`, `backend_ts_user`) are legacy or Fly platform — separate spec needed if demoting them. They're not used by app code BUT they ARE attack surface for any rogue script in the codebase that hardcodes them. Future audit candidate.
- **Cicatrix 2026-05-21 P0 SECURITY** (postgres password leak in 32 files) and W38 are orthogonal: that one is "secret leaked", this one is "even if secret leaks, blast radius minimized". Defense-in-depth layered.

**Reference**: spec `research/operations/specs/W38-backend-rag-v2-nosuperuser.md` (~330 lines, 9 sections), audit snapshot `research/operations/audits/2026-05-23-w38-backend-rag-v2-rolsuper-audit.json`. Parent cicatrix entry (T3.2 resolution) flagged this as discovery: `### ✅ RESOLVED: T3.2 Postgres MCP installato post-panel 3-LLM Hybrid D + 5 empirical discoveries (2026-05-23)` line ~770 of this file. Branch: feature branch then merge to main per L2 Autonomous Ops.

---

### ⚠️ STRUCTURAL: 12+1 mata_garuda LaunchAgents active-active Pro+Mini (2026-05-07)

_Discovered: 2026-05-06 22:45 WITA during Symbiosis W1 genome enrollment audit · Severity: P1 · Workaround: TBD (cleanup follow-up PR)_

**TRAUMA:** 13 launchd labels fire SIMULTANEOUSLY on Pro AND Mini:

```
watcher.daily, reg-alert.30min, kg-linker, wr-topic, wr2-bridge.hourly,
bridge.adaptive, sentinel.daily, intel-bridge.daily, daily-briefing,
kita-feed.daily, public-channel, weekly-digest, gap.consumer
```

Blast radius: `regulation-alert.30min` sends duplicate Telegram alerts; `kg-linker` risks duplicate PG edges; `weekly-digest`/`daily-briefing` sent twice; `intel-bridge.daily` emits 2 distinct Redis entries with same OSINT content. Masked until 2026-05-04 because Mini was offline most of April.

**ANTIBODY (proposed, NOT yet implemented):**

1. Per-organ decision: (a) Pro-only, (b) Mini-only, or (c) leader-election. Default: Pro-only (canonical CRM + API tokens).
2. `launchctl bootout + rm plist` on losing side; update `organs_registry.yaml`.
3. Extend `wave1-pro-mini-dup-resolver.sh --resolve` to cover 13 labels.
4. CI test `test_genome_no_active_active.py` — scan `organs_registry.yaml` for shared labels across hosts, fail if outside explicit allowlist.

**GOTCHA:**

- `organs_registry.yaml` `duplicates_id` is HEADER-ONLY — validator does NOT enforce it.
- `--check` returns "0 conflicts" when Mini is offline → misleading. Only reliable when Mini is up.
- Metrics: `items_processed` inflated 2× until cleanup. Dashboard queries: filter by `host_pro_or_mini`.
- 13th entry `gap.consumer` reported as 12 in topology brief — verify with Zero if dup pair or Pro-only.

---

### ⚠️ STRUCTURAL: Test infrastructure mock != production stack (Sprint 1.B 2026-05-02, 3 hotfix in chain)

_Discovered: 2026-05-02 — 3 hotfix PRs (#423, #424) chained on PR #422 because tests were green but live endpoints failed · Severity: P1_

**TRAUMA:** PR #422 added `GET /api/channels/{name}/health` router. Unit tests 4/4 green. On prod:

1. `401` — `HybridAuthMiddleware` blocked path not in `PUBLIC_ENDPOINTS`. Test `_build_app_with_db_pool()` mounted router only, not middleware. Fixed by #423: added 4 entries to `_INFRA` group in `public_endpoints.py`.
2. `404` — router added to `router_manifest.py` but `router_registration.py` uses explicit imports, not the manifest. Fixed by #424: added `from backend.app.routers import channel_health` (×2) + `api.include_router(channel_health.router)` (×2).
3. After #424: 200 ✅. Timeline: 11:30 UTC (401) → 12:50 UTC (404) → 14:25 UTC (200).

**ANTIBODY (proposed, NOT yet implemented):**

1. Integration test `tests/integration/test_endpoints_reachable.py` — mount full `create_app()` via `httpx.AsyncClient`, GET every route; `404` → fail; `/health` returning `401` → flag for PUBLIC_ENDPOINTS review.
2. Manifest-vs-registration parity test `tests/setup/test_manifest_parity.py` — assert every `RouterEntry(name=X)` for `_API`/`_BOTH` has a matching `api.include_router(X.router)` in both include functions.
3. Extend `tests/test_public_endpoints_registry.py`: routes with `/health`/`/heartbeat` NOT in PUBLIC_ENDPOINTS → warning (not failure); silence with `# health-private: <reason>`.

**GOTCHA:**

- `_build_app_with_db_pool()` is intentionally minimal (no middleware) — correct for unit tests. Bug is absence of complementary integration layer.
- PR #422 is a regression of PRs #54/#55/#60 (same scar class). The manifest was created to prevent this but only catches symmetric include-function drift, not "manifest entry with zero include_router calls".
- `HybridAuthMiddleware.__init__` logs `Public Endpoints: N` at startup — grep-able sanity check on Fly machines.

---

### ⚠️ STRUCTURAL: Untracked files lost when sibling automation switches branches mid-session (2026-04-29, twice in 9h)

_Discovered: 2026-04-29 21:42 WITA (incident #1) and 22:30 WITA (incident #2) · Partial mitigation: WIP-commit-every-10min · Permanent fix: TBD_

**TRAUMA:** Long-running sessions accumulate untracked files before commit threshold. Sibling processes (`nuz-sync`, parallel claude sessions, `agent-*` subagents `--dangerously-skip-permissions`) do `git stash` + `git checkout` automatically. `git stash` without `-u` does NOT stash untracked files → silent loss.

| Incident | Time  | Producer                                                                  | Lost                                     | Recovery                                                             |
| -------- | ----- | ------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------- |
| #1       | 21:42 | `nuz-sync` watchdog auto-pull                                             | 2 design docs ~17KB (never `git add`-ed) | Reconstructed from conversation context only                         |
| #2       | 22:30 | Parallel Claude session checking out `nbe/resend-fallback-team-templates` | 4 `.py` files ~26KB                      | Recovered from `.git/objects` dangling blobs (had been `git add`-ed) |

Incident #2 key sequence: Session-A wrote 4 untracked `.py` + 18/18 tests passing → 22:30:03 sibling stashes (tracked only) + checks out main → 22:30:06 checks out `nbe/*` → 4 files silently dropped → 22:32 Session-A diagnoses via `git fsck --dangling` → recovers to `/tmp/innervation-recovery-*/` → WIP commit `3980a1403`.

**ANTIBODY (partial — permanent fix pending):**

1. **WIP-commit-every-10min** whenever untracked files exist:
   ```bash
   if git ls-files --others --exclude-standard | grep -q .; then
     git add -A apps/<scope>/  # scope-limited, NOT bare `git add -A`
     git commit -m "WIP(<scope>): checkpoint $(date +%H:%M) — work in progress"
     git push origin "$(git rev-parse --abbrev-ref HEAD)"
   fi
   ```
2. **Push within 30 seconds of commit** — no Write/Read tool calls between commit and push.
3. **Pre-session: `ps aux | grep claude | wc -l`** — if >2, STOP and ask Zero which to kill.
4. **Recovery**: `git fsck --dangling --no-reflogs 2>&1 | grep "dangling blob"` then `git cat-file -p <hash> > /tmp/recovery-<timestamp>/<filename>`. Only works if content was `git add`-ed. After ~14 days `git gc` may prune blobs.

**ANTIBODY (TBD):** Identify producer for 22:30 switch (suspects: PID 79949, PID 42807, wave-2/3 team agents). `nuz-sync` explicitly NOT enrolled in `organs_registry.yaml` — manual restart only until producer identified.

**GOTCHA:**

- A stash labeled `temp-<branch>` does NOT guarantee it contains all WIP — only tracked-dirty files. Always cross-check with `git fsck --dangling`.
- Files written via `Write` tool but never `git add`-ed have NO blob in `.git/objects` → unrecoverable via fsck. Only `git add`-ed content is recoverable.
- `/tmp/innervation-recovery-*` dirs are volatile (cleared on macOS reboot) — commit within minutes.
- `nuz-sync` is incident #1 suspect (fired at 21:42 inside 5-min cron tick) but NOT incident #2 (watchdog log shows it ran at 22:32:31, AFTER the hijack).

---

### ⚠️ STRUCTURAL: EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams (2026-04-29)

_Discovered: 2026-04-29 audit · Severity: P0 · Phase 1 SHIPPED PR #342 (`0062090c4`); Phase 2 SHIPPED `feat/p0-2-fase2-callsite-refactor`; Phase 3 (per-handler ack + pruning cron) pending._

**TRAUMA:** `SYMBIOSIS.md` Law 4 promises "Redis Streams + consumer groups". Reality: EventBus uses **PostgreSQL LISTEN/NOTIFY** (`PG_CHANNEL_MAP`: `practice_changed`, `client_changed`, `compliance_alert`, `lkpm_ingest_completed`, `war_room_event`, `intel_event`, `cognitive_event`). When PG listener disconnects (5s window), every NOTIFY is **silently lost** — pg_notify is volatile, no queue.

**ANTIBODY phase 1 (PR #342):**

- New `events_outbox` table (migration 144). `outbox.py` exposes `publish`/`acknowledge`/`replay_unconsumed`/`prune_consumed`. `publish()` writes to outbox + fires `pg_notify($1, $2)` parameterised (**NOT** `quote_ident` — wrong for `pg_notify(text, text)`). `_outbox_id` injected into NOTIFY payload for idempotent ack.
- `EventBus._replay_outbox_on_reconnect` called after `add_listener`, before keep-alive loop.
- 20 unit tests (`test_outbox.py` + `test_event_bus_replay.py`).
- Phase-1 limit: `replay_unconsumed` auto-acks immediately after `dispatch_fn` returns; handler crash = event consumed. Phase 2 fixes.

**ANTIBODY phase 2 (feat/p0-2-fase2-callsite-refactor):**

- `EventBus.emit_pg` delegates to `outbox.publish` (local import, avoids circular init). Any future `emit_pg` call auto-writes to `events_outbox`.
- Migration `146_eventbus_triggers_use_outbox.sql`: rewrites 6 trigger functions (`notify_practice_change`, `notify_client_change`, `notify_compliance_alert`, `notify_war_room_event`, `notify_intel_event`, `notify_cognitive_event`) to `INSERT INTO events_outbox … RETURNING id` + `pg_notify(channel, payload||{_outbox_id})` inside the user transaction. Idempotent (`CREATE OR REPLACE`). ROLLBACK section restores pre-146 bodies.
- 12 new tests in `test_outbox_callsite_integration.py`.
- Channels out of scope: `lkpm_ingest_completed` (Python emitter, no DB trigger — picks up new path via `emit_pg`); `wr2_status_change` (not in PG_CHANNEL_MAP); `partner.commission_changed` (dotted name fails `validate_channel`, not in PG_CHANNEL_MAP — must be renamed `partner_commission_changed` first).

**ANTIBODY phase 3 (pending):** per-handler ack; pruning cron `prune_consumed` daily (30-day retention).

**Decision:** kept PG LISTEN/NOTIFY + Outbox. SYMBIOSIS.md doc update pending (low priority — code-as-truth). Redis Streams migration rejected as too risky for an audit fix.

**GOTCHA:**

- Migration 146 trigger wraps INSERT+NOTIFY in the SAME user transaction — rollback loses both (correct MVCC behavior). Disconnect after commit → outbox row stays unconsumed → replayed on reconnect.
- Consumers MUST be idempotent on `_outbox_id`. Phase 3 adds per-handler ack; until then `replay_unconsumed` auto-acks on `dispatch_fn` return.
- **`schema_migrations` is the active runner table (88 rows); `_schema_versions` is legacy (6 rows).** Future agents: always query `schema_migrations` to check migration status.
- `pg_notify($1, $2)` parameterised = injection-safe. Do NOT add `quote_ident($1)`.
- `events_outbox` is unbounded until phase 3. Manual: `await prune_consumed(conn, older_than_days=30)`.
- Migration 146 applies via post-deploy `run-sql-v2-migrations-post-deploy` job — no manual `workflow_dispatch` needed.

---

### ⚠️ STRUCTURAL: 53 LaunchAgents Pro, only 7 (13%) have KeepAlive=true (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: TBD (P0-3 mass plist audit)_

**TRAUMA:** `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`. Codex counted 53 project plist: 7/53 (13%) `KeepAlive=true`, 11/53 no KeepAlive at all, 5/53 missing `EnvironmentVariables` (VADEMECUM §11 violation), 6/53 logging to `/tmp/` (lost on reboot). Critical daemons missing KeepAlive: `com.cell.organism`, `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`. Cell's crisis-recovery assumes daemon respawns within 10s.

**ANTIBODY (proposed):** P0-3 — `scripts/lint_launchagents.sh` + `scripts/patch_launchagents.sh --dry-run` + PreToolUse hook. Auto-classifies daemon-vs-cron by `StartInterval`/`StartCalendarInterval` presence.

**GOTCHA:** `RunAtLoad=true + no schedule` is ambiguous — manual review needed. Each plist gets `.pre-vademecum-audit` backup before patching. **After plist corruption hardening (see next scar): must `chmod u+w "$plist"` before patch scripts can run.**

---

### ⚠️ STRUCTURAL: SQL v2 migrations duplicate numbers `129_*` and `130_*` (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: rename non-applied duplicate (P0-7)_

**TRAUMA:** `apps/backend-rag/backend/db/migrations_v2/` has TWO files each for numbers `129` and `130`. Runner (`backend/db/migration_manager.py`) tracks via `migration_number` in `_schema_versions` — duplicates cause undefined apply order and silent corruption risk.

**ANTIBODY (proposed):** P0-7 — compare contents + git history, identify which is in `_schema_versions` (applied), rename the unapplied to next-available number. CI guardrail `lint-migration-numbers.yml` prevents regression. Migration runner asserts uniqueness in `discover_migrations()`.

**GOTCHA:** If both have been applied (unlikely): Zero handoff. Renaming changes file hash but not SQL content — apply order must be re-verified.

---

### ⚠️ STRUCTURAL: Unknown agent overwrites loaded LaunchAgent plist files with JSON dump (2026-04-29)

_Discovered: 2026-04-29 ~15:30Z during P0-3 audit · Severity: P0 · Recovery automated; root cause UNKNOWN — escalation HIGH in `shared/escalations_pro.jsonl`_

**TRAUMA:** At 15:09:15-17 WITA, an unidentified process truncated **51 of 54** project plist files, replacing each XML with a tiny JSON fragment of one of the plist's own keys (e.g. `{"Hour":1,"Minute":0}` or the `EnvironmentVariables` object with secrets). Same event repeated at 16:05:18 (50 plist re-corrupted in <1s). Signature matches `plutil -extract <key> json stdout-redirect` pattern. Grep across all script dirs turned up zero matches — producer not a versioned script.

**Critical observation:** canary plist NOT loaded in launchd was NEVER corrupted — **producer enumerates `launchctl list` and writes per-label.**

On-disk corruption was masked (launchd serves cached boot config); **reboot would have lost 51 services** including `com.cell.organism`, `com.balizero.nlm-bridge`, all WR2 producers, all key cron jobs.

**Secrets leaked** into world-readable (0644) plist files:

- `post-publish-poller` → `GH_TOKEN`, `FIREWORKS_API_KEY`, `SCRAPER_API_KEY`
- `post-publish-webhook` → `POST_PUBLISH_SECRET`
- `cell.organism` → `GOOGLE_API_KEY`, `CELL_TELEGRAM_BOT_TOKEN`, `FLY_API_TOKEN`, `CELL_DATABASE_URL`
- `dlq-autopilot` + `sentinel` → `TELEGRAM_BOT_TOKEN`

Rotation plan: `~/p0-3-recovery/secrets_rotation_plan.md`.

**ANTIBODY (recovery):** `~/p0-3-recovery/reconstruct_plist.py` parses `launchctl print gui/501/<label>` (in-memory config) and emits valid plist XML via `plistlib.dump`, validated with `plutil -lint`, atomic mv. 53/54 recovered in ~30s, zero service flap.

Recovery command:

```bash
python3 ~/p0-3-recovery/reconstruct_plist.py && \
for src in ~/p0-3-recovery/plist_reconstructed/com.*.plist; do
  chmod u+w "$HOME/Library/LaunchAgents/$(basename "$src")" 2>/dev/null
  install -m 0444 "$src" ~/Library/LaunchAgents/
done
```

**ANTIBODY (prevention):**

1. **Filesystem hardening**: 5 plist with leaked secrets → `0400`; 49 remaining → `0444`. To edit: `chmod u+w "$plist"`, edit, restore mode.
2. **fs_usage audit** at `~/p0-3-recovery/fs_usage_trap/capture-*.log` — captures `WrData`/`O_TRUNC`/`truncate` on project plist. Check: `grep -E "WrData|O_TRUNC|truncate" ~/p0-3-recovery/fs_usage_trap/capture-*.log`. Stop: `sudo pkill -f "fs_usage -w -f filesys"`.

56-minute recurrence hypothesis **refuted** — no third wave by 18:44 WITA. Most likely: one-shot AI agent action (Antigravity/Cline/parallel Claude Code via filesystem MCP).

**GOTCHA:**

- Producer targets only launchd-loaded services. Unbootstrapped plist = safe canary, useless production state.
- `plutil -lint` fails on corrupted plist but launchd still serves cached boot XML. Don't equate lint-OK with service-OK.
- Most likely candidates: (a) parallel AI-agent session via filesystem MCP (Antigravity network activity at 15:09:05-13 supports this); (b) unknown binary with `plutil -convert` semantics; (c) launchd race from simultaneous `launchctl list`. 56-min cycle hypothesis refuted.
- After hardening, `patch_launchagents.sh --apply` MUST `chmod u+w` first — otherwise `plutil -insert/-replace` fails silently with `Operation not permitted`.

### ℹ️ META: the 13-agent WR2 autopsy report HALLUCINATED 3 file:line refs — re-verify before trusting any autopsy citation (2026-06-05)

_Discovered: 2026-06-05 while planning P-4 (topic_type_log) off the autopsy report · Severity: P3 (process/trust, not runtime) · Status: REPORTED — the autopsy report stays as-is (it was right about the SUBSTANCE), this scar inoculates future readers against its 3 phantom citations_

**TRAUMA:** `research/operations/2026-06-04-wr2-autopsy-report.md` (the 13-agent autopsy, finding #10 + per-dimension "Anti-monotony") cites, with PRECISE line numbers, three artifacts that DO NOT EXIST:

- `_state-schema.sql:63` (claimed to define a SQLite `topic_type_log` table)
- `_voyager-curriculum.py:49` (claimed to read it via a LEFT JOIN)
- `topic_type_log` itself as an existing-but-empty table

Direct re-verification on 2026-06-05: `find . -name _state-schema.sql -o -name _voyager-curriculum.py` → **0 results**. `grep -rl topic_type_log` (excluding .venv/.git/.worktrees) → **only the autopsy report itself**. The table was never created, there is no SQLite schema file, no Voyager curriculum reader. The autopsy described "make the existing aspirational table real" — but there was nothing aspirational on disk; it was confabulated with file:line precision that READS as ground truth.

A SECOND autopsy claim was also wrong (caught by an Explore + direct re-verify): the autopsy implied a software publish event at `wr2_carousel_orchestrator.py:900` (`transition_state → published`). That orchestrator is Pipeline A = DEAD CODE (its dispatcher AND telegram-gate both crash-loop, launchctl exit 75). The LIVE pipeline (B) has NO instagram/graph call (Legge 5 — Damar publishes manually); its terminal software status is `rendered` (`wr2_canva_desktop_apply.py` `_persist_result`). Building P-4's write at the autopsy's suggested chokepoint would have written into dead code.

**ANTIBODY:** When a long multi-agent report (autopsy, deep-research, council synthesis) cites `file:line`, treat those citations as LEADS, not facts — re-run `find`/`grep`/`Read` on each load-bearing one BEFORE building on it. The autopsy was CORRECT about the substance (the variety machine is unplugged; the fact-checker self-references; BRAND_SUFFIX clamps) — verified, and batch-1 fixes shipped on it (PR #1125). But 3 of its specific file refs were hallucinated. The discipline that caught this is the standing anti-hallucination rule (CLAUDE.md §6): "mai citare output di un tool senza averlo eseguito in QUESTO turn". Extended here to: **mai costruire un piano su un file:line di un REPORT senza ri-verificare che il file esista in questo turn.** The P-4 plan (`research/operations/P4-topic-type-log-plan.md` §0) documents the corrections and was built on the verified reality, not the report text.

**GOTCHA:**

- The autopsy is NOT retracted — it remains the authoritative diagnosis of WR2's monotony/fact problems. Only its 3 phantom citations are wrong. Future agents: use it for the WHAT, re-verify every WHERE.
- The hallucinated `_voyager-curriculum.py` is plausible because a real Voyager-style skill-library evolver DOES exist in this ecosystem (`agent-library` / EvoSkill, see `discovery_s13_evolution_loop_never_closed`). The autopsy likely pattern-matched that into a WR2 curriculum reader that was never built. Plausibility ≠ existence.
- P-4 (migration 216, shipped 2026-06-05 PR #1133) is the FIRST real `topic_type_log` — it's a Postgres table on the production path, NOT the phantom SQLite one. Anyone grepping `topic_type_log` after 2026-06-05 will find the real one; do not confuse it with the autopsy's phantom.

**Reference:** autopsy `research/operations/2026-06-04-wr2-autopsy-report.md` (finding #10). Corrections in `research/operations/P4-topic-type-log-plan.md` §0 + REV2. Real implementation: PR #1133 (squash `d45d43656`), migration `216_wr2_topic_type_log.sql`. Family: anti-hallucination discipline (the `non è vero` → re-verify-disk-state reflex), `lessons_hallucinating_tool_output_is_diabolical`.

---

## Archived

Resolved scars moved to [`cicatrix-scars-archive.md`](./cicatrix-scars-archive.md) (not auto-loaded per session). Currently archived:

**Archived 2026-05-27 sweep (~36 scars, RESOLVED/INFO/STRUCTURAL ≤2026-05-23 — W31–W57 series, T0.2/T3.2/Wave 1/3/4 spec runs, mata-garuda consumer-group + NER worker repairs, CRM-Guardian Phase 1.5 OCR layer, P0 SECURITY postgres password rotation, Cell `.env` quoting trap, KG-linker dead-upstream, claude mcp list stale-status, canva-renderer flycast DNS wrapper):**

- See archive file for full TRAUMA/ANTIBODY/GOTCHA — grep by W-number, date, or keyword. Notable entries: W31 fly_machines_restart actuator, W34 asyncpg.PostgresError lint guard, W37 incident ledger, W48 cell_skills.source migration 196, W50/W51/W52 HOME-fork family, W55 alerter retry, W57 wa-mirror enrichment self-healing.

**Archived 2026-05-25 sweep (8 scars, RESOLVED/INFO < 2026-05-18):**

- ⚠️ STRUCTURAL: GDRIVE_COMPANIES_FOLDER_ID phantom + wa-mirror bypasses POST /api/clients (2026-05-21) — fix shipped commit `1a3824b39`
- ⚠️ STRUCTURAL: Intel Lake routing prefix-blind for subdomains (2026-05-20) — patched PR-B1a
- ✅ RESOLVED: outbox-drain stderr noise (2026-05-20) — PR-B2
- ⚠️ STRUCTURAL: WR2 master template requires verified richtext slot count (2026-05-10 → bypassed 2026-05-13)
- ⚠️ STRUCTURAL: WR2 canva-apply path coupling (2026-05-10) — workaround shipped
- ✅ RESOLVED: LegalIngestionService bypasses OpenAI 300k token batch limit (2026-05-10)
- ⚠️ STRUCTURAL: NLM feeder split-brain — base_worker redis-cli no host arg (2026-05-06) — patched same day
- ✅ RESOLVED: Backend `/health` masks `app.state.startup_failed` (2026-04-29) — PR #337

**Historical archives (pre-2026-05-25 cleanup):**

- ✅ RESOLVED: OpenClaw MCP child apparent mortality = test artifact (2026-05-02)
- ✅ RESOLVED: Backend prod down — drive_poll_service called missing method on ServiceAccountDriveService (2026-04-29)
- ✅ RESOLVED: Atlas migrate-lint paywalled in v0.38 — pivoted to Squawk (2026-04-26)
- ✅ RESOLVED: SQL v2 migrations apply on OLD image, not the freshly-built one (2026-04-26 → 2026-04-29)
- ✅ RESOLVED: Deploy crash before health check went unalerted (Air A3, 2026-04-18)
- ✅ RESOLVED: Dockerfile cell-core missing (PR #56 → PR #62 → monorepo workspace promotion)

---

### ⚠️ W64 (REOPEN of W34): asyncpg silent-death pattern re-introduced by W49 sibling-fix in wr2_canva_lease_watchdog.py (2026-06-02)

_Discovered: 2026-06-02 05:15 WITA by S15 symbiosis-deep-audit (cicatrix-resurrection assailant + orchestrator independent re-verify) · Severity: P2 · Status: **REOPENED** — antibody (lint script) alive, codebase compliance regressed_

**TRAUMA**: W34 (2026-05-23, commit cb32f8214) patched 5 daemon sites + shipped `scripts/lint_asyncpg_except_completeness.py` and claimed "Live codebase post-fixes: 0 violations". S15 re-test runs the lint live → **REAL_LINT_EXIT=1** (orchestrator isolated `$?` after catching a pipe-masked exit-0 false-read). Violation: `scripts/wr2_canva_lease_watchdog.py:40` has `except (asyncio.TimeoutError, OSError, asyncpg.PostgresError) as e:` — **missing `asyncpg.InterfaceError`** (sibling of PostgresError, NOT a subclass → connection-interface failures silently swallowed in a daemon reconnect loop). The file is a genuine daemon (`async def main()` + `asyncio.run(main())` + retry loop, the W49 lease-watchdog cron). Git blame: violation introduced by commit `120078999` "fix(wr2): lease-watchdog connect-with-retry (W49)" dated 2026-05-23 14:40:54 — AFTER W34's cb32f8214 landed the SAME DAY. W34's own sibling fix re-introduced the exact silent-death class W34 was built to prevent. CI never caught it because W34's GOTCHA admitted CI integration was "deferred to W35" — the guard never gated commits.

**ANTIBODY**: (1) Patch `scripts/wr2_canva_lease_watchdog.py:40` to `except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as exc:` (lint fix-template). (2) Finally wire `lint_asyncpg_except_completeness.py` into CI / pre-commit (close the W35 deferral) so the next sibling-fix regression gates at PR time, not at audit time 10 days later. NOT executed by S15 (read-only diagnosis; reopen = structured entry, not fix).

**GOTCHA**: The antibody-vs-wound distinction matters: the lint SCRIPT is healthy and correctly detects the bug. A future agent grepping "is W34 resolved?" must RUN the lint, not check the script exists. Also: piping the lint through `tail`/`head` masks its exit code — capture `$?` immediately or redirect to file first. `asyncpg.InterfaceError` is the load-bearing omission (connection lost mid-query); `PostgresError` alone covers SQL errors but NOT interface/connection failures.

**Reference**: S15 FROZEN `research/operations/S15-symbiosis-FROZEN.json`. Lint output `/tmp/s15-lint-asyncpg.txt`. Parent W34 in `cicatrix-scars-archive.md` (Archived 2026-05-27 sweep). Regression-introducing commit `120078999`. Target file `scripts/wr2_canva_lease_watchdog.py:40`.

---

### ⚠️ W65 (RESIDUE of 2026-04-29 plist-secret-644): skills-bridge-consumer .bak leaks 64-hex API key world-readable; live plist hardened but backup ignored (2026-06-02)

_Discovered: 2026-06-02 05:15 WITA by S15 symbiosis-deep-audit (launchagent-health assailant; devils-advocate FALSELY refuted, orchestrator grep re-confirmed) · Severity: P2 SECURITY · Status: **chmod RESOLVED 2026-06-03 (verify-fix-loop empirical re-check), KEY ROTATION residual still recommended**_

> **2026-06-03 verify-fix-loop empirical re-verification** (closed-loop PR verification of S15 #1023): ran `ls -la` + `stat -f '%Sp'` on `~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist.bak-pre-chmod0400-20260531` → perms are now **`-r--------` (0400)**, NO LONGER 0444 world-readable. The chmod half of the antibody is DONE (a follow-up sweep hardened it). The 64-hex `BRIDGE_SKILLS_API_KEY` is still embedded in the backup, so **ROTATION remains the open residual** since the value was world-readable historically. ALSO re-checked `com.cell.organism.plist` (flagged in the parent 2026-04-29 scar as carrying `GOOGLE_API_KEY`/`FLY_API_TOKEN`/`CELL_DATABASE_URL` inline at 0644): it is now **805 bytes with ZERO inline secret keys** (reconstructed-minimal post 2026-04-29), so its 0644 is harmless — no leak. Net: S5 #1021 FROZEN claim "all 5 inline-secret plists are 0400" HOLDS empirically.

**TRAUMA**: The S4 2026-05-31 hardening sweep correctly chmod'd the LIVE `com.nuzantara.skills-bridge-consumer.plist` to 0400. But it created a backup `com.nuzantara.skills-bridge-consumer.plist.bak-pre-chmod0400-20260531` and left it **world-readable (`-r--r--r--`, 0444)** — and that backup still embeds the real secret: `<key>BRIDGE_SKILLS_API_KEY</key><string><<REDACTED_64HEX_ROTATE_BRIDGE_SKILLS_API_KEY>></string>` (64-hex). The hardening hardened the file but leaked its own backup — the exact 2026-04-29 plist-secret-644 scar pattern, residue edition. (Sibling finding: 3 `wa-dashboard-m1` plist backups also world-readable carrying a local postgres DSN — lower severity, no password.)

**ANTIBODY**: (1) `chmod 0400` (or `rm`) the backup: `~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist.bak-pre-chmod0400-20260531`. (2) **ROTATE `BRIDGE_SKILLS_API_KEY`** — the 64-hex value sat world-readable on a multi-process machine; treat as exposed. (3) Patch the hardening sweep script so it `chmod 0400`s every `.bak*` it produces, not just the live file. NOT executed by S15 (read-only; reopen = entry, not fix).

**GOTCHA**: The devils-advocate analyst (DeepSeek-class refuter) FALSELY claimed this backup contained ONLY a placeholder comment (`Operator must add BRIDGE_SKILLS_API_KEY here`) and NO embedded secret, trying to downgrade the finding to INFO. Orchestrator grep proved the comment is FOLLOWED by a real value on the next `<string>` line. Lesson: even adversarial verifiers hallucinate — the orchestrator's independent re-grep (anti-hallucination rule 2) is what caught it. NEVER accept a "refuted" verdict on a security finding without re-running the grep yourself.

**Reference**: S15 FROZEN `research/operations/S15-symbiosis-FROZEN.json` (contradictions_caught[1]). File `~/Library/LaunchAgents/com.nuzantara.skills-bridge-consumer.plist.bak-pre-chmod0400-20260531` (0444). Parent scar "Unknown agent overwrites loaded LaunchAgent plist files" (2026-04-29, this file). Sibling: wa-dashboard-m1 backups.

### ✅ RESOLVED: Live 503 "RAG worker unavailable" on kita /process = deploy-desync, NOT runtime (2026-06-02)

_Discovered: 2026-06-02 13:10 WITA · Severity: RESOLVED · Status: Fixed (v3429)_

**TRAUMA**: kita.balizero.com/process threw 503 "RAG worker unavailable" on /api/crm/practices. Looked like a DB/runtime outage. Reality: Fly app nuzantara-rag has 2 process groups (api + rag). The rag machine crash-looped 10x on startup with ModuleNotFoundError: backend.services.crm.whatsapp_enrichment (crm_clients.py:30), then Fly left it STOPPED. The api machine kept /health=200 and unauth endpoints=401 — masking that the rag worker was dead. Broken import was an orphan from W59 CRM AI-profile feature, already removed in origin/main by #1018 (6206f0cf4); but deployed image v3428 predated the fix. Classic deploy-desync (S4 family).

**ANTIBODY**: Clean redeploy from deploy/main (already had the fix) — no code change. Pre-deploy gate green: dep-import smoke + RAG app factory boot + 91/91 RAG pytests + zero whatsapp_enrichment grep hits. Deployed v3429, force-started rag machine, confirmed clean boot past include_heavy_routers, endpoint now 401 not 503.

**GOTCHA**: TRAP 1: `fly deploy` from inside apps/backend-rag FAILS — Dockerfile uses monorepo-root-relative COPY (packages/cell-core, apps/crm-cell), build context MUST be repo root: `cd ~/Desktop/nuzantara-deploy && fly deploy --config apps/backend-rag/fly.toml --dockerfile apps/backend-rag/Dockerfile`. TRAP 2: a STOPPED rag machine post-deploy is autostop-idle, NOT proof of fix — `fly machine start <rag-id>` + read boot logs to confirm clean startup. TRAP 3: pre-deploy import smoke fails on JWT_SECRET_KEY/API_KEYS pydantic validation (Fly runtime secrets) — export dummy 32-char values to reach the real import check. DIAGNOSTIC: split-brain health (api up, rag down) hides worker death behind /health=200 — always check per-process-group state with `fly status`, not just /health.

**Reference**: fix #1018 commit 6206f0cf4 · deployed v3429 image deployment-01KT32YTJJGN1T7YXDCK9BRGQ5 · related: fix_crm_guardian_deploy_venv_empty_2026_06_02.md, S4 structural-debt scar

### CORRECTION to above 503 scar — verified root cause is STUCK-STOPPED machine, not stale deploy (2026-06-02)

_Discovered: 2026-06-02 13:25 WITA · Severity: P2 · Status: Corrected_

**TRAUMA**: The scar entry directly above claimed "deployed image v3428 predated the fix #1018". FALSE — corrected after checking `gh run list` + post-23:51 logs. Verified timeline: (1) 18:15 UTC W59 #1010 deploys broken whatsapp_enrichment import; (2) 19:08 UTC rag machine crash-loops 10x, hits Fly max-restart cap, left STOPPED; (3) 23:51 UTC fix #1018 auto-deploys SUCCESSFULLY via CI (fly-deploy.yml) -> v3428 = FIXED image; (4) BUT the rag machine was already stopped/failed — a rolling deploy to an autostop machine stages the new image and leaves it stopped, does NOT force-boot it. So the fixed code was present from 23:51 but NEVER EXECUTED. Zero crash signatures in logs after 23:51 confirms it never re-ran the app. (5) browser hit /process -> rag worker stopped -> 503. Fix shipped 5h+ before the error was seen; machine just never rebooted to pick it up.

**ANTIBODY**: The real lesson — a Fly machine that crash-loops to the max-restart cap gets stuck STOPPED and is NOT auto-recovered by a later fixing deploy. CI auto-deploy worked correctly; the gap is machine-recovery. Mitigations: (a) cron-fly-restart-detector.yml exists — verify it actually force-starts machines stuck stopped-after-crashloop, not just alerts; (b) post-deploy, always `fly machine start <id>` + read boot logs for autostop machines (a 'stopped' state after deploy is NOT proof the new image runs); (c) consider min_machines_running=1 for the rag process group if 503-on-cold-rag is unacceptable.

**GOTCHA**: A successful `fly releases` entry + green CI does NOT mean the fix is live on an autostop machine that was already dead. `fly status` showing rag=stopped is ambiguous: could be healthy-idle OR stuck-after-crashloop. Disambiguate by force-start + boot-log read. Also: crash stack traces in `fly logs` carry the ORIGINAL crash timestamp (19:08) even when surfaced later — don't misread an old trace as a fresh crash.

**Reference**: gh run 26789282348 (#1018 deploy success 23:51Z) · supersedes mechanism-claim in scar immediately above · cron-fly-restart-detector.yml to audit

---

### ℹ️ P3 FLAKY TEST (clock race): `test_duplicate_alert_id_skipped` blocks innocent PRs on a 1-second boundary (2026-06-04)

_Discovered: 2026-06-04 06:15 WITA while monitoring PR #1101 (a scar_replay-only change touching ZERO backend code) · Severity: P3 · Status: **REPORTED — fix belongs in a backend-scoped PR, not shipped here**_

**TRAUMA**: CI "Backend Tests (Python)" failed on exactly ONE test — `apps/backend-rag/backend/tests/unit/services/ingestion/test_performance_monitor.py:311 TestCreateAlert::test_duplicate_alert_id_skipped` — with `AssertionError: assert 2 == 1` (10576 passed, 1 failed, stop-after-1). The test's OWN comment admits the design: `# Same metric + same second → same alert_id → skip`. It calls `monitor._create_alert("parsing_duration", ...)` twice and asserts `len(active_alerts) == count_before`, RELYING on both calls landing in the **same wall-clock second** so the timestamp-derived `alert_id` collides and the 2nd is skipped as a duplicate. The CI log showed the two ids were `parsing_duration_1780524705` and `parsing_duration_1780524706` — the two calls straddled a 1-second tick, so the ids differed, both alerts were stored, and `2 != 1`. There is NO time mock. The test passes most of the time and fails ~randomly whenever the two `_create_alert` calls fall across a second boundary. It blocked an unrelated PR's auto-merge.

**ANTIBODY** (proposed, NOT shipped — wrong PR scope): freeze/mock time in the test so both `_create_alert` calls deterministically share the same second. Either `@patch` the time source used to build the id (`time.time` / `datetime.now` inside `backend.services.ingestion.performance_monitor`) to a constant, or pass an explicit timestamp into `_create_alert`. The fix belongs in a backend-scoped PR. Immediate mitigation (used now): `gh run rerun <run-id> --failed` re-rolls the dice and usually passes.

**GOTCHA**: This is a non-mine flake — a scar_replay-only PR (`#1101` touches only `agent-library/scar_replay/scar_replay.py` + `test_scar_replay.py`) was blocked by it. **Diagnostic rule**: when CI Backend Tests fail on a PR that changed NO backend code, check whether the failing test is timestamp/clock-dependent BEFORE assuming regression — verify via `gh pr view <N> --json files -q '.files[].path'` that your diff doesn't touch the failing module. The same test passed clean on `#1104` minutes earlier (same suite) → proof it's nondeterministic, not a real break. Any PR whose `update-branch` re-triggers the full Backend Tests can hit it. Family: **nondeterministic-test-blocks-merge (clock race)**. Related discipline: anti-hallucination rule — verify the failing path is actually yours, don't assume.

**Reference**: CI run 26915762002 job 79404910575 (#1101). Failing test `apps/backend-rag/backend/tests/unit/services/ingestion/test_performance_monitor.py:311`. Source under test `apps/backend-rag/backend/services/ingestion/performance_monitor.py` (alert-id generation). PR #1101 files: scar_replay only.

### ℹ️ P3 (phantom-in-memory): `verify_mcp_integrity.sh` claimed-shipped in memory, ABSENT on disk M5+Pro (2026-06-06)

_Discovered: 2026-06-06 12:00 WITA while re-verifying `[ASSUMED-MEMORY]` tags for the guardrail-liveness-sentinel spec, Pro back online · Severity: P3 (process/trust) · Status: **REPORTED**_

**TRAUMA**: Memory `p2_21_mcp_integrity_verify` (2026-05-20) states `scripts/verify_mcp_integrity.sh` shipped at 6636B mode 755 with baseline LOW=24/HIGH=0/MEDIUM=0. Empirical re-check 2026-06-06: the file does **NOT EXIST** on M5 (`~/.claude/scripts/`, repo, `~/scripts/`) NOR on Pro (same three locations via `ssh pro`). A guardrail recorded as shipped-with-baseline is absent on both machines — either never shipped, or lost in a later sweep/worktree-drift. The memory reads as ground truth (precise byte count, mode, baseline numbers) but the artifact is phantom.

**ANTIBODY**: (1) The guardrail-liveness-sentinel's registry (Check B) must NOT seed `verify_mcp_integrity.sh` as `expected-present` until it's re-created or the memory corrected — otherwise the sentinel would alert on a guardrail that was never really there. (2) General rule, which is literally the sentinel's whole thesis: **a guardrail claimed-shipped-in-memory must be re-verified on disk before being relied upon**. Memory is a claim, not a fact. (3) Decide separately whether to re-create `verify_mcp_integrity.sh` (the MCP integrity baseline check is a real safety mechanism worth having) or amend `p2_21` to mark it lost.

**GOTCHA**: This is the **2nd phantom-in-memory caught this session**. The 1st was the WR2 autopsy's 3 hallucinated `file:line` refs (`_state-schema.sql:63` etc., see the META scar 2026-06-05). Same family: **claimed-artifact-absent-on-disk**. Both were caught only by re-running `find`/`ls` in-turn rather than trusting the recorded claim. The anti-hallucination discipline (CLAUDE.md §6) extends to memory entries, not just tool output: a memory that names a file with byte-precision is exactly as fabricable as a hallucinated tool result.

**Reference**: memory `p2_21_mcp_integrity_verify.md`. Spec `docs/superpowers/specs/2026-06-06-guardrail-liveness-sentinel.md` §8bis (Pro live re-verification). Sibling phantom: META WR2-autopsy scar 2026-06-05. Family: claimed-artifact-absent-on-disk. Born from: `decision_guardrail_liveness_sentinel_spec_2026_06_06`.
