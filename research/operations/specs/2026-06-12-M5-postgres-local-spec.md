---
date: 2026-06-12
status: READY FOR IMPLEMENTATION — decisions closed by Antonello delegation ("decidi tu per me", session 2026-06-12)
implements: research/operations/2026-06-12-m5-postgres-architecture.md (design + simulations)
owner: Opus implementation session on M5 (user balizero@Air-M5)
scope: M5 local PostgreSQL — test DB (CI parity) + dev snapshot (pull-only from Fly) + pre-push hook gate
out_of_scope: CI image bump (follow-up PR), LaunchAgent refresh (deferred), Redis/Qdrant on M5, any write-back to Fly, any sync from Pro PG
---

# SPEC: M5 local PostgreSQL (test + dev snapshot)

## §0 — Mandatory pre-implementation gate

Per CLAUDE.md §6 (4-LLM panel for architectural specs): run the panel on THIS file
before writing code. `agy -p` (redteam) + `codex exec --sandbox read-only` (constructive)
+ DeepSeek V4 Pro (logic holes). Incorporate CRITICAL findings only; do not let the panel
reopen the closed decisions in §2 (Antonello delegated; relitigation needs his ping).
~$0.01, ~2min. Then proceed.

## §1 — Verified ground (all facts tool-verified 2026-06-12 on M5; re-verify any you build on)

| # | Fact | Evidence |
|---|---|---|
| G1 | Tests default to `postgresql://test:test@localhost:5432/test` | `apps/backend-rag/backend/tests/conftest.py:22` |
| G2 | CI uses `postgres:15` + `DATABASE_URL=postgresql://test:test@localhost:5432/nuzantara_test` | `.github/workflows/tests.yml:25-26,129,146,159` |
| G3 | Prod is **postgres-flex 17.2, repmgr** (NOT Stolon — docs drift, see §9) | `fly image show -a nuzantara-postgres` |
| G4 | M5 has NO postgres installed | `brew list --formula \| grep -i postgres` → empty |
| G5 | Pre-push hook = `.husky/pre-push` (core.hooksPath=.husky); line 12 runs pytest, line 13 `\|\|` continues on failure — currently burns ~2min producing 141 `Connect ::1:5432` errors on M5, then "Continuing..." | `.husky/pre-push:8-17`, CI-session log 2026-06-12 |
| G6 | Keychain entry `nuzantara-postgres-readonly` **ABSENT on M5** (exists on Pro, T3.2) | `security find-generic-password -s nuzantara-postgres-readonly` → not found |
| G7 | flyctl authenticated on M5 as `zero@balizero.com` | `fly auth whoami` |
| G8 | **PreToolUse hook BLOCKS `brew install postgresql*` on M5**: `~/.claude/hooks/m5_block_heavy_brew.py`, HEAVY set lines 19-22 includes `postgresql`, `postgresql@16/17/18`, also `redis`, `qdrant`. Kill switch `M5_HEAVY_BREW_GUARD=off`. Exit 2 = block | read 2026-06-12 |
| G9 | Migrations apply INSIDE the pytest session (conftest/fixture), not a separate CI step — CI log 2026-06-11 shows `migration_base INFO Applying migration ...` during test run. So an EMPTY db + role is sufficient; pytest builds schema | CI run 27362926443 log lines 1221-1303 |
| G10 | Dual migration runners exist: `migrations_v2/*.sql` (SQL runner) + `backend/migrations/migration_NNN_*.py` (Python). The SQL test path does NOT run the Python ones — caused the `olympus_rules` failure on PR #1111, fixed by making 225 self-contained | session 2026-06-12, PR #1111 |

## §2 — Closed decisions (do NOT reopen)

1. **PG version: `postgresql@17`** — prod parity (17.2). CI's 15 is the outlier.
2. **One PR = Phases 1+2+3.** Phase 4 (LaunchAgent daily refresh) deferred until ≥1 week of manual `nuz-db-refresh` use.
3. **CI 15→17: separate follow-up PR**, gated on AC2 green locally (empirical proof 17 breaks nothing) — `.github/workflows/` is hot-zone, atomic-commit discipline.
4. **Brew-block hook**: authorized unblock. Install with one-shot `M5_HEAVY_BREW_GUARD=off`; then EDIT the hook removing only `postgresql`, `postgresql@16/17/18` from HEAVY (keep `redis`, `qdrant`, `gcc` etc. blocked — out of scope). Authorization: Antonello, this session ("che ne pensi di far girare postgresql anche su m5" + "decidi tu per me").
5. **Sync model**: schema = always-sync via repo migrations; data = pull-only snapshot Fly→M5 on demand; writes to prod = never. Pro local PG = never synced (Law 2). Full rationale + 7 simulations in the design doc.

