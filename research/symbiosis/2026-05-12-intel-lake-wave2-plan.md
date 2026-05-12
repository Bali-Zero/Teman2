---
date: 2026-05-12
wave: 2
producers: t4_monitor, yt_monitor, fact_checker
status: implemented
---

# Wave 2 — fact_checker + t4_monitor + yt_monitor

## Scope decision (refined from Wave 1)

| Producer       | Wave 2 integration    | Reason                                                                                                                                                                                                                                                         |
| -------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `t4_monitor`   | ✅ Dual-write enabled | True producer — fetches new articles from RSS/X/web, pushes to NB. Each ingest = lake observation.                                                                                                                                                             |
| `yt_monitor`   | ✅ Dual-write enabled | True producer — discovers YouTube videos from gov channels, ingests to NB. Each video URL = lake observation.                                                                                                                                                  |
| `fact_checker` | ❌ NOT integrated     | **Verifier, not producer**: reads staged-for-publish articles from `~/.intel_scraper/staged-for-publish/` and validates claims. Doesn't discover sources; checks existing ones. Adding it to the lake would create noise (validation reports ≠ news findings). |

## Patches applied

### t4_monitor.py

After successful `_call_nlm_cli` ingest, enqueue to `intel_lake_outbox`:

```python
if success:
    self._cb.record_success(state)
    self._persistence.save(state)
    try:
        from intel_lake_outbox import enqueue as _lake_enqueue
        content_hash = hashlib.sha256((article.title + " " + article.content).encode()).hexdigest()[:32]
        _lake_enqueue("t4_monitor", { ... })
    except Exception as exc:
        logger.warning("intel-lake enqueue failed: %s", exc)
```

### yt_monitor.py

New helper `_enqueue_to_intel_lake(video_url, notebook_id)` called inside
`ingest_video()` after successful nlm CLI add.

## Volume estimate (24h)

- `t4_monitor`: scheduled Mar/Gio 18:00 — ~10-30 articles/run × 2 runs/week ≈ 5/day average
- `yt_monitor`: scheduled (cadence TBD) — ~5-15 videos/run
- Combined: ~10-50 observations/day to outbox

Well within drain capacity (60s ticks × 100/batch).

## Test plan

- [x] Python syntax check both modules
- [ ] Manual smoke after Wave 1 PR merged + Fly deploy + drain bootstrap
- [ ] Verify outbox shows `producer_name='t4_monitor'` and `'yt_monitor'` rows

## Wave 2 stop-loss

Same as Wave 1: `~/.intel-lake-wave2-blocked` file triggers a halt on Wave 3+
if shadow-validate detects >15% divergence for any producer.

Status: ready to push. Will commit after Wave 1 PR merges (avoid stacking PRs on unmerged backend).
