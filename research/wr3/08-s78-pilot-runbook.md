---
date: 2026-05-18
domain: wr3-design
step: 7.8
title: S7.8 — "Manifesto Zantara" pilot runbook (executable when Chatterbox installed)
status: 4-of-5-blockers-resolved-2026-05-19
---

# WR3 Step 7.8 — "Manifesto Zantara" pilot runbook

> **Status: BLOCKED on 3 prerequisites.** This runbook is executable in
> ~30-60 min once the blockers below are resolved. Foundation S7.1→S7.7
> verified GREEN at 2026-05-18 08:51 WITA:
>
> - Smoke pilot 7/7 PASS (mock mode, zero cloud spend)
> - Lint sweep 6/6 enforcer 0 ERROR, 0 WARN
> - Test suite 74/74 PASS in 1.42s

## Prerequisites (3 blockers)

### Blocker 1 — Migration 182 collision

Two files at `apps/backend-rag/backend/db/migrations_v2/`:

| File                                | Origin                          | Status                         |
| ----------------------------------- | ------------------------------- | ------------------------------ |
| `182_wr3_eventbus_channels.sql`     | WR3 (`34f0d0825`)               | ✅ committed in genesis branch |
| `182_companies_tax_dept_folder.sql` | sibling session (CRM Phase 1.6) | ❌ untracked in disk only      |

**Resolution path** (cicatrix scar P0-7):

1. Sibling session author (CRM Phase 1.6) renames their file → `183_companies_tax_dept_folder.sql`
2. Commits to their branch
3. WR3 keeps `182_*` unchanged (committed first wins)

**Why WR3 wins:** WR3 migration is already committed in branch + applied
during post-deploy pipeline. Sibling file has never been git-add'ed.

### Blocker 2 — Flow Pro gateway

Required: local FlowKit gateway listening on `http://127.0.0.1:8100`.

**Verify:**

```bash
curl -s http://127.0.0.1:8100/health
# expected: {"status":"ok","plan":"pro","credits_remaining":N}
```

**If absent**, install + start:

```bash
# Reference: scripts/wr2_flowkit_client.py uses same gateway
# Setup docs: docs/wr2/flowkit-integration.md
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.flowkit-gateway.plist
```

Flow Pro plan: **25k cr/month Ultra plan active** (per CLAUDE.md §10).
"Manifesto Zantara" 60s episode = ~120 cr (12 clips × 10 cr Fast Tier_ONE).

### Blocker 3 — Chatterbox CLI

Required: `chatterbox-tts` CLI on PATH (or `WR3_CHATTERBOX_BIN` env var).

**Verify:**

```bash
which chatterbox-tts
chatterbox-tts --version
```

**If absent**, install via Voice-Clone-Pilot-2026-05-16 procedure
(`research/marketing/2026-05-16-tts-provider-benchmark.md`):

```bash
pip install chatterbox-multilingual  # or brew install ...
```

Emma seed pinned: `seed=42 cfg_weight=0.30 temperature=0.70 exaggeration=0.32`.
Voice corpus: `~/Desktop/Zantara-Voice-Pilot-2026-05-16/` (10 sample WAVs
already generated, ID + EN samples).

### Blocker 4 (implicit) — Claude Agent SDK

```bash
pip install claude-agent-sdk
```

Required by `scripts/wr3_dispatch_agent.py`. Without it, dispatch falls back
to subprocess `claude --print --agent <name>` which is more brittle but
Symbiosis Law 1 compliant.

## Executable runbook (T+0 = blockers resolved)

### Phase 0 — pre-flight (T+0 → T+5min)

```bash
cd ~/Desktop/nuzantara
git checkout feat/wr3-room-genesis
git pull origin feat/wr3-room-genesis
source apps/backend-rag/.venv/bin/activate

# Sanity: full WR3 sweep
python3 scripts/wr3_smoke_test.py
python3 scripts/lint/wr3_lint_runner.py
PYTHONPATH=scripts pytest scripts/tests/test_wr3_*.py -q
```

Expected: all 3 green. If any FAIL → STOP, investigate before pilot.

### Phase 1 — apply migration 182 (T+5 → T+15min)

```bash
# Trigger backend-rag deploy (applies migration 182 via post-deploy hook)
gh workflow run "Deploy Backend to Fly.io" --ref feat/wr3-room-genesis

# Watch the run:
gh run watch
```

Verify on Fly PG:

```bash
fly ssh console -a nuzantara-postgres
psql $DATABASE_URL -c "SELECT migration_number, applied_at FROM schema_migrations WHERE migration_number = 182;"
```

Expected: 1 row with `migration_number=182`, recent `applied_at`.

### Phase 2 — start supervisor in dry-run (T+15 → T+20min)

```bash
WR3_DRY_RUN=true \
  DATABASE_URL="postgres://...:15432/nuzantara_rag" \
  python3 scripts/wr3_supervisor.py
```

Expected stdout:

```
[wr3-supervisor] Loaded 13 contracts, 6 channels
[wr3-supervisor] Router version: 1.0.0
[wr3-supervisor] Dry run: True
[wr3-supervisor] Connected to PG (...)
[wr3-supervisor] LISTEN wr3_episode_brief_requested
[wr3-supervisor] LISTEN wr3_episode_pre_render_ready
... (6 channels)
```

Leave running in foreground (or LaunchAgent later).

### Phase 3 — fire pilot episode (T+20 → T+25min)

In separate terminal:

```bash
psql $DATABASE_URL -c "
SELECT publish_wr3_event(
  'wr3_episode_brief_requested',
  jsonb_build_object(
    'episode_id', 'pilot-manifesto-zantara-2026-05-18',
    'topic', 'Manifesto Zantara — Bali Zero brand intro 60s 12 clips',
    'audience', 'new-arrivals-bali',
    'mode', 'standard'
  )
);
"
```

