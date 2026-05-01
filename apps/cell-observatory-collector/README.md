# cell-observatory-collector

Pro-local Python service that listens to `cell_pulse_observed` PG channel,
classifies events with MiniMax M2, and persists to local SQLite.

Part of the Cell Pulse Observatory (Phase 0). See:
- Spec: [`docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md`](../../docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md)
- Plan: [`docs/superpowers/plans/2026-05-01-cell-observatory-fase0-implementation.md`](../../docs/superpowers/plans/2026-05-01-cell-observatory-fase0-implementation.md)

## Components (filled in across PR-3 sub-tasks)

- `cell_observatory/collector.py` — asyncpg LISTEN + dedup + dispatch (Task 3.6)
- `cell_observatory/classifier.py` — MiniMax M2 client + prompt (Task 3.5)
- `cell_observatory/storage.py` — SQLite WAL, idempotent insert (Task 3.4)
- `cell_observatory/rollup.py` — daily rollup job (Task 3.7)
- `cell_observatory/prune.py` — 90-day retention (Task 3.7)
- `cell_observatory/api.py` — FastAPI loopback :17891 for dashboard (Task 3.8)
- `cell_observatory/models.py` — Pydantic v2 schemas (Task 3.2)
- `cell_observatory/config.py` — env-based config (Task 3.3)
