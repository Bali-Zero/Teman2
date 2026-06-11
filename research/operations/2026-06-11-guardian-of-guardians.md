---
date: 2026-06-11
domain: compliance
client_case: internal — guardian-of-guardians armament audit (W64/W69/W70/W71 family)
sources:
  - "live commands run 2026-06-11 15:45–16:30 WITA on Pro (nuzantara@Nuzantara) + ssh mini, this session"
  - "gh api repos/Balizero1987/Teman2/branches/main/protection/required_status_checks"
  - ".claude/rules/cicatrix-scars.md (W64, W67, W69, W70, W71, W65)"
  - "~/.agent/decisions/state/*.json (verify_the_verifiers, mcp_integrity, cost_breaker_deadman)"
---

# Guardian of Guardians — armament audit 2026-06-11

**Method**: 6 read-only subagents (one per guardrail class), every DISARMED/LYING finding
independently re-verified by the orchestrator with a second tool call (W65 discipline:
even adversarial verifiers hallucinate). Every state below is backed by a command run
**this session**. Nothing was armed, booted out, rotated, or flipped — see Escalation queue.

**Headline**: the FASE-0 governance layer (W71) is genuinely ARMED and truthful — a real
recovery. The decay has moved: 2 live W67 crash-loops in the LaunchAgent fleet, 1 hook
family globally neutralized by a settings env var, the cascade wrapper structurally unable
to fall back on hard failure, and 6/8 governance workflows still run-but-don't-block, one
of them with an enforcement step that physically cannot fail while claiming "ENFORCING".

**Score: armed 24 / 35 verdict-items (69%)** — 7 DISARMED, 4 LYING/LOOPING (excludes
informational/UNKNOWN items).

## Master table

