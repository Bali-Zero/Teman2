# NUZANTARA DATABASE REFACTORING PLAN (Deep Clean)

**Status:** Draft / Planned
**Target Session:** Next Dedicated Session
**Goal:** Transform the current fragmented migration history into a deterministic, robust, and clean V2 schema baseline.

---

## 🛑 CURRENT STATE (Why we need this)

- **Fragmentation:** 34 migrations, some with duplicate numbers (001, 002).
- **Gaps:** Missing migration numbers (003, 023, 024, 027-032, 034, 035, 041).
- **Fragility:** Dependencies on specific Python scripts mixed with SQL.
- **Risk:** High risk of drift between production DB and local development DB.

---

## 🛠️ THE PLAN: "Squash & Reset" Strategy

### Step 1: Snapshot (The Truth)

We capture the **actual** state of the production database schema. This becomes our source of truth, ignoring how we got there.

```bash
# Command to execute on production/staging
pg_dump --schema-only --no-owner --no-privileges nuzantara > backend/db/schema_v1_snapshot.sql
```

### Step 2: Baseline V2 Creation

Instead of fixing 34 broken files, we create **ONE** monolithic migration that sets up the entire clean state.

1.  **Create:** `backend/db/migrations_v2/001_baseline_v2.sql`
2.  **Content:** Cleaned up version of `schema_v1_snapshot.sql`
    - Remove legacy tables if any.
    - Ensure all `CREATE TABLE` have `IF NOT EXISTS`.
    - Ensure all indices and foreign keys are named consistently.

### Step 3: Migration System Upgrade

Update `backend/db/migration_manager.py` to support the V2 strategy:

- **Logic:** If DB is empty -> Apply `001_baseline_v2.sql`.
- **Logic:** If DB has legacy migrations (001-044) -> Mark `001_baseline_v2.sql` as "Fake Applied" (skip execution, just record it).
- **Future:** All new migrations start from `002_...` in the `v2` folder.

### Step 4: Data Seeding Segregation

Separate schema from data. Move all `INSERT` statements (like `visa_types`, `practice_types`) into dedicated **Seeder Scripts** that run _after_ migrations.

- `backend/db/seeds/01_practice_types.sql`
- `backend/db/seeds/02_visa_types.sql`

---

## ✅ EXECUTION CHECKLIST (For Next Session)

- [ ] **Backup:** Full backup of production data (`pg_dump -Fc`).
- [ ] **Snapshot:** Generate `schema_v1_snapshot.sql`.
- [ ] **Audit:** Manually review the snapshot for "ghost tables" to drop.
- [ ] **Implementation:** Create `migrations_v2` directory and baseline file.
- [ ] **Code Update:** Patch `migration_manager.py`.
- [ ] **Verification:** Test on a fresh Docker container vs existing container.

---

## ⚠️ CRITICAL RULES

1.  **NEVER DROP DATA:** We are refactoring schema definitions, not wiping customer data.
2.  **IDEMPOTENCY:** The new baseline must run safely on an empty DB.
3.  **NO DOWNTIME:** The switch to V2 migration system must be seamless for the running app.
