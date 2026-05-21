---
date: 2026-05-21
domain: operations
title: FINAL Orchestration Regression Fix Plan — 3-panel reviewed (DS + Gemini + GPT-5.5)
basis_dossiers: 5
total_specs: 31 (was 23 → +5 DS missing → -1 R3 killed → +2 Gemini new → +1 GPT-5.5 = 30 file + INDEX)
total_effort_estimate: 13-17 hours full implementation
status: DRAFT FINAL — all 3 panel findings integrated 2026-05-21 22:50 WITA
panel_reviews:
  - deepseek-v4-pro 2026-05-21 21:49 → APPROVE_WITH_FIXES, 3 blockers, 12 concerns
  - gemini-31-pro-deep-think 2026-05-21 22:29 → DS_MISSED_CRITICAL, 3 NEW blockers, 16 concerns, 2 NEW specs
  - gpt55-xhigh-codex 2026-05-21 22:35 → THIRD_PASS_FOUND_GAPS, 5 NEW blockers, 7 code review findings
panel_totals:
  blockers_unique: 11
  concerns_unique: 40
  new_specs_recommended: 5 (T-1, G1, G2, G3, G4 from DS) + 2 (T-2, G0 from Gemini)
  specs_killed: 1 (R3 LiteLLM by DS)
---

# 00 — Master spec index (FINAL — 3 panel reviewed)

## Panel review history

| Panel                     | Time  | Verdict               | Blockers      | Concerns        | New specs                    |
| ------------------------- | ----- | --------------------- | ------------- | --------------- | ---------------------------- |
| DeepSeek V4 Pro           | 21:49 | APPROVE_WITH_FIXES    | 3             | 12              | T-1, G1, G2, G3, G4          |
| Gemini 3.1 Pro Deep Think | 22:29 | DS_MISSED_CRITICAL    | +3            | +16             | T-2, G0                      |
| GPT-5.5 xhigh (Codex)     | 22:35 | THIRD_PASS_FOUND_GAPS | +5            | +12 code review | (none new, deep refinements) |
| **Cumulative**            |       |                       | **11 unique** | **40 unique**   | **7 new**                    |

All findings integrated 2026-05-21 22:30-22:50 WITA. Decision memos:

- `decision_panel_review_outcome_2026_05_21.md` (DS)
- `decision_panel_review_gemini31_2026_05_21.md` (Gemini)
- `decision_panel_review_gpt55_2026_05_21.md` (GPT-5.5)

Raw review JSONs:

- `specs/_panel-review-deepseek-v4pro.json`
- `specs/_panel-review-gemini-31pro-deep-think.json`
- `specs/_panel-review-gpt55-xhigh.json`

## Empirical state (verified 2026-05-21)

| Item                                   | Stato                                                               | Source                       |
| -------------------------------------- | ------------------------------------------------------------------- | ---------------------------- |
| **nuzantara-mcp DNS**                  | ❌ FAIL — primary MCP unreachable (T0.2 P0)                         | empirical SessionStart       |
| **Orphaned memory files**              | ❌ 22+ orphans (T0.1)                                               | regression-fix-19            |
| Pre-orchestration-fix backup           | ❌ NOT YET (T-1 P0 mandatory)                                       | DS panel                     |
| Executor state manifest                | ❌ NOT YET (T-2 P0 mandatory)                                       | Gemini panel                 |
| External state rollback script         | ❌ NOT YET (G0 P0 disaster recovery)                                | Gemini + GPT-5.5 panels      |
| SessionStart hook count                | 13 commands (target 4-6 in T3.5)                                    | empirical                    |
| MCP servers active                     | 8 in `.mcp.json`                                                    | empirical                    |
| MOS populated                          | ✅ 2516 memorie / 45.435 sessioni in `~/.claude/memory.db` (10.9MB) | empirical                    |
| Within-session subagent dispatch decay | ❌ 8→0 dopo 500 righe; 0 in 3/4 sessioni dense                      | orchestration-21             |
| Superpowers (obra) installed           | ✅ visibile SessionStart                                            | empirical                    |
| CLAUDE.md project size                 | 29.6KB (target 8KB, T2.7 Wave 4)                                    | empirical                    |
| ENABLE_TOOL_SEARCH                     | auto:5 (target auto:10, T3.6)                                       | reference_optimization_audit |

## FINAL action ladder

### ⚠️ PRE-EXECUTION (MANDATORY) — ~40 min

