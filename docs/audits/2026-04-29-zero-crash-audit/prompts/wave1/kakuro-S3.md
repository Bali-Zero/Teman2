# kakuro-S3 — P0-7 Duplicate SQL v2 migration numbers

> Single-file prompt for one Claude Code Max x20 session.
> Macchina: **Air** (`antonellosiano@Nuzantara-9`). Worktree: `wt/p0-7-migration-dups`.
> Session command: in your tmux pane, simply type:
>
>     leggi kakuro-S3 e esegui

---

## Mission

Implementa **P0-7** dal piano audit zero-crash 2026-04-29: rinomina i file SQL v2 con numeri duplicati (`129_*` e `130_*`), aggiungi CI guardrail, aggiungi runtime assert.

**Tempo stimato: 2-4h.** Schema integrity fix.

## Context

- Repo: `/Users/antonellosiano/Projects/nuzantara` (Air path), branch `main`
- Brainstorm dedicato (READ FIRST): [`docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-7_duplicate_migration_numbers.md`](../../11_brainstorms/P0-7_duplicate_migration_numbers.md)
- Cicatrice STRUCTURAL aperta: `.claude/rules/cicatrix-scars.md` — entry "SQL v2 migrations duplicate numbers `129_*` and `130_*` (2026-04-29)"

## Files to inspect/touch

1. `apps/backend-rag/backend/db/migrations_v2/129_*.sql` (TWO duplicates — identify)
2. `apps/backend-rag/backend/db/migrations_v2/130_*.sql` (TWO duplicates — identify)
3. `apps/backend-rag/backend/db/migration_manager.py` — add runtime uniqueness assert
4. `.github/workflows/lint-migration-numbers.yml` (NEW) — CI guardrail

## Files NOT to touch

- Already-applied migrations cannot be deleted (per VADEMECUM §7 hard rule)
- `fly.toml`, `.env.production`, `zantara_core.py` (off-limits)

## Workflow

### Phase 1 — Cross-LLM brainstorm

```bash
cd ~/Projects/nuzantara  # Air path
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cat > /tmp/kakuro-S3-brief.txt <<'BRIEF'
You are giving an independent strategy for resolving duplicate migration numbers.

PROBLEM: apps/backend-rag/backend/db/migrations_v2/ has TWO files sharing
number 129 and TWO sharing 130. Listing example:
  129_war_room_drafts.sql
  129_intel_cognitive_layer.sql   <- duplicate
  130_compliance_alerts.sql
  130_practice_state_machine.sql   <- duplicate

The migration runner backend/db/migration_manager.py tracks via integer
migration_number column in _schema_versions table. Duplicates cause
undefined apply order. One duplicate may have been applied to prod, the
other never picked up — schema corruption risk.

RULES (from VADEMECUM §7):
- Never rename an already-applied migration_v2 file (breaks _schema_versions tracking)
- Never delete a migration file that's been applied to prod
- Forward DDL above '-- === ROLLBACK ===' marker
- Migration runner is custom (not Alembic): backend/db/migration_manager.py

YOUR TASK: Propose strategy for:
1. How to determine which of each duplicate pair was applied to prod
   - psql query against _schema_versions table?
   - git log on each file to see commit history?
   - both?
2. What to do with the NOT-applied duplicate
   - Rename to next-available number (141, 142)?
   - Or merge content into the applied one (if compatible)?
   - Or delete from disk if redundant?
3. Runtime assert in migration_manager.py to prevent future duplicates
4. CI guardrail in .github/workflows/lint-migration-numbers.yml
5. How to recover if BOTH duplicates were applied (very unlikely but possible)

Constraints:
- Cannot delete an applied migration file
- Cannot rename an applied migration (breaks tracking)
- Must be auditable (Telegram alert if duplicates ever appear again)
BRIEF

mkdir -p /tmp/kakuro-S3-brainstorms
coord_brainstorm "P0-7 duplicate migration numbers" /tmp/kakuro-S3-brief.txt /tmp/kakuro-S3-brainstorms

for llm in codex gemini deepseek notebooklm; do
    echo "=== $llm ==="; head -150 /tmp/kakuro-S3-brainstorms/$llm.md
done
```

### Phase 2 — Empirical inspection

```bash
cd ~/Projects/nuzantara

# Identify duplicates
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -c | awk '$1>1{print $2}'
# Expected: 129 (or whatever)

# List actual files
ls apps/backend-rag/backend/db/migrations_v2/ | grep -E "^(129|130)_"

# Compare contents
diff apps/backend-rag/backend/db/migrations_v2/129_*.sql 2>&1 | head -50
diff apps/backend-rag/backend/db/migrations_v2/130_*.sql 2>&1 | head -50

# Git history of each
for f in apps/backend-rag/backend/db/migrations_v2/{129,130}_*.sql; do
    echo "=== $f ==="
    git log --all --oneline -- "$f" | head -5
done
```

### Phase 3 — Query production _schema_versions

The CRITICAL question: which duplicate was applied?

