# intel_items pajak provenance — DML (drafted 2026-09-21, EXECUTED 2026-09-22)

> **EXECUTED on PROD on 2026-09-22, authorized by the owner.** Statement (a) ran exactly as
> written below. Statement (b) ran with 18 per-row UPDATEs; one is shown, the other 17 are
> summarised in a table. Each ran first as a rehearsal with its final `COMMIT` replaced by `ROLLBACK`,
> and all in-transaction assertions passed. The channel was `fly ssh console -a nuzantara-rag`,
> running `python3 -` from stdin, with the SQL executed through asyncpg on the app's
> `DATABASE_URL`.
>
> | step         | committed | result                                                                            | archive (rollback source)                               |
> | ------------ | --------- | --------------------------------------------------------------------------------- | ------------------------------------------------------- |
> | (a) relabel  | 15:00:42Z | 122 rows now carry their real host (67 distinct); `pajak.go.id` mislabels left: 0 | `intel_items_pajak_relabel_archive_20260921` (122 rows) |
> | (b) backfill | 15:01:03Z | 18/20 peraturan rows carry `citation`; the 2 known failures untouched             | `intel_items_pajak_backfill_archive_20260921` (20 rows) |
>
> Before the run, the 122-row cohort, the 20-row cohort and the 0 archive tables were re-measured
> read-only. The SQL host expression was checked against `pajak_parse.source_host` on all 122
> URLs (0 mismatches). The 18 backfill values were re-extracted from the live pages with
> `extract_regulation` from `origin/main` (0 differences from the values below).
>
> **Re-route after (a).** The Pro fallback router routed the 122 `unrouted` rows with an older
> copy of the rules. `backfill_needs_review(dry_run=False)` on Fly then reclassified the 24 that
> the backend `_classify` routes differently. The same call also moved the 18 ddtc/muc
> `needs_review` rows (PWC-7074 C2). Final state of the 122: `nb-intel` 26, `blog` 15,
> `needs_review` 81. The rules drift is ledger row `intel-lake-pro-fallback-router-rules-drift`.
>
> The **Rollback** blocks below are the way back. Retention, decided by the owner on 2026-09-22:
> the archive tables stay in PROD for 30 days and are dropped on or after 2026-10-22. That is
> ledger row `pajak-dml-archive-tables-retention`. After the drop, the Rollback blocks no longer
> apply.
>
> Companion code change (merged earlier as #7087):
> `feat(pajak-monitor): peraturan items carry the regulation's own citation, excerpt and date`
> adds `pajak_parse.extract_regulation()` and wires it into `pajak_monitor.py` for NEW rows
> going forward. This doc is the one-time cleanup for rows already in production.
>
> `intel_items` schema (read-only, confirmed live via `information_schema.columns`):
>
> | column           | type        | nullable                   |
> | ---------------- | ----------- | -------------------------- |
> | id               | uuid        | NO                         |
> | canonical_url    | text        | NO                         |
> | content_hash     | text        | NO                         |
> | title            | text        | NO                         |
> | summary          | text        | YES                        |
> | source_domain    | text        | NO                         |
> | language         | text        | YES                        |
> | jurisdiction     | text        | YES                        |
> | topic_tags       | ARRAY       | NO                         |
> | routing_status   | text        | NO                         |
> | routing_targets  | jsonb       | NO (default `'{}'::jsonb`) |
> | confidence_score | real        | YES                        |
> | first_seen_at    | timestamptz | NO                         |
> | last_seen_at     | timestamptz | NO                         |
> | published_at     | timestamptz | YES                        |
> | expires_at       | timestamptz | YES                        |
> | raw_payload      | jsonb       | NO                         |
> | is_probe_sandbox | boolean     | NO                         |

---

## (a) RELABEL — 122 rows mislabeled `source_domain = 'pajak.go.id'`

**Why.** `source_host()` (added to `pajak_parse.py` by #7074) derives `source_domain` from the
actual item URL. Before that fix existed, every Source-3 (`_search_djp_updates`, a Brave
`web_search`) hit was hardcoded to `source_domain = "pajak.go.id"` regardless of which site it
actually came from — DDTC, CNBC Indonesia, ortax.org, muc.co.id, etc. `intel_lake_router.py`'s
`_RULES` and `intel_source_whitelist.py`'s `INTEL_SOURCE_WHITELIST` both key on the bare domain,
so these 122 rows have been routed (or left unrouted) under the WRONG rule set ever since.

**Counted live, read-only** (`./scripts/pg.sh`, `2026-09-21`):

```sql
SELECT count(*) FROM intel_items
WHERE source_domain = 'pajak.go.id'
  AND canonical_url NOT LIKE 'https://pajak.go.id/%'
  AND canonical_url NOT LIKE 'https://www.pajak.go.id/%';
-- => 122
```

All 122 currently sit at `routing_status = 'nb-intel'` (confirmed via
`GROUP BY routing_status` on the same cohort — a single value, no other status present).

**Sample of the mislabeled rows** (real domains hiding under the wrong label):

```
https://muc.co.id/id/regulation/4539/peraturan-direktur-jenderal-pajak-nomor-per-10pj2025
https://fiskal.kemenkeu.go.id/informasi-publik/kurs-pajak
https://pajakku.com/artikel/perubahan-struktur-djp-pembagian-wajib-pajak-dalam-pmk-182026
https://ortax.org/imbas-polemik-pps-purbaya-perketat-komunikasi-dan-publikasi-kebijakan-pajak-djp
https://www.cnbcindonesia.com/news/.../bos-djp-ungkap-50-ribu-wajib-pajak-baru-jadi-patuh-berkat-coretax/amp
```

**New `source_domain`** = `pajak_parse.source_host(canonical_url)` — lowercased hostname,
`www.` stripped, port dropped (same function `pajak_monitor.py` now uses for every new row).

**routing_status/routing_targets reset**: set to `'unrouted'` / `'{}'::jsonb` (the column's own
default) so `scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py` — which selects
`WHERE routing_status = 'unrouted'` and re-`UPDATE`s `routing_targets` under the same guard —
re-classifies these 122 rows against the CORRECT domain on its next run. The router's own UPDATE
is itself `WHERE routing_status = 'unrouted'`, so this DML and the router cron can never race
each other into a double-write.

```sql
-- ═══════════════════════════════════════════════════════════════════════
-- DRAFT (a) — RELABEL 122 pajak.go.id-mislabeled intel_items rows
-- EXECUTED on PROD 2026-09-22 15:00:42Z (owner-authorized); see header.
-- ═══════════════════════════════════════════════════════════════════════

BEGIN;

SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';

-- 1. Archive current values BEFORE mutation — the only way to reconstruct
--    "what nb-intel routing this row had" if this needs to be reversed.
--    Postgres semantics of `CREATE TABLE IF NOT EXISTS ... AS SELECT`: if
--    the table already exists, the SELECT is NOT re-executed — so a retry
--    after a partial prior run does NOT re-archive rows a second time
--    (which would overwrite the original pre-mutation snapshot with an
--    already-mutated one). That is exactly the re-run-safety this needs.
CREATE TABLE IF NOT EXISTS intel_items_pajak_relabel_archive_20260921 AS
SELECT id, canonical_url, source_domain, routing_status, routing_targets, now() AS archived_at
FROM intel_items
WHERE source_domain = 'pajak.go.id'
  AND canonical_url NOT LIKE 'https://pajak.go.id/%'
  AND canonical_url NOT LIKE 'https://www.pajak.go.id/%';

-- 2. Expected-count assertion — refuse to proceed if the live cohort no
--    longer matches what this draft was built against (122 rows, one
--    routing_status value).
DO $$
DECLARE
  actual_count integer;
BEGIN
  SELECT count(*) INTO actual_count
  FROM intel_items
  WHERE source_domain = 'pajak.go.id'
    AND canonical_url NOT LIKE 'https://pajak.go.id/%'
    AND canonical_url NOT LIKE 'https://www.pajak.go.id/%';

  IF actual_count <> 122 THEN
    RAISE EXCEPTION
      'expected 122 mislabeled pajak.go.id rows, found %; cohort has drifted since this draft was written — do not proceed blind, recompute the draft',
      actual_count;
  END IF;
END $$;

-- 3. The relabel itself. Re-run-safe: the WHERE clause is the SAME
--    "mislabeled" predicate, so a row already fixed by a prior partial run
--    (source_domain no longer 'pajak.go.id') is simply not matched again.
--    source_domain is set via a CASE that mirrors pajak_parse.source_host():
--    lowercase, strip a leading "www.", drop port/path — done here with
--    regexp on canonical_url since this is a one-time SQL statement, not a
--    call into the Python helper.
UPDATE intel_items
SET source_domain = lower(regexp_replace(regexp_replace(canonical_url, '^https?://(www\.)?', ''), '[/:].*$', '')),
    routing_status = 'unrouted',
    routing_targets = '{}'::jsonb
WHERE source_domain = 'pajak.go.id'
  AND canonical_url NOT LIKE 'https://pajak.go.id/%'
  AND canonical_url NOT LIKE 'https://www.pajak.go.id/%';

-- 4. Post-mutation assertion: exactly the archived row count was touched,
--    no more, no less.
DO $$
DECLARE
  archived_count integer;
  updated_count integer;
BEGIN
  SELECT count(*) INTO archived_count FROM intel_items_pajak_relabel_archive_20260921;
  SELECT count(*) INTO updated_count
  FROM intel_items i
  JOIN intel_items_pajak_relabel_archive_20260921 a ON a.id = i.id
  WHERE i.routing_status = 'unrouted' AND i.source_domain <> 'pajak.go.id';

  IF updated_count <> archived_count THEN
    RAISE EXCEPTION
      'relabel touched % rows, expected exactly % (archived count) — ROLLBACK, do not commit a partial relabel',
      updated_count, archived_count;
  END IF;
END $$;

COMMIT;
```

**Rollback** (restores `source_domain`/`routing_status`/`routing_targets` from the archive;
run only if the relabel above was already committed):

```sql
BEGIN;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';

UPDATE intel_items i
SET source_domain = a.source_domain,
    routing_status = a.routing_status,
    routing_targets = a.routing_targets
FROM intel_items_pajak_relabel_archive_20260921 a
WHERE i.id = a.id;

COMMIT;
-- The archive table is left in place after rollback (evidence of the
-- incident); drop it manually only once the rollback is verified correct.
```

---

## (b) BACKFILL — 20 existing pajak peraturan rows

**Counted live, read-only:**

```sql
SELECT count(*) FROM intel_items
WHERE canonical_url LIKE 'https://pajak.go.id/id/peraturan/%';
-- => 20
```

None of the 20 currently carry `citation`/`verbatim_excerpt` in `raw_payload` (all 20 are
`{"type": "tax_regulation", "pipeline": "intel_stage1"}` only) — this backfill is what
`pajak_monitor.py`'s new enrichment (#7087) would have produced had it existed
when these rows were first ingested.

**Fetched live** (browser-like User-Agent, 2-4 s delay between requests, `pajak_parse.
extract_regulation()` against the fetched HTML — same function the committed code now runs
automatically):

- **18 of 20 extracted successfully** — citation + verbatim_excerpt + regulation_date all
  present, citation confirmed a literal delimited substring of the excerpt.
- **2 of 20 failed and are LEFT UNTOUCHED below** — in both cases the `field--name-field-nomor-
dokumen` value does not literally occur in the body heading (DJP data-quality issue, not an
  extractor bug — verified by re-reading the raw body text for one of the two):
  - `d41d251b-bd69-4df0-b122-606fb015ae7a` (`.../nilai-kurs-.../-1484`) — nomor field
    `30/MK/EF.2/2026`, but the body heading uses a different token (extractor correctly returned
    `citation: None` rather than guessing).
  - `046a7fc4-305f-44d8-b74c-90dc9d497cfa` (`.../pajak-pertambahan-nilai-atas-penyerahan-jasa-
angkutan-udara-niaga-berjadwal-dalam-4`) — nomor field says `PMK 43 TAHUN 2026`, but the
    body heading literally reads `...NOMOR 43 TAHUN 2026` (no `PMK` token) — confirmed by
    re-fetching and reading the raw body text.

**`intel_observations` — explicitly NOT touched.** Per `168_intel_lake_schema.sql`,
`intel_observations` is an **append-only** producer-hit ledger (`item_id` FK → `intel_items`,
`ON DELETE CASCADE`, no FK the other direction) — each row is its own historical `raw_payload`
snapshot at the moment that producer observed the URL. Backfilling `intel_items.raw_payload` does
not, and must not, rewrite `intel_observations` history; the two tables are allowed to disagree
on `raw_payload` by design (`intel_observations` is the audit trail, `intel_items` is the current
best-known state).

```sql
-- ═══════════════════════════════════════════════════════════════════════
-- DRAFT (b) — BACKFILL citation/verbatim_excerpt/extractor for 18 of 20
-- pajak peraturan rows already in intel_items. EXECUTED on PROD 2026-09-22 15:01:03Z.
-- ═══════════════════════════════════════════════════════════════════════

BEGIN;

SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';

-- 1. Archive current values BEFORE mutation.
CREATE TABLE IF NOT EXISTS intel_items_pajak_backfill_archive_20260921 AS
SELECT id, canonical_url, raw_payload, published_at, now() AS archived_at
FROM intel_items
WHERE canonical_url LIKE 'https://pajak.go.id/id/peraturan/%';

-- 2. Expected-count assertion.
DO $$
DECLARE
  actual_count integer;
BEGIN
  SELECT count(*) INTO actual_count
  FROM intel_items
  WHERE canonical_url LIKE 'https://pajak.go.id/id/peraturan/%';

  IF actual_count <> 20 THEN
    RAISE EXCEPTION
      'expected 20 pajak peraturan rows, found %; cohort has drifted since this draft was written — recompute before proceeding',
      actual_count;
  END IF;
END $$;

-- 3. Per-row backfill, keyed by canonical_url. Re-run-safe: guarded by
--    `NOT (raw_payload ? 'citation')`, so a row already backfilled by a
--    prior partial run is skipped, never double-merged.
UPDATE intel_items
SET raw_payload = raw_payload || jsonb_build_object(
      'citation', $CIT0$NOMOR KEP-185/PJ/2026$CIT0$,
      'verbatim_excerpt', $EXC0$NOMOR KEP-185/PJ/2026 TENTANG KEBIJAKAN ADMINISTRASI PERPAJAKAN SEHUBUNGAN DENGAN BENCANA ALAM DI WILAYAH PROVINSI NUSA TENGGARA TIMUR TAHUN 2026 DIREKTUR JENDERAL PAJAK,$EXC0$,
      'extractor', 'pajak_parse.extract_regulation/1'
    ),
    published_at = '2026-09-02T12:00:00Z'::timestamptz
WHERE canonical_url = 'https://pajak.go.id/id/peraturan/kebijakan-administrasi-perpajakan-sehubungan-dengan-bencana-alam-di-wilayah-provinsi-nusa'
  AND NOT (raw_payload ? 'citation');

-- ...then one UPDATE of the same shape for each of the other 17 rows in the
-- table below (citation and verbatim_excerpt as extracted, published_at =
-- the regulation date, extractor 'pajak_parse.extract_regulation/1').
-- Not repeated here: the executed values now sit in each row's raw_payload,
-- and the pre-mutation values in intel_items_pajak_backfill_archive_20260921.
-- Skipped, left untouched: d41d251b-bd69-4df0-b122-606fb015ae7a (.../-1484)
-- and 046a7fc4-305f-44d8-b74c-90dc9d497cfa (...angkutan-udara-...-4).

-- 4. Post-mutation assertion: exactly 18 rows now carry a citation, the
--    2 known-failed rows still do not.
DO $$
DECLARE
  backfilled_count integer;
BEGIN
  SELECT count(*) INTO backfilled_count
  FROM intel_items
  WHERE canonical_url LIKE 'https://pajak.go.id/id/peraturan/%'
    AND raw_payload ? 'citation';

  IF backfilled_count <> 18 THEN
    RAISE EXCEPTION
      'backfill produced % citation-bearing rows, expected exactly 18 — ROLLBACK, do not commit',
      backfilled_count;
  END IF;
END $$;

COMMIT;
```

**The 18 backfilled rows** (slug under `https://pajak.go.id/id/peraturan/`, citation, regulation date):

| slug                                                                                        | citation                                                               | date       |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------- |
| `kebijakan-administrasi-perpajakan-sehubungan-dengan-bencana-alam-di-wilayah-provinsi-nusa` | `NOMOR KEP-185/PJ/2026`                                                | 2026-09-02 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1476` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 20/MK/EF.2/2026`  | 2026-05-05 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1477` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 21/MK/EF.2/2026`  | 2026-05-12 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1478` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 22/MK/EF.2/2026`  | 2026-05-19 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1480` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 28/MK/EF.2/2026`  | 2026-06-24 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1482` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 26/MK/EF.2/2026`  | 2026-06-09 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1483` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 27/MK/EF.2/2026`  | 2026-06-16 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1485` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 31/MK/EF.2/2026`  | 2026-07-07 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1486` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 33/MK/EF.2/2026`  | 2026-07-21 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1487` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 34/MK/EF.2/2026`  | 2026-07-28 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1488` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 41/MK/EF.2/2026`  | 2026-09-01 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1492` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 38/MK/EF.2/2026`  | 2026-08-18 |
| `nilai-kurs-sebagai-dasar-pelunasan-bea-masuk-pajak-pertambahan-nilai-barang-dan-jasa-1493` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 39/MK/EF.2/2026`  | 2026-08-25 |
| `perubahan-atas-peraturan-direktur-jenderal-pajak-nomor-10pj2024-tentang-ketentuan`         | `NOMOR PER-8/PJ/2026`                                                  | 2026-07-28 |
| `tarif-bunga-sebagai-dasar-penghitungan-sanksi-administratif-berupa-bunga-dan-pemberian-54` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 019/MK/EF.2/2026` | 2026-04-30 |
| `tarif-bunga-sebagai-dasar-penghitungan-sanksi-administratif-berupa-bunga-dan-pemberian-56` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 29/MK/EF.2/2026`  | 2026-06-29 |
| `tarif-bunga-sebagai-dasar-penghitungan-sanksi-administratif-berupa-bunga-dan-pemberian-58` | `KEPUTUSAN MENTERI KEUANGAN REPUBLIK INDONESIA NOMOR 40/MK/EF.2/2026`  | 2026-08-31 |
| `tata-cara-pelaksanaan-hak-dan-pemenuhan-kewajiban-pajak-minimum-global-berdasarkan`        | `NOMOR PER-6/PJ/2026`                                                  | 2026-05-04 |

**Rollback** (restores `raw_payload`/`published_at` from the archive for all 20 rows,
including the 2 that were never touched — a no-op for those):

```sql
BEGIN;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '5s';

UPDATE intel_items i
SET raw_payload = a.raw_payload,
    published_at = a.published_at
FROM intel_items_pajak_backfill_archive_20260921 a
WHERE i.id = a.id;

COMMIT;
-- Archive table left in place after rollback; drop manually once verified.
```