## §3 — Architecture (1 glance)

```
Fly nuzantara-postgres (17.2, SOURCE OF TRUTH)
      │ pull-only: fly proxy 15432 → pg_dump -Fc (role nuzantara_readonly, Keychain)
      ▼
M5 postgresql@17 (brew, native)
  ├── db `test` + db `nuzantara_test` (role test/test)  ← pytest builds schema itself (G9)
  └── db `nuzantara_dev`  ← pg_restore --clean --no-owner, refreshed by scripts/nuz_db_refresh.sh
Pro local PG — untouched, unsynced (Law 2)
```

## §4 — Implementation steps

> Worktree discipline: repo changes happen in `.worktrees/` via `scripts/agent_start.py`
> (lane `infra`, task-id `m5-postgres-local`), branch `agent/air-m5/infra/m5-postgres-local`.
> Steps 1-2 and 6-7 are machine-local (no repo), do them from anywhere.

### Phase 1 — engine + test DBs (fixes the --no-verify pain)

1. **Install** (hook-gated, authorized):
   ```bash
   M5_HEAVY_BREW_GUARD=off brew install postgresql@17
   brew services start postgresql@17
   # keg-only: PATH needs /opt/homebrew/opt/postgresql@17/bin — add to ~/.zshenv (idempotent)
   ```
   GATE: `pg_isready -h localhost -p 5432` → `accepting connections`. Verify it listens on
   `::1` too (`psql -h ::1 -p 5432 -c 'select 1'` as admin) — tests resolve localhost→IPv6 first (G5 error signature).
2. **Roles + DBs**:
   ```bash
   psql -d postgres -c "CREATE ROLE test LOGIN PASSWORD 'test' CREATEDB;"
   createdb -O test test          # conftest default (G1)
   createdb -O test nuzantara_test  # CI-parity manual runs (G2)
   createdb nuzantara_dev          # snapshot target (owner = local admin)
   ```
