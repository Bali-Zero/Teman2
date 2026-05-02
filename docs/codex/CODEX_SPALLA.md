# CODEX_SPALLA — research log + capability matrix + scenarios

**Date:** 2026-05-03
**Status:** living document (updated as we learn)
**Sources of truth:**

- Design spec: `docs/superpowers/specs/2026-05-03-codex-spalla-design.md`
- Architecture decision: `docs/decisions/2026-05-03-codex-spalla-architecture.md`

## 1. State of the world (2026-05-03, verified)

| Aspect                        | Reality                                                                                                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Codex CLI version (Pro)       | `codex-cli 0.124.0` — official current. Prompt mentioned 0.128 (April 30 release); verify on next `brew upgrade`.                                                            |
| Auth                          | ChatGPT OAuth ("Logged in using ChatGPT"). Plus tier active.                                                                                                                 |
| Model                         | `gpt-5.5` + `model_reasoning_effort=xhigh` (already on the upgraded model — prompt assumed GPT-5.4).                                                                         |
| MCP servers                   | 7 enabled: nuzantara-mcp, nuzantara-mcp-advanced, postgres, sentry, playwright, github, qdrant-readonly. All reachable.                                                      |
| AGENTS.md                     | 63 lines, no spalla framing. Adding additive section.                                                                                                                        |
| Existing wrapper              | `scripts/ai-dispatch.sh` has `codex-fix`, `codex-review`, `codex-test`, `codex-fix-batch`, `codex-migrate`. Working.                                                         |
| Native review plugin (Claude) | `~/.claude/plugins/cache/claude-plugins-official/code-review/...` — multi-agent PR review **using only Claude agents** (same-model bias risk). Codex spalla closes that gap. |
| OpenAI `codex-plugin-cc`      | Released 2026-03-30. Requires `OPENAI_API_KEY` → **banned by CLAUDE.md hard rule**. We DIY.                                                                                  |

## 2. Capability matrix — Claude Code vs Codex CLI

