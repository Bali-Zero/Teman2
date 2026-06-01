# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

---

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

---

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

---

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

---

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

---

---

### ⚠️ STRUCTURAL: 53 LaunchAgents Pro, only 7 (13%) have KeepAlive=true (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: TBD (P0-3 mass plist audit)_

**TRAUMA:** `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`. Codex counted 53 project plist: 7/53 (13%) `KeepAlive=true`, 11/53 no KeepAlive at all, 5/53 missing `EnvironmentVariables` (VADEMECUM §11 violation), 6/53 logging to `/tmp/` (lost on reboot). Critical daemons missing KeepAlive: `com.cell.organism`, `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`. Cell's crisis-recovery assumes daemon respawns within 10s.

**ANTIBODY (proposed):** P0-3 — `scripts/lint_launchagents.sh` + `scripts/patch_launchagents.sh --dry-run` + PreToolUse hook. Auto-classifies daemon-vs-cron by `StartInterval`/`StartCalendarInterval` presence.

**GOTCHA:** `RunAtLoad=true + no schedule` is ambiguous — manual review needed. Each plist gets `.pre-vademecum-audit` backup before patching. **After plist corruption hardening (see next scar): must `chmod u+w "$plist"` before patch scripts can run.**

---

---

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

---

---

---

### ℹ️ INFO + LESSON: S1 organism audit 2026-05-31 — three traps in LaunchAgent liveness auditing + a sibling-wipe that erased an uncommitted branch mid-session

_Discovered during the S1 organism/LaunchAgent empirical audit (167 com.{nuzantara,balizero,cell} plist) · Severity: INFO (audit-method + one ops near-miss) · Status: audit shipped PR #982 (research/operations/2026-05-31-organism-truth-FROZEN.json + report)._

**TRAUMA (three method traps + one infra hazard):**

1. **ps/log-mtime liveness FALSE POSITIVE (23 phantom "dead-but-alive").** A first-pass classifier flagged 23 daemons dead because their log mtime was >1h old while launchctl reported them loaded. ALL 23 were alive — a long-running daemon legitimately writes no log for hours. The authoritative liveness signal is `launchctl print gui/501/<label>` -> `state=running` + `active count = N` + `last exit code = (never exited)`, cross-checked with `ps -p <pid>`. TRUE dead-but-alive = `state=running` with `active_count=0` (launchd thinks it should run but has no instance). Count was 0.

2. **secret-keyword grep FALSE POSITIVE (27 phantom "secret reboot-bombs").** Naive `grep TOKEN|API_KEY` over plist bodies flagged 27. Reality after per-plist `plistlib` + perms triage: only **2 plists are world-readable AND hold a real secret VALUE** (wa-dashboard-m1 WA*DASHBOARD_DATABASE_URL @0644, skills-bridge-consumer BRIDGE_SKILLS_API_KEY @0444); 3 hold a value behind `0400` owner-only (post-publish-poller, post-publish-webhook, sentinel — hardened, fine); the rest source ~/.nuzantara-secrets.env or hold ${VAR}/empty placeholders. Exclude config-number keys (REPOMAP_MAX_TOKENS, *\_TIMEOUT, \_\_RATE) from the secret regex.

3. **KeepAlive on a clean-exit one-shot = W61 storm.** 3 jobs (post-publish-poller, automap-watchdog, sentinel) are RunAtLoad+no-schedule+no-KeepAlive. The "obvious" fix (add KeepAlive) is WRONG: `sentinel` is a clean-exit one-shot (`sys.exit`), so KeepAlive would respawn it forever — the W61 retry-storm class. ALWAYS grep the target for an internal loop (`while True`/`asyncio.run`/`serve_forever`/`uvicorn`) before adding KeepAlive; a clean-exit script needs `StartInterval`, not KeepAlive.

