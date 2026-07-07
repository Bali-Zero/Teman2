# Staged migration: cron/agent tier-1 `claude-sonnet-4-6` → `claude-sonnet-5`

- **Date**: 2026-07-03 (flight session P3, operator airborne — GEAR 2, modus loop)
- **Mandate**: CLAUDE.md §5 / modus SKILL.md §Arsenal — "Cron tier-1 stays claude-sonnet-4-6 until the staged migration to Sonnet 5 is tested per-agent"
- **Branch/PR**: `agent/nuzantara/infra/sonnet5-cron`
- **Probe evidence**: session scratchpad `probes/` + `out/` (18 paired 1-shots, all exit=0)

## TL;DR

Every ACTIVE tier-1 pin was probed with a real prompt-shape 1-shot on both models.
**8/9 agent shapes SAFE on Sonnet 5** — quality equal or better (yield-optimizer applied all
R-rules incl. LKPM-in-13-days; ig-metrics-analyst self-identified sample confounds; vision
critic returned verdicts identical to 4-6 on a real slide). **1 RISKY**: the nb-agents slug
micro-prompt (3/3 wobble: 7 tokens vs "max 6", meta-leak, context-leak) — stays on 4-6; its
consumer has no scheduler (dormant) so nothing changes live.

Repo-side pins are migrated in this PR. **LIVE cron still runs the HOME copies** (`~/scripts/`,
read-only for agents — HOME-fork family #1): the operator one-liners below arm the migration.

## Inventory — every `claude-sonnet-4-6` pin

### Repo-side (migrated in this PR)

| File | Lines | Agent / role | Live? |
|---|---|---|---|
| `infra/launchagents/wrappers/regulatory-watcher-run.sh` | 3, 41, 45 | regulatory-watcher tier-1 | plist runs HOME copy (was byte-identical to repo) |
| `scripts/nb-curator-daily.sh` | 174 | nb-curator claude-cascade FALLBACK (primary brain = agy Flash) | plist runs HOME copy (was byte-identical) |
| `infra/eventbus/meta_dispatcher.py` | 237, 265 | canva-apply skill dispatch | plist runs HOME copy (`~/scripts/eventbus/meta_dispatcher.py`) — **HOME copy is AHEAD of repo** (`BZ_REDIS_HOST` env param never promoted back) |
| `scripts/wr2_html_renderer/claude_vision.py` | 222 | WR2 vision critic default (`WR2_VISION_MODEL` overridable) | live from repo (WR2 pipeline) |
| `scripts/wr3_reflexion_synthesis.py` | 38, 266 | WR3 reflexion weekly tier-1 | **NOT armed**: plist `com.balizero.wr3.reflexion.weekly` runs `~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py` = 816-byte S7.3 STUB (exit 0, does nothing) |
| `apps/backend-rag/backend/tests/unit/scripts/test_wr2_html_render_apply.py` | 226, 242 | asserts vision default | updated in same commit (W86 discipline) |
| `CLAUDE.md` | §5 | routing doctrine line | updated to migration-in-progress state |

Not pins (left untouched): `scripts/cost_baseline.py` (historical cost table),
`scripts/test_call_llm_deepseek.py` (routing-inference test), docs/, research/, vendor/evoskill,
apps/backend-rag backend clients (out of mandate scope — separate deploy-gated migration).

### HOME-side LIVE (read-only for agents — operator applies)

| File:line | Agent | Cron | Verdict |
|---|---|---|---|
| `~/scripts/regulatory-watcher-run.sh:41,45` | regulatory-watcher | daily 07:00 | SAFE → migrate |
| `~/scripts/nb-curator-daily.sh:174` | nb-curator (fallback tier) | daily | SAFE → migrate |
| `~/scripts/wr2-ig-metrics-analyst-run.sh:89` | wr2-ig-metrics-analyst | weekly Mon 06:00 | SAFE → migrate |
| `~/scripts/competitor-monitor-run.sh:29` | competitor-monitor | monthly d1 09:00 | SAFE → migrate |
| `~/scripts/yield-optimizer-run.sh:29` | yield-optimizer | weekly Sun 04:00 | SAFE → migrate |
| `~/scripts/eventbus/meta_dispatcher.py:241,269` | canva-apply dispatch | daemon | SAFE → migrate (sed only — HOME copy ahead of repo, do NOT cp) |
| `~/scripts/nb-agents-daily-dr.sh:76` | slug micro-prompt | no scheduler found (dormant) | **RISKY → keep 4-6** |
| `~/scripts/nb-curator-weekly.sh:86`, `~/scripts/run-nb-curator-mode-c.sh:55` | nb-curator weekly/mode-c | plists disabled | dormant — migrate if reactivated |
| `~/scripts/cron-agent-python/{agent_config.py,tdd_pipeline.py}` | tdd pipeline | no scheduler | dormant — migrate if reactivated |
| `~/scripts/*.bak-*` | backups | — | leave |

## Probe methodology

For each agent, the format-critical core of its REAL prompt (extracted from the live wrapper /
`build_synthesis_prompt()` / `_CRITIC_PROMPT`) ran as a sandboxed 1-shot on BOTH models
(`claude --print --model <m>`), with synthetic non-PII data inline, no Telegram, no live file
writes. Vision probe used the real `--output-format json --json-schema` invocation on a real
slide PNG (`docs/wr2/manual-assets/2026-06-13-june-deadlines/slide-01.png`). Baseline sanity:
regulatory-watcher's ACTUAL production tier-1 run of 2026-07-02 (delta JSON + Telegram, served
by 4-6) matches the probe shape. 18/18 runs exit=0; Sonnet 5 durations equal or faster on 5/9.

