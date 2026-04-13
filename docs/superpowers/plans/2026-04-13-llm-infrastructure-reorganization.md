# LLM Infrastructure Reorganization — Two-Node Strategy v2

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize LLM model allocation across Pro (48GB) and Air (16GB) to eliminate the Gemini 429 quota cascade, halve GPU RAM usage, and establish a resilient two-node model topology with clear roles.

**Architecture:** Ollama-first for all automation (zero cost, zero quota, zero internet dependency). Gemini CLI becomes last-resort fallback. Pro handles all inference. Air becomes a pure monitoring sentry with a micro-model. MLX backend enabled on Pro for 2x speed.

**Tech Stack:** Ollama 0.20.2+, OpenClaw, launchd, cell-core, backend-rag

**Informed by:** Web research (Ollama docs, GitHub issues, benchmarks), Gemini CLI review, DeepSeek Reasoner critique.

---

## Research Findings (verified 2026-04-13)

### Model Selection — Facts, Not Opinions

| Finding                                                                                                                                                                                         | Source                                                                                                                                                                                                                     | Impact on Plan                                                                                                         |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **qwen3.5:9b tool calling is BROKEN in Ollama** — XML/JSON format mismatch, prints calls instead of executing                                                                                   | [ollama/ollama#14493](https://github.com/ollama/ollama/issues/14493), [#14745](https://github.com/ollama/ollama/issues/14745), [llama.cpp#20837](https://github.com/ggml-org/llama.cpp/issues/20837)                       | Do NOT use qwen3.5 for tool-calling cron jobs                                                                          |
| **qwen3.5:9b is vastly superior to qwen3:8b on benchmarks** — Intelligence Index 32 vs 17, BFCL-V4 66.1 vs ~42, outperforms Qwen3-30B                                                           | [Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models), [ComputerTech](https://computertech.co/qwen-3-5-small-review-2026/)                                                                    | Use qwen3:8b ONLY because of Ollama tool-call bug. Upgrade to qwen3.5 when Ollama fixes template.                      |
| **qwen3:8b tool calling works** — Hermes-style JSON, stable in Ollama                                                                                                                           | [Ollama docs](https://docs.ollama.com/capabilities/tool-calling), [Qwen docs](https://qwen.readthedocs.io/en/latest/framework/function_call.html)                                                                          | Confirmed as cron primary (workaround, not ideal)                                                                      |
| **gemma4:12b does NOT exist** — Gemma 4 comes in e2b(7.2GB), e4b(9.6GB), 26b(18GB), 31b                                                                                                         | [ollama.com/library/gemma4/tags](https://ollama.com/library/gemma4/tags)                                                                                                                                                   | Translation stays on gemma4:e4b (9.6GB) or 26b                                                                         |
| **Ollama MLX on Pro = ~65-80 tok/s** (M4 Pro 273GB/s bandwidth, vs M4 Max 111 tok/s at 546GB/s). Requires >= 32GB. Air does NOT qualify. Only qwen3.5 + gemma4 have MLX support (Ollama 0.20+). | [Ollama blog](https://ollama.com/blog/mlx), [dev.to](https://dev.to/alanwest/ollama-just-got-93-faster-on-mac-heres-how-to-enable-it-3gce), [benchmark](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/) | Enable MLX on Pro. Air stays on Metal. Note: qwen3 (non-3.5) MLX support unconfirmed — may fallback to Metal silently. |
| **keep_alive=-1 does NOT survive Ollama restarts** — Runtime state only. Needs startup script to re-pin.                                                                                        | [ollama FAQ](https://docs.ollama.com/faq), [GitHub#5272](https://github.com/ollama/ollama/issues/5272)                                                                                                                     | Warm-pin LaunchAgent is mandatory                                                                                      |
| **keep_alive bug: API calls without explicit keep_alive reset the timer** — Fixed in PR #5447 but check version                                                                                 | [GitHub#5272](https://github.com/ollama/ollama/issues/5272)                                                                                                                                                                | All API calls must include explicit keep_alive parameter                                                               |
| **gemma4:26b uses 23GB with 262K context** — Not 17GB as estimated                                                                                                                              | Verified live: `ollama ps` on Pro                                                                                                                                                                                          | RAM budget must account for context expansion                                                                          |
| **Air has 87MB free pages on 16GB** — Already at memory pressure limit                                                                                                                          | Verified live: `vm_stat` on Air                                                                                                                                                                                            | Air CANNOT run a 4-5GB model warm. DeepSeek and Gemini both flagged this.                                              |
| **Qwen3.5-9B BFCL-V4 function calling: 66.1** — outperforms Qwen3-30B (42.4)                                                                                                                    | [ComputerTech review](https://computertech.co/qwen-3-5-small-review-2026/)                                                                                                                                                 | When Ollama fixes the template, qwen3.5 will be superior. For now, qwen3:8b.                                           |
| **Ollama memory fragmentation after 3-7 days continuous** — Gradual degradation, then crashes                                                                                                   | DeepSeek Reasoner critique                                                                                                                                                                                                 | Add weekly Ollama restart to maintenance schedule                                                                      |
| **Air M4 thermal throttling risk** — Fanless design, sustained inference causes latency spikes that look like model failures                                                                    | DeepSeek Reasoner critique                                                                                                                                                                                                 | Another reason Air should run only 1.5B micro-model, not 4-8B                                                          |
| **drain3 library** — Production-grade log template mining for incident clustering, no ML needed, pip installable                                                                                | [logpai/Drain3](https://github.com/logpai/Drain3)                                                                                                                                                                          | Better alternative to manual regex fingerprinting for incident correlation                                             |
| **LiteLLM config pattern** — Closest industry standard for centralized model routing with fallback chains                                                                                       | [LiteLLM docs](https://docs.litellm.ai/docs/proxy/reliability)                                                                                                                                                             | MODEL_TOPOLOGY.json follows same pattern (role-based, with fallbacks)                                                  |

### External Reviews Summary

**Gemini CLI (Senior Infra Architect perspective):**

- Air 16GB is a "critical failure point" — recommends downgrading to qwen2.5:1.5b or deepseek-r1:1.5b on Air
- Proposes "Sentry & Vault" topology — Air = read-only observer, Pro = all state and compute
- Incident correlation: Sliding Window Fingerprinting (normalize→hash→cluster by count in time window)
- Missing pieces: Dead Man's Switch heartbeat, Ollama load-shedding pre-flight, VRAM pre-warming
- MODEL_TOPOLOGY.json endorsed but needs "Health Overlay" via Redis for dynamic routing

**DeepSeek Reasoner (Critical review):**

- "Kill 50% of automations now. Be ruthless."
- Air should be pure monitoring with 2B model max — "not a production node"
- Warns about thermal throttling on fanless Air under sustained inference
- qwen3:8b "actually needs 12-14GB with context" — not just 8GB
- Suggests demand-based loading over time-based scheduling
- Flags clock skew risk between two machines running cron
- Recommends grouping automations into failure domains

---

## Current State (verified 2026-04-13)

### Full LLM Consumer Map — Pro

| Consumer                | Schedule    | Model                                        | RAM (actual) |
| ----------------------- | ----------- | -------------------------------------------- | ------------ |
| OpenClaw cron (24 jobs) | Various     | gemini-cli/flash -> gemma4:26b -> qwen3.5:9b | 0/23GB/9GB   |
| translate-articles.py   | Hourly :30  | gemma4:26b                                   | 23GB         |
| Sentinel classifier     | Every 5min  | claude-haiku-4-5 (API)                       | 0            |
| DLQ Autopilot           | Every 30min | claude --print (CLI)                         | 0            |
| Cell reasoner           | Continuous  | Tier 0: qwen3.5:9b / Tier 1: gemma4:26b      | 9/23GB       |
| Cell cortex             | On pulse    | qwen3.5:9b                                   | 9GB          |
| backend-rag FAST        | On demand   | qwen3.5:9b                                   | 9GB          |
| backend-rag KG/JSON     | On demand   | gemma4:26b                                   | 23GB         |
| backend-rag VISION      | On demand   | qwen2.5vl:7b                                 | ~5GB         |

### Full LLM Consumer Map — Air

| Consumer                | Schedule    | Model                                          | RAM (actual) |
| ----------------------- | ----------- | ---------------------------------------------- | ------------ |
| OpenClaw cron (12 jobs) | Various     | claude-opus-4-6 -> qwen3.5:27b (NOT INSTALLED) | 0            |
| Cell organism           | Continuous  | qwen3.5:9b (NOT INSTALLED)                     | 0            |
| Ollama test window      | 01:00-06:05 | qwen3.5:9b (NOT INSTALLED)                     | 0            |

**Air reality:** OpenClaw uses Claude Opus API (expensive), all Ollama fallbacks reference models that don't exist locally. Cell crashes on ModuleNotFoundError (fixed) but also can't reach any LLM.

---

## Target Architecture

### Design Principles (revised after external review)

1. **Ollama-first on Pro** — All inference happens on Pro. Period.
2. **Air = Sentry, not compute node** — Monitoring, health checks, alerting. Micro-model only (1.5B).
3. **MLX on Pro** — 2x inference speed for free (48GB >= 32GB requirement).
4. **Weekly Ollama restart** — Prevent memory fragmentation (3-7 day degradation cycle).
5. **Explicit keep_alive on every API call** — Prevent timer reset bug.
6. **Failure domains** — Group automations by shared dependencies, not just by schedule.
7. **Single MODEL_TOPOLOGY.json + Redis health overlay** — Static config + dynamic state.

### Model Allocation

#### Pro (48GB) — Warm Budget: ~10GB

| Slot             | Model              | RAM (with ctx)  | Warm?     | Role                                         |
| ---------------- | ------------------ | --------------- | --------- | -------------------------------------------- |
| **Cron primary** | `qwen3:8b` (NEW)   | ~10GB (32K ctx) | YES H24   | OpenClaw cron, cell cortex, backend-rag FAST |
| Translation      | `gemma4:e4b`       | ~10GB           | On-demand | translate-articles (replaces 26B)            |
| KG / JSON        | `gemma4:26b`       | ~23GB           | On-demand | backend-rag KG/JSON, cell Tier 1             |
| Vision           | `qwen2.5vl:7b`     | ~5GB            | On-demand | Unchanged                                    |
| Reasoning        | `deepseek-r1:32b`  | ~20GB           | On-demand | Unchanged                                    |
| **Last resort**  | `gemini-cli/flash` | 0               | Cloud     | Only if ALL Ollama models fail               |

**RAM math:** 10GB warm (qwen3:8b + 32K ctx) + 6GB OS = 16GB used. **32GB free** for on-demand loads.

#### Air (16GB) — Warm Budget: ~1.5GB

| Slot             | Model                                  | RAM    | Warm?   | Role                                              |
| ---------------- | -------------------------------------- | ------ | ------- | ------------------------------------------------- |
| **Sentry model** | `deepseek-r1:1.5b` (ALREADY INSTALLED) | ~1.5GB | YES H24 | Light triage, log analysis, health classification |
| **Last resort**  | `gemini-cli/flash`                     | 0      | Cloud   | Complex tasks only                                |

**RAM math:** 1.5GB warm + 6GB OS + 1GB PG + 1GB Redis + 1GB Ollama overhead = ~11GB. **5GB free** buffer. Safe.

**Air does NOT run:** qwen3:4b, qwen3:8b, gemma4:anything. No model > 2B. Air is a sentry, not a compute node.

---

## Implementation Plan

### Phase 1: Foundation (Tasks 1-3)

#### Task 1: Create MODEL_TOPOLOGY.json — Single Source of Truth

**Files:**

- Create: `MODEL_TOPOLOGY.json` (monorepo root)

- [ ] **Step 1: Create the topology file**

```json
{
  "_version": "2.0",
  "_updated": "2026-04-13",
  "_doc": "Single source of truth for all LLM model assignments. Every consumer reads this file. One change, one place.",
  "nodes": {
    "pro": {
      "hostname": "Nuzantara",
      "ram_gb": 48,
      "mlx_enabled": true,
      "warm_model": "qwen3:8b",
      "warm_keep_alive": "-1",
      "warm_ctx": 32768,
      "ollama_restart_schedule": "weekly sunday 05:00 WITA"
    },
    "air": {
      "hostname": "Nuzantara-9",
      "ram_gb": 16,
      "mlx_enabled": false,
      "warm_model": "deepseek-r1:1.5b",
      "warm_keep_alive": "-1",
      "warm_ctx": 4096,
      "ollama_restart_schedule": "weekly sunday 05:00 WITA"
    }
  },
  "roles": {
    "cron_primary": "qwen3:8b",
    "cron_fallback": "gemma4:e4b",
    "cloud_fallback": "google-gemini-cli/gemini-3-flash-preview",
    "translation": "gemma4:e4b",
    "kg_json": "gemma4:26b",
    "vision": "qwen2.5vl:7b",
    "reasoning": "deepseek-r1:32b",
    "fast": "qwen3:8b",
    "sentry": "deepseek-r1:1.5b",
    "code_review": "qwen3:8b",
    "cell_tier0": "qwen3:8b",
    "cell_tier1": "gemma4:26b"
  },
  "failure_domains": {
    "ollama_pro": [
      "cron_primary",
      "cron_fallback",
      "translation",
      "kg_json",
      "vision",
      "reasoning",
      "cell_tier0",
      "cell_tier1"
    ],
    "ollama_air": ["sentry"],
    "gemini_cloud": ["cloud_fallback"],
    "claude_cli": ["sentinel_classifier", "dlq_reasoning"]
  }
}
```

- [ ] **Step 2: Create Python loader utility**

Create `scripts/model_topology.py`:

```python
"""MODEL_TOPOLOGY.json loader — single import for all consumers."""
import json
import socket
from pathlib import Path

_TOPOLOGY_PATH = Path(__file__).parent.parent / "MODEL_TOPOLOGY.json"
_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(_TOPOLOGY_PATH.read_text())
    return _CACHE


def get_role(role: str) -> str:
    """Get model name for a role. E.g. get_role('cron_primary') -> 'qwen3:8b'"""
    return load()["roles"][role]


def get_node() -> dict:
    """Get config for current node based on hostname."""
    hostname = socket.gethostname()
    topo = load()
    for node_id, node in topo["nodes"].items():
        if node["hostname"] == hostname:
            return node
    raise ValueError(f"Unknown host: {hostname}")


def get_warm_model() -> str:
    """Get the warm model for current node."""
    return get_node()["warm_model"]
```

---

#### Task 2: Install models + enable MLX on Pro

- [ ] **Step 1: Pull qwen3:8b on Pro**

```bash
ollama pull qwen3:8b
```

- [ ] **Step 2: Enable MLX backend on Pro**

```bash
# Add to launchd environment for Ollama
launchctl setenv OLLAMA_MLX 1
# Restart Ollama to pick up MLX
brew services restart ollama
```

Verify MLX is active:

```bash
ollama run qwen3:8b --verbose <<< "ping" 2>&1 | grep -i "eval rate"
```

Expected: decode rate ~80-110 tok/s (vs ~40-50 without MLX).

- [ ] **Step 3: Pin qwen3:8b warm with keep_alive=-1**

```bash
# Also set env var for persistence
launchctl setenv OLLAMA_KEEP_ALIVE "-1"
# Load and pin
curl -s http://localhost:11434/api/generate -d '{"model": "qwen3:8b", "keep_alive": -1, "prompt": "warmup"}' > /dev/null
```

- [ ] **Step 4: Unload gemma4:26b from permanent warm**

```bash
curl -s http://localhost:11434/api/generate -d '{"model": "gemma4:26b", "keep_alive": 0}' > /dev/null
```

- [ ] **Step 5: Verify RAM freed**

```bash
ollama ps
```

Expected: Only qwen3:8b loaded, ~10GB GPU. gemma4:26b unloaded.

---

#### Task 3: Create warm-pin LaunchAgent (survives restarts)

**Files:**

- Create: `/Users/nuzantara/scripts/ollama-warm-pin.sh`
- Create: `~/Library/LaunchAgents/com.nuzantara.ollama-warm-pin.plist`

- [ ] **Step 1: Create warm-pin script**

```bash
#!/usr/bin/env bash
# Pin the designated warm model after Ollama starts.
set -euo pipefail

OLLAMA_URL="http://localhost:11434"
TOPOLOGY="/Users/nuzantara/Desktop/nuzantara/MODEL_TOPOLOGY.json"

# Wait for Ollama ready (max 60s)
for i in $(seq 1 60); do
    curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1 && break
    sleep 1
done

# Read warm model from topology
MODEL=$(python3 -c "import json; t=json.load(open('$TOPOLOGY')); import socket; h=socket.gethostname(); n=[v for v in t['nodes'].values() if v['hostname']==h][0]; print(n['warm_model'])")
CTX=$(python3 -c "import json; t=json.load(open('$TOPOLOGY')); import socket; h=socket.gethostname(); n=[v for v in t['nodes'].values() if v['hostname']==h][0]; print(n.get('warm_ctx', 4096))")

curl -s "$OLLAMA_URL/api/generate" \
    -d "{\"model\": \"$MODEL\", \"keep_alive\": -1, \"prompt\": \"warmup\", \"options\": {\"num_ctx\": $CTX}}" \
    > /dev/null 2>&1

echo "[$(date)] Pinned $MODEL warm (ctx=$CTX)"
```

- [ ] **Step 2: Create LaunchAgent plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.ollama-warm-pin</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/nuzantara/scripts/ollama-warm-pin.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/ollama-warm-pin.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/ollama-warm-pin.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
    </dict>
</dict>
</plist>
```

- [ ] **Step 3: Deploy on both nodes**

```bash
# Pro
chmod +x /Users/nuzantara/scripts/ollama-warm-pin.sh
launchctl load ~/Library/LaunchAgents/com.nuzantara.ollama-warm-pin.plist

# Air (copy and adapt paths)
scp /Users/nuzantara/scripts/ollama-warm-pin.sh air:~/scripts/
ssh air 'chmod +x ~/scripts/ollama-warm-pin.sh'
# Create Air plist with /Users/antonellosiano paths, then load
```

---

### Phase 2: Reconfigure Consumers (Tasks 4-9)

#### Task 4: Reconfigure OpenClaw Pro — Ollama primary

**Files:** `~/.openclaw/openclaw.json`

- [ ] **Step 1: Update agent model chains**

Both `main` and `coder` agents:

```json
{
  "primary": "ollama/qwen3:8b",
  "fallbacks": ["ollama/gemma4:e4b", "google-gemini-cli/gemini-3-flash-preview"]
}
```

- [ ] **Step 2: Add qwen3:8b model params**

```json
"ollama/qwen3:8b": {
  "params": {
    "temperature": 0.4,
    "top_p": 0.9,
    "top_k": 20,
    "num_ctx": 32768,
    "keep_alive": "-1"
  }
}
```

- [ ] **Step 3: Restart OpenClaw gateway and test**

```bash
launchctl kickstart -k gui/$(id -u)/ai.openclaw.gateway
# Test a job
openclaw cron run <daily-ops-job-id> --timeout 30000
```

---

#### Task 5: Reconfigure OpenClaw Air — Sentry mode

**Files:** Air `~/.openclaw/openclaw.json`

- [ ] **Step 1: Update Air agent model chains**

```json
"main": {
  "primary": "ollama/deepseek-r1:1.5b",
  "fallbacks": ["google-gemini-cli/gemini-3-flash-preview"]
},
"coder": {
  "primary": "ollama/deepseek-r1:1.5b",
  "fallbacks": ["google-gemini-cli/gemini-3-flash-preview"]
}
```

Remove qwen3.5:27b, qwen3.5:9b, claude-opus references — none of these are available or appropriate.

- [ ] **Step 2: Add deepseek-r1:1.5b model params**

```json
"ollama/deepseek-r1:1.5b": {
  "params": {
    "temperature": 0.3,
    "num_ctx": 4096,
    "keep_alive": "-1"
  }
}
```

- [ ] **Step 3: Restart Air OpenClaw + pin warm model**

```bash
ssh air 'launchctl kickstart -k gui/$(id -u)/ai.openclaw.node'
ssh air 'curl -s http://localhost:11434/api/generate -d "{\"model\": \"deepseek-r1:1.5b\", \"keep_alive\": -1, \"prompt\": \"warmup\"}" > /dev/null'
```

---

#### Task 6: Update Cell organism model references

**Files:**

- `apps/cell/cell/slow/reasoner.py:60-61`
- `apps/cell/cell/cortex/goal_generator.py:116`
- `apps/cell/cell/cortex/strategy_mutator.py:96`
- `apps/cell/cell/sensors/ollama_sensor.py:41`

- [ ] **Step 1: Update reasoner defaults**

```python
# Before:
ollama_model_fast: str = "qwen3.5:9b",
ollama_model_heavy: str = "gemma4:26b",
# After:
ollama_model_fast: str = "qwen3:8b",
ollama_model_heavy: str = "gemma4:26b",  # unchanged
```

- [ ] **Step 2: Update cortex defaults**

```python
# goal_generator.py and strategy_mutator.py
# Before:
ollama_model: str = "qwen3.5:9b",
# After:
ollama_model: str = "qwen3:8b",
```

- [ ] **Step 3: Update ollama_sensor expected models**

```python
# Before:
self._required = required_models or ["qwen3.5:9b", "gemma4:26b"]
# After:
self._required = required_models or ["qwen3:8b", "gemma4:26b"]
```

---

#### Task 7: Update backend-rag LLM config

**Files:** `apps/backend-rag/backend/llm/config.py:33`

- [ ] **Step 1: Change FAST model**

```python
# Before:
FAST = "qwen3.5:9b"
# After:
FAST = "qwen3:8b"
```

---

#### Task 8: Update translate-articles.py

**Files:** `scripts/translate-articles.py:25`

- [ ] **Step 1: Change default model**

```python
# Before:
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:26b")
# After:
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
```

gemma4:e4b (9.6GB on disk, ~10GB in RAM) is the same Gemma 4 family — MoE with 4.5B effective params, strong multilingual. Saves ~13GB RAM vs 26b.

---

#### Task 9: Retire qwen-code-review or align to warm model

**Files:** `scripts/qwen-code-review.sh`, `~/Library/LaunchAgents/com.nuzantara.qwen-code-review.plist`

- [ ] **Step 1: Change model to qwen3:8b (shares warm model = zero additional RAM)**

```bash
# In qwen-code-review.sh
# Before:
MODEL="qwen2.5-coder:32b-instruct-q4_K_M"
# After:
MODEL="qwen3:8b"
```

- [ ] **Step 2: Load the LaunchAgent if keeping**

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.qwen-code-review.plist
```

---

### Phase 3: Self-Healing Intelligence (Tasks 10-13)

#### Task 10: Incident Correlation in Sentinel

**Files:**

- Create: `scripts/sentinel_lib/incident_detector.py`
- Modify: `scripts/nuzantara-sentinel.py` (add incident detection after main loop)

**Algorithm: Sliding Window Fingerprinting** (Gemini recommendation, validated by research)
**Alternative: drain3** (`pip install drain3`) — production-grade log template mining library (logpai project). Builds a fixed-depth parse tree that clusters messages into templates in streaming fashion. No ML required. Consider for v2 if regex fingerprinting proves too coarse.

- [ ] **Step 1: Create incident detector module**

```python
"""Incident detector — groups related failures into single incidents.

Algorithm: Sliding Window Fingerprinting
1. Normalize: strip timestamps, hex IDs, PIDs from error messages
2. Fingerprint: MD5 hash of normalized string
3. Window: if same fingerprint appears N+ times within T minutes across different jobs,
   cluster into one incident
4. Report: "Incident #N: X jobs failing with 'Y' on Node:Z"
"""
import hashlib
import re
import time
from collections import defaultdict
from typing import Optional


# Normalization regexes — strip volatile parts of error messages
STRIP_PATTERNS = [
    (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*[Z]?", "TIMESTAMP"),  # timestamps
    (r"0x[0-9a-fA-F]+", "HEX"),  # hex addresses
    (r"PID[= ]\d+", "PID"),  # process IDs
    (r"pid=\d+", "PID"),
    (r"port[= ]\d+", "PORT"),  # ports
    (r"consecutiveErrors=\d+", "consecutiveErrors=N"),  # error counts
    (r"attempt \d+/\d+", "attempt N/M"),  # retry counts
]

# Minimum cluster size to create an incident (not N individual DLQ entries)
MIN_CLUSTER_SIZE = 3
# Time window for clustering (seconds)
WINDOW_S = 600  # 10 minutes


def normalize_error(error: str) -> str:
    """Strip volatile parts from error message for fingerprinting."""
    result = error
    for pattern, replacement in STRIP_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result.strip()


def fingerprint(error: str) -> str:
    """MD5 hash of normalized error."""
    normalized = normalize_error(error)
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def detect_incidents(failures: list[dict], window_s: int = WINDOW_S) -> list[dict]:
    """Group failures into incidents.

    Args:
        failures: list of {"job": str, "error": str, "ts": float}

    Returns:
        list of incidents: {"fingerprint": str, "normalized_error": str,
                           "jobs": list[str], "count": int, "first_ts": float}
    """
    now = time.time()
    recent = [f for f in failures if now - f.get("ts", 0) < window_s]

    clusters: dict[str, dict] = {}
    for f in recent:
        err = f.get("error", "")
        if not err or len(err) < 10:
            continue
        fp = fingerprint(err)
        if fp not in clusters:
            clusters[fp] = {
                "fingerprint": fp,
                "normalized_error": normalize_error(err),
                "jobs": [],
                "count": 0,
                "first_ts": f.get("ts", now),
            }
        clusters[fp]["jobs"].append(f.get("job", "?"))
        clusters[fp]["count"] += 1

    # Only return clusters with MIN_CLUSTER_SIZE+ members
    return [c for c in clusters.values() if c["count"] >= MIN_CLUSTER_SIZE]
```

- [ ] **Step 2: Integrate into Sentinel main loop**

In `nuzantara-sentinel.py`, after `process_job()` loop, add:

```python
from sentinel_lib.incident_detector import detect_incidents

# After processing all jobs, check for correlated failures
failures_this_run = [
    {"job": j, "error": err, "ts": time.time()}
    for j, err in current_failures.items()
]
incidents = detect_incidents(failures_this_run)
for incident in incidents:
    n = incident["count"]
    jobs = ", ".join(incident["jobs"][:5])
    err = incident["normalized_error"][:100]
    logger.warning(f"INCIDENT: {n} jobs failing with same root cause: {err} | Jobs: {jobs}")
    send_alert(f"🔥 Incident: {n} jobs failing\n{err}\nJobs: {jobs}")
    # Create ONE DLQ entry for the incident, not N individual entries
```

---

#### Task 11: Dead Man's Switch (Pro -> Air heartbeat)

**Files:**

- Create: `scripts/deadman-heartbeat.sh`
- Create: `~/Library/LaunchAgents/com.nuzantara.deadman-heartbeat.plist` (Pro)
- Air: cron job to check heartbeat

- [ ] **Step 1: Pro heartbeat writer (every 30s)**

```bash
#!/usr/bin/env bash
# Write timestamp to a file that Air monitors
echo "$(date +%s)" > /tmp/pro_heartbeat
# Also write to Redis for Air to read
redis-cli -h localhost SET pro:heartbeat "$(date +%s)" EX 120 > /dev/null 2>&1
```

- [ ] **Step 2: Air heartbeat checker (cron every 2min)**

```bash
#!/usr/bin/env bash
# Check Pro heartbeat via Redis (Pro writes, Air reads)
LAST=$(ssh -o ConnectTimeout=3 pro 'cat /tmp/pro_heartbeat 2>/dev/null' || echo "0")
NOW=$(date +%s)
AGE=$((NOW - LAST))
if [ "$AGE" -gt 300 ]; then
    # Pro hasn't heartbeat in 5 min — alert
    curl -s -m 10 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_ADMIN_CHAT_ID}" \
        -d "text=🚨 DEADMAN: Pro non risponde da ${AGE}s. Ultimo heartbeat: $(date -r $LAST '+%H:%M:%S')" > /dev/null
fi
```

---

#### Task 12: Sentinel Self-Measurement

**Files:** Modify `scripts/sentinel_lib/alerter.py` or create `scripts/sentinel_lib/metrics.py`

- [ ] **Step 1: Add metrics tracking**

Track per Sentinel run:

- Jobs checked, jobs failed, jobs recovered (OPEN->CLOSED)
- Incidents detected (from Task 10)
- Auto-heal attempts and successes

```python
"""Sentinel self-measurement — Pillar 7: Numeri Prima."""
import json
import time
from pathlib import Path

METRICS_FILE = Path.home() / ".agent" / "decisions" / "sentinel_metrics.json"


def load_metrics() -> dict:
    try:
        return json.loads(METRICS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"runs": 0, "total_failures": 0, "total_recoveries": 0,
                "auto_heal_attempts": 0, "auto_heal_successes": 0,
                "incidents_detected": 0, "history": []}


def record_run(checked: int, failed: int, recovered: int,
               auto_heal_ok: int, auto_heal_fail: int, incidents: int) -> None:
    m = load_metrics()
    m["runs"] += 1
    m["total_failures"] += failed
    m["total_recoveries"] += recovered
    m["auto_heal_attempts"] += auto_heal_ok + auto_heal_fail
    m["auto_heal_successes"] += auto_heal_ok
    m["incidents_detected"] += incidents
    # Keep last 100 runs for MTTR calculation
    m["history"].append({
        "ts": time.time(), "checked": checked, "failed": failed,
        "recovered": recovered, "auto_heal_ok": auto_heal_ok,
    })
    m["history"] = m["history"][-100:]
    # Compute rolling stats
    if m["auto_heal_attempts"] > 0:
        m["auto_heal_success_pct"] = round(
            m["auto_heal_successes"] / m["auto_heal_attempts"] * 100, 1)
    if m["runs"] > 0:
        m["avg_failures_per_run"] = round(m["total_failures"] / m["runs"], 2)
    tmp = str(METRICS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(m, indent=2))
    Path(tmp).replace(METRICS_FILE)
```

---

#### Task 13: Weekly Ollama restart (prevent memory fragmentation)

**Files:**

- Add cron entry on Pro and Air

- [ ] **Step 1: Add weekly restart to Pro crontab**

```bash
# Sunday 05:00 WITA — restart Ollama and re-pin warm model
0 5 * * 0 brew services restart ollama && sleep 10 && /Users/nuzantara/scripts/ollama-warm-pin.sh >> /Users/nuzantara/logs/ollama-warm-pin.log 2>&1
```

- [ ] **Step 2: Same on Air**

```bash
ssh air 'crontab -l > /tmp/crontab_bak && (crontab -l; echo "0 5 * * 0 brew services restart ollama && sleep 10 && ~/scripts/ollama-warm-pin.sh >> ~/logs/ollama-warm-pin.log 2>&1") | crontab -'
```

---

### Phase 4: Cleanup (Tasks 14-16)

#### Task 14: Reset all circuit breakers

- [ ] **Step 1: Reset OPEN/TERMINAL circuits to HALF_OPEN after model changes are live**

```bash
python3 -c "
import json, time
cb_path = '$HOME/.agent/decisions/circuit_breakers.json'
cb = json.load(open(cb_path))
reset = 0
for job, data in cb.items():
    if data.get('state') in ('OPEN', 'TERMINAL'):
        data['state'] = 'HALF_OPEN'
        data['failures'] = 0
        data['phase'] = 'T0'
        data['phase_updated_at'] = time.time()
        reset += 1
import os; tmp = cb_path+'.tmp'
with open(tmp,'w') as f: json.dump(cb,f,indent=2)
os.replace(tmp, cb_path)
print(f'Reset {reset} circuits to HALF_OPEN')
"
```

- [ ] **Step 2: Clear DLQ OpenClaw entries (root cause fixed)**

```bash
python3 -c "
import json, os
dlq_path = '$HOME/.agent/decisions/dlq.json'
dlq = json.load(open(dlq_path))
q = dlq.get('queue', [])
keep = [e for e in q if 'OpenClaw' not in e.get('error_summary','')]
tmp = dlq_path+'.tmp'
with open(tmp,'w') as f: json.dump({'queue':keep},f,indent=2)
os.replace(tmp, dlq_path)
print(f'DLQ: {len(q)} -> {len(keep)}')
"
```

---

#### Task 15: Remove Air Ollama cron window

The window (01:00-06:05) is obsolete — Air Ollama runs H24 with deepseek-r1:1.5b pinned.

- [ ] **Step 1: Remove ollama_cron_window entries from Air crontab**

```bash
ssh air 'crontab -l > /tmp/crontab_bak.txt'
# Edit to remove ollama start/stop entries
```

---

#### Task 16: Automation Audit — Kill Zombies

This is a decision task for Zero, not an automated step.

- [ ] **Step 1: Generate audit list**

```bash
python3 -c "
import json
reg = json.load(open('$HOME/.agent/decisions/job_registry.json'))
cb = json.load(open('$HOME/.agent/decisions/circuit_breakers.json'))
jobs = reg.get('jobs', {})
print(f'Total registered jobs: {len(jobs)}')
print()
print('=== CANDIDATES FOR DECOMMISSION ===')
for name, data in sorted(jobs.items()):
    cb_data = cb.get(name, {})
    failures = cb_data.get('failures', 0) + len(cb_data.get('_failure_timestamps', []))
    critical = data.get('critical', False)
    scope = data.get('repair_scope', '?')
    if failures > 20 and not critical:
        print(f'  {name:35s} failures={failures:3d} scope={scope:10s} CANDIDATE (high failure, non-critical)')
"
```

- [ ] **Step 2: For each candidate, answer the 5 VADEMECUM questions**

1. Does this code know where it is in the organism?
2. Does it produce something that persists?
3. If it fails, does the organism continue?
4. Has it respected documented scars?
5. Will it be measurable in a month?

If >= 3 answers are "no" -> decommission.

---

## Verification Checklist

After all phases complete:

- [ ] `ollama ps` on Pro: qwen3:8b warm, MLX active (check tok/s > 80)
- [ ] `ssh air 'ollama ps'`: deepseek-r1:1.5b warm, nothing else
- [ ] OpenClaw Pro test job uses qwen3:8b (check logs for model name)
- [ ] OpenClaw Air test job uses deepseek-r1:1.5b
- [ ] `MODEL_TOPOLOGY.json` exists at monorepo root, valid JSON
- [ ] translate-articles.py runs with gemma4:e4b (check log)
- [ ] Cell organism on Pro completes pulse without error
- [ ] All circuit breakers recover to CLOSED within 2 Sentinel cycles
- [ ] `AUTOMATIONS_REFERENCE.md` regeneration shows 0 FAILED OpenClaw jobs
- [ ] sentinel_metrics.json is being written after each run

---

## Before/After Metrics

| Metric                    | Before                                 | After                           |
| ------------------------- | -------------------------------------- | ------------------------------- |
| Pro warm GPU RAM          | 23GB (gemma4:26b+ctx)                  | ~10GB (qwen3:8b+32K ctx)        |
| Air warm GPU RAM          | 0 (models not installed)               | ~1.5GB (deepseek-r1:1.5b)       |
| Pro free RAM for dev      | 19GB                                   | 32GB (+68%)                     |
| Air free RAM buffer       | ~0 (memory pressure!)                  | ~5GB (safe)                     |
| Pro inference speed       | ~45 tok/s (Metal)                      | ~90-110 tok/s (MLX, 2x)         |
| Internet dependency       | Primary (Gemini CLI)                   | Last-resort only                |
| Circuit breakers OPEN     | 13                                     | 0 (target)                      |
| DLQ entries               | 14                                     | 0 (target)                      |
| OpenClaw failures         | 13/24 jobs                             | 0/24 (target)                   |
| Gemini quota risk         | HIGH (24 jobs \* every few hours)      | NEAR-ZERO (local primary)       |
| Tool calling reliability  | Broken (qwen3.5 XML/JSON bug)          | Working (qwen3 Hermes JSON)     |
| Model config locations    | 8 files to update                      | 1 (MODEL_TOPOLOGY.json)         |
| Incident correlation      | None (13 DLQ entries for 1 root cause) | Fingerprint clustering          |
| Sentinel self-measurement | None                                   | MTTR, auto-heal %, failure rate |
| Ollama memory stability   | Degrades after 3-7 days                | Weekly restart scheduled        |
| Pro/Air heartbeat         | None                                   | Dead Man's Switch every 30s     |

---

_Version: 2.0 — 2026-04-13_
_Author: Claude Opus 4.6 + Zero_
_Informed by: Web research (Ollama docs, GitHub issues, Apple Silicon benchmarks), Gemini CLI architectural review, DeepSeek Reasoner critical analysis_
