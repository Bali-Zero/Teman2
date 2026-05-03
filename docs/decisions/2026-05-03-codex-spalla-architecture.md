# Codex spalla — architecture decision memo

**Date:** 2026-05-03
**Status:** accepted (user, 2026-05-03)
**Supersedes:** none
**Related:** `docs/superpowers/specs/2026-05-03-codex-spalla-design.md`, `docs/codex/CODEX_SPALLA.md`, memory `decision_cross_llm_review_concrete_value.md`

## Context

Codex CLI 0.124 (GPT-5.5 + xhigh) on ChatGPT Plus OAuth is operative and proven (PR #181 BLOCKER catch on 2026-04-22) but under-used as a co-pilot. The team needs:

1. A small set of low-friction tools to dispatch Codex _as a sidekick_ (not a replacement).
2. A design that respects CLAUDE.md hard rules (no Anthropic API keys; no `OPENAI_API_KEY`).
3. A position on whether to integrate Codex into the existing Consiglio v1 deliberation orchestrator.

## Decision

Adopt three production artifacts on branch `feat/codex-spalla`:

1. **`~/.codex/AGENTS.md` Spalla Mode** (additive section) — output template + adversarial bias + narrow scope rules, triggered by `[SPALLA]` prefix.
2. **`/codex-second-opinion` slash command** (project-level at `.claude/commands/`) — Pattern B (adversarial review) default, Pattern A (autonomous exec) via `--mode=exec`.
3. **PostToolUse telemetry hook** — observability only, no auto-spawn.

Keep `/codex-second-opinion` and Consiglio v1 **separate**. Do not bolt Codex into `consiglio_orchestrator.py` as a 4th voice.

### Why separate from Consiglio v1

- **Consiglio v1** deliberates _design questions_ — multi-LLM brainstorm, judge, synthesis. Codex spalla is anti-pattern A1 here (cold-start kills design coherence).
- **`/codex-second-opinion`** operates on _diffs and exec_ — orthogonal surface (post-implementation review, autonomous exec loops).
- Consolidating risks confusing both. Better: two sharp tools for two sharp jobs.

### Why no auto-spawn from hooks

- ChatGPT Plus quota is shared with all other Codex use cases.
- "Auto-Codex on every Edit" would burn quota silently and conflict with `decision_cross_llm_review_concrete_value.md` cost discipline ("default to triple-review _when_ the change touches the ReAct/reasoning pipeline" — explicit gating, not auto).
- Hook is **suggestion-only** with telemetry. Auto-promotion requires explicit decision after evidence.

### Why DIY instead of OpenAI's `codex-plugin-cc`

- Official plugin requires `OPENAI_API_KEY` (not OAuth). CLAUDE.md user-global hard rule bans paid API keys (Antonello holds 3× MAX, ChatGPT Plus, Gemini OAuth — paying per-token would duplicate flat subscriptions).
- DIY using `codex` CLI shells out to ChatGPT OAuth via Codex itself, which is the sanctioned path.

## Decision parameters (recap of the 3 design Q&A)

### Q1 — Slash command placement

**Chosen: (c) project-level at `<repo>/.claude/commands/codex-second-opinion.md`** with helper at `<repo>/.claude/scripts/codex-spalla.sh`.
**Reason:** machine-portability hard constraint per CLAUDE.md (Pro+Mini+Air sync via git). Helper script logic is non-trivial (anti-pattern guard, transcript routing, telemetry) and worth git-tracking.

### Q2 — Transcript storage

**Chosen: (c) hybrid** — `~/logs/codex-spalla/<ts>-<rand>-<mode>-<slug>.md` for routine runs (per-machine, not git-tracked). BLOCKER-tagged runs are also `cp`'d to `docs/codex-reviews/<ts>-<rand>-blocker-<slug>.md`, but **that path is gitignored** (transcripts contain `(see ~/.codex/AGENTS.md)`-style references that `docs_audit.py` parses as broken markdown links, breaking the Docs Guardian inventory-check on every PR). The canonical audit trail therefore lives in `~/logs/codex-spalla/` + the JSONL telemetry; `docs/codex-reviews/` is a per-machine convenience copy. The `<rand>` 4-hex suffix + race-safe noclobber creation in the helper guarantee no two concurrent runs ever silently clobber each other's transcript.
**Reason:** keeps repo clean while preserving high-signal transcripts for future learning (parallel to PR #181 case study citation).

### Q3 — Anti-pattern guard threshold

**Chosen: (c) smart-loud** — never hard-refuse non-empty diffs, but warn on small diff (< 10 lines OR < 3 files) with 3-line banner + 5s countdown.
**Three explicit specs from user:**

1. Banner is exactly 3 lines (defined in script).
2. **Empty diff → hard refuse** (no countdown, exit 2).
3. Telemetry includes `diff_lines`, `files_changed`, `warned`, `cancelled` (all 4 required).

## Exit criteria for Q3 (14-day calibration)

Run weekly (cron `0 6 * * 1`):

```bash
jq -r '. | select(.warned==true) | "\(.diff_lines)\t\(.blocker)"' \
  ~/logs/codex-spalla.jsonl | sort | uniq -c
```

| Observed pattern                      | Action                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| `warned=true` + `blocker=false` ≥ 90% | Promote to **strict mode** (option (a) refused below thresholds). Saves Codex quota. |
| `warned=true` + `blocker=true` ≥ 30%  | Keep **smart-loud (c)**. Small diffs CAN find blockers; warning is enough.           |
| Mixed (50–90% no-blocker)             | Hold (c) for another 14 days, expand sample size.                                    |

Decision recorded in this memo via amendment after 2026-05-17.

## Trade-offs accepted

- **Slower than auto-spawn**: user has to type `/codex-second-opinion`. Worth it for quota and intent clarity.
- **Two parallel review systems**: native `code-review` plugin (Claude-only) and `/codex-second-opinion` (Codex). Acceptable — they cover different risks (same-model bias vs nothing-at-all).
- **Per-machine telemetry**: not aggregated cross-machine. Defer to future work; per-machine is enough for first 14 days.
- **No `.codex/skills/codex-spalla/SKILL.md` mirror**: Codex-native skill discovery would require additional plumbing (per Trail of Bits convention). Defer.

## Future work / explicit non-goals tonight

- Pattern A end-to-end automation (`make migrate-spalla` style targets).
- Mini-Pro2 verification pass after merge (will inherit via git pull).
- Promotion path to `~/.claude/commands/` (user-global) if pattern stabilizes.
- Cross-machine telemetry aggregation.
- Auto-spawn graduation criteria (separate decision after Q3 calibration).

## ChatGPT Pro upgrade decision

**Stay on Plus.** Pro $100 evaluation triggers:

- Codex usage-limit errors ≥2/week (verified blocker for real work).
- Active migration/refactor sprint expecting >4h/day Codex use.

Pro $200 not recommended until sustained hours/day Codex use. May 2026 promo (10× temp Codex usage) would make Pro $100 the cheapest A/B window if needed.

Re-evaluate weekly with telemetry data; record any upgrade in this memo.

## References

- `docs/superpowers/specs/2026-05-03-codex-spalla-design.md` — full design spec.
- `docs/codex/CODEX_SPALLA.md` — research log + capability matrix + scenarios.
- Memory `decision_cross_llm_review_concrete_value.md` — PR #181 proof case study (2026-04-22).
- Memory `feedback_codex-safety-fix.md` — `ai-dispatch.sh` 3-tier safety system (2026-03-25).
- Memory `feedback_claude-cli-redundant.md` — why we DON'T have a `/claude-second-opinion` (circular).
- `scripts/ai-dispatch.sh` — existing wrapper for Gemini/Codex/DeepSeek/Aider dispatch.
- ChatGPT pricing 2026: <https://chatgpt.com/pricing/>.