| Probe | 4-6 | Sonnet 5 | Notes |
|---|---|---|---|
| regwatch (delta JSON schema, filter, verbatim) | PASS | PASS | S5 semantics perfect (Pergub correctly excluded AND seen); S5 added md fences + trailing prose despite "ONLY JSON" — harmless here (wrapper never parses stdout; agent writes the file via tools) |
| nbcur (hard limits, SUMMARY line, dup pairs) | PASS | PASS | S5 found exactly the 2 planted dup pairs, clean SUMMARY |
| igmetrics (insights + confidence grading) | PASS | PASS | S5 explicitly flagged the domain/layout confound — better statistical honesty |
| compmon (digest structure, material-changes) | PASS | PASS | validator false-FAIL on S5 (bold `**Material changes: yes**` + "Let's Move" apostrophe — MY check was a #3 guard-over-match, model was fine) |
| yield (R1-R6 rules, no pitch text, no invented names) | PASS | PASS | S5 flawless: R4 LKPM 13-days caught, R6 honestly not fired, correct owner routing |
| slug (kebab ≤6 words) | PASS | **FAIL 3/3** | 7 tokens; "slug-generation" meta-leak; "nuzantara" context-leak (cwd context injection). 4-6 clean 1/1 |
| canva (dry-run discipline) | PASS | PASS | weak probe (no live MCP) — risk accepted: prompt is trivial skill dispatch, Sonnet 5 already the fleet implementer tier |
| wr3refl (lessons JSON, honest thin-signal) | PASS | PASS | S5: 4 lessons all confidence=low, real episode ids |
| vision (real slide, real schema) | PASS | PASS | verdicts IDENTICAL (passes=false, score=0.15, lever=rerender); S5 found 5 issues vs 3 |

## §Solo-operatore — arming steps (exact diffs)

After this PR merges to main and Pro's main checkout is pulled:

```bash
# 1. regulatory-watcher + nb-curator (repo copies byte-identical pre-edit → clean cp)
cp ~/Desktop/nuzantara/infra/launchagents/wrappers/regulatory-watcher-run.sh ~/scripts/regulatory-watcher-run.sh
cp ~/Desktop/nuzantara/scripts/nb-curator-daily.sh ~/scripts/nb-curator-daily.sh

# 2. Standalone wrappers (no repo counterpart) — in-place sed
sed -i '' 's/--model claude-sonnet-4-6/--model claude-sonnet-5/' ~/scripts/wr2-ig-metrics-analyst-run.sh
sed -i '' 's/--model claude-sonnet-4-6/--model claude-sonnet-5/' ~/scripts/competitor-monitor-run.sh
sed -i '' 's/--model claude-sonnet-4-6/--model claude-sonnet-5/' ~/scripts/yield-optimizer-run.sh

# 3. meta_dispatcher — sed ONLY (HOME copy ahead of repo: BZ_REDIS_HOST param), then restart daemon
sed -i '' 's/"claude-sonnet-4-6"/"claude-sonnet-5"/g' ~/scripts/eventbus/meta_dispatcher.py
launchctl kickstart -k gui/$(id -u)/com.balizero.meta-dispatcher   # restart, NOT reinstall (W84)

# DO NOT touch: ~/scripts/nb-agents-daily-dr.sh (RISKY slug — stays 4-6, dormant anyway)
```

Proof-of-armed (probe the work, not the command): next `~/logs/regulatory-watcher.log` run line
shows `used: claude-sonnet-5`; ig-metrics/competitor/yield logs show the run completing on the
new model; `~/logs/meta-dispatcher.log` shows spawn lines post-restart.

Also operator-only:
- **OAuth token hygiene**: during this session an env inventory printed the 3 numbered
  `CLAUDE_CODE_OAUTH_TOKEN_N` values in cleartext into the LOCAL session transcript
  (`~/.claude/projects/...`). Exposure = Pro filesystem only, but if you want zero residue:
  rotate/refresh the tokens in `~/.nuzantara-secrets.env`.
- **WR3 reflexion stub** (pre-existing Esiste≠Armato, found during inventory): the weekly plist
  runs an 816-byte placeholder that exits 0 — the full `scripts/wr3_reflexion_synthesis.py`
  never runs in cron. Decide: promote the real script into the plist target, or accept the
  firebreak until WR3 S7.5 lands.

## §Meta-pattern (short — Gear 2)

All friction in this task traces to superscar **#1 HOME-fork** (5 of 6 live pins execute from
`$HOME`, one live copy AHEAD of repo, one live target is a stub the repo version outgrew) and
**#3 guard-over-match** (my own probe validator false-failed a healthy output on a bold-prefix
and an apostrophe — substring matching on form, not fact). The migration itself was the easy part.

## Follow-ups recorded in PENDING-ARMS

1. HOME wrapper sync (operator one-liners above) — the actual arming of this migration.
2. `~/scripts/eventbus/meta_dispatcher.py` reverse-promotion (BZ_REDIS_HOST param → repo).
3. WR3 reflexion stub-vs-real decision.