3. **Empirical smoke** (this is AC2's dry run):
   ```bash
   cd apps/backend-rag && source .venv/bin/activate
   PYTHONPATH=backend python -m pytest backend/tests/ -q 2>&1 | tail -5
   ```
   Expect: zero `Connect call failed` errors; migrations applied by pytest (G9).
   If any test trips on the dual-runner gap (G10) — a SQL migration INSERTing into a
   Python-runner table — fix forward with the self-contained pattern proven in PR #1111
   (CREATE TABLE IF NOT EXISTS mirrored from the Python migration). Do NOT build a
   second bootstrap system.

### Phase 2 — dev snapshot from Fly

4. **Keychain import (G6)** — value must NEVER appear in transcript/logs (W65 discipline):
   ```bash
   ssh pro "security find-generic-password -s nuzantara-postgres-readonly -w" | \
     xargs -I{} security add-generic-password -s nuzantara-postgres-readonly -a nuzantara_readonly -w {} 
   ```
   ⚠️ The xargs form risks the value in `ps` — prefer a small python/pipe variant reading
   stdin directly into `security add-generic-password -w` interactive stdin, or accept the
   short ps-window on a single-user machine. Implementer's call; NEVER echo it.
   GATE: `security find-generic-password -s nuzantara-postgres-readonly >/dev/null && echo OK`.
5. **`scripts/nuz_db_refresh.sh`** (new, in repo; ~80 lines; `set -euo pipefail`):
   - Preflight: `fly auth whoami` (G7), `pg_isready` local, disk space check.
   - `fly proxy 15432:5432 -a nuzantara-postgres &` with `trap kill` cleanup; wait-for-port loop (timeout 30s).
   - `PGPASSWORD` from Keychain → `pg_dump -h localhost -p 15432 -U nuzantara_readonly -d <dbname> -Fc --no-owner --no-acl --exclude-table-data='events_outbox' --exclude-table-data='olympus_heartbeats*' -f ~/.nuzantara-db-snapshots/prod-$(date +%Y%m%d-%H%M).dump`
     (discover `<dbname>` empirically: `psql ... -l` via proxy; likely the backend DB behind Fly secret DATABASE_URL).
   - `pg_restore --clean --if-exists --no-owner --no-acl -d nuzantara_dev <dump>`.
   - Verify: row counts on 3 anchor tables (`clients`, `practices`, `schema_migrations`) > 0; print summary.
   - Rotate: keep last 3 dumps; dir `~/.nuzantara-db-snapshots/` chmod 700, files 600.
   - If the readonly role hits a permission error mid-dump (sequence/table outside the 255
     SELECT grants): STOP and surface to Antonello. Do NOT escalate to a higher-privilege
     role autonomously (W38 spirit).
   GATE: exit 0 + `psql -d nuzantara_dev -c 'select count(*) from clients'` > 0.

### Phase 3 — pre-push hook gate

6. **Edit `.husky/pre-push`** (repo change, in the PR): wrap the Python-tests block (G5) with:
   ```bash
   if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
       # existing pytest invocation, unchanged
   else
       echo "⏭️  SKIP Python DB tests — no local PostgreSQL (install per specs/2026-06-12-M5-postgres-local-spec.md)"
   fi
   ```
   Declared skip replaces 2min of connection-error noise. With PG present: tests actually gate.
7. **Fleet hooks (machine-local, no PR)**: edit `~/.claude/hooks/m5_block_heavy_brew.py`
   HEAVY set — remove the 4 postgresql tokens (G8, authorized §2.4). Locate the SessionStart
   machine-check that prints `postgresql@18: none` (grep `postgresql@` in `~/.claude/hooks/`
   + session-start scripts) and point it at `postgresql@17`.

## §5 — Acceptance criteria (all falsifiable; run each, paste outputs in PR)

- **AC1**: `pg_isready -h localhost -p 5432` → 0; `psql -U test -d test -c 'select 1'` → 1 row; IPv6 `-h ::1` works.
- **AC2**: full pytest on M5 → **zero** `Connect call failed ('::1', 5432)` occurrences (was 141); only genuine failures remain, count matches CI ballpark.
- **AC3**: `git push` of a dummy branch runs the hook with REAL tests (no "skipped or failed. Continuing"); on a PG-stopped machine it prints the declared SKIP line.
- **AC4**: `scripts/nuz_db_refresh.sh` exit 0; `nuzantara_dev` has clients/practices rows; second run idempotent.
- **AC5**: `grep -r` of transcript artifacts + script: readonly password appears NOWHERE; dumps dir 700, files 600.
- **AC6**: SessionStart on M5 reports `postgresql@17: started` (or equivalent); `M5_HEAVY_BREW_GUARD` no longer needed for pg minor ops.
- **AC7**: PR green in CI (the hook edit must not alter CI behavior — CI has its own service container).

## §6 — Non-goals (do not implement)

- No LaunchAgent (Phase 4 — revisit after 1 week; when built: it's a CRON, no KeepAlive — 2026-04-29 scar).
- No CI image bump in this PR (§2.3 follow-up).
- No Redis/Qdrant on M5 (same snapshot pattern later if wanted; keep them in HEAVY).
- No replication slots, no logical replication, no write path to Fly, no Pro PG access.

## §7 — Risks & gotchas (scar-informed)

- **Keg-only PATH**: postgresql@17 binaries not on PATH by default; zshenv addition must be idempotent (M5 path-drift scar family — native installs, never copied).
- **IPv6 first**: the 141 errors were on `::1` — verify listen on IPv6 localhost, not just 127.0.0.1.
- **fly proxy lifetime**: must be trap-killed; an orphan proxy holds the port and the next run fails confusingly.
- **Dump size unknown**: first run measures; if > a few GB, add more `--exclude-table-data` (candidates: notification_log, intel_events) — decide empirically, log exclusions in the script header.
- **`pg_restore --clean` on live dev connections**: close psql sessions first or restore drops fail; `--if-exists` covers most.
- **Husky hook is repo-shared**: the pg_isready gate must behave identically on Pro/Mini (both have local PG → gate passes → tests run, as today).

## §8 — Rollback

- Engine: `brew services stop postgresql@17 && brew uninstall postgresql@17` (data dir removable after).
- Hook edit: revert the `.husky/pre-push` commit.
- Brew-guard: re-add the 4 tokens to HEAVY.
- Snapshot data: `dropdb nuzantara_dev` + `rm -rf ~/.nuzantara-db-snapshots`. Prod untouched by design at every step.

## §9 — PR deliverables

1. `.husky/pre-push` gate edit.
2. `scripts/nuz_db_refresh.sh` (+ ~10-line usage note in `docs/runbooks/m5-local-postgres.md`).
3. This spec + the design doc (`2026-06-12-m5-postgres-architecture.md`) committed (currently untracked on M5 main checkout — pick them up FIRST, sibling-race risk W50/51/52).
4. Doc drift fix (1 line): CLAUDE.md §11 "Stolon HA" → "postgres-flex 17.2 (repmgr)" (G3).
5. Cicatrix/memory: `mem save decision` for the architecture choice + AC outputs in PR body.
