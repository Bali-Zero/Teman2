# W1.4 Pilot Migration Status (2026-05-09)

5 pilot agents identified for event-driven migration. Status:

| #   | Agent                              | Migration status            | Event emitted                                        | Notes                                                                                                                                                                                                                   |
| --- | ---------------------------------- | --------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | regulatory-watcher                 | **MIGRATED** ✓              | `regulatory.delta.detected` (one per delta found)    | Wrapper `regulatory-watcher-run.sh` patched. Smoke verified — emits work end-to-end via Meta-Dispatcher.                                                                                                                |
| 2   | intel.nightly (bali-intel-scraper) | **PENDING** — wrapper-style | `intel.collected` (1 event per scrape run)           | Approach: patch the inline cmd in `com.balizero.intel.nightly.plist` to use `pilot_emit_post_cron.sh intel-scraper intel.collected ...`. Script is ready (`/Users/nuzantara/scripts/eventbus/pilot_emit_post_cron.sh`). |
| 3   | wr2-topic-selector                 | **PENDING** — script-side   | `topic.candidate.created` (one per topic picked)     | Cleanest path: edit `wr2_topic_selector.py:243` (the line that writes a draft) to also `from eventbus import publish; publish("topic.candidate.created", {...})`. ~20 line change.                                      |
| 4   | wr2-supervisor (daemon)            | **PENDING** — script-side   | `content.draft.ready` after each carousel completion | Daemon writes `slides.json`. After write, add `publish("content.draft.ready", {...})`. ~10 line change.                                                                                                                 |
| 5   | wr2-canva-apply (skill)            | **PENDING** — script-side   | `publish.completed` after Canva URL emitted          | Skill is markdown-driven (orchestrator runs MCP calls). Add Bash `python3 -m eventbus.publisher publish.completed '...'` at end of skill.                                                                               |

## Why staged migration

**Pattern**: cron-driven AND event-driven coexist for 2 weeks. Original cron keeps running. Wrappers ALSO emit events. Downstream subscribers gain real-time wake-up. Once verified stable, original cron schedules can be relaxed (e.g., from daily to weekly safety net) or removed.

**Why not patch all 5 today**: 4 of 5 require touching production Python scripts in `~/Desktop/nuzantara` repo (Nuzantara apps), which has its own CI + autonomous ops contract. Doing 5 simultaneously risks compound bugs. Migrating 1 pilot (regulatory-watcher, owned by `~/.claude` / `~/scripts`) validates the pattern without touching the main repo.

## Verification (regulatory-watcher pilot)

```bash
# 1. Trigger watcher (any tier in cascade succeeds)
launchctl kickstart -k gui/$(id -u)/com.balizero.regulatory-watcher.daily
# 2. After completion, check eventbus stream
redis-cli -h 100.93.236.6 -p 6379 XREVRANGE bz:regulatory.delta.detected + - COUNT 5
# 3. Meta-Dispatcher log shows kickstart of wr2.topic-selector
tail /Users/nuzantara/logs/meta-dispatcher.log
```

## Next steps (W2-W4)

- W2: Trajectory observability — record every event as a span in `trajectories.db`. No more agent migration in W2.
- W3: Begin migrating pilot #2-#5 (intel-scraper, topic-selector, supervisor, canva-apply). Each is an isolated PR-style change.
- W4: All 5 pilots emitting. Cron schedules unchanged (parallel mode). Original cron-debt can be retired in W5+.
