# P0-7 Brainstorm — Duplicate SQL v2 migration numbers

**Goal:** Resolve duplicate `129_*` and `130_*` migration files. Add CI guardrail to prevent recurrence.
**Effort:** 2-4 hours
**Dependencies:** None.

---

## Strategy options

### Option A: Identify + rename non-applied duplicate

Each duplicate pair: one is in `_schema_versions`, the other isn't. Rename the not-applied one to next available number.

**Pros:**
- Preserves prod schema state
- Minimal surgery

**Cons:**
- Requires PG query against prod to know which one is applied

**Effort:** 2 hours.

### Option B: Manual review of each duplicate to decide

Owner decides: are the two duplicates both desired (need different content) or is one a leftover?

**Pros:**
- Catches the case where both are real changes that got named the same by accident

**Cons:**
- Requires owner judgment

**Effort:** 1-2 hours per duplicate pair.

**Recommendation:** **Option A** preceded by Option B preview. First review what the duplicates contain (probably one is leftover), then mechanically rename.

---

## Implementation plan

### Step 1: Identify duplicates

```bash
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -c | awk '$1>1{print $2}'
# Expected: 129, 130
ls apps/backend-rag/backend/db/migrations_v2/ | grep -E "^(129|130)_"
```

### Step 2: Compare contents

```bash
diff apps/backend-rag/backend/db/migrations_v2/129_*.sql
diff apps/backend-rag/backend/db/migrations_v2/130_*.sql
git log --all --oneline apps/backend-rag/backend/db/migrations_v2/129_*.sql
git log --all --oneline apps/backend-rag/backend/db/migrations_v2/130_*.sql
```

Likely scenario: Same content, different commits (PR merge collision). Or: Different content, both unmerged into prod (need both applied with new numbers).

### Step 3: Query production `_schema_versions`

```bash
fly ssh console -a nuzantara-rag --command "psql ... -c \"SELECT migration_number, name, applied_at FROM _schema_versions WHERE migration_number IN (129, 130) ORDER BY applied_at\""
```

Expected: 1 row for 129, 1 row for 130. The `name` column tells us which file was applied.

### Step 4: Rename not-applied duplicates

For each pair, the file NOT matching `_schema_versions.name` gets renamed.

```bash
# Example: if `129_foo.sql` was applied and `129_bar.sql` is the duplicate
git mv apps/backend-rag/backend/db/migrations_v2/129_bar.sql apps/backend-rag/backend/db/migrations_v2/143_bar.sql
# Verify content still valid
PYTHONPATH=apps/backend-rag python -m backend.db.migrate apply-all --dry-run
```

### Step 5: CI guardrail

```yaml
# .github/workflows/lint-migration-numbers.yml
name: Migration number uniqueness lint
on: [pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          DUPS=$(ls apps/backend-rag/backend/db/migrations_v2/ \
            | grep -E "^[0-9]+_.*\.sql$" \
            | awk -F_ '{print $1}' \
            | sort \
            | uniq -d)
          if [ -n "$DUPS" ]; then
            echo "::error::Duplicate migration numbers detected: $DUPS"
            ls apps/backend-rag/backend/db/migrations_v2/ | grep -E "^($DUPS)_"
            exit 1
          fi
```

### Step 6: Migration runner: assert uniqueness in code

```python
# apps/backend-rag/backend/db/migration_manager.py

def discover_migrations(self) -> list[Migration]:
    files = list(self.migrations_dir.glob("*.sql"))
    # NEW: assert no duplicate numbers
    numbers = [int(f.stem.split("_")[0]) for f in files if f.stem.split("_")[0].isdigit()]
    duplicates = [n for n in set(numbers) if numbers.count(n) > 1]
    if duplicates:
        raise RuntimeError(f"Duplicate migration numbers in migrations_v2/: {duplicates}")
    # Existing logic
```

This catches duplicates at runtime even if CI guardrail is bypassed.

---

## Dependencies

- **Before:** None.
- **After:** Schema integrity restored.

## Rollback plan

`git mv` reversible.

## L2 autonomy decision

**Auto-implementable: PARTIAL.**

Step 3 (PG query) requires Fly SSH access — L2 yes (read-only console allowed per AUTONOMOUS_OPS).
Step 4 (rename) — L2 yes if obvious (one applied, one not).
If both have been applied (very unlikely but possible): Zero handoff.

## Verification

```bash
ls apps/backend-rag/backend/db/migrations_v2/ | awk -F_ '{print $1}' | sort | uniq -c | awk '$1>1'
# Expected: empty (no duplicates)

PYTHONPATH=apps/backend-rag python -m backend.db.migrate apply-all --dry-run
# Expected: clean dry-run

# Plant duplicate to verify CI catches it
cp apps/backend-rag/backend/db/migrations_v2/129_*.sql /tmp/dupcanary
git add /tmp/dupcanary
gh pr create
gh pr checks
# Expected: lint-migration-numbers fails

# Cleanup
git rm /tmp/dupcanary
```

Numbers:
- Before: 2 duplicate pairs (4 files for 2 numbers) = silent corruption risk
- After: 0 duplicates + CI guardrail prevents future recurrence
