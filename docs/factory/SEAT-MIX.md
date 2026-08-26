# Seat-mix daily report

Spec: A7/R12 (`/Users/nuzantara/Desktop/2026-08-26-PIANO-SPEC-receptor-live.md` §3 A7, §8
R12/E5). Script: `scripts/seat_mix_report.py`. Tests: `scripts/tests/test_seat_mix_report.py`.

## Why this exists

The fleet dispatches Claude subagents (the `Agent` tool: model + `subagent_type`) and shells
out to a whole cross-family arsenal (Codex, Kimi, agy, Ollama, NotebookLM, `seat_build.sh`,
TP1) from inside Claude Code sessions, but until this script existed nobody had ever counted
the mix in a repeatable way. A one-off hand parse on 2026-08-26 found 882 Agent dispatches
fleet-wide in 48h (sonnet 86%, haiku 0.9%, opus the rest), ~512 non-Anthropic shell calls, the
`Workflow` tool at 0 genuine runs, and only 5 of 20 evidence packs carrying a cross-family
reviewer. That parse was never published and could not be re-run. This script is the
repeatable version.

## What it measures

It stream-parses Claude Code's own project transcripts (`~/.claude/projects/**/*.jsonl`, or
`--projects-root`) inside a lookback window (`--since HOURS`, default 24) and counts, purely
structurally, three things:

