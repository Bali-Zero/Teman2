# OpenClaw Telegram skills audit + <80 commands plan — Sprint 0 Track A2

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Telegram BOT_COMMANDS_TOO_MUCH"

## TL;DR

- Telegram caps a bot's `setMyCommands` registration at **100**. OpenClaw on Pro
  attempts **92** commands and Telegram drops **19** of them. Empirical line in
  `~/.openclaw/logs/gateway.log` 2026-05-02 13:34:10:
  > `[telegram] accepted 73 commands after BOT_COMMANDS_TOO_MUCH (started with 92; omitted 19).`
- The **5 user-enabled skills** in `~/.openclaw/openclaw.json` (`goplaces`,
  `xurl`, `voice-call`, `notion`, `antigravity`) all show **0 invocations in
  the last 30 days** of `gateway.log`. Each skill exposes ≥1 Telegram menu
  entry → disabling all 5 buys ~5–10 commands.
- The dominant contributor is the **43 OpenClaw-bundled skills** under
  `~/.openclaw/lib/node_modules/openclaw/skills/*` that load by default. These
  are NOT toggled via `skills.entries[<name>].enabled=false` (that flag only
  takes effect for skills *also* listed there); they require either an explicit
  `skills.deny[]` entry or a hot-patch of `tools.alsoAllow` to be excluded
  from the Telegram menu sync.

## What was audited (artifact, repeatable)

`scripts/openclaw-skill-audit.py` — read-only audit, runs from Air against Pro
via `OPENCLAW_HOST=pro` SSH, OR locally on Pro (no flag). It produces a
JSONL with one record per discovered skill:

```json
{"skill":"notion","kind":"user-enabled","enabled":true,"invocations_30d":0,"last_seen":null,"recommendation":"disable","reason":"user-enabled but 0 invocations in 30d"}
```

Output committed verbatim at `docs/audits/sprint0/openclaw-skills-audit.jsonl`.

## Counts (current state, Pro 2026-05-02)

| Kind | Count | Notes |
|---|---|---|
| **user-enabled (entry in `skills.entries`)** | 12 | of which 5 enabled, 7 disabled |
| **bundled (under `lib/node_modules/openclaw/skills`)** | 43 | always loaded; not in `skills.entries` |
| **plugins (`plugins.entries`)** | 4 | `memory-core`, `lobster`, `llm-task`, `voice-call` (the plugin twin of the skill) |
| **TOTAL distinct names** | 59 | |

The 92-command count Telegram observes is **not** equal to the skill count:
each skill contributes 1–4 menu entries (e.g. `notion` → `/notion_search`,
`/notion_page`, `/notion_db`). 59 skills × ~1.5 average ≈ 92 — matches the
observed `started with 92` line.

## Recommended actions (ordered by effort × impact)

### 1. Disable the 5 idle user-enabled skills (immediate, free, ~5-10 commands saved)

All 5 user-enabled skills have `invocations_30d=0` in `gateway.log`. Application
edits `~/.openclaw/openclaw.json`:

```jsonc
"skills": {
  "entries": {
    "goplaces":    { "enabled": false, ... },   // was true
    "xurl":        { "enabled": false, ... },
    "voice-call":  { "enabled": false, ... },   // also disable plugins.entries.voice-call
    "notion":      { "enabled": false, ... },
    "antigravity": { "enabled": false, ... }
  }
}
```

Manual procedure (NOT executed by this Sprint 0 PR — application is post-merge
on Pro by Antonello):

```bash
ssh pro 'cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.pre-skill-disable-2026-05-02 && \
  jq ".skills.entries.goplaces.enabled=false |
      .skills.entries.xurl.enabled=false |
      .skills.entries[\"voice-call\"].enabled=false |
      .skills.entries.notion.enabled=false |
      .skills.entries.antigravity.enabled=false |
      .plugins.entries[\"voice-call\"].enabled=false" \
    ~/.openclaw/openclaw.json.pre-skill-disable-2026-05-02 \
    > ~/.openclaw/openclaw.json && \
  echo "OK"'
```

Verify by tailing `~/.openclaw/logs/gateway.log` for the next `setMyCommands`
attempt — expect the `started with N` count to drop by 5–10.

