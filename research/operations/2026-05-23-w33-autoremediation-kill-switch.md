---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W33 CELL_AUTOREMEDIATION_ENABLED operator kill switch (W27 panel Codex non-negotiable)
sources: 3
---

# W33 — CELL_AUTOREMEDIATION_ENABLED kill switch

## Why

W27 4-LLM panel (Codex+Gemini+DeepSeek) flagged as Codex non-negotiable: operator must have a fast off-switch for the auto-heal chain (Cell sustained_red → Organism → fly_machines_restart) without ssh+grep+kill workflow.

When auto-heal misbehaves (restart loop, wrong actuator, false-positive red), the operator should be able to flip ONE env var and have the chain disarm on the next pulse cycle — no Cell daemon restart, no fly ssh, no chasing PIDs.

## Implementation (commit `2eeccee93`)

### Helper function — `apps/cell/cell/core/pulse.py`

```python
def _autoremediation_enabled() -> bool:
    import os
    val = os.environ.get("CELL_AUTOREMEDIATION_ENABLED", "").strip().lower()
    return val not in {"false", "0", "no", "off", "disabled"}
```

Reads env each invocation (no cache). Operator can flip the flag without restarting Cell — next pulse cycle (60s) sees new state.

### Gate at emit site

```python
if (self._red_streak >= SUSTAINED_RED_THRESHOLD
        and not self._sustained_red_emitted):
    if not _autoremediation_enabled():
        logger.warning(
            "W33 kill switch active "
            "(CELL_AUTOREMEDIATION_ENABLED=false): "
            f"would emit sustained_red (streak={self._red_streak}) "
            "but suppressed by operator override"
        )
        self._sustained_red_emitted = True
    else:
        # ... original W27 path A emit code unchanged
```

Idempotency flag set even when suppressed so the WARNING log doesn't spam during the same red window.

### Default-ON discipline

The chain has been validated end-to-end (W27 + W31 live test 2026-05-23). Defaulting OFF would silently disarm new deployments where someone forgets to set the var. Explicit opt-out is safer than default-out.

Disabled values (case-insensitive, whitespace-trimmed): `false`, `0`, `no`, `off`, `disabled`. Everything else → enabled.

## Tests — `apps/cell/tests/test_w33_autoremediation_kill_switch.py`

23/23 PASS in 0.11s:

- `test_default_enabled_when_unset` — env unset → True
- `test_explicit_true_enabled` — "true" → True
- `test_empty_string_enabled` — "" → True (default-on)
- `test_disabled_values` (parametrized 11 variants): all False
- `test_active_values` (parametrized 7 variants): all True (including unknown→default-on)
- `test_no_caching_between_calls` — alternating sequence proves env is re-read each call

## Operator usage

To disable auto-heal:

```bash
echo "CELL_AUTOREMEDIATION_ENABLED=false" >> ~/Desktop/nuzantara/apps/cell/.env
launchctl bootout gui/$(id -u)/com.cell.organism
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cell.organism.plist
```

To re-enable: remove the line or set to any value other than the disabled set.

## Verification

Log signal when kill switch triggers:

```
WARNING cell: W33 kill switch active (CELL_AUTOREMEDIATION_ENABLED=false):
  would emit sustained_red (streak=3) but suppressed by operator override
```

Cell continues to monitor and report, just doesn't dispatch the W27/W31 chain.

## Sources

1. `apps/cell/cell/core/pulse.py:53-83` — `_autoremediation_enabled()` helper
2. `apps/cell/cell/core/pulse.py:862-895` — gated emit site
3. `apps/cell/tests/test_w33_autoremediation_kill_switch.py` — 23/23 PASS evidence
