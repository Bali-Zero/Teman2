# nb_monitor

Daily cron measuring which NotebookLM notebooks produce value consumed downstream by Nuzantara.

## Quick start (Pro)

```bash
cd apps/mata-garuda
.venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram
python ../../scripts/nb-monitor/show.py
```

## Architecture

- `registry.py` — loads bootstrap JSON registry, returns `NotebookEntry` dataclasses.
- `collectors/` — five small modules, one per metric (3 live, 2 placeholder).
- `tier.py` — pure decision tree, classifies (`ALIVE`/`IDLE`/`DYING`).
- `alerts.py` — pure logic, evaluates 3 alert conditions with floor + cooldown.
- `telegram_send.py` — minimal urllib-based Telegram dispatcher.
- `persist.py` — SQLite WAL helper + dataclasses.
- `report.py` — markdown weekly report renderer.
- `run.py` — entrypoint that wires it all together. Hard-coded paths via env-overrideable
  constants in `__init__.py`.

## See also

- Spec: [`docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`](../../../../../docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md)
- Plan: [`docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md`](../../../../../docs/superpowers/plans/2026-05-07-nb-mitochondrial-monitor.md)
- Runbook: [`docs/operations/nb-mitochondrial-monitor.md`](../../../../../docs/operations/nb-mitochondrial-monitor.md)
- ADR: [`docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md`](../../../../../docs/adr/ADR-006-nb-mitochondrial-monitor-bootstrap-json.md)
- Round 2 memo: `~/.claude/projects/-Users-nuzantara/memory/project_nb_lifecycle_round2_2026_05_04.md`