```bash
# Use fly ssh console (read-only mode)
fly ssh console -a nuzantara-rag --command "psql \$DATABASE_URL -c \"
SELECT migration_number, name, applied_at
FROM _schema_versions
WHERE migration_number IN (129, 130)
ORDER BY migration_number, applied_at
\""
# Expected: 1 row for 129 with name=<one-of-the-files>, 1 row for 130 with name=<one-of-the-files>
```

The `name` column tells which file was applied. The OTHER file in the pair is the rename candidate.

### Phase 4 — Worktree

```bash
cd ~/Projects/nuzantara
git fetch origin
git worktree add -b feat/p0-7-migration-dups ../nuzantara-wt/p0-7 origin/main
cd ../nuzantara-wt/p0-7
```

### Phase 5 — Resolve duplicates

For each pair:
- If applied = `129_war_room_drafts.sql` (example) and not-applied = `129_intel_cognitive_layer.sql`, rename:

```bash
# Find next available number
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort -n | tail -3
# e.g., 138, 139, 140 — next free = 141

git mv apps/backend-rag/backend/db/migrations_v2/129_intel_cognitive_layer.sql \
       apps/backend-rag/backend/db/migrations_v2/141_intel_cognitive_layer.sql

# Same for 130 pair
git mv apps/backend-rag/backend/db/migrations_v2/130_X.sql \
       apps/backend-rag/backend/db/migrations_v2/142_X.sql
```

**Sanity check:**
```bash
PYTHONPATH=apps/backend-rag python -m backend.db.migrate apply-all --dry-run
# Expected: no errors, shows "would apply 141 and 142"
```

### Phase 6 — Add runtime assert

Edit `apps/backend-rag/backend/db/migration_manager.py`. Find the `discover_migrations` (or similar) method:

```python
def discover_migrations(self) -> list[Migration]:
    """Walk migrations_v2/ and parse migration files.

    Asserts uniqueness of migration_number to prevent silent corruption
    documented in cicatrix STRUCTURAL 2026-04-29 (P0-7).
    """
    files = sorted(self.migrations_dir.glob("*.sql"))

    # P0-7: assert no duplicate migration numbers
    numbers = []
    for f in files:
        prefix = f.stem.split("_")[0]
        if prefix.isdigit():
            numbers.append(int(prefix))

    duplicates = [n for n in set(numbers) if numbers.count(n) > 1]
    if duplicates:
        dup_files = {n: [f.name for f in files if int(f.stem.split("_")[0]) == n] for n in duplicates}
        raise RuntimeError(
            f"Duplicate migration numbers in migrations_v2/: {duplicates}. "
            f"Files: {dup_files}. "
            f"See cicatrix STRUCTURAL 2026-04-29 P0-7 for resolution."
        )

    # Existing logic continues...
```

### Phase 7 — CI guardrail

Create `.github/workflows/lint-migration-numbers.yml`:

```yaml
name: Migration number uniqueness lint

on:
  pull_request:
    paths:
      - 'apps/backend-rag/backend/db/migrations_v2/**'

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect duplicate migration numbers
        run: |
          DUPS=$(ls apps/backend-rag/backend/db/migrations_v2/ \
            | grep -E "^[0-9]+_.*\.sql$" \
            | awk -F_ '{print $1}' \
            | sort \
            | uniq -d)
          if [ -n "$DUPS" ]; then
            echo "::error::Duplicate migration numbers detected: $DUPS"
            for n in $DUPS; do
              echo "  Number $n found in:"
              ls apps/backend-rag/backend/db/migrations_v2/ | grep -E "^${n}_"
            done
            echo ""
            echo "Resolution: rename one duplicate to next-available number."
            echo "See cicatrix STRUCTURAL 2026-04-29 P0-7."
            exit 1
          fi
          echo "✓ All migration numbers unique"
```

### Phase 8 — Tests

```python
# apps/backend-rag/backend/tests/db/test_migration_uniqueness.py

import pytest
from pathlib import Path
from backend.db.migration_manager import MigrationManager

def test_no_duplicate_migration_numbers(tmp_path):
    """Runtime assert: discover_migrations raises if duplicates."""
    mig_dir = tmp_path / "migrations_v2"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("-- forward\nSELECT 1;\n-- === ROLLBACK ===\nSELECT 2;")
    (mig_dir / "001_duplicate.sql").write_text("-- forward\nSELECT 3;\n-- === ROLLBACK ===\nSELECT 4;")

    mgr = MigrationManager(migrations_dir=mig_dir)
    with pytest.raises(RuntimeError, match="Duplicate migration numbers"):
        mgr.discover_migrations()


def test_unique_migration_numbers_pass(tmp_path):
    mig_dir = tmp_path / "migrations_v2"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("-- forward\nSELECT 1;\n-- === ROLLBACK ===\nSELECT 2;")
    (mig_dir / "002_second.sql").write_text("-- forward\nSELECT 3;\n-- === ROLLBACK ===\nSELECT 4;")

    mgr = MigrationManager(migrations_dir=mig_dir)
    migs = mgr.discover_migrations()
    assert len(migs) == 2


def test_actual_migrations_v2_no_duplicates():
    """Smoke test against the real directory."""
    real_dir = Path(__file__).parents[3] / "db" / "migrations_v2"
    if not real_dir.exists():
        pytest.skip("migrations_v2 dir not found")
    files = list(real_dir.glob("*.sql"))
    numbers = []
    for f in files:
        prefix = f.stem.split("_")[0]
        if prefix.isdigit():
            numbers.append(int(prefix))
    duplicates = [n for n in set(numbers) if numbers.count(n) > 1]
    assert not duplicates, f"Duplicates in real migrations_v2: {duplicates}"
```