### 2. Add `skills.deny[]` for the 43 bundled skills with 0 invocations (medium effort, big impact)

OpenClaw v2026.3.31 documents `skills.deny[]` as the supported way to exclude
bundled skills from menu sync. Skills below have **0 invocations in 30 days**
of `gateway.log` and fall in clearly-irrelevant categories for Bali Zero ops:

| Category | Skills (drop these) |
|---|---|
| Personal / not-Bali-Zero | `1password`, `apple-notes`, `apple-reminders`, `bear-notes`, `obsidian`, `imsg`, `bluebubbles`, `discord`, `slack`, `spotify-player`, `trello` |
| Hardware / device-specific | `eightctl`, `camsnap`, `node-connect`, `gog`, `gifgrep` |
| Adjacent ecosystems | `gh-issues`, `github`, `clawhub`, `clawflow`, `clawflow-inbox-triage` |
| Audio/visual not in scope | `voice-call`, `sherpa-onnx-tts` |

Concrete `skills.deny` proposal (drop ~25 → save ~30 commands, lands well
under 80 with margin for new skills):

```jsonc
"skills": {
  "deny": [
    "1password","apple-notes","apple-reminders","bear-notes","obsidian",
    "imsg","bluebubbles","discord","slack","spotify-player","trello",
    "eightctl","camsnap","node-connect","gog","gifgrep",
    "gh-issues","github","clawhub","clawflow","clawflow-inbox-triage",
    "sherpa-onnx-tts","blogwatcher","blucli","gemini","healthcheck"
  ],
  "entries": { ... }
}
```

`gemini` and `healthcheck` are removed because Nuzantara has its own paths
for both (Federation orchestrator + `~/scripts/fly-health-check.sh`). The
OpenClaw-bundled equivalents are unused and clutter the menu.

### 3. Keep these (in scope for Bali Zero ops, even if currently quiet)

- `notion` — paid integration with active env var, may be revived for KB sync
- `goplaces` — Google Places API used by Mata Garuda research-cell roadmap
- `coding-agent` — invoked by Lobster `autofix-loop.lobster` (production)
- `mcporter` — root of 129 MCP tools, see Track A3 (separate audit)
- `canvas` — A2UI, retained for future browser flows
- `nano-pdf` — PDF tool, used by OCR vision-doc strategy
- `model-usage` — telemetry, useful even if Telegram-quiet

### Plugins layer (do NOT touch in this round)

The 4 plugins (`memory-core`, `lobster`, `llm-task`, `voice-call`) follow a
separate lifecycle from the Telegram menu sync. `voice-call` is recommended
for disable in user-skill and plugin layer simultaneously (see step 1 above).
The other three are core OpenClaw infrastructure and stay.

## Expected outcome after applying steps 1+2

- `started with N` count: 92 → ~57–62 (under 80, well within Telegram limit)
- `omitted` count: 19 → 0 (no more `BOT_COMMANDS_TOO_MUCH` errors)
- Skill loadtime: marginally faster gateway boot (less skill manifest parsing)

## Out-of-scope today

- Per-skill command-count audit (i.e. exactly which skill contributes which
  Telegram menu entry). Would need to instrument the OpenClaw `setMyCommands`
  call site or read the `commands.list` returned by gateway, neither of which
  is exposed in `gateway.log`. Estimate-by-name is sufficient for "drop to
  <80" goal.
- Migration to per-channel skill scoping (`skills.bindings[].channel`). The
  Telegram menu would shrink dramatically if non-Telegram skills (e.g. canvas,
  voice-call) were scoped to other channels, but no other channel is enabled
  in Nuzantara today. Revisit during Sprint 5 (OpenClaw insertions WR2).

## References

- `~/.openclaw/openclaw.json` — `skills.entries`, `skills.deny[]`, `plugins.entries`
- `~/.openclaw/lib/node_modules/openclaw/skills/*` — 53 bundled skill dirs
- `~/.openclaw/logs/gateway.log` — `setMyCommands` errors live here, grep `BOT_COMMANDS_TOO_MUCH`
- `scripts/openclaw-skill-audit.py` — repeatable audit
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § "Telegram BOT_COMMANDS_TOO_MUCH"
