# Rollback procedure — Migration 156 (`mata_garuda.tag_intel_finding`)

This document covers the manual rollback path for migration 156 (Sprint 5 —
intel_radar provenance wiring).

## TL;DR

Migration 156 is **forward-safe** — its rollback path is a single
`DROP FUNCTION` and produces no data loss. The function is only a helper;
the underlying `asset_provenance` table (created in mig 154) is unaffected.
Existing rows in `asset_provenance` for `asset_kind='intel_finding'`
continue to be valid and queryable.

## Rollback step

```sql
DROP FUNCTION IF EXISTS mata_garuda.tag_intel_finding(UUID, TEXT, TEXT, TEXT, BOOLEAN, SMALLINT);
```

The migration file's `-- === ROLLBACK ===` section contains exactly this.
The migration runner (`backend/db/migration_manager.py`) honors that marker
and applies it on a `--rollback` invocation.

## What happens after rollback

### On the database

* The function is removed.
* Schema `mata_garuda` is preserved (idempotency requirement — re-applying
  mig 156 must not fail). Empty schemas have no operational cost; drop
  manually only if no other `mata_garuda.*` objects exist (verify with
  `\dn` and `\df mata_garuda.*` in psql).
* Existing `asset_provenance` rows tagged with `asset_kind='intel_finding'`
  remain. They keep their reliability/credibility/TTL/metadata exactly as
  last UPSERTed.
* The TTL invalidation sweep
  (`com.matagaruda.invalidation-sweep` LaunchAgent on Pro) continues to run
  at 04:13 WITA and continues to invalidate intel_finding rows whose
  `valid_until` has passed. This behavior is upstream of mig 156 (it
  belongs to mig 154+155).

### On the cron (`~/scripts/cron-agent-python/intel_radar.py`)

* The cron continues to run every hour and INSERT new findings into
  `intel_radar_findings`.
* The `tag_intel_finding` call is wrapped in a try/except that logs a
  warning on failure. After the function is dropped, every call yields
  Postgres error `42883 (undefined_function)`, which is caught and
  logged as `tag_provenance_failed`. The cron continues to the next
  finding without crashing.
* As a result, **no provenance rows are created** for new findings until
  the function is re-applied. Existing rows are unaffected.

### Roll-forward after rollback

To re-apply, re-run the migration runner with mig 156. The migration is
idempotent (`CREATE SCHEMA IF NOT EXISTS` + `CREATE OR REPLACE FUNCTION`
+ explicit `DROP FUNCTION IF EXISTS` for prior signatures).

After re-application, cron runs resume tagging. Any findings inserted
during the rollback window will NOT have provenance rows — they need to
be back-filled by an ad-hoc reconciliation script if the gap is
material:

```sql
-- Example reconciliation: tag any intel_radar_findings without provenance.
INSERT INTO asset_provenance (
    asset_kind, asset_id, source, reliability, credibility,
    owner, invalidation_mode, valid_until, tlp, metadata, created_at, updated_at
)
SELECT
    'intel_finding',
    f.id::TEXT,
    COALESCE(f.source_domain, 'unknown'),
    'F',
    5,
    'intel_radar',
    'auto',
    NOW() + (
        CASE f.query_tier WHEN 'L1' THEN 90 WHEN 'L2' THEN 30 WHEN 'L3' THEN 7 ELSE 30 END
        || ' days'
    )::INTERVAL,
    'amber',
    jsonb_build_object(
        'original_tier', f.query_tier,
        'latest_tier', f.query_tier,
        'first_tagged_at', to_jsonb(NOW()),
        'last_tagged_at', to_jsonb(NOW()),
        'source_domain', COALESCE(f.source_domain, 'unknown'),
        'corroborating_queries', jsonb_build_array(f.query),
        'corroboration_count', 1,
        'backfilled', true
    ),
    NOW(),
    NOW()
FROM intel_radar_findings f
LEFT JOIN asset_provenance p
  ON p.asset_kind = 'intel_finding' AND p.asset_id = f.id::TEXT
WHERE p.id IS NULL
  AND f.created_at > NOW() - INTERVAL '<rollback window>'
ON CONFLICT (asset_kind, asset_id) DO NOTHING;
```

Set `<rollback window>` to the duration the rollback was active.

## Operational gotchas

1. **Schema preservation** — keep `mata_garuda` schema across rollbacks.
   Empty schema is fine; future mig 157+ may add more `mata_garuda.*`
   objects.

2. **No event notification on rollback** — the mig 155 trigger only fires
   on actual `asset_provenance` row writes. Dropping the helper function
   does not trigger any notification on its own. If downstream consumers
   need to know, send an explicit Telegram alert as part of the rollback
   procedure.

3. **GRANT cleanup** — `DROP FUNCTION` automatically removes any GRANTs
   on the function. No separate REVOKE step needed.

4. **The cron's failure log is the rollback signal** — if you see a
   sustained burst of `tag_provenance_failed: 42883 undefined_function`
   warnings in the cron log, the rollback has been observed by the
   producer side.