4. **SIBLING-WIPE mid-session (the real scare).** Twice during this audit a sibling process did a `git checkout` that switched the working tree off my feature branch back to another audit branch AND a `/tmp` cleanup deleted my scratch scripts. Net effect: a branch I believed I had created + committed + PR'd ("commit a1d927c84 / PR #980") NEVER actually persisted — `git cat-file -t a1d927c84` = "Not a valid object", the branch didn't exist, and the report.md I "wrote" was gone from disk. The intermediate tool outputs that appeared to show success were either from a transient state that got reset, or I misread them. Only the untracked stale FROZEN.json and one /tmp dataset survived.

**ANTIBODY:**

- Liveness audit primitive = `launchctl print active_count`, NEVER ps-log-mtime, NEVER raw `launchctl list` Status (which shows -9/-15 for a SIGKILL/SIGTERM reload that is NOT a crash — qdrant showed Status=-9 yet print=running active_count=1 and curl :6333/healthz=HTTP 200).
- Secret triage = plistlib + perms, not grep. World-readable AND real-value = RED; 0400-owner-only = acceptable; secrets-file-source = good.
- KeepAlive-policy = check for internal loop in the target before adding it.
- **VERIFY PERSISTENCE AGAINST THE GIT OBJECT STORE, NOT INTERMEDIATE OUTPUT.** After commit+push: `git cat-file -e HEAD:<path>` for every deliverable, `git rev-parse HEAD == git rev-parse origin/<branch>`, and re-read numbers via `git show HEAD:<file>`. On a contested worktree with sibling automation, a "successful" commit can be silently reset; only the object store is authoritative. Keep the authoritative dataset (merged.json) in a /tmp-cleanup-proof location and regenerate outputs from it idempotently.

**GOTCHA:**

- `launchctl print gui/501/<label>` returns 0 bytes for ~9/167 labels (codex-\* family + a few watchdogs) in this env — fall back to `launchctl list` Status for those.
- ps/pgrep DO work in this audit sandbox (postgres/redis/ollama/Finder/WindowServer all visible, 1453 procs) — so ps is usable to confirm a PID, but it was the log-mtime heuristic, not ps, that produced the 23 FP.
- The 5 binary-missing RED (wr3.supervisor, wr3.editorial-bench.monthly, wr3.yt-metrics.weekly, wr2.canva-renderer, cleanup-2026-05-16-ttl-sentinel) are the 2026-04-29 P0-3 / W62 / W63 orphan-automation family resurfacing: wrapper deleted from ~/.openclaw/bin (gitignored HOME) but plist left LOADED — fails only on next trigger, silent until then.

**Reference:** PR #982, research/operations/2026-05-31-organism-truth-FROZEN.json (167 records), research/operations/2026-05-31-organism-nervous-system-audit.md. Family: cousin of 2026-04-29 "untracked files lost when sibling switches branches" + 2026-05-13 "Write returns success but file removed by sibling" + W61 storm.

---

## Archived

Resolved scars moved to [`cicatrix-scars-archive.md`](./cicatrix-scars-archive.md) (not auto-loaded per session). Currently archived:

**Archived 2026-06-01 sweep (4 scars, RESOLVED-de-facto, empirically re-verified 2026-06-01 via 4-subagent fan-out — mata_garuda active-active (Pro23/Mini5 ZERO overlap bidirectional), test-infra mock≠prod (all 3 antibody tests shipped), EventBus Phase-3 (per-handler ack + daily/weekly prune cron + SYMBIOSIS.md updated), migrations 129/130 dup (0 dup/89 files, 4-layer lint guard)).** The 5 STRUCTURAL kept active are all PARTIALLY-FIXED with live residue: W62 (GC daemon shipped, missing CI test), evolver/puller (shared-path coupling + benign hourly `fatal`), untracked-files (no WIP daemon — broker+GC+stop_verify mitigate), 53-launchagents (37/192 KeepAlive, post-publish-poller correctly bare per W61), unknown-agent-plist (0 corrupted/recurrence, fs_usage trap OFF, 102/192 still 0644).

**Archived 2026-05-31 sweep (6 scars, RESOLVED/INFO 2026-05-26→05-29 — W57 wa-mirror self-heal, W58 openclaw 2-profile cascade, W60 Fly api flap, W61 dlq retry-storm, W63 nested-worktree, Canva-headless REVERSAL):** grep archive by W-number.

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