```bash
cd ../nuzantara-wt/p0-7/apps/backend-rag
source venv/bin/activate  # Air uses venv (NOT .venv)
PYTHONPATH=. pytest backend/tests/db/test_migration_uniqueness.py -v
# Expected: 3/3 pass
```

### Phase 9 — Commit + Push + Deploy (COORDINATED)

```bash
source ~/Projects/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cd ~/Projects/nuzantara-wt/p0-7

git status --short  # verify only intended changes

git add apps/backend-rag/backend/db/migrations_v2/  # the renames
git add apps/backend-rag/backend/db/migration_manager.py
git add .github/workflows/lint-migration-numbers.yml
git add apps/backend-rag/backend/tests/db/test_migration_uniqueness.py

coord_commit "fix(p0-7): resolve duplicate SQL v2 migration numbers + CI guardrail

P0-7 from zero-crash audit 2026-04-29.

Resolves cicatrix STRUCTURAL 2026-04-29 'Duplicate SQL v2 migration
numbers 129_* and 130_*'.

- Rename non-applied duplicate to next-available numbers (141, 142)
  Identified via 'SELECT name FROM _schema_versions' against prod.
  Already-applied files unchanged per VADEMECUM §7 hard rule.
- migration_manager.discover_migrations(): runtime assert raises
  RuntimeError if any duplicate migration_number detected.
- New CI workflow lint-migration-numbers.yml: PR-time guardrail
  fails if duplicates introduced.
- 3 new tests covering: duplicate raises, unique passes, real-dir smoke."

coord_push origin feat/p0-7-migration-dups

gh pr create \
  --title "fix(p0-7): resolve duplicate migration numbers + CI guardrail" \
  --body "Resolves cicatrix STRUCTURAL 2026-04-29 P0-7.

## Summary
- 2 file renames (non-applied duplicate of 129 → 141, of 130 → 142)
- Runtime assert in migration_manager.py
- CI workflow lint-migration-numbers.yml prevents regression
- 3 new tests

## Test plan
- [x] Renamed files dry-run apply-all OK
- [x] 3 unit tests pass
- [x] Real-directory smoke test passes (no duplicates)
- [ ] Post-deploy: SQL v2 post-deploy job (P0-4) applies 141 and 142

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

gh pr merge --auto --squash

# Watch deploy
PR_NUMBER=$(gh pr view --json number -q .number)
sleep 60
gh run watch $(gh run list --workflow="Deploy Backend to Fly.io" --limit 1 --json databaseId -q '.[0].databaseId')

# Verify post-deploy: 141 and 142 applied
fly ssh console -a nuzantara-rag --command "psql \$DATABASE_URL -c \"
SELECT migration_number, name FROM _schema_versions
WHERE migration_number IN (141, 142)
\""
# Expected: 2 rows showing the renamed migrations applied

~/.claude/scripts/mem save decision "P0-7 duplicate migration numbers resolved — PR #$PR_NUMBER. Renamed 129_* and 130_* duplicates to 141, 142. Runtime assert + CI guardrail in place. Cicatrix STRUCTURAL 2026-04-29 P0-7 resolved." 9
```

### Phase 10 — Cleanup

```bash
cd ~/Projects/nuzantara
git worktree remove ../nuzantara-wt/p0-7
```

## Reporting

```
[kakuro-S3 DONE] P0-7 merged in PR #<num>. Fly deploy success.
Renamed 2 duplicate migrations to 141, 142. Runtime assert + CI guardrail active.
3 new tests. Cicatrix STRUCTURAL 2026-04-29 P0-7 resolved.
Brainstorms saved in /tmp/kakuro-S3-brainstorms.
```

## Failure modes

- **Production query shows BOTH duplicates applied**: Zero handoff. Both migrations applied means schema is in some valid state but cannot be reverted by file rename. Document the situation, pause work, await Antonello decision.
- **Renamed file fails apply-all dry-run**: rollback rename, investigate. Possibly the file content wasn't idempotent.
- **CI passes but SQL v2 post-deploy (P0-4) doesn't apply 141/142**: P0-4 fix may not have landed yet on main, or the renamed files weren't picked up. Check `gh run view` of fly-deploy.
- **Coord lock stuck**: same recovery as kakuro-S1/S2.

## Autonomy boundary

L2 autonomous EXCEPT for:
- BOTH duplicates applied scenario → Zero handoff (data integrity decision)
- Otherwise proceed L2.