- **Agent dispatch mix** -- every `Agent` tool_use, bucketed by `input.model` (missing model
  means the subagent inherited the session's model, recorded as `inherit`) and by
  `input.subagent_type`. `cheap_seat_share_pct` is the haiku share of that total.
- **Non-Anthropic seat calls** -- every `Bash` tool_use whose `input.command` matches a small,
  fixed seat vocabulary (`codex exec -m gpt-5.6-{sol,terra,luna}` or the bare default tier,
  `kimi -m kimi-code/{k3,kimi-for-coding,kimi-for-coding-highspeed}`, `agy --model`,
  `seat_build.sh --seat/--tier`, `ollama run`, `nlm`/`notebooklm`, `jules_dispatch.py`,
  `tp1_call`/`review_routes`). Everything else running under `Bash` (`git`, `pytest`, `ls`, ...)
  is not a "seat" and is not counted. `non_anthropic_seat_calls.per_anthropic_dispatch` is the
  ratio of that total to total Agent dispatches.
- **Workflow tool runs** -- a bare count of `Workflow` tool_use blocks.

Each scanned session's `gitBranch` field is best-effort joined to a PR number via
`gh pr list --search "head:<branch>"` (skipped entirely if `gh` is unavailable, or with
`--no-map-prs`); sessions with dispatch activity whose branch didn't map to any open PR are
counted in `unmapped_sessions_with_activity` rather than silently dropped.

## What it does not measure, and why

There are no targets or thresholds anywhere in this report or in this doc. The 2026-08-26
retro's A5 proposal (imposing a target ratio) was rejected: this is descriptive telemetry, not
a gate. It tells you what the mix IS; deciding what it SHOULD be is a separate, human
conversation informed by these numbers, not something the script enforces.

It also does not measure cost or token volume (that is `scripts/usage/seat_usage_collector.py`,
which parses the same transcript family for `message.usage` token counts per Claude-profile
seat -- a different join key: profile-dir to account-seat, not branch to PR). The two are
complementary, not overlapping: this script answers "what got dispatched and where", that one
answers "how many tokens did each account burn".

## Output

- `~/logs/seat-mix/<YYYY-MM-DD>.json` -- full structured report.
- `~/logs/seat-mix/<YYYY-MM-DD>.md` -- the same numbers, rendered readable, also printed to
  stdout by the CLI.

## PII boundary (SYMBIOSIS Law 2)

Transcripts carry real client PII inside `tool_result` blocks and free-text `text` blocks. The
scanner never reads either -- it only inspects `tool_use` blocks' `name` field and a handful of
narrow-charset regex captures out of `input.command` / `input.model` / `input.subagent_type`,
and discards the raw command text immediately after classification. Every string that reaches
the report additionally passes through a sanitizer (truncate to 120 chars, strip to
`[A-Za-z0-9 _./:%()\-=,]`) at the point of extraction, and a final `assert_all_strings_safe`
pass re-walks the whole report as a hard defense-in-depth gate before anything is written. This
is tested directly: `test_pii_in_tool_result_and_command_text_never_leaks` feeds a fixture
transcript containing an email, a phone number and an `sk-...`-shaped secret inside a
`tool_result` block and asserts none of them appear in the emitted JSON or Markdown.

## Day-0 baseline (Pro, `--since 48`, 2026-08-27 00:38 WITA, post cross-family review)

Scoped to this machine's own `~/.claude/projects` only -- not the fleet-wide hand parse this
script replaces, which spanned M5+Pro+Mini. A per-machine cron on each node is how the two
become comparable; nothing here sums them. This is the run taken AFTER the mandatory Kimi K3
adversarial review of the shipping PR (findings and fixes below), not the first draft.

```
# Seat-mix daily report

- generated_at: 2026-08-27 00:38:00 WITA
- window_hours: 48.0
- sessions_scanned: 118
- files_skipped (over size cap): 0

## Agent dispatch mix

Total Agent dispatches: 148

| model | count | pct |
|---|---|---|
| sonnet | 127 | 85.8% |
| inherit | 18 | 12.2% |
| haiku | 2 | 1.4% |
| opus | 1 | 0.7% |

cheap_seat_share_pct (haiku share): 1.4%

| subagent_type | count |
|---|---|
| general-purpose | 113 |
| Explore | 14 |
| backend-verifier | 12 |
| fork | 5 |
| unspecified | 2 |
| spalla-review | 1 |
| mcp-health | 1 |

## Non-Anthropic seat calls (Bash)

Total: 112
Per Anthropic dispatch: 0.76

| seat | count |
|---|---|
| nlm | 23 |
| kimi:k3 | 16 |
| seat_build:default | 15 |
| kimi:default | 15 |
| agy:default | 10 |
| codex:sol | 8 |
| tp1 | 8 |
| codex:default | 7 |
| seat_build:codex/unset | 3 |
| codex:luna | 3 |
| jules_dispatch | 3 |
| kimi:kimi-for-coding | 1 |

## Workflow tool

workflow_runs: 1

## Per-PR seat counts (best-effort branch join)

unmapped_sessions_with_activity: 35

| PR | agent_dispatches | seat_calls | sessions |
|---|---|---|---|
| 5043 | 1 | 0 | 1 |
| 5037 | 1 | 0 | 1 |
| 5039 | 0 | 1 | 1 |
```

Most sessions-with-activity are unmapped, and that is a correct reading of this machine's
work that day, not a join failure: a metadata-only branch tally (names only, no message
content) over the same window shows the bulk of sessions on `main`, on detached `HEAD`, and on
the long-lived `feature/visa-oracle` integration branch -- none of which a `head:<branch>` PR
search can ever match, by construction (no PR has `main`/`HEAD` as its head ref, and this
repo's integration branches are merged by the conducting session directly, per
`docs/factory/ASSEMBLY-LINE.md`, not through per-lane PRs). The mapped PRs came from
short-lived per-lane `agent/...` branches, this report's own PR (#5047 -> #5043 above) included.

### What the cross-family review changed

The mandatory Kimi K3 (`kimi-code/k3`) adversarial pass on this report's own shipping PR found
two real issues before merge, both fixed and both re-tested:

1. **A secret/PII leak in free-captured flag values.** `--model`/`--seat`/`--tier`/ollama's
   model argument are captured from arbitrary command text (unlike the codex/kimi tier labels,
   which come from a fixed enumeration). The output-safety charset is a _superset_ of common
   secret shapes -- an `sk-...`-style key or a bare-digit phone number is made entirely of
   letters/digits/hyphens, so it would have survived the sanitizer intact. Fixed with a
   `_redact_if_sensitive()` check (secret-key prefixes, or >=7 digits) applied before
   sanitization, replacing the value with the fixed literal `redacted` rather than propagating
   it in any form.
2. **Over-counting when a vocabulary script is read/edited, not run.** `cat scripts/seat_build.sh`,
   `git log -- scripts/jules_dispatch.py`, `grep review_routes -r .` all matched the vocabulary
   even though nothing was invoked -- a systematic inflation risk in a repo whose daily work is
   editing these very scripts. Fixed by splitting each command on shell separators and skipping
   any segment whose own first word is a read/inspect/edit verb (`cat`, `grep`, `git`, `vim`, ...)
   before running any vocabulary check on it.

Neither finding was a full PII leak of the kind the original PII fixture already covered (that
one -- email/phone/key inside a `tool_result` or a non-matching command -- was correct from the
start); both were narrower gaps the refuter located precisely, and both now have their own
guilt+innocence test coverage in `scripts/tests/test_seat_mix_report.py`.

## Cron

`infra/launchagents/com.nuzantara.seat-mix.daily.plist` -- `StartCalendarInterval` 06:30, no
`KeepAlive` (superscar #7: this is a one-shot job, not a long-running daemon). Not installed by
the PR that ships it (Agent PR Contract): install per machine with

```bash
cp infra/launchagents/com.nuzantara.seat-mix.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nuzantara.seat-mix.daily.plist
```

on both Pro and Mini (the H24 node) -- not on M5, which runs no daemons/cron by design.