| ID      | File                                          | Cosa                                                                                                 | Effort | Priority     |
| ------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------ | ------------ |
| **T-1** | `T-1-pre-execution-global-backup.md`          | Snapshot SQLite quiesced + extended scope (Keychain/LaunchAgents/MCP/zshenv/npm inventory) + git tag | 15 min | P0 MANDATORY |
| **T-2** | `T-2-executor-state-manifest.md` (NEW Gemini) | Persistent JSON exec tracker survive compaction/crash                                                | 30 min | P0 MANDATORY |

### Wave 0 — Critical P0 unblock (≤2h)

| ID       | File                                                                                          | Cosa                                               | Effort    | Priority |
| -------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------- | --------- | -------- |
| **T0.1** | `T0.1-orphan-memory-triage.md` (+dry-run gate per DS)                                         | Triage 22+ orphan files                            | 30 min    | P0       |
| **T0.2** | `T0.2-fix-nuzantara-mcp-dns.md` (was T3.1, promoted by DS)                                    | Fix nuzantara-mcp DNS                              | 30-45 min | P0       |
| **T2.5** | `T2.5-precompact-mnemos-hook.md` (PROMOTED Wave 0 by Gemini B3, + GPT-5.5 B5 anti-halluc fix) | PreCompact handoff structured tool_use/tool_result | 60-75 min | P0       |

**🚧 G1 GATE** — `~/scripts/gate-validate-wave.sh 0` MUST PASS

### Wave 1 — Orchestration regression fix (≤90 min)

| ID       | File                                                                       | Cosa                                                                | Effort          | Priority |
| -------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------- | --------------- | -------- |
| **T1.1** | `T1.1-dispatch-nudge-hook.md`                                              | UserPromptSubmit nudge >500 righe                                   | 15 min          | P0       |
| **T1.2** | `T1.2-guardrails-hook.md` (DS extension + GPT-5.5 B3 SQL/MultiEdit/bypass) | PreToolUse Bash+MCP+Edit/Write/MultiEdit + base64/python -c blocked | 35 min (was 25) | P0       |
| **T1.3** | `T1.3-feedback-orchestration-first-memory.md`                              | Memory rule orchestration-first                                     | 5 min           | P1       |
| **T1.4** | `T1.4-karpathy-discipline-skill.md`                                        | 4 principi Karpathy                                                 | 10 min          | P1       |
| **T1.5** | `T1.5-alzheimer-diagnose-script.md`                                        | Telegram alert MEMORY > 25KB                                        | 10 min          | P1       |

**🚧 G1 GATE** — MUST PASS

### Wave 2 — Install MCP + hooks (~2h)

| ID       | File                          | Cosa                                              | Effort          | Priority |
| -------- | ----------------------------- | ------------------------------------------------- | --------------- | -------- |
| **T2.1** | `T2.1-superpowers-install.md` | Verify Superpowers (likely already done)          | 15 min          | P1       |
| **T2.2** | `T2.2-playwright-mcp.md`      | Install Playwright MCP (+ version pin per Gemini) | 20 min (was 15) | P1       |
| **T2.3** | `T2.3-github-mcp.md`          | Install GitHub MCP (+ PAT scope review)           | 25 min (was 20) | P1       |
| **T2.4** | `T2.4-vercel-mcp.md`          | Install Vercel MCP HTTP                           | 10 min          | P1       |
| **T2.6** | `T2.6-stop-verify-hook.md`    | Stop hook dirty worktree block                    | 15 min          | P2       |

**🚧 G1 GATE** — MUST PASS

### Wave 3 — Structural (~3-5h)

| ID       | File                                                                                         | Cosa                                                               | Effort                      | Priority |
| -------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------- | -------- |
| **T3.2** | `T3.2-postgres-qdrant-mcp.md` (DS read-only + GPT-5.5 B4 password leak fix + wrapper script) | Postgres MCP scoped wrapper + read-only role + 8 enforcement tests | 60 min (was 45)             | P2       |
| **T3.3** | `T3.3-6-named-subagent-lanes.md` (+ DS enforcement test)                                     | 6 lane aggregators                                                 | 90 min                      | P2       |
| **T3.4** | `T3.4-custom-slash-commands.md`                                                              | /verify, /panel, /research, /scar, /resume, /dispatch-stat         | 60 min                      | P3       |
| **T3.5** | `T3.5-session-start-consolidation.md` (+ DS compare checklist)                               | SessionStart 13→6                                                  | 60 min                      | P2       |
| **T3.6** | `T3.6-tool-search-auto-10.md`                                                                | A/B `auto:5` vs `auto:10`                                          | 20 min spec + 3 session A/B | P3       |

**🚧 G1 GATE** — MUST PASS