| # | Guardrail | Machine | State | Evidence command (run this session) | Remediation (NOT executed) |
|---|---|---|---|---|---|
| 1.1 | Cascade Tier 1 Claude OAuth | Pro | **ARMED** | `unset ANTHROPIC_API_KEY; claude auth status` → loggedIn, max, antonellosiano@gmail.com (claude 2.1.173) | none — update CLAUDE.md slot note (was kaiser…@) |
| 1.2 | Cascade Tier 2 agy/Gemini | Pro | **ARMED** | `echo … \| agy -p --print-timeout 1m` → `pong`, EXIT=0 (agy 1.0.7) | none — CLAUDE.md says v1.0.2, doc-stale |
| 1.3 | Cascade Tier 3 Codex GPT-5.5 | Pro | **ARMED** (noise) | `codex exec --sandbox read-only … 'pong'` → pong, EXIT=0; stderr shows dead embedded-MCP token `TokenRefreshFailed(invalid_grant)` | reauth/remove dead MCP in codex config (panel-hang cause, cf. 2026-06-06) |
| 1.4 | Cascade Tier 4 Ollama | Pro | **ARMED** | `ollama list` → qwen3.5:9b + qwen2.5vl:7b present | deepseek-r1:32b/gemma4:26b absent vs CLAUDE.md arsenal — doc or re-pull |
| 1.5 | Cascade **wrapper** regulatory-watcher-run.sh | Pro | **LYING** | `grep -n 'set -e' ~/scripts/regulatory-watcher-run.sh` → line 6 `set -euo pipefail`; lines 39/51/64/77 `EXIT=$?` are unreachable after a non-zero tier exit (empirically proven by subagent with zsh repro; log 2026-05-30 shows the silent-death signature). Fallback fires only on exit-0+quota-string; never exercised in prod | rewrite per-tier capture `if ! cmd; then` — code PR |
| 1.6 | Cascade Tier 1 | Mini | UNKNOWN | `ssh mini 'claude --version'` → 2.1.162; auth not live-verified; `~/.local/bin/claude` (wrapper's path) absent on Mini | run `claude auth status` in a Mini session |
| 1.7 | Cascade Tier 2 agy | Mini | **DISARMED** | `ssh mini 'command -v agy'` → AGY_NOT_FOUND; `/Users/nuzantara/.local/bin/agy: No such file` (re-verified by orchestrator) | install agy on Mini |
| 1.8 | Cascade Tier 3 codex | Mini | UNKNOWN | `ssh mini 'codex --version'` → 0.133.0 present, token_revoked trap not excluded without live ping | 1-token ping from a Mini session |
| 1.9 | Cascade Tier 4 Ollama | Mini | **ARMED** | `ssh mini 'ollama list'` → qwen3.5:9b + qwen2.5vl:7b present | none |
| 2.1 | com.nuzantara.verify-the-verifiers | Pro | **ARMED** | `launchctl print` → runs=170, last exit 0; signal `verify_the_verifiers.json` age 24s (cadence 600s): `status: ok, gates_armed: 20/21, warn: 1` (the 1 WARN = asyncpg lint, item 6.2) | none |
| 2.2 | com.nuzantara.mcp-integrity | Pro | **ARMED** | live re-run `verify_mcp_integrity.sh` → `YELLOW connected=12 failed=5`, EXIT=0; independent `claude mcp list` → 12 ✔ exact match; glyph re-verified by orchestrator: line 113 `grep -cE '✔ Connected\|✓ Connected'` (W71 bug fixed) | optional: ~15% of launchd ticks hit 60s timeout → honest YELLOW reachable=-1; consider retry-once |
| 2.3 | com.nuzantara.cost-breaker-deadman | Pro | **ARMED** | `launchctl print` → runs=170 exit 0; signal age 25s `status: ok, all fresh`; OBSERVED_FILES = the 3 governance signals (W71 §G5 closed); caught a REAL 2.7h stall 2026-06-10 11:41 | none — optionally investigate the 2026-06-10 stall cause |
| 2.4 | com.nuzantara.cost-breaker (hourly) | Pro | **ARMED** | runs=29 exit 0; ledger export `~/.agent/cost-ledger` refreshed 15:45 today; log 15:41: real spend → ALLOW verdicts per provider (W71 deferral SHIPPED) | none |
| 3.1 | verify-the-verifiers.yml required check | GitHub (from Pro) | **ARMED** | `gh api …/required_status_checks` → context present; sentinel pattern (no top-level paths:); last 5 runs success | none |
| 3.2 | p1s2 "Canary self-test + incremental mutation" | GitHub | **ARMED** | required context present; sentinel inside; last 5 success | none |
| 3.3 | hot-zone-pr-gate.yml | GitHub | **DISARMED + 1 step LYING** | NOT in required contexts (re-verified verbatim list, 11 contexts); CODEOWNERS step `continue-on-error: false` (line 156) **but** body ends `echo "Phase 2a monitor-mode…"; exit 0` (re-verified, lines ~183-186) — claims ENFORCING since 2026-06-07, cannot fail | remove `exit 0` (code PR); then add to required checks — see queue |
| 3.4 | p3-sandbox-gates.yml | GitHub | **DISARMED** | paths-filtered, NO sentinel, 3 runs ever (last 2026-06-07, 1 failure), not required | sentinel-ize FIRST (paths-trap), then require |
| 3.5 | p6-federation-parallelize.yml | GitHub | **DISARMED (red 5/5)** | `gh run list` → last 5 ALL failure incl. today; root cause `ModuleNotFoundError: No module named 'dotenv'` (workflow installs only pytest) | add `python-dotenv` to workflow pip install (code PR), then sentinel-ize, then require |
| 3.6 | p7-lesson-harvester.yml | GitHub | **DISARMED** | green when triggered (5 success) but paths-filtered, no sentinel, not required | sentinel-ize, then require |
| 3.7 | p8-brand-api.yml | GitHub | **DISARMED** | runs exist (1 failure 2026-06-11 on sancho branch, recovered), paths-filtered, no sentinel, not required | sentinel-ize, then require |
| 3.8 | p9-cost-breaker.yml | GitHub | **DISARMED** | green-stable but paths-filtered, no sentinel, not required | sentinel-ize, then require |
| 4.1 | com.balizero.indexing-sweep.daily | Pro | **LOOPING (live W67)** | re-verified: `launchctl print` runs=9551 (subagent saw 9528→9539 → CLIMBING); plist KeepAlive=true + StartCalendarInterval + one-shot wrapper script; log `daily_indexing_sweep.log` → **10,736 "started" entries today** (~every 5.4s), 175k cumulative "Telegram sent" lines | set KeepAlive=false or delete (twin `com.nuzantara.daily-indexing-sweep` already covers 01:00) — see queue |
| 4.2 | com.nuzantara.launchagent-state-bridge | Pro | **LOOPING (live W67)** | re-verified: runs=10,027 (subagent saw 10,000→10,014 → CLIMBING ~1/20s); KeepAlive=true + RunAtLoad=true, script is one-shot `raise SystemExit(main())` | replace KeepAlive with StartInterval — see queue |
| 4.3 | com.balizero.wa-mirror-launcher | Pro | **ARMED** | real `while true` supervisor; runs=1, PID 1686 stable across 330s snapshots (W67 antibody holding) | none |
| 4.4 | WR2 Pipeline-A plists (carousel-dispatcher, telegram-gate, supervisor) | Pro | **LYING-by-presence** | KeepAlive=true on disk, NOT loaded (re-verified: launchctl grep → only supervisor-watchdog matches); consistent with F23 deliberate bootout. BUT `wr2.supervisor-watchdog` IS loaded (PID 11622, last exit 74) guarding a supervisor that isn't loaded | delete the 3 dead plists + decide watchdog fate |
| 4.5 | com.nuzantara.daily-gsc-indexing-sweep | Pro+Mini | **LYING + active-active** | re-verified: `plutil -lint` FAILS ("unknown ampersand-escape line 11" — raw `2>&1` in XML) yet loaded from cached config (2026-04-29 gotcha class → dies silently at next reboot); `ssh mini launchctl list | grep gsc` → loaded on Mini too (runs=4) → duplicate GSC submissions | fix XML escape + pick one owner (memory says Mini) — see queue |
| 4.6 | post-publish-poller / automap-watchdog | Pro | **DISARMED** | RunAtLoad-only, runs=1, state not-running → ran once at login, dead since (poller named critical in 2026-04-29 scar) | classify: add KeepAlive or StartInterval |
| 4.7 | mata-garuda 13 active-active labels | Mini | **ARMED/closed** | `ssh mini launchctl list` → only 7 project labels, NONE of the 13 dup labels, no wa-mirror (W67c holding) | none |
| 5.1 | stop_verify.py | Pro | **ARMED** (interactive) | wired settings.json:474; **STOP_VERIFY_ALLOW_DIRTY absent from settings.json** (re-verified by grep — the 2026-06-06 line 472 bypass is GONE); designed cron-skip lines 53-55 (rewritten 2026-06-09) | optional interactive canary to prove exit-2 branch |
| 5.2 | seam_verify.py | Pro | **ARMED** (advisory-by-contract) | exists 7959B, wired settings.json:492; always-exit-0 is its documented contract (2026-06-06 "file missing" remediated) | none |
| 5.3 | guardrails chain (client+daemon+static) | Pro | **ARMED — proven blocking** | daemon PID 1749 alive; socket probe `DROP TABLE` → BLOCK; end-to-end client probe destructive → exit 2, benign → exit 0; W69 "guardrails_static not registered" SUPERSEDED (wired as Tier-2 inside guardrails-client.sh, delivered the BLOCK) | minor: client TIMEOUT_SEC=2 sometimes shunts to static fallback |
| 5.4 | worktree-isolation triple (worktree_isolation.py + file_write_check + workspace_setup) | Pro | **LYING (wired-but-neutralized)** | re-verified: `~/.claude/settings.json:14 "AGENT_WORKTREE_ENFORCEMENT": "false"` + this session's own env = false; hooks healthy (exit 2 with =true, exit 0 with current env, empirically probed) | remove/flip settings line 14 — **operator decision** (may be a deliberate toggle) |
| 5.5 | pre-commit lease-check | Pro | **ARMED** | lives in `.husky/pre-commit:49-70` (core.hooksPath → .husky, applies in worktrees); `AGENT_LEASE_ENFORCEMENT` unset; `redis-cli ping` → PONG (not in degrade) | informational: shadowed `.git/hooks/pre-commit` duplicates |
| 5.6 | dispatch_nudge / repomap inject / orchestrate_gate / stadio_zero_nudge | Pro | **ARMED** | all wired, scripts exist+exec, kill-switch env vars unset; repomap age 682s (<30min, injecting) | none |
| 6.1 | asyncpg lint — codebase compliance (W34/W64) | Pro | **ARMED/HEALED** | re-run by orchestrator: `python3 scripts/lint_asyncpg_except_completeness.py` → **REAL_LINT_EXIT=0** isolated, zero violations; `wr2_canva_lease_watchdog.py:40` now includes `asyncpg.InterfaceError` (W64 wound healed) | none |
| 6.2 | asyncpg lint — CI/pre-commit wiring (W35 deferral) | Pro/GitHub | **DISARMED** | re-verified: `grep -rn lint_asyncpg .github/workflows/ .husky/pre-commit` → exit 1, zero hits; `verify_the_verifiers_gates.yaml:181-188` self-documents `consumer: null` → the standing 1 WARN in the H24 meta-verifier (observable, but WARN never blocks a merge) | ship `asyncpg-lint.yml` blocking on PR + flip gate `consumer:` |

## The 4 known-decay points, re-checked by name

| Decay point | 2026-05/06 state | Empirical state TODAY (command run this session) |
|---|---|---|
| Cascade depth | 2-deep (2026-05-24) | **4 of 4 tiers individually live on Pro** — but wrapper degrades to 1-deep on any hard tier-1 failure (`set -euo pipefail` line 6 vs `EXIT=$?` captures, never-exercised fallback). Mini = 2 of 4 confirmed |
| mcp-integrity glyph (W71) | counted ✓ only → false connected=0 | **FIXED**: line 113 greps `'✔ Connected\|✓ Connected'`; live run connected=12 = exact match with independent `claude mcp list` count |
| Required checks on main (W69 BUCO #1) | 9 historical checks, zero P* | **11 contexts** — `verify-the-verifiers` + `Canary self-test + incremental mutation` added with sentinel (partially closed); 6 governance workflows still run-but-don't-block; **blocking: 2 of 8** |
| stop_verify ALLOW_DIRTY | `=1` at settings.json:472 (2026-06-06) | **REMOVED** — grep finds no STOP_VERIFY_ALLOW_DIRTY anywhere in settings/env/rc; hook re-armed for interactive sessions with a designed cron-skip |

## DISARMED/LYING ranked by blast radius

1. **P1 — indexing-sweep.daily crash-loop (4.1)**: 10,736 runs today, one every ~5.4s, each logging a Telegram send — API quota burn, GSC submission spam risk, CPU/log churn, and a perfect W67 signature (KeepAlive=true + one-shot). The twin `com.nuzantara.daily-indexing-sweep` already does this job at 01:00.
2. **P1 — worktree-isolation neutralized globally (5.4)**: `AGENT_WORKTREE_ENFORCEMENT=false` in settings env means EVERY session (incl. parallel agents) inherits the bypass → re-opens the sibling-race / untracked-loss scar class (2026-04-29 ×2). May be a deliberate operator toggle — needs explicit confirmation, not silent re-arm.
3. **P1 — cascade wrapper `set -e` (1.5)**: the 4-tier resilience story is structurally 1-deep for hard failures; every cron that uses this wrapper pattern dies silently exactly when Tier 1 has a non-zero exit (the scenario the cascade exists for). Log already shows one silent death (2026-05-30).
4. **P1 — hot-zone CODEOWNERS step LYING (3.3)**: header + scar W69 claim "ENFORCING since 2026-06-07", `continue-on-error: false` is set, but the script body still ends `exit 0` on the non-owner branch — a CODEOWNERS modification by a compromised/rogue branch passes the gate. The flip changed the YAML attribute, not the behavior.
5. **P2 — p6 chronic red (3.5)**: 5/5 failures incl. today, trivial cause (`python-dotenv` missing) — a gate that is always red trains everyone to ignore it.
6. **P2 — launchagent-state-bridge loop (4.2)**: 10k respawns, ~3/min, log churn; lower harm than 4.1 but same W67 class.
7. **P2 — 6 governance workflows run-but-don't-block (3.3-3.8)**: W69 BUCO #1 remains ~75% open; every one is paths-filtered without sentinel → naive `gh api` arming would freeze ALL PRs.
8. **P2 — asyncpg lint no consumer (6.2)**: a `120078999`-class sibling-fix regression would land unguarded; mitigated by the H24 WARN (observable decay — the system works).
9. **P3 — agy absent on Mini (1.7)**: Mini cascade = 2-deep; matters only for Mini-resident cron.
10. **P3 — daily-gsc-indexing-sweep (4.5)**: lint-broken plist dies at next reboot (silent), and Pro+Mini active-active double-submits.
11. **P3 — post-publish-poller / automap-watchdog dead after login (4.6)**; **WR2 orphan watchdog exit 74 + 3 dead plists on disk (4.4)**; **codex embedded dead MCP token (1.3)** — hygiene tier.

## Escalation queue — exact commands, **NOT RUN**, Antonello decides

```bash
# E1 (P1) — stop the indexing-sweep crash-loop (pick A: kill the redundant twin)
launchctl bootout gui/501/com.balizero.indexing-sweep.daily
rm ~/Library/LaunchAgents/com.balizero.indexing-sweep.daily.plist   # twin com.nuzantara.daily-indexing-sweep keeps the 01:00 job
# (or B: edit plist KeepAlive=false + bootout/bootstrap)

# E2 (P1) — re-arm worktree isolation (CONFIRM INTENT FIRST — may be deliberate)
# edit ~/.claude/settings.json line 14: "AGENT_WORKTREE_ENFORCEMENT": "false" -> "true" (or delete the line)

# E3 (P1) — cascade wrapper: code PR replacing `set -euo pipefail` + bare EXIT=$? with per-tier
#   `if ! out=$(tier_cmd); then EXIT=$?; else EXIT=0; fi` capture in ~/scripts/regulatory-watcher-run.sh
#   (file lives in HOME, not repo — W50-class fork: also sync any repo copy)

# E4 (P1) — hot-zone CODEOWNERS: code PR removing the `exit 0` in the non-owner branch of
#   .github/workflows/hot-zone-pr-gate.yml (~line 185), THEN (rename job out of "(monitor-mode)") and:
gh api -X POST repos/Balizero1987/Teman2/branches/main/protection/required_status_checks/contexts \
  --input - <<< '["Hot-zone enforcement (monitor-mode)"]'   # paths-trap-SAFE (no paths filter) but rename first

# E5 (P2) — p6 red: code PR adding python-dotenv to the workflow's pip install line
# E6 (P2) — sentinel-ize p3/p7/p8/p9 (copy the p1s2 "Did relevant paths change?" pattern), then per-workflow:
#   gh api -X POST .../required_status_checks/contexts --input - <<< '["<check name>"]'
#   ⚠️ NEVER add a paths:-filtered check as required without the sentinel — pending-forever blocks ALL PRs (W69 trap)

# E7 (P2) — state-bridge: edit plist com.nuzantara.launchagent-state-bridge: drop KeepAlive, add StartInterval 300
# E8 (P2) — asyncpg lint consumer: new .github/workflows/asyncpg-lint.yml (blocking) + flip
#   scripts/verify_the_verifiers_gates.yaml consumer: null -> the workflow path
# E9 (P3) — Mini: install agy; run `claude auth status` + codex 1-token ping in a Mini session
# E10 (P3) — GSC sweep: fix `2>&1` -> `2&gt;&amp;1` in com.nuzantara.daily-gsc-indexing-sweep.plist (Pro),
#   then bootout the Pro copy (memory says Mini owns it)
# E11 (P3) — delete 3 dead WR2 Pipeline-A plists; bootout com.balizero.wr2.supervisor-watchdog (guards nothing, exit 74)
# E12 (P3) — classify post-publish-poller + automap-watchdog (KeepAlive or StartInterval)
# E13 (P3) — codex: remove/reauth the dead embedded MCP server token (invalid_grant) to kill panel hangs
```

## Recoveries since the scars were written (give the antibodies their due)

- FASE-0 trio (W71) all ARMED, fresh, truthful; deadman caught a real 2.7h stall on 2026-06-10.
- cost-breaker real-ledger bridge SHIPPED (was the W71 deferral) — real spend, real verdicts, hourly.
- W64 wound healed (`wr2_canva_lease_watchdog.py:40` has InterfaceError) and codebase lint-clean (exit 0).
- stop_verify ALLOW_DIRTY bypass removed; seam_verify shipped; guardrails_static proven blocking — all three 2026-06-06 disarmaments closed.
- W69 BUCO #1 partially closed: 2 governance checks required with proper sentinels.
- wa-mirror supervisor (W67) and W67c Mini bootout both holding; mata-garuda active-active closed on Mini.
- mcp-integrity glyph bug (W71) fixed and verified against an independent count.
