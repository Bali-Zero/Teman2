# 7 Leggi admission test rubric

Each cell candidate is evaluated against the 7 immutable Symbiosis laws
before being promoted from "automation" to "cell". The runtime check lives
in `packages/cell-core/cell_core/admission_test.py`; this doc is the
*human* rubric — pass and fail examples per Legge — that the runtime check
codifies.

A cell PASSES iff zero blocker violations across all 7 laws.

## YAML template (cell-candidate definition)

A cell candidate is a plain dict (or YAML doc) with the following fields:

```yaml
name: system-doctor-cell        # short slug, kebab-case
level: L1                       # cognitive level: L0, L1, L2, L3, L4, L4.5
exposes_gui: false              # Law 1
llm_invocation: ollama          # Law 1: cli | oauth_cli | ollama | deepseek_api | none
external_sources:               # Law 2: list of upstream feed names
  - fly-api
client_data_access: false       # Law 2: does the cell read client PII?
publishes_via: pg_notify        # Law 3: pg_notify | pg_trigger | consumer_only | none
fallback_modes:                 # Law 4: ≥1 declared
  - redis_down
  - llm_provider_down
kill_switch: true               # Law 5
auto_publishes: false           # Law 5: never auto-publish externally without human
depends_on_other_cell_decisions: false  # Law 6
metrics:                        # Law 7: ≥3 metrics
  - ttr
  - error_rate
  - throughput
```

## Law-by-law rubric

### Legge 1 — CLI-only (no paid HTTP API)

Each LLM invocation must go through the CLI subprocess for Claude (which
consumes Max-plan OAuth quota), or local Ollama, or DeepSeek API
(documented exception). The Anthropic Python SDK is forbidden.

**PASS example:**
```yaml
exposes_gui: false
llm_invocation: cli   # claude --print, gemini --print, codex exec, etc.
```

**FAIL example:**
```yaml
exposes_gui: true     # ← cell exposes UI; Law 1 is headless-only
```

**Why:** Antonello holds 3 Claude Max plans. Paying per-token via
`ANTHROPIC_API_KEY` doubles a flat sub he already pays. The CLI path
sidesteps this. GUI exposure also tends to drag in client SDKs.

### Legge 2 — OSINT blindato

Intelligence-source data does NOT leave Pro. A cell must NOT mix
external (OSINT) sources with client PII access.

**PASS example:**
```yaml
external_sources: [fly-api]      # infra metric, not OSINT
client_data_access: true         # OK — no OSINT mixing
```

**PASS example 2:**
```yaml
external_sources: [intel-scraper]  # OSINT
client_data_access: false          # OK — no client mixing
```

**FAIL example:**
```yaml
external_sources: [intel-scraper, exa-research]  # OSINT
client_data_access: true                          # ← client PII present
# → blocker: contamination of client facts with unverified intelligence
```

**Why:** UU PDP scope. Bali Zero clients trust Pro to handle their NPWP/
NIB/passport without leaking it into intelligence pipelines that go to
NotebookLM/external feeds.

### Legge 3 — Event-driven

IPC between cells uses PostgreSQL LISTEN/NOTIFY (today's substrate, with
events_outbox durability layer). No filesystem polling, no Redis Streams,
no in-memory queues.

**PASS example:**
```yaml
publishes_via: pg_notify     # explicit, e.g. via outbox.publish()
```

**PASS example 2:**
```yaml
publishes_via: pg_trigger    # writes to a table whose AFTER trigger emits NOTIFY
```

**PASS example 3:**
```yaml
publishes_via: consumer_only # cell only LISTENs, doesn't produce
```

**FAIL example:**
```yaml
publishes_via: filesystem    # ← downstream consumer must poll. Bad.
# → blocker: violates Law 3
```