### Wave 4 — CLAUDE.md refactor (moved from Wave 2 by DS, ~2-3h)

| ID       | File                                                     | Cosa                          | Effort      | Priority |
| -------- | -------------------------------------------------------- | ----------------------------- | ----------- | -------- |
| **T2.7** | `T2.7-claude-md-project-refactor.md` (DS effort revised) | CLAUDE.md 29.6KB → 8KB router | 120-180 min | P1       |

**🚧 G2 FINAL VALIDATION** — `~/scripts/validate-orchestration-fix.sh` (30 min)

### Research / R&D — opzionale

| ID         | File                                                      | Cosa                                                             | Effort | Priority |
| ---------- | --------------------------------------------------------- | ---------------------------------------------------------------- | ------ | -------- |
| **R1**     | `R1-claude-mem-3layer.md`                                 | claude-mem evaluation (+ Gemini hard-rule check embedding model) | 60 min | P4       |
| **R2**     | `R2-exa-mcp-oauth.md`                                     | Exa MCP OAuth                                                    | 10 min | P3       |
| ~~**R3**~~ | `R3-KILLED-litellm-gateway.md`                            | ❌ KILLED by DS panel                                            | N/A    | KILLED   |
| **R4**     | `R4-experimental-agent-teams.md` (deprioritized P5 by DS) | Agent teams pilot (only after 2 weeks T1.x stability)            | 60 min | P5       |

### Gates (5 specs)

| ID     | File                                                                            | Cosa                                                                | Effort               | Priority |
| ------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------- | -------- |
| **G0** | `G0-external-state-rollback.md` (NEW Gemini + GPT-5.5)                          | Teardown MCP registry/npm/Keychain/Postgres role                    | 30 min + 10-20/run   | P0       |
| **G1** | `G1-inter-wave-validation-gate.md`                                              | Inter-wave validation (×4 gates)                                    | 30 min + 5/wave      | P0       |
| **G2** | `G2-post-fix-validation-suite.md`                                               | Post-fix 6-test validation                                          | 60 min + 30/run      | P0       |
| **G3** | `G3-global-rollback.md` (DS + Gemini B1 SQLite kill + GPT-5.5 scope + pipefail) | Single-cmd global rollback with WAL safety + external state pointer | 30 min + 5-10/run    | P0       |
| **G4** | `G4-continuous-monitoring.md` (Gemini B2 plist secret fix)                      | Weekly cron orchestration health, no plist secret                   | 30 min + 5 auto/week | P2       |

## Dipendenze (FINAL)

```
T-1 (backup) ──► T-2 (state manifest) ──► G1.0 (gate Wave 0)

Wave 0:
  T0.1 (orphan) + T0.2 (DNS) + T2.5 (PreCompact PROMOTED)  ──► G1.0 ──► Wave 1

Wave 1:
  T1.1 + T1.2 + T1.3 + T1.4 + T1.5  ──► G1.1 ──► Wave 2

Wave 2:
  T2.1 + T2.2 + T2.3 + T2.4 + T2.6  ──► G1.2 ──► Wave 3

Wave 3:
  T3.2 + T3.3 + T3.4 + T3.5 + T3.6  ──► G1.3 ──► Wave 4

Wave 4:
  T2.7 (CLAUDE.md)  ──► G2 (final validation)

G0 + G3 = available disaster recovery anytime
G4 = scheduled cron weekly post-completion
T-2 manifest updated by each Wave executor
```

## Total effort (FINAL)

| Phase                 | Effort  | Cumulative |
| --------------------- | ------- | ---------- |
| T-1 + T-2             | 45 min  | 45 min     |
| Wave 0 (3 specs)      | 2h 5min | ~3h        |
| Wave 1 (5 specs)      | 75 min  | ~4h        |
| Wave 2 (5 specs)      | ~85 min | ~5h 30min  |
| Wave 3 (5 specs)      | ~4h     | ~9h 30min  |
| Wave 4 (T2.7)         | 2-3h    | ~12h       |
| G2 final              | 30 min  | ~12h 30min |
| **R-series optional** | +2h     | +2h        |

Total: **13-17 hours** (was 8-10h, 30-50% increase per cumulative panel findings).

## Final integration status

