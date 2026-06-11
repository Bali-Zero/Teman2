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

---

### ✅ RESOLVED: W67 — wa-mirror reconnect storm = `supervise-launcher.sh` was `exec start-all.sh` (one-shot) under KeepAlive=true → launchd SIGTERM-kills healthy node bridges every ~22s (2026-06-07)

_Discovered: 2026-06-07 ~08:45 WITA by background-job triage of streaming `wa-mirror disconnected: <name>; reconnect_attempt=35x` notifications · Severity: P2 (OSINT mirror effectively churning, healthy sessions killed) · Status: **RESOLVED** — fix deployed live + empirically verified, PR #1161 to main_

**TRAUMA**: `com.balizero.wa-mirror-launcher` (`KeepAlive=true`, `RunAtLoad=true`, `ThrottleInterval=10`) ran `apps/wa-mirror/scripts/supervise-launcher.sh`, which — despite the name — was a thin **compatibility passthrough** ending in `exec /bin/bash ~/scripts/wa-mirror-launcher/start-all.sh`. But `start-all.sh` is a **one-shot**: it spawns the 6 per-employee Baileys node bridges (`nohup node dist/bridge/index.js --employee=X &`), prints a Summary, and exits 0. Under `KeepAlive=true`, launchd treats every exit as "job died" and restarts it after `ThrottleInterval`. Because the `nohup`'d node children stay in the **launchd job's process group** (nohup ignores SIGHUP but does NOT `setsid`/detach the group), each KeepAlive restart tore down the previous job's process group and **SIGTERM-killed the healthy node bridges**. Net effect: every ~22s (12s launcher run incl. `sleep 2` stagger + 10s throttle) every account was killed and relaunched → endless reconnect storm, `reconnect_attempt` climbing into the hundreds (352+ observed).

Empirical evidence (read-only triage):

- `surya.log`: `wa-mirror session connected` + `opened connection to WA`, then `{"signal":"SIGTERM","msg":"wa-mirror shutdown requested"}` ~21s later — a perfectly healthy session killed from outside.
- launchd `runs = 1369` and climbing; launcher log had **15,732** `START ALL` (cumulative across reloads; the `runs` counter resets on reload, the log persists — that's why the two numbers don't match).
- Node bridge etimes all <40s, staggered ~8-10s apart = single relaunch wave, constantly recycled. No zombie accumulation (~5MB total) → pure churn, not a leak.
- start-all's Summary always read `Launched: 6 / Already running: 0` — the "already running" guard never held _across cycles_ because the processes it would have skipped were being SIGTERM-killed between cycles.

A SEPARATE, independent failure mode surfaced in the same triage (NOT fixed by W67): `sahira.log` showed `Connection Failure → code:401 reason:"logged_out" terminal:true` = the linked device was removed **phone-side**. The bridge retries in an internal backoff loop forever — futile until a human re-links via QR. This is the other contributor to the `reconnect_attempt` counter and is **operational, not code-fixable**.

**ANTIBODY (shipped + verified)**: Rewrote `supervise-launcher.sh` from `exec one-shot` into a **real blocking supervisor**: run the launcher once, then re-run on an interval (`while true; do start-all.sh; sleep ${WA_MIRROR_SUPERVISE_INTERVAL:-60}; done`). A single long-lived supervisor process means launchd's `KeepAlive` never cycles the job, so the node bridges (now grandchildren of a stable, long-lived process group) keep running uninterrupted. `start-all.sh`'s existing pidfile + `kill -0` guard now actually holds across iterations (skips live accounts, relaunches only dead ones). Dropped `set -e` → `set -uo pipefail` so a non-zero launcher iteration is logged + tolerated instead of killing the supervisor and handing churn back to KeepAlive (verified with an exit-1 stub: logs `continuing`, survives). **NO plist change needed** — the plist already pointed at `supervise-launcher.sh`; only the script body changed, so blast radius = 1 file, no plist re-hardening dance.

