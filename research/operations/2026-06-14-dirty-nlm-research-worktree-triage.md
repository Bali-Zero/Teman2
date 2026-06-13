# Dirty NLM Research Worktree Triage - 2026-06-14

## Summary

Spark correctly flagged the main checkout at `/Users/nuzantara/Desktop/nuzantara`
as dirty, but the actionable root cause is mixed:

- The Spark lifecycle itself is healthy.
- The cleanup cron bad-exit signal is already diagnosed as a stale runtime
  checkout issue; the live LaunchAgent still points at the dirty main checkout.
- Most modified NLM source/config files in the main checkout are byte-identical
  to current `origin/main`, so they are stale-checkout symptoms rather than new
  source WIP.
- The clear generated-artifact leak is local output data under root `outputs/`
  and `apps/evaluator/nlm_deep_research/output/`.

## Live Evidence

Commands run from the isolated overnight worktree:

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short
git -C /Users/nuzantara/Desktop/nuzantara rev-list --left-right --count HEAD...origin/main
launchctl print gui/$(id -u)/com.nuzantara.agent-worktree-cleanup.daily
tail -220 /Users/nuzantara/logs/agent-worktree-cleanup.log
```

Observed state:

- Main checkout: `2` ahead, `158` behind `origin/main`.
- Cleanup LaunchAgent target: `/Users/nuzantara/Desktop/nuzantara/scripts/agent_worktree_cleanup_cron.sh`.
- Cleanup log still ends with WIP-safe `WARN: skip ... (WIP)` followed by
  `done (exit 1)` from the stale runtime wrapper.
- Previous overnight run opened PR #1402 for cleanup-cron regression coverage.

## Dirty Tree Classification

### Already Matches Current Origin Main

These modified files in the main checkout are byte-identical to the current
overnight branch / `origin/main`:

- `apps/evaluator/nlm_deep_research/cross_notebook_correlator.py`
- `apps/evaluator/nlm_deep_research/freshness_monitor.py`
- `apps/evaluator/nlm_deep_research/gap_scanner.py`
- `apps/evaluator/nlm_deep_research/multimodal_pipeline.py`
- `apps/evaluator/nlm_deep_research/nb5_pipeline.py`
- `apps/evaluator/nlm_deep_research/nb6_pipeline.py`
- `apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py`
- `apps/evaluator/nlm_deep_research/persona_definitions.json`
- `apps/evaluator/nlm_deep_research/pipeline.py`
- `apps/evaluator/nlm_deep_research/t4_monitor.py`
- `apps/evaluator/nlm_deep_research/t4_nb5_config.json`
- `apps/evaluator/nlm_deep_research/yt_monitor.py`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`

These article files are untracked in the stale main checkout but already tracked
in current `origin/main`:

- `apps/mouth/src/content/articles/immigration/indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists.mdx`
- `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.id.mdx`
- `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.it.mdx`
- `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.id.mdx`
- `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.it.mdx`

### Preserve Before Fast-Forward

These are real local deltas relative to current `origin/main` and should not be
discarded by an automated cleanup:

- `apps/bali-intel-scraper/data/published_articles.json`
- `docs/AUTOMATIONS_REFERENCE.md`
- `scripts/curiosity_loop.sh`
- `shared/escalations_pro.jsonl`
- `apps/crm-cell/war-room/interactive_cli.sh`
- `research/nb-health/2026-06-10-health.md`
- `research/nb-health/2026-06-11-health.md`
- `research/nb-health/2026-06-12-health.md`
- `research/nb-health/2026-06-13-health.md`
- `research/operations/2026-06-11-drive-crm-unified-client-folders-design.md`
- `research/operations/2026-06-11-fable5-extra-task-allocation.md`
- `research/regulatory/2026-06-10-delta.json`
- `research/regulatory/2026-06-11-delta.json`
- `research/regulatory/2026-06-12-delta.json`
- `research/regulatory/2026-06-13-delta.json`

### Generated Artifacts

These are local generated outputs and should stay out of git by default:

- `outputs/` (client/base64 export artifacts)
- `apps/evaluator/nlm_deep_research/output/` (multimodal audio/image outputs)

This PR adds ignore rules for those two generated-output roots only.

## Safe Next Step

Do not run a blind cleanup or `git pull` in `/Users/nuzantara/Desktop/nuzantara`
while it is dirty. Preserve the "Preserve Before Fast-Forward" files into a
dedicated worktree/branch or local handoff, then fast-forward the runtime main
checkout so LaunchAgents use the current wrapper and current NLM notebook IDs.

After the runtime checkout is updated, rerun or wait for
`com.nuzantara.agent-worktree-cleanup.daily` and verify the log ends with:

```text
done (broker rc=1, exit 0)
```

when only WIP-safe skips remain.