| #   | Dimension                                       | Claude Code (Opus 4.7 1M, MAX OAuth)                     | Codex CLI 0.124 (GPT-5.5 xhigh, ChatGPT Plus OAuth)     | Verdict                                   |
| --- | ----------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| 1   | Codebase awareness in current session           | Native (Claude session is hot)                           | Cold start every dispatch                               | Claude wins                               |
| 2   | Multi-file refactor with cross-file consistency | Strong (1M ctx + skills)                                 | Strong but cold start tax                               | Claude wins (context already warm)        |
| 3   | Different training-data perspective             | Self-reviewing self → bias                               | Independent training history                            | **Codex wins** (proven PR #181)           |
| 4   | Sandbox layer                                   | Application-layer hooks/permissions                      | Kernel-level Seatbelt (macOS) / bubblewrap (Linux)      | **Codex wins** for risky autonomy         |
| 5   | `--full-auto` unattended execution              | `--dangerously-skip-permissions` available but app-layer | Kernel-enforced workspace-write sandbox                 | **Codex wins** for fire-and-forget        |
| 6   | MCP integration breadth                         | 50+ tools loaded                                         | 7 MCP servers configured (similar set)                  | Tie                                       |
| 7   | Web search                                      | WebSearch tool                                           | None native CLI (uses general web via plugins)          | Claude slight edge                        |
| 8   | Diff-only review (PR/uncommitted)               | Possible via `gh pr diff` + reasoning                    | Native `codex review --uncommitted/--base/--commit`     | **Codex wins** for fast diff review       |
| 9   | Long-running 2–3h refactor                      | Subject to OAuth turn limits / context drift             | Native long-running supported                           | Codex slight edge                         |
| 10  | Test running until pass                         | Task tool + Bash (steered by user)                       | `codex exec --full-auto` runs tests in loop until green | **Codex wins** for "make tests green"     |
| 11  | Reasoning style for adversarial review          | Trained helpful & cautious                               | GPT-5.5 in xhigh runs more verification (PR #181)       | **Codex wins** for skeptical second-pass  |
| 12  | Cost (already paid)                             | 3× MAX OAuth (flat)                                      | ChatGPT Plus OAuth (flat)                               | Tie                                       |
| 13  | Native skills/superpowers                       | Yes (this session)                                       | Different skill ecosystem (`.codex/skills/`)            | Claude wins for nuzantara-tuned workflows |
| 14  | Output format consistency                       | Highly tunable per task                                  | Less control over formatting                            | Claude wins                               |
| 15  | Speed for short queries                         | Fast                                                     | Slower (cold start + xhigh effort = 30–90s)             | Claude wins                               |

**Net read:** Codex wins genuinely on rows 3, 4, 5, 8, 10, 11. That's the spalla edge. Everywhere else, Claude is at least equal.

## 3. Brainstorm output (Consiglio v1, 2026-05-03)

**Sources:**

- Claude Opus 4.7 (this session, primary synthesis)
- Gemini 3.1 Pro (independent reply, on-topic, high quality)
- Codex GPT-5.5 self-aware: produced output but went off-topic (loaded prior CRM-audit session memory). Output became _evidence_ for the spalla edge claim (caught CRIT-4 hardcoded secret, cross-system reasoning) rather than direct answer.
- DeepSeek Reasoner: dispatch failed (DEEPSEEK_API_KEY blocked by deny-list). Acceptable per Wave-2 lessons (2026-04-29) — 2/4 threshold met.

### 3.1 Five spalla scenarios

#### S1. Adversarial security review of mutating endpoints

**Trigger:** new auth/payment/state-mutating route in `apps/backend-rag` lands in a PR.
**Prompt template:** _"Adversarial review. Assume the diff is exploitable. Find race conditions, SQL injection, auth bypass, IDOR. Run the code in sandbox if it shortens uncertainty. Mark findings as BLOCKER / MEDIUM / LOW."_
**Edge:** different training data on exploit patterns + kernel-level Seatbelt to safely run untrusted PoCs + GPT-5.5 sceptical bias (vs Claude's helpful bias).
**Expected output:** prioritized findings with PoC commands or line-cites.

#### S2. Mocked-test-masked logic reviews (PR #181 class, **proven**)

**Trigger:** the diff (a) introduces a new branch of behavior, (b) depends on a contract from a file off-limits to edit, (c) is tested primarily with mocks.
**Prompt template:** _"Verify this implementation against the un-mocked dependency. Quote line numbers from the real implementation file. Mark BLOCKER if behavior diverges in production."_
**Edge:** Codex with `--full-auto` actually runs the un-mocked code path; Claude's tests-pass-mocks-pass loop missed it (proven 2026-04-22, PR #181).
**Expected output:** BLOCKER + cited line numbers from real source.

#### S3. Long-running `--full-auto` loops (test green / migration grind)

**Trigger:** "make tests green for X" or "rename Y across 200 files until type-check passes" — repetitive grind that doesn't fit Claude's interactive turn cadence.
**Prompt template:** _"Run pytest until all tests in apps/backend-rag/tests/services/test_pricing pass. Iterate atomic commits. Stop when 0 failures or after 10 cycles."_
**Edge:** kernel-enforced `--full-auto` autonomy + commit-loop pattern + frees Claude session for design work.
**Expected output:** chain of small commits + final pass/fail report.

#### S4. PR diff review with `codex review --base main`

**Trigger:** any PR before merge, especially when author and would-be reviewer are both Claude.
**Prompt template:** native `codex review --base main` with optional `--title` for context (no custom prompt needed for default review).
**Edge:** built-in 3-mode review (branch/uncommitted/commit), no token cost from current Claude session, separate transcript turn keeps context clean.
**Expected output:** structured prioritized findings (Codex review preset).

#### S5. "I am not sure I trust my own judgment here" gate

**Trigger:** Claude is about to ship something high-blast-radius (auth, billing, migration, deploy config) AND the Claude turn-count for this branch is already long (high context-drift risk).
**Prompt template:** _"Pre-ship audit. Read CLAUDE.md / AGENTS.md, then verify the diff against project rules. Output a punch-list of must-fix vs nice-to-have."_
**Edge:** orthogonal context — Codex starts cold and is forced to read project conventions fresh; flags violations Claude missed because Claude's context-drift hid them.
**Expected output:** punch-list grouped by must-fix / nice-to-have / informational.

### 3.2 Two hybrid workflow patterns

#### Pattern A — "Claude plans, Codex grinds" (long-running execution)

**When better than Claude doing both:** Claude's interactive turns + token cost are too expensive for tedious file-by-file grind. Examples: deleting `typing.Any` across 253 files, renaming a database column with cross-cutting type updates, running pytest until green.

```bash
# Claude writes /tmp/migration-plan.md with steps + acceptance criteria
codex exec --full-auto -c model_reasoning_effort=xhigh \
  "Read /tmp/migration-plan.md. Execute each step. Run pytest after each. Commit atomically. Stop on first acceptance failure."
```

**Runtime:** 10–60 min wall-clock. Codex commits live to a feature branch. Claude's session stays clean.

#### Pattern B — "Claude implements, Codex adversarially reviews" (red-team)

**When better than Claude self-review:** any high-risk diff. Same-model bias is real (PR #181). Cost is negligible (~3–8 min, OAuth flat rate).

```bash
# /codex-second-opinion slash command:
#   1. anti-pattern guard (3-line banner + 5s countdown if small)
#   2. git diff base..HEAD captured
#   3. dispatch: codex review --base main --title "[SPALLA] <task>"
#   4. transcript saved to ~/logs/codex-spalla/<ts>-<slug>.md
#   5. BLOCKER-tagged → also copy to docs/codex-reviews/
#   6. summarize verdict to user inline
```

**Runtime:** 2–8 min. Output stays in repo (auditable). Claude reads markdown, applies fixes, optionally re-runs spalla.

### 3.3 Three anti-patterns (do NOT spawn Codex spalla)

#### A1. Brainstorming + design dialogue

**Why degraded:** brainstorming is iterative back-and-forth; Codex is cold-start each dispatch. Two-model brainstorm produces incoherent design (Wave 2 Pro lesson — Codex+Gemini+NotebookLM simultaneous capacity exhaustion is a wave-level pattern). Better: keep brainstorm in Claude's continuous session, then spawn spalla on the _output_.
**Alternative:** stay in Claude session.

#### A2. Trivial fixes (typo, missing import, single-line null check)

**Why degraded:** Codex cold-start latency (30–90s on xhigh) > the fix itself; spawning is pure overhead. Sandbox guarantees are wasted on syntax. Claude in-session is faster + cheaper.
**Alternative:** Claude does it directly.

#### A3. UI/visual frontend work (Next.js components, Tailwind, mockups)

**Why degraded:** Codex has no visual rendering loop, no Playwright integration in CLI mode that's better than Claude's. Claude with `mcp__claude-in-chrome__*` already iterates against a real browser. Codex spalla here adds 0 edge.
**Alternative:** Claude + claude-in-chrome MCP, or a specialized visual agent.

## 4. ChatGPT Pro upgrade analysis

| Tier           | $/mo | GPT-5.5 access | Codex usage limits                    | 1M ctx    | Deep Research | Verdict          |
| -------------- | ---- | -------------- | ------------------------------------- | --------- | ------------- | ---------------- |
| Plus (current) | $20  | yes (400K ctx) | baseline                              | no        | 10/mo         | **stay**         |
| Pro $100       | $100 | yes            | 5× Plus (10× temp through 2026-05-31) | no        | 50/mo         | wait for trigger |
| Pro $200       | $200 | yes (Pro mode) | 20× Plus                              | yes (API) | 250/mo        | not yet          |

**Decision:** stay on Plus. Re-evaluate weekly using `~/logs/codex-spalla.jsonl` data.

**Pro $100 trigger:** Codex usage-limit errors ≥2/week AND blocking real work. May 31 promo makes May the cheapest A/B-test window if it triggers.
**Pro $200 trigger:** sustained >4h/day Codex use across multiple days. Not currently the case.

## 5. Implementation log

### 5.1 Quick wins shipped (branch `feat/codex-spalla`)

- **Commit 1**: `~/.codex/AGENTS.md` Spalla Mode section (additive, pre-spalla backup created).
- **Commit 2**: `.claude/commands/codex-second-opinion.md` + `.claude/scripts/codex-spalla.sh` helper.
- **Commit 3**: `.claude/hooks/codex-spalla-trigger.sh` + `.claude/settings.json` PostToolUse entry.

### 5.2 Real-scenario test

(filled in after test in §10 of design spec)

## 6. Open questions / future research

- After 14 days of telemetry: promote Q3 from smart-loud (c) to strict (a) if blocker rate ≤ 10% on small diffs.
- Pattern A: real cron-driven test green loop (e.g., flaky-test cleanup branch).
- Mini-Pro2 verification: after merge, smoke test on Mini.
- Should Codex review be added to GitHub Actions CI? Probably not (cold-start latency × every PR ≠ value); user-triggered only.

## 7. Sources / references

- Codex CLI 0.124 official: <https://developers.openai.com/codex/cli>
- Codex changelog (April–May 2026): <https://developers.openai.com/codex/changelog>
- ChatGPT pricing 2026: <https://chatgpt.com/pricing/>
- Hamel Husain — claude-review-loop reference architecture: <https://github.com/hamelsmu/claude-review-loop>
- BSWEN — practical Claude × Codex workflow patterns: <https://docs.bswen.com/blog/2026-04-02-claude-codex-workflow-integration/>
- MindStudio — codex-plugin-cc analysis: <https://www.mindstudio.ai/blog/openai-codex-plugin-claude-code-cross-provider-review>
- Memory `decision_cross_llm_review_concrete_value.md` — PR #181 proof case (internal).
