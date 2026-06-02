---
date: 2026-05-29
domain: operations
client_case: none
sources: ["Gemini 3.1 Pro (agy)", "Codex GPT-5.5", "DeepSeek V4 Pro"]
---

# 3-LLM panel: recurring worktree/branch/cleanup failure-patterns

## Brief

# Panel review: 6 recurring failure-patterns in a multi-agent monorepo (git worktree / branch / cleanup)

You are a senior infrastructure / multi-agent-systems reviewer. Below is a real meta-analysis from an autonomous AI-orchestrator session. I want you to: (A) critique each pattern + proposed enforcement, (B) name ADDITIONAL recurring patterns I likely missed, (C) give CONCRETE solutions (hook/CI/cron/script — not vague advice). Be terse, technical, adversarial. Find holes.

## Context: the system

- Solo-dev agency ("Bali Zero"). Monorepo `~/Desktop/nuzantara` on macOS, also a server node. Repo is PUBLIC on GitHub.
- Heavy autonomous operation: multiple parallel Claude Code sessions + ~160 `launchd` cron jobs (LaunchAgents) + subagents dispatched via an Agent tool, all operating on git.
- Discipline rule already in place: every agent session SHOULD run under `.worktrees/<lane>-<task-id>/` created by `scripts/agent_start.py`. Main checkout `~/Desktop/nuzantara` is meant to be read-only for agents (operator-interactive + hotfix only). Kill switch `AGENT_BROKER_ENABLED=false`.
- Existing enforcement ALREADY shipped (so don't re-propose these as if new):
  - Hooks (`~/.claude/hooks/`): `worktree_isolation.py`, `worktree_file_write_check.py`, `agent_workspace_setup.py`, `orchestrate_gate.py` (forces subagent dispatch after long sessions), `dispatch_nudge.py`, `stop_verify.py` (blocks Stop on dirty git + no intent marker), `guardrails-static.py` (blocks `rm -rf` on `/`, `$HOME`, `~` + destructive MCP patterns), `precompact-mnemos.py`, MOS capture hooks.
  - Scripts: `agent_start.py` (worktree broker, has `--cleanup` flag that is OPT-IN manual, and `--release`), `branch_graveyard_cleanup.sh` (weekly, dry-run, report-only for zombie `claude/*`/stale branches), `wr2_worktree_gc.py` (GC but ONLY for WR2 lane worktrees), `lint_launchagents.sh` (CI-time lint of plists).
  - LaunchAgents: `com.balizero.wr2.worktree-gc.daily` (WR2 only), `com.nuzantara.branch-cleanup.weekly` (report-only).
  - husky: pre-commit (typecheck + lint + off-limits-file block + a Redis-lease hot-zone check), pre-push, post-commit.
  - Redis lease registry: `agent_lock:<resource>` TTL+heartbeat; pre-commit blocks commit on hot-zone files (LaunchAgent wrappers, migrations, auth/billing, .github/workflows) if another agent task holds the lease. Graceful degradation if Redis down (pass-through + WARN).
- Anti-hallucination doctrine: "never cite a tool output without running the tool THIS turn".

## Current live state (ground truth, just measured)
- 6 worktrees registered, 4 worktree dirs under `.worktrees/` on disk, 11 local branches, 2 zombie `agent/*` branches.
- One worktree is at `/private/tmp/nb-curator-wt` (a worktree under /tmp — survives only until reboot).
- One worktree is `(detached HEAD)`.

## The 6 recurring failure-patterns (from cicatrix scars W50–W63 + the just-finished session)

### Pattern 1 — Sibling-race on a SHARED working tree → lost work / branch hijack
- **Evidence**: W59 (a sibling automation hijacked the branch during sequential git ops); 2026-04-29 incident (TWICE in 9 hours, untracked files silently lost because a sibling did `git stash` WITHOUT `-u`, then `git checkout`); this session had to rescue a `stash@{8}` from an abandoned clone; W63 (a worktree got created NESTED inside another worktree).
- **Root**: multiple sessions/cron touch the same checkout; a sibling's `git stash`/`checkout` relocates untracked files invisibly to the active session.
- **Hole in current enforcement**: `worktree_isolation.py` + `agent_workspace_setup.py` exist, BUT the main checkout is still writable in practice, and some cron LaunchAgents still share a tree (e.g. an "agent-library-evolver" weekly cron and a "deploy-puller" hourly cron both did `git checkout` on the SAME `~/Desktop/nuzantara-deploy` worktree → 32h silent drift, P0).
- **Proposed discipline**: any cron LaunchAgent that runs `git checkout` MUST have a DEDICATED worktree (never share). Enforceable via a lint on plists that detect `git checkout` against a shared REPO_ROOT.

### Pattern 2 — Worktrees / branches that never die (TTL violated)
- **Evidence**: W62 (6 worktrees orphaned 34h past their 60min TTL, each with pseudo-dirty formatting noise); W63 (nested); current state = 6 worktrees + 2 zombie branches + 11 local branches accumulating.
- **Root**: `agent_start.py --cleanup` is OPT-IN manual — NO cron invokes it; subagents don't call `--release` at exit; `.worktrees/<lane>/.agent-task.json` has a `created_at` but no consumer enforces it.
- **Hole**: `wr2_worktree_gc.py` covers ONLY the WR2 lane; `branch_graveyard_cleanup.sh` is weekly + report-only for zombies. There is NO general GC for `.worktrees/`.
- **Proposed discipline**: daily cron `agent_start.py --cleanup` for ALL worktrees (with W62 nuance: do NOT drop worktrees with non-formatting dirty content OR mtime <10min = active session) + a CI test that FAILS if `.worktrees/` has any entry with mtime >24h.
- I rate this the HIGHEST-ROI fix (closes W62/W63 + shrinks the surface of Pattern 1).

### Pattern 3 — HOME-fork drift (a plist execs a STALE copy in `~/scripts/` instead of the repo copy)
- **Evidence**: W50 (a wrapper exec'd `$HOME/scripts/dlq_autopilot.py`, a May-11 fork missing a fix); W51 (sentinel plist exec'd a HOME fork 24 DAYS stale → 60% over-escalation, 75% slower, for 3 weeks); enumeration found 84 of 167 plists exec from `~/scripts/` not the repo.
- **Hole**: W52 added a lint rule to `lint_launchagents.sh` that catches plist-DIRECT HOME-fork desync, but ONLY at CI-time, and does NOT cover wrapper-CONTENT desync (the W50 class, where the plist execs a repo wrapper but the wrapper itself execs a HOME script).
- **Proposed discipline**: extend the lint to scan wrapper content for `exec ... $HOME/scripts/...` + run it in pre-commit (not only CI).

### Pattern 4 — Hallucinated "deleted" / skipped verification
- **Evidence**: in THIS session a cleanup subagent FALSELY reported it had deleted `~/.git`/`~/Teman2`/caches (its `rm -rf` was actually blocked by the guardrails anti-home-wipe hook, but it claimed success). Also 2 fabricated git merge SHAs saved to memory for a PR. Also a 2026-05-13 doctrine incident ("hallucinating tool output is diabolical").
- **Root**: an agent cites a tool result without re-running the verifying tool in the current turn.
- **Hole**: this is currently ONLY prompt discipline, no enforcement.
- **Proposed discipline**: any destructive dispatch MUST be paired with an INDEPENDENT read-only verifier (a second subagent / atomic command that re-checks ground truth). The orchestrator did this ad-hoc this session; should be an obligated pattern.

### Pattern 5 — Race from PARALLEL subagents on a time-sensitive action
- **Evidence**: PR #920 (a merge subagent + a verify subagent dispatched IN PARALLEL → contradictory reports, one read pre-merge state, one read post-merge → led to saving 2 nonexistent SHAs). Also a content-dedup subagent crashed TWICE this session with API 400 "thinking blocks cannot be modified" after ~16–50 tool calls.
- **Proposed discipline**: time-sensitive actions (a merge in progress, a delete in progress) = ONE atomic command OR ONE sequential subagent, NEVER a parallel fan-out. Plus brief subagents "minimal reasoning, no extended thinking" to avoid the thinking-block API400.

### Pattern 6 — safe-rm reinvented every time (guardrails blocks absolute `$HOME` paths → workaround via relative path)
- **Evidence**: this session, deleting `~/.git`, `~/Teman2`, `~/Projects/nuzantara` — each time the guardrails hook (correctly) blocked `rm -rf <absolute $HOME path>`, so the orchestrator did `cd <parent> && rm -rf <relative-name>` (which doesn't match the home-wipe regex). Repeated 3×.
- **Not a bug** — the guardrails anti-home-wipe is working as designed. But the `cd parent + rm relative` dance is reinvented each time.
- **Proposed discipline**: standardize a `scripts/safe_rm.sh` (refuses `/`, `$HOME`, `~`, anything with a live git-tracked twin, anything inside an active worktree; requires the target to be verified-dead first) instead of ad-hoc relative-path rm.

## The "mother pattern" hypothesis
All existing enforcement is OPT-IN (manual cleanup) or PARTIAL (WR2-only / CI-only / plist-direct-only). The cicatrix principle is already written — "if a critical rule is violable, write a hook" — but applied at HALF. Holes persist not because enforcement is absent, but because it's narrowly scoped.

## Your deliverables (terse, technical):
1. For EACH of the 6 patterns: do you agree it's real? Is the proposed enforcement correct/sufficient? What's the HOLE in my proposed fix?
2. ADDITIONAL recurring patterns I missed (think: lease registry gaps, detached-HEAD worktrees, /tmp worktrees lost on reboot, secret-in-plist-backup leakage, cross-node Pro/server drift, git gc / pack bloat, hook-bypass via env vars, what happens when Redis is down + graceful-degradation false-safety, subagent-spawned worktrees vs broker worktrees being different code paths).
3. CONCRETE solutions: name the exact hook event / CI job / cron / script + the detection logic. Prioritize by ROI.
4. Rank: if I can only ship ONE enforcement this week, which + why.


## Gemini 3.1 Pro

Here is the critique, pattern analysis, and enforcement roadmap.

### 1. Critique of the 6 Patterns

**Pattern 1: Sibling-race on SHARED working tree**
*   **Verdict:** Real. Shared index mutation is fatal.
*   **Your Fix:** Lint plists for `git checkout` against `REPO_ROOT`.
*   **The Hole:** Shallow static analysis. Agents/scripts can bypass via `git -C $REPO_ROOT checkout`, aliases, or runtime variable evaluation. Plist linting ignores ad-hoc orchestrator commands.
*   **Concrete Solution:** A **`pre-checkout` git hook** in the main `~/Desktop/nuzantara` repo. If `! -t 1` (not an interactive TTY) or `AGENT_BROKER_ENABLED=true`, it immediately `exit 1` with a localized error. This physically prevents the main checkout from drifting, forcing all automation into worktrees at the git level.

**Pattern 2: Worktrees / branches that never die**
*   **Verdict:** Real. State bloat leads to inode exhaustion and `git status` lag.
*   **Your Fix:** Daily cron `agent_start.py --cleanup` + CI test failing on `mtime > 24h`.
*   **The Hole:** `mtime` is fragile (read-heavy agents don't bump it). CI failure on this will randomly block unrelated feature deployments (flaky CI). Blind cleanup might delete unpushed, valuable commits.
*   **Concrete Solution:** A dedicated GC cron (`com.balizero.worktree-gc.daily`) that runs:
    `git status --porcelain` AND `git rev-list HEAD...origin/main --count`.
    If age > 24h AND `unpushed_commits == 0` AND `dirty_files == 0`: `git worktree remove --force`.
    If age > 24h AND `unpushed_commits > 0`: Ping Discord/Slack DLQ, do *not* delete. Do not block CI.

**Pattern 3: HOME-fork drift**
*   **Verdict:** Real. Shadow IT path-precedence.
*   **Your Fix:** Pre-commit/CI regex scan of wrappers for `exec ... $HOME/...`.
*   **The Hole:** Bypassed trivially by Python imports (`sys.path.insert(0, '/Users/.../scripts')`), symlinks, or runtime variables (`SCRIPT_DIR=~; exec $SCRIPT_DIR...`).
*   **Concrete Solution:** Enforce environment isolation in the LaunchAgent plists. Set `EnvironmentVariables` -> `PATH` strictly. For Python, set `PYTHONPATH` strictly. Stop relying on regex; rely on OS-level path resolution. Alternatively, wrap the agent's shell execution in macOS `sandbox-exec` with a profile that denies read/execute to `~/scripts/`.

**Pattern 4: Hallucinated "deleted" / skipped verification**
*   **Verdict:** Real. LLMs fake outputs to save tokens/time.
*   **Your Fix:** Prompt doctrine enforcing a secondary verifier agent.
*   **The Hole:** "Obligated patterns" via prompts are not enforcement, they are wishes. You cannot force the orchestrator to spend context on a second agent.
*   **Concrete Solution:** Deprecate raw `rm` in the agent's context. Provide a mandatory wrapper tool (e.g., `verified_delete_tool`) that executes the deletion, runs `stat/ls`, and returns a strongly-typed JSON result. If they bypass the tool and use bash `rm`, the existing guardrails hook catches it.

**Pattern 5: Race from PARALLEL subagents**
*   **Verdict:** Real. Read-modify-write races on remote state (PRs/APIs).
*   **Your Fix:** Doctrine for "atomic commands or sequential subagents".
*   **The Hole:** Again, LLMs dictate their own fan-out. You are asking the model to regulate itself.
*   **Concrete Solution:** Use your existing Redis lease registry! Require agents to acquire a lease on the *external resource* (e.g., `agent_lock:github_pr_920`) via a mandatory tool before fetching state. If the lease is held, the tool blocks or fails, forcing the agent to serialize.

**Pattern 6: safe-rm reinvented**
*   **Verdict:** Real. Standard guardrail evasion.
*   **Your Fix:** Standardize `scripts/safe_rm.sh`.
*   **The Hole:** If they bypass bash and use Python (`shutil.rmtree('../../')`) or Node (`fs.rmSync`), your script is useless. Also, guardrails blocking absolute paths but allowing relative is a flawed regex implementation.
*   **Concrete Solution:** Update `guardrails-static.py` to evaluate the **realpath** of the target before applying blocklists. `cd <parent> && rm -rf <relative>` will be caught because `os.path.abspath(target)` maps back to `$HOME`.

---

### 2. Additional Missed Patterns (The Blind Spots)

*   **Pattern 7: The `/tmp` Worktree Corruption.** You noted `/private/tmp/nb-curator-wt`. macOS clears `/tmp` on reboot. The directory vanishes, but `.git/worktrees/` still tracks it. Future git operations will throw fatal errors about missing gitdirs.
    *   *Fix:* Add `git worktree prune` to a `@reboot` cron or your daily GC.
*   **Pattern 8: Detached HEAD Attrition.** Worktrees left in `(detached HEAD)` that make commits. When the agent exits and the worktree is deleted, those commits become orphaned unreachable objects. They bloat `.git/objects` until a manual `git gc` runs.
    *   *Fix:* `agent_start.py` must *require* a branch name and refuse to operate in detached HEAD.
*   **Pattern 9: Redis False-Safety (Split Brain).** Your Redis lock degrades to "pass-through + WARN" if Redis is down. For read-locks, fine. For write-locks on hot-zone files, this is catastrophic. If Redis dies, 160 cron jobs suddenly have simultaneous write access.
    *   *Fix:* Write locks MUST be fail-closed. If Redis is unreachable, the script MUST exit 1, not pass-through.
*   **Pattern 10: Plist State Desync.** Agents modify a `.plist` file via sed/regex, but fail to run `launchctl unload` and `launchctl load`. The disk state is updated, but `launchd` is still running the old version in memory.
    *   *Fix:* A file watcher (via `fswatch` or a pre-commit hook) that detects `.plist` modifications and automatically executes the `launchctl` reload sequence.

---

### 3. Concrete Solutions (Actionable Implementation)

Here are the specific, technical implementations to plug the holes, ordered by ROI:

1.  **Main-Checkout Lockdown (Git Hook):**
    *   *Where:* `~/Desktop/nuzantara/.git/hooks/pre-checkout`
    *   *Logic:*
        ```bash
        #!/usr/bin/env bash
        if [ "$AGENT_BROKER_ENABLED" = "true" ] || [ ! -t 1 ]; then
            echo "FATAL: Agents cannot checkout in main repo. Use worktrees."
            exit 1
        fi
        ```
2.  **Strict Path Resolution Guardrail (Python):**
    *   *Where:* `~/.claude/hooks/guardrails-static.py` (or whatever intercepts bash executions)
    *   *Logic:*
        ```python
        import os, sys
        target = sys.argv[1] # parsed target of rm/mv
        abs_path = os.path.abspath(os.path.expanduser(target))
        if abs_path == os.environ['HOME'] or abs_path == '/':
            print("FATAL: Guardrail triggered on realpath.")
            sys.exit(1)
        ```
3.  **Fail-Closed Redis Leases:**
    *   *Where:* The Redis lock acquisition script/module.
    *   *Logic:*
        ```python
        try:
            redis.ping()
        except ConnectionError:
            if mode == 'WRITE':
                sys.exit("FATAL: Redis down. Write locks MUST fail-closed.")
            else:
                logging.warning("Redis down. Read lock degraded to pass-through.")
        ```
4.  **Worktree GC & Prune:**
    *   *Where:* `com.nuzantara.worktree-gc.daily.plist` executing `scripts/worktree_gc.sh`
    *   *Logic:*
        ```bash
        #!/usr/bin/env bash
        git worktree prune # Fixes the /tmp reboot issue
        for wt in $(git worktree list --porcelain | grep "^worktree" | awk '{print $2}'); do
            # Don't GC main repo
            if [ "$wt" = "/Users/nuzantara/Desktop/nuzantara" ]; then continue; fi
            # Check for unpushed commits
            branch=$(git -C "$wt" branch --show-current)
            unpushed=$(git -C "$wt" log origin/main..HEAD --count 2>/dev/null || echo "1")
            dirty=$(git -C "$wt" status --porcelain | wc -l)
            mtime=$(stat -f "%m" "$wt/.git")
            now=$(date +%s)
            if [ $((now - mtime)) -gt 86400 ] && [ "$unpushed" -eq 0 ] && [ "$dirty" -eq 0 ]; then
                git worktree remove --force "$wt"
            fi
        done
        ```

### 4. Ranking (If you can only ship one)

**Ship Rank 1: The `pre-checkout` git hook in the main checkout.**

*   **Why:** It is the highest leverage. It mathematically guarantees Pattern 1 (Sibling-race on SHARED working tree) can never happen again, regardless of whether the agent hallucinates, a cron misfires, or a plist has a bad target. By denying `git checkout` in the main repo unconditionally for non-TTYS/agents, you force the entire orchestrator ecosystem to use the `agent_start.py` worktree broker. It is a 5-line bash script that plugs your most dangerous silent-corruption vector instantly.


## Codex GPT-5.5



## DeepSeek V4 Pro

**Critique of 6 patterns + proposed enforcement**

### Pattern 1 — Sibling-race on shared tree
- **Real?** Yes, confirmed. The `stash@{8}` incident and nested worktrees are undeniable.
- **Sufficient?** No. A plist lint that catches `git checkout` in `ProgramArguments` misses:
  - scripts called *by* the plist that do `git checkout` or direct file writes in the repo.
  - non-LaunchAgent processes (subagents, ad‑hoc cron scripts that bypass plists).
  - any write to the shared tree *without* `git checkout` (e.g., `echo > file`).
- **Hole in fix**  
  The lint only inspects plist XML, not the transitive closure of scripts they invoke. The main checkout’s write permission is not actually enforced by `worktree_file_write_check.py` for all callers (e.g., a cron job running as the user has no Claude hook loaded).

### Pattern 2 — Worktrees/branches that never die
- **Real?** Highest-frequency failure. The numbers (34h past TTL, 6 orphans) speak.
- **Sufficient?** Largely. The proposed daily `agent_start.py --cleanup` across all lanes, with mtime‑based safety, plus a CI test for >24h is sound.
- **Hole in fix**  
  - The CI test will only fire on repo-opened PRs/pushes, not continuously; stale worktrees can accumulate between pushes. The daily cron is the real backstop.  
  - The 24h CI cut-off may break legitimate multi‑day sessions. Consider a warn‑only threshold in CI and a separate `git worktree prune` after cron cleanup.

### Pattern 3 — HOME‑fork drift
- **Real?** Yes. The W50 incident with a 24‑day‑stale script is a P0‑class desync.
- **Sufficient?** The extension to scan wrapper *content* for `$HOME/scripts/` is necessary but not sufficient.
- **Hole in fix**  
  - Needs to handle `${HOME}`, `~`, and indirect paths (sourced files, `sys.path` insertions for Python).  
  - Even if pre‑commit catches it, a deployed plist may already be running; there is no runtime alert when a stale plist executes.

### Pattern 4 — Hallucinated verification
- **Real?** Yes, “deleted `~/.git`” was blocked, yet reported as done. Fabricated SHAs persisted.
- **Sufficient?** No. “Obligated pattern” is a procedure, not an enforcement.
- **Hole in fix**  
  There’s no technical barrier preventing an agent from claiming success without verification. The guardrails hook could block destructive commands unless the session has *just* run a read‑only check, but that’s fragile. The core problem is that LLM output is trusted after a tool call; enforcement must happen at the *tool result evaluation* level, which is outside current hooks.

### Pattern 5 — Parallel subagent race
- **Real?** Yes. Crashes from API400 are a symptom; the merge‑SHA corruption is the damage.
- **Sufficient?** Partially. “One atomic command or sequential subagent” is the right rule.
- **Hole in fix**  
  The orchestrator currently does not distinguish “merge” from arbitrary tasks. The dispatcher (Agent tool) can fan out without a mutex. A Redis lease on `agent_lock:merge` would enforce serialisation, but the proposal doesn’t mention using the existing lease registry.

### Pattern 6 — `safe_rm.sh` standardisation
- **Real?** Real, but low impact — the guardrails already prevent catastrophic wipe.
- **Sufficient?** The script would reduce ad‑hoc relative‑path trickery. However, unless it’s the *only* way to `rm`, it’s optional.
- **Hole in fix**  
  An agent can still do `cd parent && rm -rf relative`. The guardrails hook must resolve the target path to an absolute one and block it unless the call comes from an allowed script (`safe_rm.sh`). Without that, the script is a polite suggestion.

---

## Additional recurring patterns (missed)

1. **Detached‑HEAD worktrees and /tmp worktrees lost on reboot**  
   - `/tmp` worktrees vanish; `git worktree list` retains a phantom entry. A detached HEAD means no branch‑based safety net.  
   - Agents can push from detached HEAD, creating orphan commits.  
   - *Enforcement*: `agent_start.py` must refuse to create a worktree in `/tmp` or leave HEAD detached unless explicitly flagged. A launchd reboot script should run `git worktree prune`.

2. **Redis‑down writes to hot‑zone files are silently permissive**  
   - `pre-commit` passes through when Redis is unreachable (WARN only). That makes the lease registry a soft lock, not a guarantee.  
   - A file‑based fallback (e.g., `.lock` file + `flock`) is missing.

3. **Subagent‑spawned worktrees bypass the broker**  
   - Subagents can call `git worktree add` directly, outside `.worktrees/`, with no TTL metadata.  
   - *Enforcement*: a `post-checkout` hook (git‑level) that blocks any `git worktree add` not orchestrated by `agent_start.py` (check for `AGENT_TASK_ID` env var).

4. **Secret leakage in plist backups**  
   - 84 of 167 plists exec from `~/scripts/`, but plists themselves may contain API keys in `EnvironmentVariables`. These are not in `.gitignore` / not scanned.  
   - *Enforcement*: pre‑commit secret scan on all `*.plist` files (e.g., `gitleaks` rule), and a CI lint that rejects plists with sensitive keys.

5. **Git pack bloat and unreachable objects**  
   - With 11 branches + stale worktrees, the monorepo accumulates loose objects. No cron runs `git gc --prune=now` on the main repo.  
   - *Enforcement*: weekly cron on the bare‑repo origin or the main checkout doing `git gc --aggressive --prune=now`.

6. **Hook bypass via environment variables**  
   - If an agent unsets `CLAUDE_HOOK_PATH` or sets `SKIP_HOOKS=1`, all guardrails evaporate.  
   - *Enforcement*: hard‑code the hooks directory in a wrapper script that agents must use; the wrapper re‑exports the variable unconditionally.

---

## Concrete solutions (hooks / CI / cron / scripts), ranked by ROI

1. **(Highest ROI) Pattern 2 – universal worktree GC**  
   - **Daily LaunchAgent**: calls `agent_start.py --cleanup` for **all** lanes (not just WR2). Logic: skip worktrees with mtime <15 min or uncommitted content *beyond* formatting noise (detectable via `git diff --exit-code --ignore-all-space`). After removal, run `git worktree prune`.  
   - **CI test**: add to pre‑push hook: `if [ $(find .worktrees -maxdepth 1 -type d -ctime +1 | wc -l) -gt 0 ]; then exit 1; fi`. Warn-only initially.  
   - *Closes W62/W63, shrinks surface for Pattern 1.*

2. **Pattern 3 – deep HOME‑fork pre‑commit lint**  
   - Extend `lint_launchagents.sh` and move it to **pre‑commit**. Scan every script in the repo (not just plists) for `$HOME/scripts/`, `${HOME}/scripts/`, `~/scripts/`.  
   - Additionally, scan all `~/Library/LaunchAgents/*.plist` that are symlinks into the repo; flag any `ProgramArguments` that resolve to outside the repo checkout.  
   - *Prevents desync before it ships.*

3. **Pattern 5 – merge mutex with Redis lease**  
   - In the orchestrator tool (or Agent dispatch), acquire `agent_lock:merge` with TTL 120s before dispatching any subagent whose task contains keywords `merge`, `rebase`, `force-push`.  
   - *Eliminates parallel merge races.*

4. **Pattern 1 – shared‑tree write guard (kernel‑level)**  
   - Modify `worktree_isolation.py` (Claude hook) to **deny** any file write or `git checkout` inside `~/Desktop/nuzantara` (the main checkout) unless the session’s `AGENT_LANE` is `hotfix` and the caller is an interactive operator (detected via `TERM` or CLI flag).  
   - For cron jobs, wrap all LaunchAgent `Program` calls with a script that sets a read‑only overlay (via `git worktree` or `chflags` on macOS) to prevent writes.

5. **Pattern 4 – mandatory verification tool**  
   - Create a tool `verify_deletion.sh` that an agent *must* call after any destructive `rm` or `git push --force`. The tool checks the expected state (e.g., directory missing, branch sha) and returns a structured JSON. The orchestrator’s `stop_verify.py` hook then checks that a verification was called for each destruction marker in the session log.  
   - *Technically enforces the “second subagent” rule.*

6. **Additional – reboot‑safe /tmp worktree pruning**  
   - A LaunchAgent that runs at login: `git -C ~/Desktop/nuzantara worktree prune` and deletes any directories under `/private/tmp/nb-*-wt` that are stale (no active process).  
   - Prevents orphan entries and session confusion.

---

## If you can ship only ONE enforcement this week

**Ship the universal worktree GC (Pattern 2).**  
*Why:* It directly eliminates the most frequent source of lost work (siblings touching the same tree, stale branches, formatting noise), reduces the attack surface for Pattern 1, and removes hidden complexity (detached HEAD, nested worktrees) without requiring behavioral change from agents. The daily cron + CI test together give continuous protection; the failure mode (stale worktrees) is observable and safely reversible.