| Panel finding type     | Count                                                                                    | Integration status                                                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| DS blockers            | 3                                                                                        | ✅ All integrated                                                                                                             |
| DS missing specs       | 5 (T-1, G1, G2, G3, G4)                                                                  | ✅ All created                                                                                                                |
| DS effort revisions    | 2 (T2.5, T2.7)                                                                           | ✅ Applied                                                                                                                    |
| DS killed              | 1 (R3 LiteLLM)                                                                           | ✅ Renamed `R3-KILLED-*`                                                                                                      |
| Gemini blockers        | 3 (G3 WAL, G4 plist, Wave compaction)                                                    | ✅ All fixed in disk                                                                                                          |
| Gemini security        | 3 (supply chain, ghost access, guardrail bypass)                                         | ✅ Patterns added T1.2                                                                                                        |
| Gemini hallucination   | 3 (predictable JSON, /verify gaming, script source)                                      | ⚠️ Partial (T3.4 documented, /verify accepted as gameable)                                                                    |
| Gemini hard rule edges | 2 (R1 embedding, T2.2 Playwright bin)                                                    | ⚠️ Documented Open Questions                                                                                                  |
| Gemini new specs       | 2 (T-2, G0)                                                                              | ✅ Both created                                                                                                               |
| GPT-5.5 blockers       | 5 (T-1 WAL/SHM, T-1 scope, T1.2 SQL/MCP/MultiEdit, T3.2 password leak, T2.5 anti-halluc) | ✅ All fixed                                                                                                                  |
| GPT-5.5 code review    | 7 (line-number bugs)                                                                     | ✅ All addressed                                                                                                              |
| GPT-5.5 alternatives   | 4 (policy engine, quiesced snapshot, scoped wrapper, structured parser)                  | ⚠️ Adopted scoped wrapper (T3.2) + structured parser (T2.5), policy engine deferred (P3 R&D), quiesced snapshot adopted (T-1) |

## File list (FINAL)

```
specs/
├── 00-INDEX.md                                              (THIS FILE)
├── T-1-pre-execution-global-backup.md                       (DS new + GPT-5.5 SQLite/scope/pipefail fixes)
├── T-2-executor-state-manifest.md                           (NEW Gemini)
├── T0.1-orphan-memory-triage.md                             (+DS dry-run gate)
├── T0.2-fix-nuzantara-mcp-dns.md                            (was T3.1, promoted DS)
├── T1.1-dispatch-nudge-hook.md
├── T1.2-guardrails-hook.md                                  (DS MCP+Edit + GPT-5.5 SQL/MultiEdit/bypass)
├── T1.3-feedback-orchestration-first-memory.md
├── T1.4-karpathy-discipline-skill.md
├── T1.5-alzheimer-diagnose-script.md
├── T2.1-superpowers-install.md
├── T2.2-playwright-mcp.md
├── T2.3-github-mcp.md
├── T2.4-vercel-mcp.md
├── T2.5-precompact-mnemos-hook.md                           (PROMOTED Wave 0 Gemini + GPT-5.5 anti-halluc)
├── T2.6-stop-verify-hook.md
├── T2.7-claude-md-project-refactor.md                       (Wave 4 DS)
├── T3.2-postgres-qdrant-mcp.md                              (DS read-only + GPT-5.5 password leak wrapper)
├── T3.3-6-named-subagent-lanes.md                           (+DS enforcement test)
├── T3.4-custom-slash-commands.md
├── T3.5-session-start-consolidation.md                      (+DS compare checklist)
├── T3.6-tool-search-auto-10.md
├── R1-claude-mem-3layer.md
├── R2-exa-mcp-oauth.md
├── R3-KILLED-litellm-gateway.md                             (KILLED DS)
├── R4-experimental-agent-teams.md                           (P5 DS)
├── G0-external-state-rollback.md                            (NEW Gemini + GPT-5.5)
├── G1-inter-wave-validation-gate.md                         (NEW DS)
├── G2-post-fix-validation-suite.md                          (NEW DS)
├── G3-global-rollback.md                                    (DS + Gemini WAL kill + GPT-5.5 scope + pipefail)
├── G4-continuous-monitoring.md                              (DS + Gemini plist secret fix)
└── _panel-review-{deepseek-v4pro,gemini-31pro-deep-think,gpt55-xhigh}.json  (3 raw reviews)
```

**31 spec files** + INDEX + 3 panel JSON = 35 files total. All 3-panel findings integrated.

## Sintesi 1 frase

31 spec finali post-3-panel-review (DS+Gemini+GPT-5.5): T-1 + T-2 pre-execution mandatori, Wave 0 (T0.1+T0.2+T2.5 promoted) → G1 gate → Wave 1 (5 hooks) → G1 → Wave 2 (5 installs) → G1 → Wave 3 (5 structurals) → G1 → Wave 4 (CLAUDE.md refactor) → G2 final validation. G0+G3 disaster recovery. R3 LiteLLM killed. Total 13-17h effort. 11 unique blockers + 40 concerns integrated.
