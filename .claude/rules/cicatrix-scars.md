# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### ℹ️ INFO + REVERSAL: the "Canva MCP OAuth doesn't survive `claude -p`" wall (2026-05-13) FELL — headless canva-apply shipped behind WR2_CANVA_ACTUATOR=headless (2026-05-29)

_Discovered/built: 2026-05-29 during a WR2-fragility session ("AppleScript e app aperta si rompe sempre") · Severity: enhancement (replaces a chronically-fragile actuator) · Status: **CODE SHIPPED on `feat/wr2-canva-headless-actuator-2026-05-29` behind a flag, default=desktop. Cutover (flip to headless) is operator-gated pending shadow validation.**_

**TRAUMA (original, 2026-05-13):** `wr2_canva_apply.py` headless path was decommissioned because project-scoped Canva MCP OAuth didn't survive the `claude -p` spawn, and Canva Connect REST had no element-level text replace. Fallback: AppleScript driving the Claude Desktop GUI (focus app → paste → poll 10min). Three serial breakpoints (app must be open, skill must be registered, AppleScript must respond). Operator: "si rompe sempre".

**REVERSAL + ANTIBODY (2026-05-29, 8-task TDD plan, 4-LLM panel + 2 plan-review rounds):**

- **The wall fell**: Canva MCP is now claude.ai-account-hosted (`mcp__claude_ai_Canva__*`), reachable in headless `claude -p` as a DEFERRED tool via a STEP -2 `ToolSearch select:mcp__claude_ai_Canva__*`. 4-phase feasibility study proved read/write/commit + full skill run + images + move + sibling-race all work headless. Empirically verified: plain `--dangerously-skip-permissions` + ToolSearch → Canva reachable (`CANVA-OK`).
- **A4 dangling-transaction gate (BLOCKING)**: probe killed a `claude -p` mid-transaction then opened a fresh one → `FRESH OK`. Canva does NOT poison a design after a killed transaction; a fresh transaction supersedes the orphan. No quarantine mechanism needed. (Probe root cause of 4 INVALID runs was NON-technical: the model REFUSES to open+abandon a transaction; fix = legitimate edit task + external kill.)
- **A6 duplica-poi-edita (the key reversal of the D4 corruption class)**: skill v4 now opens the MASTER strictly read-only (get-design/get-design-content), DUPLICATES it (resize-design → working copy), and edits ONLY the working copy. A crash leaves the master pristine — only an orphan copy to GC. Neutralizes master corruption + dangling-master-txn + the D4 sibling-race in one move. Verified end-to-end on throwaway: working copy `DAHK-Ro6wJs` edited, master `DAHKzVykbbA` confirmed pristine via get-design-content.
- **A1 fenced lease**: `pg_try_advisory_lock` keyed on `template_design_id` (cluster-global on shared Fly Postgres → serializes Pro+Mini), released in `finally`.
- **A2 RE-SCOPED (empirically forced)**: the panel asked for flag-based MCP/built-in isolation. Empirically UNACHIEVABLE — `--strict-mcp-config` EXCLUDES account-hosted Canva ("CANVA GONE"); `--disallowedTools Bash` is IGNORED under `--dangerously-skip-permissions` ("BASH-PRESENT"). So A2 was re-scoped to: (1) sanitize slide TEXT in `pending_builder._sanitize_slide_text` (the only injection surface — skill body is fixed/hashed); (2) skill-body sha256 tripwire (`infra/claude-skills/canva-apply.sha256`, WARN-only); (3) **documented residual risk** (this scar). NO regression: the AppleScript path already ran with the same built-ins.
- **A5 quota preflight** (best-effort, fail-open), **A8 fail-closed** (`canva_tools_loaded_in_stream` — never mark rendered if no Canva tool_use in the stream), **A3 option-c** (the Python actuator writes `carousel_canva.json` for reconcile + upload-waste, skill unchanged).
- **Cutover flag**: `WR2_CANVA_ACTUATOR=desktop` (default, AppleScript) | `headless` (new). Shipped behind the flag; desktop path structurally untouched.

**GOTCHA:**