Supervisor should pick up the NOTIFY within ~1 second. With `WR3_DRY_RUN=true`,
it logs the dispatch decision but does NOT spend cloud credits — confirms
wiring without burning credits.

Expected supervisor log:

```
[wr3-supervisor] wr3_episode_brief_requested → wr3-design-architect ep=pilot-manifesto-zantara-2026-05-18 dry=True
```

### Phase 4 — flip to real dispatch (T+25 → T+45min)

Stop dry-run supervisor (`Ctrl+C`). Restart without `WR3_DRY_RUN`:

```bash
DATABASE_URL="postgres://...:15432/nuzantara_rag" \
  python3 scripts/wr3_supervisor.py
```

Re-fire the brief event (same psql command). Supervisor now executes the
full pipeline:

1. `wr3-design-architect` dispatches `wr3-brief-interpreter`
2. `brief-interpreter` queries NB (cost ~$0.12)
3. `pre_render_ready` fans out → `script-editor` + `audio-asset-producer` + `shot-director` (parallel)
4. `pre-render-gatekeeper` reviews → emits `gate_passed`
5. `clip-renderer` submits ~12 clips to Flow Pro (120 cr)
6. `assembly_ready` → `post-assembler` builds master + 4 variants
7. `critic` reviews 4 lanes → emits `critic_verdict`
8. If PASS: `staged` → Drive + Telegram P0

End-to-end target: ≤45 min, ≤$0.50 cash + 120 cr Flow Pro.

### Phase 5 — review + decide v0→v1 (T+45min)

Check artifacts:

```bash
ls apps/war-room/output/episode/pilot-manifesto-zantara-2026-05-18/
# expected: master.mp4, variants/{tiktok,ig-reels,yt-shorts,fb}.mp4,
#           episode_manifest.json, critic-report.json
```

Read manifest:

```bash
jq '.critic_verdict, .total_cost_usd, .flow_credits_spent, .identity_overall_cosine_avg' \
  apps/war-room/output/episode/pilot-manifesto-zantara-2026-05-18/episode_manifest.json
```

Antonello reviews master.mp4 via Drive. Decision matrix per dossier 06:

| Metric             | Target          | Hard fail if                      |
| ------------------ | --------------- | --------------------------------- |
| End-to-end latency | ≤45 min         | >75 min                           |
| Total cost         | ≤$0.50 + 120 cr | >$2                               |
| Critic 4 lanes     | PASS all 4      | Any FAIL after 2 retry rounds     |
| ArcFace identity   | ≥0.6 avg        | <0.55 in any clip                 |
| Manifest fields    | 18/18           | Any missing                       |
| Silent placeholder | 0               | ≥1 (Law 4 degrade-loud violation) |

**v0 → v1 transition: 3 consecutive pilots PASS** (rule of 3 from Q10 panel).

## Telemetry inspection (post-pilot)

```bash
ls ~/.cell-observatory/wr3/
# wr3-design-architect.jsonl
# wr3-brief-interpreter.jsonl
# wr3-script-editor.jsonl
# ... (one per dispatched agent)

# Total cost & duration:
jq -s 'map(.cost_usd // 0) | add' ~/.cell-observatory/wr3/*.jsonl
jq -s 'map(.duration_ms) | add' ~/.cell-observatory/wr3/*.jsonl
```

## Failure recovery

### Supervisor crashes

LaunchAgent (S7.5 stub) with `KeepAlive=true` respawns. Outbox replay on
reconnect picks up unconsumed events within 60min window. If supervisor
crashes mid-episode, the event stays UNCONSUMED — manual retry:

```bash
psql $DATABASE_URL -c "
UPDATE events_outbox SET consumed_at = NULL
WHERE id = <event_id>;
NOTIFY wr3_episode_<channel>, <payload>;
"
```

### Critic FAIL on a specific lane

Per dossier 06 §"Episode lifecycle", FAIL routes orchestrator to retry:

- Lane 1 (identity) → re-prompt shot-director
- Lane 2 (audio sync) → post-assembler re-render
- Lane 3 (brand voice) → script-editor rewrite
- Lane 4 (legal/regulatory) → brief-interpreter re-ground

Max 2 retry rounds. If still FAIL → manifest flagged, Telegram P0 to Antonello.

### Flow Pro quota exhaustion mid-episode

Episode parks, Telegram P0 fires. Next month quota refresh OR manual cr
purchase via Flow console. Failed clips dispatch `wr3-b-roll-curator`
fallback for license-clean alternatives.

## Skill cortex feedback loop

After each pilot:

1. `wr3-reflexion-synth` (Sun 02:30 WITA cron, S7.5 stub) reads
   `apps/war-room/output/episode/<recent-7-days>/*`
2. Synthesizes ≤10 lessons/week/agent into
   `~/.claude/skills/bali-zero-brand/wr3/<agent>/lessons.md`
3. Proposes new skills in `~/.claude/skills/bali-zero-brand/wr3/_proposed/`
4. Antonello manually graduates after 3 successful uses (Voyager curriculum)

`wr3-yt-metrics-analyst` (Mon 06:00 WITA cron, S7.5 stub) correlates
engagement metrics with episode attributes after publish, proposes
amendments to brand cortex.

## See also

- Architecture: `research/wr3/06-architecture-skeleton.md`
- Genesis state: `research/wr3/07-genesis-execution-state.md`
- Symbiosis precedence: `docs/wr3/symbiosis-precedence.md`
- Smoke test: `scripts/wr3_smoke_test.py`
- Lint sweep: `scripts/lint/wr3_lint_runner.py`
- Test suite: `scripts/tests/test_wr3_*.py`
