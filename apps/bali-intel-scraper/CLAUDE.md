# Bali Intel Scraper — Non-Inferable Knowledge

> Archive: `docs/sessions/CLAUDE-archive-2026-04-06.md`

---

## Critical Patterns

### Centralized Logging
```python
from scripts.utils.logging_config import setup_logging, get_logger
logger = get_logger(__name__)

# Context manager for correlation
with correlation_context(job_id="nightly-001"):
    logger.info("Processing started", extra={"articles": count})
```

Rotation: 100MB per file. Never log full data objects.

### Metrics Module
```python
from scripts.utils.metrics import MetricsCollector
mc = MetricsCollector()

with mc.track_latency("llm_call_ms"):
    result = await llm.generate(prompt)

mc.increment("articles_processed")
mc.set_gauge("dedup_filtered", filtered_count)
```

Metric names use `_ms` suffix for latencies. Counters: `articles_input`, `articles_processed`, `dedup_filtered`.

---

## Deployment

- Runs LOCALLY on Pro via OpenClaw (03:00 WITA cron), NOT on Fly.io
- Sentinel bridge checks every 5min via `intel-scraper-sentinel-bridge.sh`
- Status written to `~/.agent/decisions/state/intel_scraper.last.json`

## Test Commands

```bash
pytest --cov=scripts --cov-report=html
pytest tests/unit/ -q --tb=short
```
