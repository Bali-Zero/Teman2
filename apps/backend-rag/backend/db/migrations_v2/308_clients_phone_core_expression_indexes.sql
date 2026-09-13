-- Expression indexes for the upsert-by-phone core-equivalence matcher.
--
-- UPSERT_MATCH_SQL (backend/app/routers/crm_clients.py) matches a client by
-- collapsing phone_normalized / phone / whatsapp to the canonical phone core
-- (digits, one leading 62/0 stripped — backend.phone_lock.phone_core) INSIDE
-- the WHERE clause, so none of the plain btree indexes on those columns can
-- serve it and every call is a sequential scan of the whole table with three
-- regexp_replace() per row. Measured 2026-09-10 on the production primary:
-- 2.54M seq scans / 30.6B tuples read lifetime on `clients` (12k rows),
-- ~0.6 scans/s sustained from the wa-mirror auto-promote loop (345 upserts
-- every ~12 min), and the primary shared-cpu-2x pinned at its CPU baseline
-- (cpu_balance 234 vs 100000 on the replicas, throttle 87%/24h, `vm` health
-- check critical on `cpu`). The three CASE expressions below are copied
-- VERBATIM from the query so the planner can match them (a parity test pins
-- the two texts together); with them the predicate becomes a BitmapOr of three
-- index probes. No column, trigger or query text changes.
--
-- regexp_replace / substr / COALESCE / LIKE on text are IMMUTABLE, so the
-- expressions are indexable; `clients` is ~50 MB, the build is sub-second.
-- Slot 308 was free on origin/main at implementation. Recheck at merge.
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = public, pg_catalog;

CREATE INDEX IF NOT EXISTS idx_clients_phone_core_normalized
    ON public.clients ((
        CASE WHEN regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') LIKE '62%'
                  THEN substr(regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g'), 3)
             WHEN regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') LIKE '0%'
                  THEN substr(regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g'), 2)
             ELSE regexp_replace(COALESCE(phone_normalized, ''), '[^0-9]', '', 'g') END
    ));

CREATE INDEX IF NOT EXISTS idx_clients_phone_core_phone
    ON public.clients ((
        CASE WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '62%'
                  THEN substr(regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g'), 3)
             WHEN regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') LIKE '0%'
                  THEN substr(regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g'), 2)
             ELSE regexp_replace(COALESCE(phone, ''), '[^0-9]', '', 'g') END
    ));

CREATE INDEX IF NOT EXISTS idx_clients_phone_core_whatsapp
    ON public.clients ((
        CASE WHEN regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g') LIKE '62%'
                  THEN substr(regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g'), 3)
             WHEN regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g') LIKE '0%'
                  THEN substr(regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g'), 2)
             ELSE regexp_replace(COALESCE(whatsapp, ''), '[^0-9]', '', 'g') END
    ));

-- === ROLLBACK ===
-- Pure additive indexes: dropping them restores the sequential-scan plan and
-- nothing else. No data is touched in either direction.
DROP INDEX IF EXISTS public.idx_clients_phone_core_whatsapp;
DROP INDEX IF EXISTS public.idx_clients_phone_core_phone;
DROP INDEX IF EXISTS public.idx_clients_phone_core_normalized;
