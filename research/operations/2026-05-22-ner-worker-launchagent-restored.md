---
date: 2026-05-22
domain: operations
client_case: NB automations hardening — W6 NER worker resurrection
sources: 5
---

# NER worker LaunchAgent restored — closes W4/W5/W6 chain

## Context

Loop iteration 6 of NB-automations hardening (after W1+W2+W3+W4+W5). W4
discovered `kg-linker` had `entities_total: 0` for months (614 dead runs vs
22 non-idle runs). W5 discovered Redis consumer-group `ner` on
`garuda:enriched` had lag=1403 + pending=45 + consumer idle=2745190111ms
(~31.8 days). W6 closes the chain: the NER worker library AND runner script
exist, what was missing was the LaunchAgent triggering it.

## Empirical evidence — pre-fix (2026-05-22 05:00 WITA)

| Stream | Group | Pending | Lag | Consumer Idle |
|---|---|---|---|---|
| garuda:enriched | ner | 45 | 1403 | **31.8 days** |

Consumer name `ner-1`, single instance, last activity ~31 days ago. The
script `scripts/run_ner_worker.py` exists and is correct:

```python
from mata_garuda.workers.ner_worker import run_ner
# drains in batches of 20, cap 200/run via Ollama qwen3.5:9b
```

`ls ~/Library/LaunchAgents/ | grep ner` → empty. `~/scripts/` had no
matagaruda-ner-worker.sh wrapper. The infrastructure existed at the library
+ script level but was never wired into launchd.

## Fix shipped

1. **Wrapper script**: `~/scripts/matagaruda-ner-worker.sh` (33 lines, zsh
   `set -e`, TCC-safe — calls `.venv/bin/python` directly, adhoc-signed
   binaries bypass macOS TCC). Loads `~/.nuzantara-secrets.env` (no quoting
   trap — NER needs only OLLAMA_HOST, no FLY tokens which carry the
   whitespace bug from cell `.env` cicatrix 2026-05-22).
2. **LaunchAgent**: `~/Library/LaunchAgents/com.matagaruda.ner.adaptive.plist`,
   `StartInterval=300` (5min cadence — slower than bridge 60s because NER
   is LLM-heavy). Logs to `~/logs/matagaruda-ner-worker.{log,err}`. Loaded
   via `launchctl bootstrap gui/$(id -u)`. State `not running, last exit code
   = (never exited), run interval = 300 seconds` post-bootstrap.
3. **Smoke test**: manually invoked wrapper, qwen3.5:9b loaded into Ollama
   memory (visible via `ollama ps`), NER consumer started draining the 1403
   message lag. Verified Redis XINFO GROUPS lag drops from 1403→1076 within
   first 5 minutes.

## Cron schedule

| Cadence | Action |
|---|---|
| 5min | NER worker drains batch of ~200 messages from `garuda:enriched` |
| 1h | KG-linker (existing cron `com.matagaruda.kg-linker`) consumes the freshly-enriched items now carrying `entities` field |

## Expected impact on W4 chain

After 24h:
- `garuda:enriched` lag for `ner` group should be **<100** (drainage rate
  ~200 entries / 5min)
- `kg-linker` runs should start showing `entities_total > 0` and
  `kg_entities` count in KnowledgeGraph SQLite should grow beyond 6
- W4 dead-upstream sidecar `~/.agent/decisions/kg-linker-dead-upstream-runs.json`
  should self-delete on the first healthy run
- W5 lag monitor (`scripts/check_consumer_lag.py`) should stop alerting on
  `ner` group

## Verification commands

```bash
# After 24h
redis-cli XINFO GROUPS garuda:enriched | grep -A4 "^ner$"
launchctl print "gui/$(id -u)/com.matagaruda.ner.adaptive" | grep -E "last exit|launched|state"
tail -20 ~/logs/matagaruda-ner-worker.log
python /Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/scripts/check_consumer_lag.py
```

## Sources

1. `mata_garuda/workers/ner_worker.py` — library implementation (qwen3.5:9b, dead-letter retry pattern)
2. `scripts/run_ner_worker.py` — runner (cap 10×20 = 200 messages per invocation)
3. `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist` — pattern reference for TCC-safe plist
4. `~/scripts/matagaruda-bridge.sh` — pattern reference for TCC-safe wrapper
5. Empirical XINFO GROUPS / XINFO CONSUMERS output 2026-05-22 05:00-05:30 WITA
