# ADR-006: nb_monitor bootstrap JSON registry, migrate to notebook_registry post-FASE-2

**Status:** Accepted (2026-05-07)
**Authors:** Antonello Siano (Zero), Claude Opus 4.7
**Related:** spec `2026-05-07-nb-mitochondrial-monitor-design.md`

## Context

FASE 5 (NB Mitochondrial Value Monitor) needs a list of "active" notebook UUIDs to iterate per cron run. FASE 2 (SENESCENT decommissioning, separate session) is concurrently building `apps/mata-garuda/mata_garuda/notebook_registry.py` as the SSOT for NB classification (`active_routing`, `lifecycle_stage`, `family`, etc.).

Two scope conflicts:

1. FASE 5 cannot wait for FASE 2 to land — they're independent. Need a registry NOW.
2. We do NOT want two registries permanently — drift would compound across PRs.

## Decision

For this PR, FASE 5 reads from `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` (NOT git-tracked, lives on Pro disk). Schema mirrors what FASE 2 will publish in `notebook_registry.py`. The bootstrap file is hand-curated from `apps/mata-garuda/mata_garuda/config.py::NLM_NOTEBOOKS` (6 UUIDs) plus 1 manually added Property NB; further entries to be added as FASE 2 produces classification data.

`registry.py::load_registry` is written so that — once `notebook_registry.py` exists — a future PR can swap the loader to:

```python
try:
    from mata_garuda.notebook_registry import NB_REGISTRY
    return _from_registry_dict(NB_REGISTRY)
except ImportError:
    return load_from_bootstrap_json(BOOTSTRAP_FILE)
```

…without changing any callsite.

JSON instead of YAML to avoid adding `pyyaml` to `apps/mata-garuda/pyproject.toml` deps (mata-garuda venv is intentionally minimal: `pydantic`, `pytest`, `pytest-asyncio`).

## Consequences

- Two registry sources transiently coexist for ≤7 days post FASE-2 merge.
- A follow-up PR (`feat(nb-monitor): consume notebook_registry SSOT`) will:
  1. Update `registry.py::load_registry` to prefer the import path.
  2. Add a deprecation warning (one log line, info-level) when the bootstrap JSON is used.
  3. After 14 days of clean runs against the SSOT, delete the bootstrap JSON.
- Drift risk during the transition: if someone adds an NB to the bootstrap JSON manually but not to `notebook_registry.py`, the cron logs a WARN at the next run (`registry: <uuid> in bootstrap but missing in SSOT`). No silent divergence.

## Alternatives considered

- **Block this PR until FASE 2 ships.** Rejected: FASE 2 and FASE 5 deliver value independently; blocking is sequential coupling without reason.
- **Read from `config.py NLM_NOTEBOOKS` only (6 UUIDs).** Rejected: 6/60+ is too narrow — produces a partial mitochondrial picture. The bootstrap JSON adds CORE/RESEARCH NBs that `NLM_NOTEBOOKS` does not contain.
- **YAML format.** Rejected: pyyaml is a 1-MB dep added solely for human readability. JSON is human-readable enough for a 7-NB file and is part of stdlib.
- **Live MCP `nlm notebook list`.** Rejected: cookie 5min TTL makes this fragile for daily cron. Cookie expiry would result in NULL metrics for every UUID daily.