**Why:** PG LISTEN/NOTIFY (with the events_outbox replay path post PR #342)
is durable enough that consumer disconnects don't lose events. Filesystem
polling has no such guarantee.

### Legge 4 — Graceful degradation

When a dependency fails, the cell must continue operating in a
documented degraded mode. Empty `fallback_modes` blocks promotion.

**PASS example:**
```yaml
fallback_modes:
  - llm_provider_down   # falls back to deterministic heuristic
  - redis_down          # in-memory cache is fine for an hour
  - postgres_down       # cell rolls back the transaction and emits an alert
```

**FAIL example:**
```yaml
fallback_modes: []       # ← no degradation paths declared
# → blocker: Law 4 requires resilience by design
```

**Why:** "L'organismo è resiliente per design, non per eccezione."

### Legge 5 — Zero come ultima istanza

Structural decisions go through Zero (the human owner). At the cell level
that means: (a) every cell has a kill switch the operator can flip, and
(b) no externally-visible publish happens without human review.

**PASS example:**
```yaml
kill_switch: true
auto_publishes: false   # Telegram review gate or Lobster approval
```

**FAIL example A — no kill switch:**
```yaml
kill_switch: false      # ← operator can't stop a misbehaving cell mid-flight
```

**FAIL example B — auto-publishes:**
```yaml
kill_switch: true
auto_publishes: true    # ← ships content to clients without a human review
```

**Why:** Cell propose; Zero (or human delegate via Telegram) decides.
The cell-organism Trend → Consiglio → Drafter → Validator → Telegram
review gate is the canonical pattern.

### Legge 6 — Local sovereignty

Each cell is an independent decisional unit. Reading another cell's
data is fine; depending on its REASONING is not — that turns the
"dependent" cell into an organelle of the "decisional" one.

**PASS example:**
```yaml
depends_on_other_cell_decisions: false
# Cell may read intel_event payloads but its own logic decides outcomes
```

**FAIL example:**
```yaml
name: oracle-bypass-attempt
depends_on_other_cell_decisions: true
# ← cell takes oracle L4's verdict and acts on it without independent judgment
# → blocker: re-classify as oracle organelle, not standalone cell
```

**Why:** This is exactly the DeepSeek round-2 risk callout
"Oracle/WR2 SPOF decisionale": if oracle-L4's verdict is the input
to another cell's reasoning, that cell stops being autonomous.

### Legge 7 — Numbers first

Every cell must declare ≥3 metrics so its before/after performance can
be measured. "If it has no metric, it's not an improvement."

**PASS example:**
```yaml
metrics:
  - ttr             # time to resolution
  - error_rate
  - throughput
```

**PASS example 2 (also fine):**
```yaml
metrics:
  - confidence_self
  - confidence_observer
  - retry_count
  - p99_latency_ms
```

**FAIL example:**
```yaml
metrics: [ttr]      # ← only 1 metric
# → blocker: Law 7 requires ≥3 measurable signals
```

**Why:** Symbiosis Law 7 demands quantitative justification for any
evolution. A cell with 1 metric can game it. With 3+, gaming gets harder.

## Two complete examples

### Passing — HGT coordinator (propose-only quarantine, Sprint 1 candidate)

```yaml
name: hgt-coordinator
level: L2
exposes_gui: false
llm_invocation: cli
external_sources: []           # operates on internal Genome, not OSINT
client_data_access: false
publishes_via: pg_notify       # emits propose-only events
fallback_modes:
  - llm_provider_down
  - redis_down
  - cell_observatory_down
kill_switch: true
auto_publishes: false           # propose-only; humans/cells review before merge
depends_on_other_cell_decisions: false
metrics:
  - propose_count
  - merge_acceptance_rate
  - false_positive_rate
  - p99_latency_ms
```

Result: PASS — all 7 laws clean. Note: confidence threshold ≥0.7 + ≥10
uses gate is enforced inside the cell, not at admission time.

### Failing — naive "oracle L4 cell" (DeepSeek round-2 example)

```yaml
name: oracle-l4-standalone
level: L4
exposes_gui: false
llm_invocation: cli
external_sources: [intel-scraper, exa-research]   # OSINT
client_data_access: true                          # mixes — Law 2 fail
publishes_via: filesystem                         # writes JSON to disk — Law 3 fail
fallback_modes: []                                # Law 4 fail
kill_switch: false                                 # Law 5 fail
auto_publishes: true                              # Law 5 fail
depends_on_other_cell_decisions: false
metrics:
  - run_count
```                                                 # Law 7 fail (only 1 metric)

Result: FAIL — 6 blocker violations. Right classification: organelle inside
war-room-organism (per round-2 99b_synthesis_v2.md verdict, not a
free-standing cell).

## How to run the test

```python
from cell_core.admission_test import AdmissionTest

cell = {  # load from YAML or define inline
    "name": "system-doctor-cell",
    "level": "L1",
    "exposes_gui": False,
    "llm_invocation": "ollama",
    "external_sources": ["fly-api"],
    "client_data_access": False,
    "publishes_via": "pg_notify",
    "fallback_modes": ["redis_down", "llm_provider_down"],
    "kill_switch": True,
    "auto_publishes": False,
    "depends_on_other_cell_decisions": False,
    "metrics": ["ttr", "error_rate", "throughput"],
}

result = AdmissionTest().run_all(cell)
print(result.summary())
```

Output:

```
=== Admission test for cell 'system-doctor-cell': PASS ===
  (no violations)
```

## Tests

`packages/cell-core/tests/test_admission.py` — 9 tests covering: passing
cell, GUI block, OSINT contamination, filesystem-publish block, dependency
on other cell decisions, <3 metrics, no kill switch, no fallbacks, and
summary formatting (PASS + FAIL).

## References

- `packages/cell-core/cell_core/admission_test.py` (runtime check)
- `packages/cell-core/tests/test_admission.py` (9 tests)
- `SYMBIOSIS.md` (the 7 immutable laws — DNA helix)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/05_cell_architecture_complete.md`
  (cognitive levels L0-L4.5)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md`
  § "Codex disagreement on flat promotion"