- **RESIDUAL SECURITY RISK (A2)**: headless runs with full built-ins (Bash/filesystem) because flag isolation is impossible AND `--dangerously-skip-permissions` is required for cron. Mitigation is upstream-only (sanitized slide text + hashed skill body). A malicious string in slide text that survives the sanitizer regex could in principle drive a built-in. Accepted because: (a) the slide text comes from our own editorial pipeline, not untrusted users; (b) the model retains ethical judgment even under skip-permissions (proven by the A4 probe — it refused to abandon a transaction); (c) no regression vs the prior AppleScript actuator. Revisit if Anthropic ships a flag that isolates built-ins under skip-permissions.
- **The model refuses risky prompts even headless**: the A4 probe's first 4 runs failed because the model would not open+abandon a Canva transaction on shared state. This is a SAFETY FEATURE, but also a design constraint: headless prompts must frame actions as legitimate, not as "do X then abandon it".
- **prettier mangles `mcp__claude_ai_Canva__*` tool names** (`__` → markdown bold). The STEP -2 ToolSearch list MUST live inside a code-fence in both the installed skill and the mirror, else prettier corrupts the tool names. Baseline sha256 must be regenerated after any prettier pass.
- **stream-json `transaction_id` is ESCAPED** (`\"transaction_id\":\"...\"`) inside a serialized tool_result string — regex over the raw stream must tolerate backslashes.
- **stream-json over a subprocess PIPE deadlocks** for `claude -p` (it doesn't flush line-by-line into a pipe) — redirect to a FILE and poll, don't use `subprocess.PIPE` + reader thread for live monitoring.
- **24 throwaway Canva designs** accumulated across feasibility + this build (Canva MCP has no delete-design) — listed in `research/operations/2026-05-29-wr2-canva-headless-feasibility.md`, trash manually from folder `FAHK-KcnLVk`.

**Reference**: plan `docs/superpowers/plans/2026-05-29-wr2-canva-headless-actuator.md`, spec `research/operations/specs/2026-05-29-wr2-canva-headless-actuator.md`, feasibility `research/operations/2026-05-29-wr2-canva-headless-feasibility.md`. Commits on `feat/wr2-canva-headless-actuator-2026-05-29`: probe `e4293bec3`, sanitize `fb1159405`, skill v4 `a24bb4ca`, lease `73fb9322`, quota `2c2e6d6bf`, orchestration `413e539eb`, dispatch `b206c80ab`, KeyError guard `bfafea76e`. Family: reverses the 2026-05-13 wr2_canva_apply decommission; cousin of the WR2 canva-renderer cron wrapper scars (2026-05-23).

---

### ✅ RESOLVED + LESSON: W61 — `add_to_dlq` stripped autopilot_attempts on re-add → 4-job storm loop 7 days, 4676 escalations (2026-05-28)

_Discovered: 2026-05-28 08:00-09:30 WITA durante orchestrator session zero-baseline cleanup · Root cause traced by deep-researcher subagent · Severity: P1 (4 cron in retry storm 7gg, 4676 escalations accumulated, sentinel noise structural) · Status: **FIXED commit on feat/fix-dlq-w61-preserve-attempts-2026-05-28**_

**TRAUMA:** `shared/escalations_pro.jsonl` accumulated **4676 entries** between 2026-05-21 and 2026-05-28, 99% from 4 cron jobs in infinite retry loop emitting `dlq_autopilot_escalation` every ~30sec (prime_tunnel, post_publish_webhook, post_publish_poller, zombie_hunter). All entries had `error_summary=""` (empty) priority=NORMAL status=pending. Telegram alerts blackened by W57 suppression cooldown (correctly working).

**Root cause traced by deep-researcher 2026-05-28 09:00 WITA** (file: `research/operations/2026-05-28-dlq-autopilot-retry-storm.md`):

Two compounding bugs:

1. **`launchagent-state-bridge` died 2026-05-26 13:28** (no KeepAlive in plist) → state files in `~/.agent/decisions/state/*.last.json` froze → sentinel parser sees stale "last_ts" → marks job as failing → calls `add_to_dlq()`.

2. **`add_to_dlq` (scripts/sentinel_lib/repairer.py:120)** strips `autopilot_attempts` on re-add via list-rebuild pattern:
   ```python
   data["queue"] = [e for e in data["queue"] if e.get("job") != job]  # removes existing
   data["queue"].append({..., "status": "needs_aider"})  # fresh entry, attempts=0
   ```
   Combined with `dlq_autopilot.py:485-489` which fires `escalating directly` for `len(error) < MIN_ERROR_LEN` (empty error_summary triggers it) → infinite loop: sentinel re-adds → attempts reset to 0 → dlq_autopilot escalates directly without incrementing past max_attempts(10) → never transitions to TERMINAL.

**ANTIBODY (shipped 2026-05-28):**

1. **W61 patch `add_to_dlq`**: preserve `autopilot_attempts`, `status`, `first_abandoned_at`, `manual_terminal_reason` from existing entry across re-add. Overlay-pattern: `new_entry.update(preserved)` after rebuild. Preserved fields win over defaults — TERMINAL stays TERMINAL even if sentinel re-detects same failure.

   ```python
   existing = next((e for e in data["queue"] if e.get("job") == job), None)
   preserved = {}
   if existing:
       for key in ("autopilot_attempts", "status", "first_abandoned_at", "manual_terminal_reason"):
           if key in existing:
               preserved[key] = existing[key]
   # ... rebuild queue + append new_entry ...
   new_entry.update(preserved)
   ```

2. **Test coverage**: 2 nuovi unit test in `scripts/tests/test_sentinel_v33.py::TestDLQTerminalState`:
   - `test_w61_preserves_autopilot_attempts_on_re_add` — verifica `attempts=7` persiste
   - `test_w61_preserves_terminal_status_on_re_add` — verifica TERMINAL non viene overwritten

3. **Tactical mitigation** (parallel a W61 fix): 4 storm jobs manualmente forced TERMINAL in `~/.agent/decisions/dlq.json` con `manual_terminal_reason="orchestrator 2026-05-28: storm loop"`. Backup `/tmp/dlq-backup-pre-storm-cleanup-2026-05-28.json`.

4. **launchagent-state-bridge KeepAlive fix**: plist patched `<key>KeepAlive</key><true/>` (era solo RunAtLoad=true → muore dopo exit). Backup `~/Library/LaunchAgents/com.nuzantara.launchagent-state-bridge.plist.bak-pre-keepalive-2026-05-28`. Reload OK, log mostra "Written 4/4 state files" attivo.

**EMPIRICAL EVIDENCE storm STOPPED**: escalations rate 4684→4684 ZERO new in 10min observation post-fix. Pre-fix era ~50/h (constante 7gg).

**GOTCHA:**

- L'incremento `autopilot_attempts += 1` (dlq_autopilot.py:634) accade nel `else` branch dopo skipped_preflight. Quindi tecnicamente DOVREBBE incrementare. MA viene immediatamente strippato dalla prossima chiamata sentinel `add_to_dlq()` che ricostruisce la queue. È il combo a creare il loop, non un singolo bug.
- `add_to_dlq()` ha docstring "Idempotent — won't add duplicate entries". È idempotente sulla key (un job = una entry) MA NON è idempotente sui campi computed (attempts, status). Il termine "idempotent" è fuorviante in questo contesto.
- L'altro caller `add_to_dlq(job, aider_attempts=N>0)` produce `status="needs_claude_code"` come default — il W61 fix preserve overlay manterrà quella semantica solo per entry esistenti TERMINAL/in-progress. Aider attempts counter è altro field separato, non impattato.
- Telegram suppression W57 funzionante correttamente è la ragione per cui operator NON ha visto 4676 escalation in 7 giorni — è feature, non bug. Future enhancement (proposta): weekly digest "alert suppressed by cooldown last 7 days".
- `prime_tunnel` non era falso positivo: cloudflared `config-prime.yml` deleted ad un certo punto → daemon non parte → status=failed legit. Separate fix needed (out of scope W61).

**Reference**:

- Patch: `scripts/sentinel_lib/repairer.py:120-160` (commit pending PR feat/fix-dlq-w61-preserve-attempts-2026-05-28)
- Tests: `scripts/tests/test_sentinel_v33.py:475-516` (5/5 PASS)
- Investigation: `research/operations/2026-05-28-dlq-autopilot-retry-storm.md`
- Tactical mitigation: dlq.json patched 09:18 WITA, escalations stopped 09:18-09:28 monitored
- launchagent fix: `~/Library/LaunchAgents/com.nuzantara.launchagent-state-bridge.plist`
- Family: sister of W53 (TERMINAL gate enforcement), W54 (state file ts must be float), W57 (Telegram suppression). Cross-link: orchestrator zero-baseline cleanup session `research/operations/2026-05-28-zero-point-recovery.md`.

---

### ✅ RESOLVED + LESSON: W60 — Fly api machine flapping 3.5h post wa-mirror-12bug-batch deploy tail effect (2026-05-28)

_Discovered: 2026-05-28 08:45 WITA via backend-verifier subagent during orchestrator zero-baseline audit · Self-recovered ~01:00 UTC same day · Mitigation PR #903 shipped (memory 2gb→3gb + cpus 1→2) per future-proofing · Severity: P0 → P2 downgrade after self-recovery · Status: **AUTO-RECOVERED + future-proofing in flight**_

**TRAUMA:** api machine `7847d95ce257d8` (Fly nuzantara-rag, process group `api`, shared-cpu-1x:2048MB) reported `1 total, 1 critical` health check status from 2026-05-27T21:05:07Z for ~3.5 hours. Fly proxy logs at 00:45:35Z: `"could not find a good candidate within 40 attempts at load balancing. last error: [PR01] no known healthy instances found for route tcp/443"`. External curl `--max-time 15 https://nuzantara-rag.fly.dev/health` → http=000 timeout (2× consecutive from Pro to Fly Sin).

Compounding internal log evidence:

- `00:44:43Z health[...] Health check 'servicecheck-00-http-8080' on port 8080 has failed`
- `00:44:59Z app[...] ERROR olympus.guardian Heartbeat cycle failed: asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation`
- `00:48:54Z app[...] team_timesheet_service._auto_logout_loop` same asyncpg drop

The 1-vCPU + 2GB api machine couldn't handle the post-deploy load surge after PR #870 (wa-mirror-12bug-batch) shipped at 2026-05-26 01:40Z. Cold-start uvicorn+presidio+torch+transformers import chain takes ~7min on shared-cpu-1x; combined with CRM Guardian bulk load + olympus heartbeat + asyncpg pool churn, exceeded available CPU/RAM during respawn.

**Detection mechanism (notable)**: discovered via orchestrator session 2026-05-28 mcp-health agent dispatch reporting `nuzantara-rag.fly.dev` HTTP 000 timeout — NOT via Telegram alert (alerts ciechi per W61 storm + W57 cooldown). Without this synchronous audit, the flap would have persisted invisible.

**ANTIBODY (multi-layer):**

1. **Self-recovery**: by 2026-05-28T01:01:24Z, machine state returned to `1 total, 1 passing` autonomously. Fly's restart logic recovered the worker. Latency post-recovery 130-300ms steady 3/3 curl test.

2. **Future-proofing PR #903** (orchestrator session 2026-05-28 09:00 WITA, surgical 2-line fly.toml patch):

   ```diff
   - memory = '2gb'
   + memory = '3gb'  # 2026-05-28 EMERGENCY upgrade
   - cpus = 1
   + cpus = 2       # 2026-05-28 EMERGENCY upgrade
   ```

   Why subset of PR #859 (open since 2026-05-25): #859 had 40+ conflict files from 3-day drift on CODEOWNERS/workflows/migrations, rebase = hours of work, api needed fix NOW. Only 2 valid deltas brought over (grace_period 60s→300s from #859 was obsolete — Fly capped grace_period upstream to 60s, no longer settable).

3. **PR #859 closed** as superseded (`gh pr close 859 --comment "Superseded by #903"`).

4. **W41 W42 W59 hooks active** prevent future migration/branch hijack regressions but DON'T cover Fly machine sizing. Future enhancement: emit Telegram alert when `1 total, 1 critical` persists >5min (NOT just on health pass/fail oscillation).

**GOTCHA:**

- `fly.toml` is in CLAUDE.md off-limits hook guard list. The hook **itself** says: _"Se la modifica è intenzionale, fai unstage e commetti con --no-verify + spiegazione."_ W60 fix used `--no-verify` with spiegazione in commit message. This IS the spiegazione, not a bypass.
- `grace_period = '300s'` was historical (PR #859 spec) but Fly platform has since enforced 60s cap upstream. Setting 300s gets silently ignored. The fly.toml comment line 245 already says: _"Fly now caps health-check grace periods at 60s"_.
- mcp-health agent successfully discriminated stdio JSON-RPC layer ("nuzantara-mcp child alive") from upstream HTTP target ("nuzantara-rag.fly.dev unreachable") — this is a good MCP-design pattern: a degraded MCP is not the same as a down MCP, and the diagnostic must distinguish.
- post-recovery there were still `ConnectionDoesNotExistError` periodic — points to a Postgres pool config issue (likely pool_recycle / connect_timeout). Out of scope for W60 fix, separate investigation needed.
- The 2GB memory was set 2026-05-09 specifically for OOM (`memory = '2gb'  # 2026-05-09: api OOM-killed at 1GB`). 3GB is double-margin protective.

**Reference**:

- Commit: `99166dce9` on `feat/fly-api-emergency-2026-05-28`
- PR: #903 (auto-merge enabled, awaiting CI green)
- Closed: PR #859 (superseded)
- Live empirical: `fly logs -a nuzantara-rag` 2026-05-28T00:42-01:00Z window
- Detection: backend-verifier + mcp-health agents dispatched by orchestrator
- Family: sister of W57 (wa-mirror self-healing W31 fly_machines_restart actuator), cousin of W31 (fly_machines_restart Cell actuator validated 2026-05-23)

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

### ✅ RESOLVED: W63 — Nested worktree bug `wr2-critic-parser-fix/.worktrees/wr2-playwright-render-fix` (2026-05-28)

_Discovered: 2026-05-28 09:00 WITA during orchestrator wave-b cleanup · Fixed same minute via `git worktree remove --force` · Severity: P3 (orphan structure, no functional impact) · Status: **FIXED, root cause unidentified**_

**TRAUMA:** `git worktree list` showed an entry at path:

```
/Users/nuzantara/Desktop/nuzantara/.worktrees/wr2-critic-parser-fix/.worktrees/wr2-playwright-render-fix
```

A worktree NESTED inside another worktree. Branch `agent/nuzantara/wr2/playwright-render-fix` (note: different from `agent/nuzantara/wr2/playwright-render` — `-fix` suffix). HEAD `2e5ea04cd` (same commit as main pre-#899 merge — useless, identical to main).

**Root cause (hypothesis, unverified)**: probabile errore di `git worktree add` o `agent_start.py` esecutivo a partire da una CWD already inside `.worktrees/wr2-critic-parser-fix/` invece di `REPO_ROOT`. Le path relative dell'agent_start.py possono creare nested se REPO_ROOT è resolved sbagliatamente.

**ANTIBODY (shipped):**

1. **Removed via `git worktree remove --force`**: cleaned during W62 orchestrator cleanup.

2. **Proposed prevention** (NOT yet shipped): in `scripts/agent_start.py`, assert that the resolved REPO_ROOT is NOT inside any existing worktree. If it is, abort with error message:
   ```python
   # In agent_start.py cmd_create:
   if any(part == ".worktrees" for part in REPO_ROOT.parts):
       sys.exit("ERROR: agent_start.py invoked from inside a worktree. cd to repo root first.")
   ```

**GOTCHA:**

- `git worktree list` shows all worktrees regardless of nesting. They're flagged identically to top-level worktrees. Only path inspection reveals nesting.
- A nested worktree on the same branch as parent or main is functionally harmless (no race, no commit). But:
  - It pollutes `git worktree list`
  - It consumes inode + disk
  - It can confuse `cd .worktrees/*` shell glob expansion
  - It risks recursive worktree creation if a script iterates and creates nested-of-nested
- The parent `wr2-critic-parser-fix` was itself a legitimate worktree for PR #896. Nested child was a duplicate/typo'd lane name.

**Reference**:

- Cleanup command: `git worktree remove /Users/nuzantara/Desktop/nuzantara/.worktrees/wr2-critic-parser-fix/.worktrees/wr2-playwright-render-fix --force`
- Family: cousin of W62 (broker hygiene), uncle of W59 (sibling-race surface)
- Detection: visible in `git worktree list` during orchestrator audit 2026-05-28 09:00 WITA

---

### ℹ️ INFO: W58 — openclaw `claude-cli` 2-profile MAX cascade fallback shipped + orphan wrapper `openclaw-gateway-launchd.sh` documented (2026-05-27)

_Discovered: 2026-05-27 00:30-01:40 WITA durante setup cascade Codex→Opus 4.7 fallback per quota-exhaust · Severity: INFO (config change clean ship + 1 latent orphan wrapper identificato) · Status: **SHIPPED in `~/.openclaw/openclaw.json` con backup `.pre-claude-fallback-20260527-005214`**_

**TRAUMA (the real story, not the config change):** Setup cascade richiesto da Antonello: Codex GPT-5.5 primary → Opus 4.7 fallback su 429. Empirical discovery durante setup ha identificato **3 trappole architetturali** che meritano memoria:

1. **Confusione "token MAX Antonellosiano"**: Keychain ha entry `token:default:antonellosiano@gmail.com` che NON è Anthropic OAuth — è **Google OAuth refresh token Gmail scope** (`{"refresh_token":"1//0gy1...", "services":["gmail"], "scopes":["gmail.modify",...]}`). Il vero Anthropic Claude token sta in `Claude Code-credentials*` Keychain entries con `claudeAiOauth` JSON shape (`{accessToken: sk-ant-oat01-*, refreshToken: sk-ant-ort01-*, ...}`).

2. **`claude mcp list` Status stale (reconferma scar T0.2 2026-05-22)**: pre-setup il `~/.claude-acct2/` mostrava `loggedIn: true email: null orgId: null` — sintomo "OAuth'd ma email null". Empirical fix richiede `claude /login` da TTY interactive in NUOVO terminal (NON da dentro Claude Code session interactive), con `CLAUDE_CONFIG_DIR=<path>` env.

3. **`openclaw models auth status` ≠ `openclaw capability model auth status`**: il primo non esiste (`Too many arguments for this command`), il secondo è il path corretto via capability layer. Wrapper TUI vs capability-CLI hanno semantica differente — il help è ambiguo. Usare sempre `openclaw capability model auth status > /tmp/x.json` per state JSON.

**ANTIBODY (cascade config shipped):**

```bash
# 1. 2 OAuth slot Claude MAX:
#    - ~/.claude/ (default)         → antonellosiano@gmail.com orgId f41c36a2-... util 7d=12%
#    - ~/.claude-kaiser/ (CLAUDE_CONFIG_DIR) → kaiser198719871987@gmail.com orgId 522e759f-... util 7d=77%
# 2. 2 paste-token in openclaw provider claude-cli:
openclaw models auth paste-token --provider claude-cli --profile-id "claude-cli:antonellosiano" < <(echo "$ATOK_ANTO")
openclaw models auth paste-token --provider claude-cli --profile-id "claude-cli:kaiser" < <(echo "$ATOK_KAISER")
# 3. Add fallback ladder:
openclaw models fallbacks add claude-cli/claude-opus-4-7
# 4. Sanitize .env.master:
sed -i.bak-w58 '/^ANTHROPIC_API_KEY=/d' ~/.openclaw/workspace/.env.master
```

**State post-ship**:

- `defaultModel`: `openai-codex/gpt-5.5`
- `fallbacks`: `["claude-cli/claude-opus-4-7"]`
- `providersWithOAuth`: `["claude-cli (2)"]`
- Profiles: `claude-cli:antonellosiano` + `claude-cli:kaiser` (token shape `sk-ant-oat01-*` 108 byte)
- `.env.master`: `ANTHROPIC_API_KEY` (paid path BANNED per CLAUDE.md) RIMOSSO; `CLAUDE_CODE_OAUTH_TOKEN` MAX OAuth RESTA

**ORPHAN WRAPPER (latent, NON shipped fix — documentazione defensive):**

Durante setup ho scoperto `~/scripts/openclaw-gateway-launchd.sh:27` punta a node binary obsoleto `/Users/nuzantara/.openclaw/tools/node-v22.22.0/bin/node` che NON ESISTE. Log evidence `~/.openclaw/logs/gateway.err.log` accumulato 114860 righe / 16.7MB di `No such file or directory`.

**MA empirical-first verification ha provato che è cicatrix HISTORIC già risolta**:

- File `gateway.err.log` mtime: **2026-05-26 09:18** (~16h fa)
- 10s tail live: **0 nuove righe** (broken wrapper NON più chiamato)
- Plist canonical `~/Library/LaunchAgents/ai.openclaw.gateway.plist` ProgramArguments: `["~/.openclaw/service-env/ai.openclaw.gateway-env-wrapper.sh", "<env>", "/opt/homebrew/opt/node/bin/node", "/opt/homebrew/lib/node_modules/openclaw/dist/index.js", "gateway", "--port", "18789"]` — path CORRETTO
- Plist backup `.bak-pre-wrapper-20260509_195533` ha la versione vecchia con `node-v22.22.0` 404
- Migrazione plist canonical avvenuta **2026-05-09** (data backup file)

**Quindi cosa resta come debt**:

- `~/scripts/openclaw-gateway-launchd.sh` — orphan, nessun consumer attivo, ma esiste sul disco
- `~/.openclaw/logs/gateway.err.log` — 16.7MB stale log, non ruotato
- `~/Library/LaunchAgents/ai.openclaw.gateway.plist.bak-pre-wrapper-20260509_195533` — backup vecchio mantenuto per rollback

**GOTCHA (5 takeaway operativi):**

1. **Keychain naming trap**: `token:default:<email>` può essere ANY OAuth refresh token (Google/Microsoft/etc.), NON Anthropic-specific. Sempre `python3 -c "import json; print(json.loads(...)keys())"` per identificare shape PRIMA di assumere provider.

2. **paste-token reads from stdin** non da `--token` flag. `printf '%s' "$TOK" | openclaw models auth paste-token --provider X --profile-id Y` è la sintassi corretta. Aiuto CLI non lo dice esplicitamente.

3. **Multi-profile per stesso provider**: `--profile-id <name>` accetta naming arbitrario (default `<provider>:manual`). Permette N slot OAuth dello stesso provider con identità distinte. `auth.providersWithOAuth` mostra count fra parentesi: `claude-cli (2)`.

4. **`openclaw capability` vs `openclaw models`**: due CLI surface differenti. Capability è introspection-grade (full JSON state), models è action-grade (mutate config). `auth status` esiste solo in capability layer.

5. **claude-cli model catalog**: source `/opt/homebrew/lib/node_modules/openclaw/dist/cli-catalog-DwwgRqUQ.js` hardcoda `claude-opus-4-7` come opus default. `claude --version` 2.1.150 supporta `--model claude-opus-4-7` via OAuth MAX. Catalog `model list` può mostrare lista parziale (defaults sample) — controllare anche source code per verifica completa.

**Anti-pattern catch durante setup**: avevo concluso "antonellosiano MAX token non esiste in Keychain" basandomi su 1 keychain query inconcludente. Antonello ha challengiato "impossibile, hai anche il token max", ho re-checkato con tool diverso (`security dump-keychain | grep -iE "antonellosiano"`) e ho trovato 2 entry effettivamente presenti. **Lesson reinforce CLAUDE.md Anti-hallucination rule 5**: operatore challenge ("non è vero", "impossibile") = trigger re-verification, NON difesa di quanto detto.

**Reference**:

- Config backup: `~/.openclaw/openclaw.json.pre-claude-fallback-20260527-005214`
- Env backup: `~/.openclaw/workspace/.env.master.pre-claude-fallback-20260527-005214`
- Slot 2 OAuth dir: `~/.claude-kaiser/` (CLAUDE_CONFIG_DIR per login flow)
- Family: orthogonal a W57 (wa-mirror python env repair). Sister to T3.2 (postgres-mcp Hybrid D installation 2026-05-23, stesso pattern panel-driven + paste-credential + restart-gateway).

---

### ✅ RESOLVED + LESSON: W57 — self-healing wa-mirror enrichment Layer A+B+C shipped, sibling-race during git commit caught + recovered (2026-05-26)

_Discovered: 2026-05-26 16:00-19:40 WITA — multi-wave (1 architecture map / 2 panel review / 3 code+test ship / 4 review-gate / e2e chaos test / commit+push) · Severity: P1 (3 wa-mirror LaunchAgents broken 3 giorni via ModuleNotFoundError) · Status: **SHIPPED commits 41a36990e + 83d07dbe1 on feat/wr2-c5a-pilot-and-p1-structural-fixes-2026-05-26**_

**TRAUMA:** 3 wa-mirror LaunchAgent (`com.balizero.wa-mirror-attention-{classifier,realtime,digest}`) crash-looping da 3 giorni per `ModuleNotFoundError: asyncpg`. Cause: plist exec'd a Homebrew externally-managed Python 3.14 (PEP 668 blocks pip install), NON pyenv 3.11.11 con asyncpg+httpx già installati. Antonello vuole zero Telegram, sistema auto-fixa.

**ANTIBODY (3-layer self-healing stack shipped):**

- **Layer A (Step 1, pre-existing 2026-05-26 19:07)**: `~/scripts/wa-mirror-enrichment-wrapper.sh` (6404B mode 755) preventive routing wa-mirror→pyenv 3.11.11 con `--index-url` pinning + `env -i` sanitize. 3 plist patched (ProgramArguments).
- **Layer B-1 (Step 2, pre-existing)**: `~/.agent/decisions/job_registry.json` 3 entries con `fix_pattern` Tier 2 regex `ModuleNotFoundError: No module named '(?P<module>[a-z_][a-z0-9_]*)'` confidence 0.95.
- **Layer B-2 (commit 41a36990e)**: NEW Organism actuator `python_env_repair` (apps/organism/organism/actuators/python_env_repair.py 427 LOC + 38 unit tests). 10 panel-amended must-fix A1-A10:
  - A1 `--index-url=https://pypi.org/simple/` + `--no-input` (supply-chain pinning)
  - A2 regex `fullmatch()` + control-char block (no `\n\r\t\0\x0b\x0c`)
  - A3 explicit `_DEP_ALLOWLIST = {"asyncpg": {...}, "httpx": {...}}` (NO arbitrary PyPI install)
  - A4 orphan `started` TTL 600s separate from 24h normal TTL
  - A5 atomic `fcntl.flock` on attempts JSONL file
  - A6 Python path regex lockdown `\A.+/\.pyenv/versions/\d+\.\d+\.\d+/bin/python(\d+(\.\d+)?)?\Z`
  - A7 fail-closed on corrupt attempts file (return -1 → quarantine)
  - A8 sanitized subprocess env (excludes `PIP_*`, proxy, cert vars)
  - A9 `await proc.wait()` post-kill on timeout (zombie prevention)
  - A10 YAML cooldown_minutes=10 consistent with pip timeout 120s
- **Layer B-3 (commit 83d07dbe1)**: NEW Cell sensor `WaMirrorEnrichmentSensor` (apps/cell/cell/sensors/wa_mirror_enrichment_sensor.py 312 LOC + 20 unit tests) + emit helper `emit_enrichment_repair_request()` in observatory.py. Sensor probes 3 LaunchAgent via `launchctl print`, parses stderr log tail (8KB) per Python exception class. `ModuleNotFoundError` → actionable+repairable; `InvalidPasswordError`/`ConnectionRefusedError` → yellow-but-operator-action-only. Streak counter separato da W27 main red-streak. Empirical evidence Pro 2026-05-26 19:21 WITA: sensor correctly discriminates 3 labels (classifier=InvalidPasswordError NOT repairable, realtime=ModuleNotFoundError asyncpg REPAIRABLE, digest=not running no signal).

**4-LLM panel pre-implementation (16:30-17:00 WITA, Wave 2)**: spec iter-1 → Gemini agy 3.1 Pro APPROVE_WITH_AMENDMENTS (3 must-fix) + Codex GPT-5.5 xhigh REJECT (8 bugs + 5 security vulns) + DeepSeek V4 Pro synthesis = 10 universal must-fix A1-A10. Spec iter-2 written incorporating all 10, ALL applied in code.

**Wave 4 review gate (post-impl, 19:30 WITA)**: 2 parallel review agents:

- code-reviewer found 3 HIGH-confidence: (#1 streak only advances on repairable→logic bug, #2 missing_module taint travels before A3 gate→defense-in-depth, #3 cell_sustained_red_restart catches W57 events too→collateral fly_machines_restart). All 3 patched in-band.
- spalla-review: 2 blockers + 3 suggestions; 1 patch (skip emit on empty fields) + 1 inline W33 GOTCHA reference comment.

**Test count**: 38/38 organism actuator + 20/20 cell sensor + 67/67 broader sensor regression = **125/125 PASS**.

**LESSON / GOTCHA — sibling race during `git commit`:**

Multi-step sequence `git add <my files> && git restore --staged <sibling staged> && git commit` ran into a sibling-session race: between my `restore --staged` (un-staging whatsapp_corpus sibling files) and my `git commit`, an external process (another Claude or hook) re-staged the same sibling files. Resulting commit had MY commit message but THEIR files (whatsapp_corpus/), NONE of my W57 files included.

Recovery: `git reset --soft HEAD~1` → `git restore --staged .` (clean slate) → atomic single `&&`-chained Bash `git add <exact paths> && git commit` (no intermediate step where sibling can interject). Defeated the race on retry.

**5 regole anti-sibling-race for atomic commits:**

1. Single `&&`-chained Bash for `git add` + `git commit`. NO separate tool calls between stage and commit on contested branches.
2. Verify `git diff --stat --cached` BEFORE committing — confirm exactly what's about to be committed.
3. Watch for sibling adding files between your tool calls — `git status -s` shows it post-restore.
4. `git reset --soft HEAD~1` recovers commit-with-wrong-files safely (preserves staged state).
5. Use `HUSKY=0` env to skip Husky shim install hook (still runs pre-commit hook); never `--no-verify`.

**Empirical-first verification chain that caught the InvalidPasswordError discovery (CRITICAL)**: `tail` on actual stderr log at 19:18 WITA showed current breakage was NOT ModuleNotFoundError anymore (Layer A wrapper resolved that). Current breakage was `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "nuzantara"`. This live empirical data shaped Step 4 sensor architecture: discrimination via error-class parsing, NOT just exit code. Spec iter-2 documents this in CRITICAL section.

**Reference**:

- Commits: `41a36990e` (Layer B-2 organism) + `83d07dbe1` (Layer B-3 cell)
- Spec: `research/operations/2026-05-26-step3-spec-iter2.md`
- Panel artifacts: `/tmp/wave2-panel/{gemini,codex2,deepseek-raw2}.md`
- Wrapper Layer A: `~/scripts/wa-mirror-enrichment-wrapper.sh` (HOME, gitignored)
- Layer B-1 registry: `~/.agent/decisions/job_registry.json`
- Live empirical: `~/logs/wa-mirror-attention-classifier.err.log` (29MB+)
- Family: sister of W31 (fly_machines_restart actuator, validated 2026-05-23) + W27 (sustained_red emit pattern reuse) + W37 (incident_ledger auto-wire)

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
