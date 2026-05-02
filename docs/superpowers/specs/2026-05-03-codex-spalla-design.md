# Codex CLI as "spalla" complementare — design spec

**Date:** 2026-05-03
**Status:** approved (user, 2026-05-03)
**Authors:** Claude Opus 4.7 (1M ctx) + Antonello (Bali Zero)
**Branch:** `feat/codex-spalla`

## 1. Problem

Codex CLI is installed (0.124.0, ChatGPT Plus OAuth, GPT-5.5 + xhigh) and operative on Pro/Mini, but under-used as a co-pilot. The team has empirical evidence (PR #181, 2026-04-22) that Codex catches BLOCKER-grade issues that Claude's mocked-test green runs miss — a same-model bias problem documented in `decision_cross_llm_review_concrete_value.md`. We need a small, opinionated set of tools that make spawning Codex _as a sidekick_ (not as a replacement) cheap and habitual.

## 2. Non-goals

- Replacing Claude as primary developer.
- Auto-spawning Codex from hooks (would burn ChatGPT quota silently).
- Building a parallel skill ecosystem in `.codex/skills/` (separate concern).
- Migrating Consiglio v1 to include Codex as 4th voice (see §7 — separate workflow recommended).

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Claude Code session (primary)                               │
│                                                             │
│   user typing or working ───► Claude does the work          │
│                                                             │
│   triggers spalla:                                          │
│     • /codex-second-opinion [args]                          │
│     • PostToolUse hook → suggest in stderr (no auto-spawn)  │
│                                                             │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ .claude/commands/codex-second-opinion.md (project-level)    │
│   instructs Claude to capture diff, build [SPALLA] prompt,  │
│   delegate to .claude/scripts/codex-spalla.sh               │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ .claude/scripts/codex-spalla.sh                             │
│   1. anti-pattern guard (3-line banner + 5s countdown)      │
│   2. diff capture                                           │
│   3. dispatch:                                              │
│      Pattern B (default): codex review --base main          │
│      Pattern A (--mode=exec): codex exec --full-auto        │
│   4. transcript saved to ~/logs/codex-spalla/<ts>-<slug>.md │
│      copied to docs/codex-reviews/ if BLOCKER found         │
│   5. telemetry → ~/logs/codex-spalla.jsonl                  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Codex CLI ─── reads ─►  ~/.codex/AGENTS.md                  │
│                          (new "Spalla Mode" section          │
│                           triggered by [SPALLA] prefix)     │
└─────────────────────────────────────────────────────────────┘
```

## 4. Component contracts

### 4.1 `~/.codex/AGENTS.md` "Spalla Mode" section

Additive to existing AGENTS.md. Triggered by `[SPALLA]` literal in prompt. Defines:

- Output template: one-line verdict (`BLOCKER` / `MEDIUM` / `LOW` / `LGTM`) → diff summary → bullets.
- Adversarial bias: assume diff broken until disproven; quote real (un-mocked) line numbers.
- Narrow scope: don't reformulate, don't refactor, don't summarize at end.
- Verify-before-assert: grep before citing symbols.
- Sandbox-first: prefer `--sandbox read-only` runs over speculation.

### 4.2 `.claude/commands/codex-second-opinion.md`

Project-level slash command. Args: optional `[focus brief]` and `--mode=exec|review` and `--base=<branch>`.

**Frontmatter `allowed-tools`:**

- `Bash(.claude/scripts/codex-spalla.sh:*)` (whitelist the helper)
- `Bash(git diff:*)`, `Bash(git status:*)`, `Bash(git log:*)`
- `Read`, `Write`

**Behavior in markdown body:** instructions to Claude to delegate to the helper script, then summarize the helper's verdict file.

### 4.3 `.claude/scripts/codex-spalla.sh`

Shell helper, single source of truth. Bash 3.2-compatible (macOS default).

**Inputs:**

- `$1` = mode (`review` default | `exec`)
- `$2` = base branch (`main` default)
- `$3` = focus brief (free text, optional)

**Anti-pattern guard (per design Q3 approval):**

1. **Empty diff** → hard refuse with exit code 2 (no countdown).
2. **Diff < 10 lines OR < 3 files** → loud 3-line warning banner:
   ```
   ⚠ scope is small — Claude self-review may be cheaper.
   ⚠ proceeding in 5s (Ctrl-C to cancel) ...
   ⚠ logged warned=true to telemetry.
   ```
   Then 5-second countdown, then proceed unless cancelled.
3. **Otherwise** proceed silently.

**Dispatch logic:**

- Pattern B (review): `codex review --base "$BASE" --title "[SPALLA] ${FOCUS:-uncommitted-diff}"`. If `codex review` doesn't accept stdin context, fall back to `codex exec --full-auto --sandbox read-only -c model_reasoning_effort=xhigh "<built prompt>"`.
- Pattern A (exec): `codex exec --full-auto -c model_reasoning_effort=xhigh "<built prompt>"`.

**Output handling:**

- Always: `~/logs/codex-spalla/<UTC-ts>-<slug>.md` (full transcript).
- If BLOCKER detected (regex `^BLOCKER` in output, case-insensitive on first 50 lines): also `cp` to `docs/codex-reviews/<UTC-ts>-blocker-<slug>.md`.
- Telemetry one-line JSON to `~/logs/codex-spalla.jsonl`:
  ```json
  {
    "ts": "2026-05-03T14:30:00Z",
    "mode": "review",
    "base": "main",
    "focus": "<brief>",
    "diff_lines": 47,
    "files_changed": 3,
    "warned": false,
    "cancelled": false,
    "exit_code": 0,
    "blocker": true,
    "transcript": "~/logs/codex-spalla/...md"
  }
  ```

**Hard rules:**

- Never `--dangerously-bypass-approvals-and-sandbox`.
- Never set `OPENAI_API_KEY`; depend on existing OAuth.
- If `codex login status` shows not logged in → exit with helpful message.

### 4.4 PostToolUse hook (telemetry-only)

`.claude/hooks/codex-spalla-trigger.sh` + entry in `.claude/settings.json` (project-level).

**Triggers** (suggest only — no auto-spawn):

- After `Bash(gh pr create:*)` regardless of size.
- After `Bash(git diff:*)` whose output > 100 lines AND mentions `auth|payment|migration|pricing|webhook`.
- After `Edit` or `Write` to `apps/backend-rag/backend/services/auth*` or `services/pricing*`.

**Output:**

- One-line stderr suggestion: `[spalla-suggest] consider /codex-second-opinion before commit`.
- Telemetry: `~/logs/codex-spalla-trigger.jsonl` with `{ts,event,tool,target,recommended_command}`.

## 5. Data flow on a typical `/codex-second-opinion` invocation

1. User types `/codex-second-opinion adversarial — focus on race conditions`.
2. Slash command markdown loads. Claude parses args.
3. Claude calls `bash .claude/scripts/codex-spalla.sh review main "adversarial — focus on race conditions"`.
4. Script captures `git diff main...HEAD`, runs anti-pattern guard.
5. Script dispatches `codex review --base main --title "[SPALLA] adversarial — focus on race conditions"`.
6. Codex reads `~/.codex/AGENTS.md`, sees `[SPALLA]` prefix, switches to spalla output mode.
7. Codex returns verdict (~3-8 min on xhigh).
8. Script saves transcript, parses verdict, writes telemetry.
9. Claude reads transcript path from script stdout and surfaces the verdict to user.

## 6. ChatGPT Pro upgrade — current decision

**Stay on ChatGPT Plus.** Trigger criteria for Pro $100 evaluation:

- Codex usage-limit errors hit ≥2/week AND block real work.
- Active migration sprint expects >4h/day Codex execution.

Pro $200 not recommended until we have a workflow that runs Codex hours/day. The May 31 promo (10× temporary on Pro $100) makes it cheap to A/B-test if needed.

## 7. Long-term: Consiglio v2 with Codex role

Open question: should Codex become a 4th voice in `apps/backend-rag/backend/services/research/consiglio_orchestrator.py` (currently Claude + Gemini + DeepSeek + Ollama)?

**Recommendation: NO — keep separate.**

- Consiglio v1 deliberates on _design_ questions (where Codex spalla is anti-pattern A1: brainstorming/architecture).
- Spalla operates on _diffs and exec_ (orthogonal use case).
- Consolidating risks confusing both. Better: keep Consiglio v1 for design; `/codex-second-opinion` for diff/exec.

Tracked separately in `docs/decisions/2026-05-03-codex-spalla-architecture.md`.

## 8. Telemetry calibration plan (14-day post-launch)

After 14 days of telemetry collection, run weekly cron job to compute:

```bash
jq -r '. | select(.warned==true) | "\(.diff_lines)\t\(.blocker)"' ~/logs/codex-spalla.jsonl | sort | uniq -c
```

**Promotion criteria:**

- If `warned=true` + `blocker=false` ≥ 90% → promote to **strict mode (option (a))**: hard refuse on small diff. Saves quota.
- If `warned=true` + `blocker=true` ≥ 30% → keep **smart-loud mode (option (c))**: small diffs CAN find blockers; warning is enough.
- Document outcome in `docs/decisions/2026-05-03-codex-spalla-architecture.md` as the "exit criteria" of this design choice.

## 9. Testing

Per the brainstorming skill flow:

1. Write all 3 components on `feat/codex-spalla` branch.
2. Run `/codex-second-opinion` against a real recent diff (e.g., the `chore/dependabot-npm-bumps` work) to verify end-to-end.
3. Inspect telemetry, transcript, and BLOCKER routing.
4. Memory entry `project_codex_spalla_2026_05_03.md`.

## 10. Out of scope / future work

- Mini-Pro2 mirroring (depends on git push to main; will sync automatically once merged).
- Pattern A integration with `make migrate` / `make test-fix` automation.
- Cross-machine telemetry aggregation (per-machine for now).
- `.codex/skills/codex-spalla/SKILL.md` mirror (Codex-native discovery).

## 11. Acceptance criteria

- [ ] `~/.codex/AGENTS.md` has Spalla Mode section, `[SPALLA]` prefix correctly switches Codex behavior in a manual smoke test.
- [ ] `/codex-second-opinion` runs end-to-end against a diff > 10 lines / 3 files, returns a transcript and verdict.
- [ ] Anti-pattern guard: empty diff → hard refuse; small diff → 3-line warning + 5s countdown + telemetry `warned=true`.
- [ ] BLOCKER-tagged transcripts auto-copied to `docs/codex-reviews/`.
- [ ] Telemetry has all 4 required fields: `diff_lines`, `files_changed`, `warned`, `cancelled`.
- [ ] Memory entry written.
- [ ] PR opened with the 3 commits + this spec + architecture memo + CODEX_SPALLA.md.