Deploy: live-incident hotfix on main checkout (commit `b55f9c705`, scoped — operator's pre-staged `infra/launchagents/*` untouched) + clean PR #1161 from `worktree-wa-mirror-supervisor-loop` (commit `926da933b`). `launchctl kickstart -k`. **Empirical verification ~135s post-restart**: `runs` stayed at 1370 (= +1 for the kickstart, then flat → churn STOPPED); single `supervise-launcher` pid 47356 alive 2m15s; all 6 bridges alive with etimes 1:17–2:14 (survived past the old ~22s kill window; before, max etime was 39s); zero new SIGTERM in any bridge log.

**GOTCHA**:

- **`nohup` does NOT detach from the process group.** A backgrounded `nohup cmd &` child still dies when launchd tears down the job's group. If you ever want children to outlive the launchd job _without_ a long-lived supervisor, you need `setsid`. The chosen fix (long-lived supervisor) sidesteps this — the group simply never gets torn down.
- **`launchd runs` resets on plist reload but the StandardOutPath log is cumulative** — don't equate the two counts (here 1369 vs 15732). To prove a KeepAlive crash-loop is fixed, watch whether `runs` _climbs_ over a window, not its absolute value.
- **A "stopped"/short-lived child is not proof of crash** — here the bridges were healthy and killed by SIGTERM from _outside_. Always read the child's own log for the death cause (`signal:SIGTERM` vs `code:401`) before assuming the child crashed. Two different death causes (SIGTERM-from-launcher vs 401-logout) coexisted and need different fixes.
- **The script was NAMED `supervise-launcher.sh` but did not supervise** — name ≠ behavior. The header even called it a "thin compatibility entrypoint". Grep for `exec ` in anything launchd runs with `KeepAlive=true`: `exec one-shot` + KeepAlive is the crash-loop signature (family of the 2026-04-29 "53 LaunchAgents, 13% KeepAlive" scar — daemon-vs-cron misclassification).
- **W67 fixes ONLY the launcher churn.** Accounts logged out phone-side (sahira `628213454723`, and the notification names `Ari` / `+628213454721` which are sequential Bali Zero numbers not in the start-all roster) still need a manual QR re-link: `bash ~/scripts/wa-mirror-launcher/start-one.sh <name> --qr` with the employee scanning on their phone. Until then their bridge runs but loops internally on 401.

**Reference**: PR #1161 (branch `worktree-wa-mirror-supervisor-loop`, commit `926da933b`) + live hotfix commit `b55f9c705`. Memory `discovery_wa_mirror_reconnect_storm_2026_06_06`. Files: `apps/wa-mirror/scripts/supervise-launcher.sh` (fixed), `~/scripts/wa-mirror-launcher/{start-all,start-one}.sh` + `_lib.sh` (HOME-fork, unchanged; `PID_DIR=/tmp/wa-mirror-pids`, `LOG_DIR=/tmp/wa-mirror-logs`). Plist `~/Library/LaunchAgents/com.balizero.wa-mirror-launcher.plist` (0400, unchanged). Verification snapshot: `runs` flat at 1370, 6 bridges etime >70s, zero SIGTERM. Family: daemon-vs-cron KeepAlive misconfig (2026-04-29 plist audit scar).

#### W67b — the loggedOut (401) follow-up: retry-stop + keepalive (2026-06-07)

After W67 stopped the launcher churn, **4 of 6 accounts reconnected on their own with zero QR** (proof the mass "disconnect storm" was the churn, not real logouts). Only **sahira** had a genuine terminal `loggedOut` (401): `creds.json` intact locally (it reaches `logging in…`) but WhatsApp rejects them → device removed/invalidated **server-side** (`session.ts` doc: "the team member removed the linked device", or phone offline >14d, or anti-automation flag). Two code defects made one real logout look like a crisis:

1. **`runAccountForever` (index.ts) retried EVERY error identically** — including the terminal `loggedOut` that `session.ts` rejects with — backoff-capped at 60s, **forever**, firing a Telegram `disconnected; reconnect_attempt=N` alert each time (that is the literal source of the `reconnect_attempt=352` notifications — `index.ts:150`). Fix: `session.ts` now rejects with a typed `SessionLoggedOutError` (instanceof-safe via `Object.setPrototypeOf`); `index.ts` matches it, logs once, sends ONE "needs QR re-link" alert, and `return`s (stops that account's loop). Realizes the intent already documented in `index.ts:10-13`.

2. **The process then EXITED** and start-all relaunched it every ~60-120s (spam just moved from the bridge's internal loop to the supervisor's relaunch loop). Root cause: `await new Promise(() => undefined)` is **NOT** an event-loop handle — once the last Baileys socket/timer drains, Node exits 0. Fix: added an explicit ref'd `setInterval(() => undefined, 1 << 30)` heartbeat in `main()` so the process stays idle-alive; start-all then logs `⏭️ already running PID X` and skips it. **Verified**: sahira pid 67119 stable across a full supervisor cycle (etime 3:04→4:14), launcher log flipped from `🚀 launching` to `⏭️ already running`, `stopping retries=1`, exactly one logout alert; 6/6 bridges present.

Net: a logged-out account now produces **exactly one** alert and one idle process until a manual `start-one.sh <name> --qr` re-link (which kills+restarts it). Daemon restart re-fires one alert (rare now). PR #1161 commits `4c8092248` (retry-stop + 2 vitest cases) + `2b8377dff` (keepalive); live `f5f1aed04` + `50263172e` (+ `npm run build` → `dist/`, gitignored).

**GOTCHA W67b**: (a) `await new Promise(() => undefined)` is a classic false keepalive — it does NOT keep Node alive; only an unref-free timer/handle / open socket does. (b) The launcher log has NO per-line timestamps and is cumulative across kickstarts — `🚀 launching` lines can be stale settling noise; disambiguate "relaunch loop vs stable" by watching the **pid/etime across a full supervisor cycle**, never by the log tail alone. (c) `instanceof` across an `extends Error` needs `Object.setPrototypeOf(this, X.prototype)` to survive TS downleveling — the orchestrator's stop-decision is load-bearing on it. (d) This does NOT prevent the logout itself (server-side) — to actually reduce QR frequency the employee's phone must stay online ≥1×/14d (WhatsApp companion-device limit, not software-fixable). (e) `Ari (+628213454721)` / `Vino (+628213454727)` have sessions but are NOT in `WA_MIRROR_SUPERVISED_NAMES` — orphan/dismissed, pending operator decision.

#### W67c — the Telegram spam was a SECOND machine (Mini active-active orphan), not the Pro (2026-06-07)

After W67/W67b made the Pro silent + clean, the operator was STILL getting `wa-mirror disconnected: <name>; reconnect_attempt=1715` Telegram alerts (Adit, Surya, **Ari**, **+628213454721**), counter climbing live. The trap: I assumed the source had to be the machine I'd been fixing (Pro). It was **Mini-Pro2**. Two independent tells pointed off-Pro: (1) the Pro plist passes `TELEGRAM_BOT_TOKEN=""` to `start-one.sh`, so **Pro bridges physically cannot send Telegram** — every alert had to originate elsewhere; (2) `Ari` / `+628213454721` are NOT in the Pro roster (`WA_MIRROR_SUPERVISED_NAMES`), so a different roster was in play. `ssh mini` found `com.balizero.wa-mirror` (the LEGACY **monolithic** launcher: `~/bin/wa-mirror-runner.sh` → `node dist/bridge/index.js` with NO `--employee`, i.e. the full roster incl. Ari/Vino in one process), pid 735 alive **1d6h**, dist WITHOUT the fix (`grep SessionLoggedOutError dist = 0`), looping `attempt":1720` with its own `~/.wa-mirror.env` Telegram token. Classic **active-active Pro+Mini** (same family as the 2026-05-07 "12+1 mata_garuda LaunchAgents active-active" scar). Operator confirmed "wa-mirror è solo sul Pro" → Mini's instance is a pure orphan: it wrote to Mini's local PG that nothing reads (the dashboard `com.balizero.wa-dashboard-m1` + `wa-viewer` run on the **Pro**, which is therefore canonical). Fix: `ssh mini` → `launchctl bootout gui/$UID/com.balizero.wa-mirror` + `launchctl disable …` (rc=0, process dead, job unloaded, disable persists across reboot). No data loss (Pro canonical). Reverse if ever needed: `ssh mini launchctl enable … && launchctl bootstrap …`.

**GOTCHA W67c**: (a) **A daemon's Telegram/alert spam can originate on a DIFFERENT machine than the one you're debugging.** Before concluding, `ps -eo` + `launchctl list | grep` on EVERY node in the fleet (Pro AND Mini), not just the local one. (b) `ps etime` in `hh:mm:ss`/`DD-hh:mm:ss` form is easy to misread as minutes — a process that looks "7 min old" may be 7 HOURS; use `ps -o lstart` for an unambiguous start timestamp. (c) Two architectures coexisted for the same service: Pro = new single-account-per-process (`start-one --employee=X`), Mini = legacy monolithic (one process, whole roster). When you "fix the launcher", confirm WHICH launcher each running process belongs to. (d) `TELEGRAM_BOT_TOKEN=""` in a plist is a deliberate mute — its presence on one host and absence on another is a strong "who is actually sending alerts" discriminator.

### 🐛 W68: WhatsApp `_guard_property_zoning_reply` over-broad on "lease" → clobbered every villa-leasehold-DURATION answer with a canned Airbnb/zoning lecture (2026-06-08)

_Discovered: 2026-06-08 by the WhatsApp quality-loop test session (31 Q across visa/tax/property/adversarial) · property batch Q4 · Severity: P1 (silent wrong-answer to real clients) · Status: **FIXED** PR #1195 (`d1823ea9d`), verified live 5/5 + 3 regression tests_

**TRAUMA:** Zantara WhatsApp answered "How long is a typical villa leasehold in Bali?" with an unrelated **Airbnb/short-stay zoning lecture** (KBLI 55203, OSS, etc.) — never the ~25-30yr duration. NOT a knowledge gap (KB was correct) and NOT a cache: a post-LLM guard `_guard_property_zoning_reply` (scripts/openclaw_whatsapp_bridge.py) **overwrote** the correct answer with a hardcoded canned text (`_canonical_property_zoning_answer`). The guard fires on `("villa"|"vila"|"airbnb") AND ("zoning"|"residential"|"zone"|"lease")`. The bare `"lease"` token is a substring of `"leasehold"`, so any "villa leasehold" / "villa lease" question tripped it. Its escape clause requires the reply to contain oss+bkpm AND ≤125 words — which a correct lease-DURATION reply never satisfies → the guard **always** clobbered a correct answer. Reproduced live 5/5: "villa leasehold"/"villa lease" broken; "property leasehold" (no "villa") and "villa rental" (no "lease") correct — the asymmetry that pinpointed the trigger. Deterministic, message-keyed (NOT phone-keyed — reproduced on fresh phones), so it hit EVERY client asking villa lease duration.

**ANTIBODY:** Bail out of the guard for pure lease-DURATION intent (how long / how many years / duration / berapa lama / durata / quanto dura …) UNLESS the message also signals Airbnb/short-stay OPERATION intent (airbnb / short-stay / rent out / operate / sewa harian / pondok wisata / business). Genuine "can I run my villa as Airbnb in a residential zone" still gets guarded. 3 regression tests added (`test_property_zoning_guard_allows_villa_leasehold_duration`, `_reworded`, `_still_fires_on_airbnb_operation`). 22/22 bridge tests pass. PR #1195.

**GOTCHA:** The bridge lives in TWO byte-identical copies — `scripts/openclaw_whatsapp_bridge.py` (repo, git-tracked) and `~/.openclaw/bin/openclaw_whatsapp_bridge.py` (HOME, deployed, NOT git-tracked). The fix was applied to BOTH and the HOME bridge restarted (`launchctl kickstart -k gui/501/com.nuzantara.openclaw-whatsapp-bridge`) so it's live NOW — but if a deploy script re-syncs repo→HOME or they drift, re-verify both carry the fix (HOME-fork drift class, cf. W50/W51/W52). The guard family (`_guard_property_zoning_reply`, `_guard_villa_kbli_reply`, `_guard_tax_compliance_reply`, `_guard_lkpm_reply`) is a curated anti-hallucination layer (intro `be06d86ba` #969) — useful but keyword-triggered, so EVERY guard is a candidate for the same over-match class (substring traps, unreachable escape clauses). When adding/auditing a guard: test that it does NOT clobber a correct on-topic answer, not just that it catches the bad one. The broader pattern the quality-loop found: Zantara is **over-cautious** (hides stable facts behind "verify with team") — but this specific case was worse, an active wrong-answer, because a guard _substituted_ text rather than just hedging.

**Reference:** PR #1195, commit `d1823ea9d`, branch `agent/nuzantara/cicatrix-fix/villa-zoning-guard`. Guard `_guard_property_zoning_reply` scripts/openclaw_whatsapp_bridge.py. Tests `apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py`. Discovered during WA quality-loop (memory `decision_zantara_wa_live_test_protocol_2026_06_07`). Family: HOME-fork drift (W50/W51/W52), over-cautious-persona pattern (same session, visa Q3/Q8 + tax property-sale).

---

### ⚠️ P2 STRUCTURAL: W69 — FASE-0 armament audit: le 9 spec P1-P9 sono codice+CI su main ma 2 buchi di armamento restano + 2 trappole che impediscono il fix-facile (2026-06-09)

_Discovered: 2026-06-09 06:54 WITA da M5 (thin-client), audit indipendente post-chiusura sessione sibling FASE-0 · Severity: **P2 STRUCTURAL** · Status: **REPORTED — fix richiede sessione SUL Pro (non armabile da M5)**_

**TRAUMA**: Dopo che la sessione sibling ha implementato le 9 spec del ciclo meta-dev-loop come codice reale su main (`scripts/verify_the_verifiers.py`, `cost_breaker.py` + `cost_breaker_deadman.sh`, `federation_parallelize.py`, `brand_api_gen.py`, `agent-library/learn/lesson_harvester.py` + 8 workflow `.github/workflows/p*.yml` + `hot-zone-pr-gate.yml`), un audit di armamento indipendente (principio W64: **esistere ≠ armato**) trova 2 buchi:

- **BUCO #1**: i workflow P\* **NON sono required-status-checks su main**. I required su main sono solo i 9 storici (`Backend Tests (Python)`, `CodeQL Analysis (javascript/python)`, `E2E Tests (Playwright)`, `Detect Secrets`, `Bandit Python Security`, `Frontend Tests (Next.js) (mouth, true)`, `MCP Server Tests`, `root-guard`). I workflow P\* **girano ma non bloccano** un merge → "esiste-ma-disarmato".
- **BUCO #2**: `cost_breaker.py` (P9) **non ha LaunchAgent runtime** → il dead-man's switch (`cost_breaker_deadman.sh`, G5) è armato solo in CI per-PR, **non H24**.

**ANTIBODY** (NON eseguito — richiede sessione SUL Pro):

1. **Buco #1 NON è chiudibile con un `PUT required_status_checks` cieco** (TRAPPOLA #1): `verify-the-verifiers` e `p1s2-mutation-incremental` sono `pull_request` **`paths:`-filtered** (girano solo se il PR tocca rispettivamente `scripts/verify_the_verifiers.py` / `scripts/mutation_incremental.py`). Un required-check che non gira resta **`pending` forever** → **BLOCCA OGNI PR** che non tocca quei path. Serve PRIMA un job **skip→success sentinel** per ogni workflow (riporta success quando i path non sono toccati), POI il PUT. Inoltre **`p6-federation-parallelize` = FAILURE** su main (run 27100900310, 7 giu) e **`p7`/`p8`/`p3`/`hot-zone` = NO-RUNS** (mai girati): solo `verify-the-verifiers` (success ×3) + `p1s2` (success) sono verdi-stabili candidabili — gli altri NON sono required-safe.
2. **Buco #2** (TRAPPOLA #2): `cost_breaker.py` legge il ledger Postgres `llm_cost_events` (migrazione 117) e `cost_breaker_deadman.sh` osserva `~/.agent/decisions/state/verify_the_verifiers.json` + `sentinel_meta_watchdog.json` → il LaunchAgent **DEVE girare su Pro/Mini** (ledger + cron pesanti), **NON su M5 thin-client**.

**GOTCHA**: **Nessuno dei 2 buchi è armabile da M5** — entrambi richiedono una sessione SUL Pro (coerente con la nota-pending lasciata dal sibling). `hot-zone-pr-gate` è **GIÀ flipped a enforcing 2026-06-07**: gli step `CODEOWNERS self-mod check` + `Replay lint_migration_numbers` sono `continue-on-error: false` (= bloccano); gli step `Redis lease` + `LaunchAgent notice` restano `continue-on-error: true` ma è **monitor-by-design** (i runner effimeri non hanno Redis né LaunchAgent), **NON disarmo accidentale** — non confonderli con il buco #1.

**Reference**: audit in worktree isolato `.worktrees/ops-fase0-armament-audit` allineato a `origin/main` 8bab25ba5. Branch sibling `agent/air-m5/fase0-instrumentation-rearm` (locale, 2 commit `verify_mcp_integrity.sh` + W67-sentinel) **MAI toccato**. Required-checks letti via `gh api repos/Balizero1987/Teman2/branches/main/protection/required_status_checks`. Family: W64 (`esistere ≠ armato`, asyncpg sibling-fix), il verdetto eserciti `2026-06-07-sota-9-spec-armies-verdict.md §4c` rischio-max "decadimento entropico inosservabile / esiste-ma-disarmato". Fix → sessione-Pro dedicata.

---

### ⚠️ W70 (P2, renumber of m5-branch W67): sentinel + meta-watchdog OK but 39 jobs DLQ-terminal (21 in 24h), healing=0 — common cause = Air-decommissioned path-drift in backup scripts + sentinel captures no real stderr (blind autopilot) (2026-06-09)

_Discovered: 2026-06-09 ~04:45 WITA during FASE-0 instrumentation re-arm (read-only audit from M5 via ssh pro) · Severity: P2 · Status: **DIAGNOSED — fix deferred to a dedicated Pro session**. Renumbered from the m5-branch's "W67" because W67 was independently taken on main by the wa-mirror reconnect-storm scar (2026-06-07); two different scars, same number → this DLQ one becomes W70._

**TRAUMA**: FASE-0 re-arm went hunting for "disarmed guardians" (per the 9-spec armies verdict). The verdict said `sentinel_meta_watchdog` was "esiste ma non gira" — FALSE: `launchctl list` on Pro shows `com.nuzantara.sentinel-meta-watchdog` LOADED, `LastExitStatus=0`, state file fresh. The watchdog WORKS. But verifying it surfaced the real wound: `sentinel_status.json` reports `jobs_circuit_terminal=38 dlq_terminal=38 healing_actions_24h=0`. The true source `~/.agent/decisions/dlq.json` → **39 entries, all status=TERMINAL**, age **21 ≤1d / 12 2-7d / 6 8-30d**. NOT stale legacy noise — CORE infra jobs dying NOW: `fly_pg_backup`, `qdrant_snapshot`, `fly_qdrant_backup`, `rag_canary`, `garuda_indexer`, `knowledge_graph_builder`, `nlm_nb1_daily_refresh`, `post_publish_poller`, etc. The fleet sheds jobs into terminal-DLQ and **nobody resuscitates them** (`healing_actions_24h=0`).

Two compounding root causes (found by EXECUTING the real scripts, which the sentinel does not):

1. **Air-decommissioned path-drift (W50/W51/W52 family)**: `qdrant_snapshot` + `fly_qdrant_backup` fail with `/Users/nuzantara/Projects/nuzantara/.../.env not found` — the **Air checkout path decommissioned 2026-05-05**. Live path is `~/Desktop/nuzantara`. Hardcoded dead-machine path.
2. **`fly_pg_backup` runs but produces a 0-byte dump**: `pg_dump` inside the Fly primary returns empty, silent.

**META-problem (load-bearing)**: the sentinel's `log_tail` captures only the retry-wrapper summary ("exit 1 after 3 attempts"), NOT the job's real stderr. So every terminal entry has `classification={type:UNKNOWN, confidence:0.0}` → the autopilot retries blind 10× → gives up → TERMINAL. Observability exists (we KNOW 39 died) but is BLIND on WHY — the exact "instrumentation disarmed" thesis made concrete.

**ANTIBODY (DIAGNOSED, NOT executed — highest-leverage = #3):**

1. grep `~/scripts/*backup*.sh` + `*snapshot*.sh` for `Projects/nuzantara` → repoint to `~/Desktop/nuzantara` (resuscitates the qdrant pair + several of the 21).
2. Fix `fly_pg_backup` 0-byte dump (Fly-side pg_dump empty; cf. W38 role demotion in flight).
3. Make the sentinel capture REAL stderr in `log_tail` (not the retry-summary) — re-arms the WHOLE auto-heal loop.
4. Resolve `com.nuzantara.sentinel` one-shot-vs-daemon mismatch (RunAtLoad, no StartInterval → one-shot the watchdog tamps every ~1h, W55-masked slow crash-loop).

**GOTCHA**: monitor-alive ≠ fleet-healthy — read `dlq.json` / `jobs_circuit_terminal` + `healing_actions_24h`, not just "is the sentinel running". `log_tail="exit 1 after 3 attempts"` is a false friend (zero diagnostic signal). The Air decommission (2026-05-05) keeps spawning path-drift scars 35 days later — no sweep ever grepped all scripts for `Projects/nuzantara`. Family: W50/W51/W52 (Air-path drift), W55 (cooldown masks slow failure).

**Reference**: `~/.agent/decisions/dlq.json` (39 terminal), `sentinel_status.json`, `~/scripts/nuzantara-sentinel.py` (log_tail handling). Origin: m5 branch `agent/air-m5/fase0-instrumentation-rearm` commit d6ae97e33. Pending: triage 39 DLQ + 3 fixes on a dedicated Pro session.

---

### ✅ W71: FASE-0 governance-liveness ARMED H24 on Pro (W69 BUCO #2 closed) + verify_mcp_integrity.sh shipped-but-untested glyph bug caught (2026-06-09)

_Discovered/Fixed: 2026-06-09 ~08:00-08:30 WITA, dedicated Pro session closing W69 · Severity: P2 → RESOLVED for BUCO #2; BUCO #1 + cost_breaker-ledger deferred · Status: **ARMED (2/3 live) + PR**_

**TRAUMA**: W69 found the FASE-0 governance layer running only per-PR in CI, never H24. Arming it surfaced THREE latent wounds, each an instance of W64 (`esistere ≠ armato`):

1. **`verify_the_verifiers.json` permanently MISSING on Pro** — the P1 §4 meta-verifier had NO Pro cron, so its alive-signal never existed, which ALSO blinded `cost_breaker_deadman.sh` (it observes that file). At first deadman boot it correctly alerted `verify_the_verifiers=MISSING`.
2. **`verify_mcp_integrity.sh` (m5 branch) shipped-but-never-run** — it counted the WRONG checkmark glyph (`✓` U+2713) while `claude mcp list` emits `✔` (U+2714) → `connected` parsed as **0** despite ~12 truly connected; and `failed>0 → RED` pinned it perma-RED on chronically-unconfigured optional plugin MCP servers (slack/asana/pagerduty/github-copilot). A guardian that exists, runs, and lies.
3. **`cost_breaker.py` CLI cannot read the real ledger from the Pro** — its `_check_all` path reads ONLY the JSONL fallback (`${LLM_COST_JSONL_ROOT:-/data}`), but the real ledger is Fly Postgres `llm_cost_events`; on the Pro every provider returns UNKNOWN → fail-closed DEGRADE-log every tick. (G4 fail-closed is CORRECT; it just isn't governing real spend.)

**ANTIBODY (SHIPPED + live-verified):**

- 3 LaunchAgents authored (`infra/launchagents/com.nuzantara.{verify-the-verifiers,mcp-integrity,cost-breaker-deadman}.plist`) + idempotent installer `install_fase0_governance.sh` (runtime home = deploy worktree; graceful-SKIP a label whose script is absent; `/bin/bash` 3.2-compatible — NO `declare -A`, a `case()` function). 2 armed live (verify-the-verifiers + deadman); mcp-integrity SKIPs until this PR merges + the deploy worktree syncs the fixed script.
- `verify_mcp_integrity.sh` fixed: glyph `✔|✓`; RED only on failures INCREASING vs a baseline (pre-existing optional-plugin failures tolerated, captured first-run); + a per-tick alive-signal `mcp_integrity.json` (the m5 version wrote only the frozen baseline, useless for staleness).
- `cost_breaker_deadman.sh` OBSERVED_FILES extended with `mcp_integrity.json` → closes the W69 §G5 mutual-watch (deadman now watches all three governance signals).
- GATES (live on Pro): verify-the-verifiers `runs≥1`, `verify_the_verifiers.json` now FRESH; deadman exit 0 on fresh signals (zero false alarm) + FORCE_ALERT emits a SELF-TEST Telegram; cost_breaker proven UNKNOWN→DEGRADE, over-budget $25/$20→STOP, known-low→ALLOW; verify_mcp_integrity now YELLOW (was false-RED) with `connected=12`.

**GOTCHA**: arming ≠ value — a cron that runs but reads the wrong glyph / a missing ledger is W64 theater; RUN the guardian and read its verdict before trusting the green light. macOS `/bin/bash` is 3.2 — `declare -A` raises "invalid arithmetic operator" (it failed silently here until run with `/bin/bash` explicitly; `which bash` was 3.2 too). The deadman's first-boot `MISSING` alert is a one-time transient (the signal persists on disk after first write). DEFERRED (not this session): cost_breaker.py real-ledger bridge (Fly PG → Pro), BUCO #1 (P\* required-status-checks), and the 2 disarmed claude_hook gates verify_the_verifiers surfaced (`seam_verify` hook file missing, `guardrails_static` not registered in settings.json).

**Reference**: PR (FASE-0 instrumentation rearm) branch `agent/nuzantara/infra/fase0-governance-rearm`. Live state: `~/.agent/decisions/state/{verify_the_verifiers,mcp_integrity,cost_breaker_deadman}.json`. Family: W69 (parent audit), W70 (sibling DLQ), W64 (esistere ≠ armato), W50/W51/W52 (deploy-worktree as runtime home).

---

### ⚠️ W72: WhatsApp persona over-cautious — deflected STABLE regulatory facts (B211-vs-KITAS etc.) to "verify with team"; root cause was prompt blanket-clause + \_guard_legacy_b211_reply clobbering correct answers (2026-06-08)

_Discovered: 2026-06-08 during the WhatsApp quality-loop session · Severity: P2 (persona quality / trust, not runtime) · Status: **FIXED** — prompt split + b211 guard gate narrowed + 2 regression tests, both file copies patched, bridge restarted (PR #1197)_

**TRAUMA:** The quality-loop found Zantara hiding STABLE, published regulatory facts behind "I'll verify with the Bali Zero team" deflection — the B211-vs-KITAS definitional difference, the standard overstay fine, and standard property-sale rates were all deferred instead of answered. A competent consultant answers those on sight; deferring them read as evasive. The first investigation blamed the prompt alone (`reply_rules` ~L886 + `knowledge_tool_contract` ~L858 conflated three different things: exact prices, this-client status, and "legal/tax/immigration rules" — and deferred all of them). But the fix loop FALSIFIED the "pure prompt" hypothesis: `_guard_legacy_b211_reply` (a post-reply guard) was OVERWRITING correct definitional B211 answers with a canned deflection — the SAME guard-over-match class as the villa zoning guard fixed in W68/#1195. Editing only the prompt flipped 1/4 cases; the guard dragged the other 3 back to the canned answer.

**ANTIBODY:** Split defer from state-directly across `reply_rules` + `knowledge_tool_contract` + the `_tool_mandates` visa block: DEFER (unchanged caution) exact prices, custom quotes, service-package totals, case-specific timelines, and this-client filing/eligibility/status; STATE DIRECTLY the stable published facts (visa-type definitions and differences, standard overstay fines, standard property-sale rates, statutory capital thresholds), then note the team confirms client-specific application. Rewrote the `_guard_legacy_b211_reply` gate: it now PASSES correct legacy/definitional answers (those that frame B211 as old wording, or define it against a KITAS / short-stay / residency permit, or give the current C2/C12 route) and CLOBBERS only genuinely-unsafe "B211 is the current route" claims with no legacy/definitional framing. Added 2 regression tests (`test_b211_guard_allows_correct_definitional_answer`, `test_b211_guard_still_clobbers_unsafe_current_claim`) — 21/21 unit tests green. Both copies patched identically (repo `scripts/openclaw_whatsapp_bridge.py` + HOME `~/.openclaw/bin/openclaw_whatsapp_bridge.py`) and the bridge restarted. PR #1197.

**GOTCHA:** This is the THIRD guard-over-match found in the `_guard_*` family (after the villa zoning guard W68/#1195, same author-class). The guards (introduced be06d86ba / #969) are a recurring over-deflection source: each one is a post-reply enforcement that can clobber a CORRECT on-topic answer because its gate predicate is too tight. **When auditing ANY `_guard_*`, write a test that it does NOT clobber a CORRECT on-topic answer, not just that it clobbers a wrong one.** HOME-fork double-file applies (W50/W51/W52): the live bridge runs the HOME copy, so a fix that only touches `scripts/` is invisible to production until the HOME copy is patched and the bridge restarted — keep them byte-identical in the edited regions. The over-caution had TWO layers (prompt + guard): fixing only the visible prompt layer is insufficient because the post-reply guards are the load-bearing enforcement that runs AFTER the model has already produced a good answer.

**Reference:** PR #1197, branch `agent/nuzantara/cicatrix-fix/persona-overcaution`, fix commit `2bd9af3cd`. Edited functions: `_tool_mandates` (visa mandate block ~L153), `_guard_legacy_b211_reply` (~L502, the load-bearing gate rewrite), `_build_prompt` `knowledge_tool_contract` (~L858) + `reply_rules` (~L886). Tests: `apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py` (`test_b211_guard_*`). Family: `_guard_*` over-match (W68 villa zoning), HOME-fork double-file (W50/W51/W52).

---

### 🐛 W73: WhatsApp `_guard_*` family — 5 MORE over-match defects found by an 8-agent parallel quality-loop; root class = bare-substring triggers + unreachable positive-gating escapes (2026-06-09)

_Discovered: 2026-06-09 by an 8-agent parallel quality-loop (5 service domains + 3 transversal axes: guard-hunter, multilingua, adversarial-caution) sweeping 80 questions against the live OpenClaw/GPT-5.5 bridge · Severity: P1 (2 live-proven wrong-topic answers) + P2 (3 over-caution) · Status: **FIXED** — all 5 + word-boundary helper + 4 persona reply_rules, 11 regression tests (38/38 green), both copies byte-identical + bridge restarted + 7/7 live-verified end-to-end_

**TRAUMA:** After W68 (villa) and W72 (b211), a structured 8-agent fan-out confirmed the model itself is SOLID (zero price/KBLI/regulatory hallucinations across 80 Qs, all verified to the rupiah vs `migration_066`/`157`) — but **five more `_guard_*` functions clobber CORRECT answers**, all the same class:

1. **`_guard_villa_kbli_reply` / `_VILLA_TERMS` (P1, live-proven):** the term tuple held `"ota"` and `"rent"` as bare substrings — `"ota"` matches "qu**ota**"/"bi**ota**", `"rent"` matches "diffe**rent**"/"cu**rrent**". A live probe _"Which KBLI code covers the import quota for frozen food distribution?"_ returned the **verbatim villa Airbnb 55203 canonical** — a food-import client got a villa answer.
2. **`_guard_lkpm_reply` (P1, live-proven):** the escape clause `"1 to 15 april" not in reply` was near-unsatisfiable — ANY correct LKPM answer lacking that exact English literal (a definition, an ID/IT answer, "April 1-15") was clobbered into the deadline-heavy canonical. A "what is LKPM" definition got the "do not use old 1-10 deadlines" lecture.
3. **`_guard_tax_compliance_reply` (P2):** the OSS/BKPM verify-suffix was appended on bare `"tax"/"spt"/"ppn"/"pph"` — so 5/10 STABLE-fact answers (Coretax definition, SPT deadline, VAT rate) got an irrelevant compliance tail. Worst case: "What is Coretax?" (a dictionary definition) got a risk-verify suffix.
4. **`_guard_cafe_pma_reply` (P2, intermittent live):** fired on `"pt pma" in message` + cafe/coffee NEL **reply** (never checking the message) — so a definitional "difference between PT PMA and PT lokal" answer that named a cafe as an example was randomly clobbered into the cafe-Canggu canonical.
5. **`_guard_nominee_reply` (P2, two compounding bugs):** (a) the trigger was the literal word `"nominee"` only, so the most common real request — "can my Indonesian friend hold the title for me?" — never fired; (b) even when it fired, the canonical said only "risky / red flag", **never illegal/void** under agrarian law, so a client could read "risky but doable".

**ANTIBODY:** Root-class fix + 5 targeted gates, all live-verified:

- **`_contains_any_word()`** new helper: word-boundary (`\b`) containment so short triggers (`tax`/`spt`/`lease`/`ota`) can't match inside longer words. Applied to the tax trigger; the recurring substring-trap root.
- **(1)** dropped `"ota"`/`"rent"` from `_VILLA_TERMS` (kept `"rental"`). Food-import query no longer mis-classified.
- **(2)** LKPM escape rewritten to **negative-gating**: clobber only on a stale-deadline marker OR a wrong deadline-window assertion (`deadline`/`due date`/`no later than` terms — NOT generic verbs like "submit"); a reply with no deadline at all (pure definition) passes.
- **(3)** tax suffix gated on **RISK/PENALTY/EXPOSURE intent** (`risk`/`penalty`/`denda`/`fine`/`late`/`audit`/`compliance`/`owe`/…), not bare tax keywords. Stable rate/definition answers stay clean.
- **(4)** cafe guard now requires cafe intent in the **MESSAGE** (`cafe`/`coffee`/`kafe`/`kedai`/`56303`/…), not merely in the reply.
- **(5)** nominee: a **compositional intent detector** `_is_nominee_intent()` (verb `hold/keep/register/put-in` + asset `title/land/property/shares` + proxy `for me/friend/wife/atas nama`) catches lexical variants a fixed phrase list missed ("hold the land **title** for me"); the canonical now states the arrangement is **ILLEGAL and void under Indonesian agrarian law** (land can fall to the State, no enforceable claim) in all 3 languages; a short risky-only answer to a real request is substituted regardless of length, while a correct definitional answer that already frames the illegality passes.
- **4 persona `reply_rules`** (the over-caution levers, not guards): never convert a published threshold into a personal eligibility verdict; working in Indonesia plainly requires a work permit and a tourist/VOA does not grant work rights (say it, don't hedge to "I wouldn't rely on that"); office is in the Kerobokan area of Bali by appointment; VAT is 11% effective / 12% headline (PPnBM luxury full 12%) stated consistently across languages.

11 new regression tests, **38/38 green** — each asserts the guard does NOT clobber a CORRECT answer AND still catches the bad one (the W68/W72 discipline). Both copies patched byte-identical (repo `scripts/openclaw_whatsapp_bridge.py` + HOME `~/.openclaw/bin/openclaw_whatsapp_bridge.py`), bridge restarted, **7/7 live-verified** (food-import→no-villa, LKPM-def→clean, Coretax→no-suffix, PT-PMA-vs-lokal→no-cafe, nominee×2→ILLEGAL, + W68 villa-leasehold and PT-PMA-HGB regressions hold).

**GOTCHA:** This is the FOURTH+ guard-over-match sweep (W68, W72, now 5 at once). The recurring root is now named: (a) **bare-substring triggers** — `_contains_any` does `term in value`, so every short term is a landmine; use `_contains_any_word()` for triggers. (b) **positive-gating escapes** — a guard that keeps the reply only if it contains one exact phrase (`"1 to 15 april"`, `oss`+`bkpm`) is unreachable for a correct answer phrased any other way; flip to **negative-gating** (clobber only on a detectable WRONG signal, default passthrough). (c) **fixed phrase lists are brittle** — "hold the title for me" missed "hold the land title for me"; prefer a compositional verb+noun+signal detector. (d) HOME-fork double-file (W50/W51/W52) — the live bridge runs the HOME copy; a `scripts/`-only fix is invisible until HOME is patched + bridge restarted. The cherry-pick base for this PR pulled #1197 (persona + b211) forward so this is a super-set; #1197 can close as subsumed. **Meta-recommendation (not yet shipped): a shared test-matrix harness — for each `_guard_*`, one "correct-answer-passes" + one "wrong-answer-clobbers" assertion — would have caught all five at once and gates the next one.**

**Reference:** branch `agent/air-m5/wa-guard-family-fix`, fix commit (this PR). Edited: `_VILLA_TERMS`, `_contains_any_word` (new), `_guard_lkpm_reply`, `_guard_tax_compliance_reply`, `_guard_cafe_pma_reply`, `_canonical_nominee_answer`, `_is_nominee_intent` (new) + `_guard_nominee_reply`, `_build_prompt` `reply_rules`. Tests: `apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py` (11 new). Discovered via the 8-agent quality-loop (memory `decision_zantara_wa_live_test_protocol_2026_06_07`). Family: `_guard_*` over-match (W68 villa, W72 b211), HOME-fork double-file (W50/W51/W52), bare-substring-trigger root class.

---

### ✅ RESOLVED: M5 dev-environment path-drift — 5 MCP venvs + 7 plugin marketplaces copied from Pro with `/Users/nuzantara/` paths, dead on M5 (`balizero`) (2026-06-09)

_Discovered: 2026-06-09 ~21:40 WITA during a "fixa tutto" on the M5 startup diagnostic (5 MCP servers `failed`, 19 plugin `cache-miss` errors) · Severity: RESOLVED · Status: **FIXED + empirically verified** (all 5 venvs import, GitHub PAT HTTP 200, 7/7 marketplaces updated) — requires Claude Code restart to re-spawn_

**TRAUMA**: The M5 (`balizero@Air-M5`) Claude Code diagnostic showed two failure clusters that turned out to share ONE root cause — **Pro→M5 path-drift** (family W50/W51/W52). (1) All 5 venv-backed MCP servers (`ga4-analytics`, `ocr-tesseract`, `nuzantara-mcp`, `nuzantara-mcp-advanced`, `nuzantara-browser`) failed `posix_spawn` ENOENT: their `.venv` dirs were **copied from the Pro** (mtime 15-25 feb/mar), so the `bin/python3` symlinks pointed at `/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3` (and one set at a dead `python3.14`) — interpreters that do not exist on M5 where the user is `balizero`, not `nuzantara`. The venvs even had working entrypoint scripts (`ga4-mcp-server`, `mcp-ocr`) with shebangs hardcoded to `/Users/nuzantara/...`. (2) All 19 plugin errors were `cache-miss` because `~/.claude/plugins/known_marketplaces.json` had every `installLocation` set to `/Users/nuzantara/.claude/plugins/marketplaces/...` (the real dirs DID exist under `/Users/balizero/...`, only the JSON pointer was wrong) → `claude plugin marketplace update` refused with "corrupted installLocation". Compounding: this all surfaced AFTER Antonello clarified the M5 doctrine — "thin-client NON per il coding, M5 deve essere UGUALE, qui codifichiamo" — i.e. the dev environment (venvs, MCP, marketplaces) MUST be native on M5, not borrowed from the Pro.

**ANTIBODY**: (1) For each of the 5 MCP servers: `rm -rf <dir>/.venv` then recreate native — `uv venv --python 3.11 <dir>/.venv` + install. The 2 pip-packaged ones reinstalled from PyPI at their pinned versions read off the copied `dist-info` (`google-analytics-mcp==2.0.1`, `mcp-ocr==0.1.4`); the 3 app ones `uv pip install -e <dir>` from their `pyproject.toml`. `mcp-ocr` also needed the SYSTEM dep `tesseract` (`brew install tesseract` → 5.5.2). Verified empirically: each server's module imports under its native interpreter (not just "binary exists"). (2) Marketplace fix: backup `known_marketplaces.json` then a single replace-all `/Users/nuzantara/.claude/plugins/marketplaces/` → `/Users/balizero/...` (after confirming all 7 target dirs already existed) — re-update succeeded 7/7. (3) The 2 missing MCP tokens (`GITHUB_PERSONAL_ACCESS_TOKEN`, `NUZANTARA_API_KEY`) pulled from the Pro (`~/.zshrc` / `~/.nuzantara-secrets.env`) into M5 `~/.zshenv` (chmod 600) WITHOUT printing values (ssh-pipe, value never in transcript); GitHub PAT validated live (api.github.com/user HTTP 200). `LANGSMITH_API_KEY` does not exist even on the Pro → left unset (optional, tracing-only). Memory `decision_m5_air_fleet_join_2026_05_31.md` updated with the "dev-uguale-al-Pro, venvs NATIVE not copied" rule.

**GOTCHA**: A copied venv is the silent-death trap — `bin/ga4-mcp-server` and the whole `site-packages` look intact, only the `python3` symlink is a dangling cross-machine path, so the failure is `posix_spawn ENOENT` on the interpreter, NOT an import error you can grep. To re-verify a fix here, RUN `python -c "import <module>"` under the venv (interpreter resolves) — don't trust `ls bin/`. `uv venv` REFUSES to overwrite an existing (broken) `.venv` without `--clear` or a prior `rm -rf`. The marketplace dirs already existed natively under `/Users/balizero/` — only the JSON pointer was Pro-pathed, so the fix is a pointer rewrite, not a re-clone. **The deeper lesson**: any cold-copy of a dev environment Pro→M5 (`~/.pyenv`-linked venvs, `.claude/plugins/*.json` with absolute installLocation, plist/script shebangs) carries `/Users/nuzantara/` paths that are dead on M5's `/Users/balizero/` home — a future M5 bootstrap or sync MUST create venvs/caches native, never rsync them whole. Family: W50/W51/W52 (Air/Pro home-fork path-drift), W70 (Air-decommissioned path-drift in backup scripts). Requires a Claude Code restart for the client to re-spawn the 5 servers with the native venvs + reload the marketplaces.

**Reference**: M5 session 2026-06-09. Files fixed: `.mcp-servers/{ga4-analytics,ocr}/.venv`, `apps/{nuzantara-mcp,nuzantara-mcp-advanced,nuzantara-mcp-browser}/.venv`, `~/.claude/plugins/known_marketplaces.json` (backup `.bak-pathfix-20260609`), `~/.zshenv` (0600). Memory `decision_m5_air_fleet_join_2026_05_31.md`. Family: W50/W51/W52, W70.
