# TKA Knowledge Graph Ingestion Report

**Date:** 2026-02-21  
**Time:** 02:19:07 UTC+8  
**Status:** ✅ COMPLETED SUCCESSFULLY

---

## Summary

The TKA (Tenaga Kerja Asing / Foreign Workers) data has been successfully ingested into the PostgreSQL Knowledge Graph.

## Data Source

- **File:** `/Users/nuzantara/Desktop/TKA_KG_INSERTS.sql`
- **Size:** 818,782 bytes (799.6 KB)
- **Generated:** 2026-02-21T02:05:42
- **Source:** TKA_ISCO_FINAL.json

## Database Connection

- **Host:** localhost
- **Database:** nuzantara
- **User:** nuzantara
- **Tables:** `kg_nodes`, `kg_edges`

## Ingestion Results

### Nodes Inserted by Type

| Entity Type     | Count   | Expected | Status |
| --------------- | ------- | -------- | ------ |
| KBLI            | 246     | 246      | ✅     |
| Jabatan         | 59      | 59       | ✅     |
| KepmenCategory  | 12      | 12       | ✅     |
| ISCOGroup       | 8       | 8        | ✅     |
| **Total Nodes** | **325** | **325**  | ✅     |

### Edges Inserted

| Metric      | Count | Expected | Status |
| ----------- | ----- | -------- | ------ |
| Total Edges | 1,370 | ~1,370   | ✅     |

### Execution Time

- **Duration:** 0.09 seconds
- **Throughput:** ~3,600 records/second

## Schema Adjustments Made

The following schema modifications were applied to align the database with the SQL file format:

1. **Added to `kg_nodes`:**
   - `source_collection` (TEXT)

2. **Modified `kg_edges`:**
   - Changed primary key from `id` (INTEGER) to `relationship_id` (TEXT)
   - Added `source_collection` (TEXT)
   - Added `updated_at` (TIMESTAMP WITH TIME ZONE)

## Sample Queries Verified

### 1. TKA Positions for KBLI 62110

```sql
SELECT j.name, j.properties->>'isco' as isco
FROM kg_nodes k
JOIN kg_edges e ON k.entity_id = e.source_entity_id
JOIN kg_nodes j ON e.target_entity_id = j.entity_id
WHERE k.entity_type = 'KBLI' AND k.properties->>'code' = '62110'
AND e.relationship_type = 'HAS_ELIGIBLE_POSITION';
```

**Result:** Information Technology Manager position found.

### 2. Top KBLI by Position Count

- KBLI 11030: 14 positions
- KBLI 11051: 14 positions
- KBLI 11010: 14 positions
- KBLI 11020: 14 positions
- KBLI 11053: 14 positions

### 3. ISCO Groups

All 8 ISCO groups are present:

- ISCO 12xx
- ISCO 13xx
- ISCO 14xx
- ISCO 21xx
- ISCO 23xx
- ISCO 26xx
- ISCO 31xx
- ISCO 34xx

## Verification Checklist

- [x] Database connection established
- [x] Tables `kg_nodes` and `kg_edges` exist
- [x] Schema compatibility ensured
- [x] SQL file executed successfully
- [x] Node counts match expected values
- [x] Edge counts match expected values
- [x] Sample queries return correct results
- [x] No errors during ingestion

## Idempotency Note

The SQL file uses `ON CONFLICT UPDATE` for all INSERT statements. This means:

- Running the script multiple times is safe
- Existing records will be updated, not duplicated
- Properties will be refreshed with latest values

## Next Steps

The TKA Knowledge Graph is now ready for use. You can query the data using:

```sql
-- Find eligible TKA positions for a specific KBLI
SELECT j.name, j.description
FROM kg_nodes k
JOIN kg_edges e ON k.entity_id = e.source_entity_id
JOIN kg_nodes j ON e.target_entity_id = j.entity_id
WHERE k.entity_type = 'KBLI'
  AND k.properties->>'code' = 'YOUR_KBLI_CODE'
  AND e.relationship_type = 'HAS_ELIGIBLE_POSITION';
```

## Files

- **Ingestion Script:** `apps/backend-rag/ingest_tka_kg.py`
- **SQL Data:** `/Users/nuzantara/Desktop/TKA_KG_INSERTS.sql`
- **This Report:** `TKA_KG_INGESTION_REPORT.md`

---

**Report Generated:** 2026-02-21T02:19:07  
**Status:** ✅ ALL VERIFICATION CHECKS PASSED
