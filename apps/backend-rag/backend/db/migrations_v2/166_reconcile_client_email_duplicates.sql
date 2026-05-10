-- Migration 166: reconcile client email duplicates and enforce normalized uniqueness
--
-- Context:
--   `clients.email` has a legacy UNIQUE(email) constraint, but PostgreSQL text
--   uniqueness is case-sensitive. Prod had a case-only duplicate on
--   2026-05-10: `guasraf32@gmail.com` / `Guasraf32@gmail.com`.
--
-- Safety:
--   - Client rows are not merged or deleted.
--   - Every changed email is archived before mutation.
--   - Non-canonical duplicate emails are nulled so their attached records and
--     Drive/document links remain intact.
--   - Remaining emails are normalized with trim/lowercase.
--   - A partial unique expression index prevents future case/space variants.

SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS client_email_reconciliation_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    migration_name TEXT NOT NULL,
    client_id BIGINT NOT NULL,
    old_email TEXT,
    new_email TEXT,
    reason TEXT NOT NULL,
    client_snapshot JSONB NOT NULL,
    UNIQUE (migration_name, client_id)
);

WITH annotated_clients AS (
    SELECT
        c.id AS client_id,
        c.email AS old_email,
        LOWER(BTRIM(c.email)) AS normalized_email,
        COUNT(*) OVER (
            PARTITION BY LOWER(BTRIM(c.email))
        ) AS normalized_count,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(BTRIM(c.email))
            ORDER BY c.created_at NULLS LAST, c.id
        ) AS normalized_rank,
        TO_JSONB(c) AS client_snapshot
    FROM clients c
    WHERE c.email IS NOT NULL
),
changes AS (
    SELECT
        client_id,
        old_email,
        CASE
            WHEN BTRIM(old_email) = '' THEN NULL::TEXT
            WHEN normalized_count > 1 AND normalized_rank > 1 THEN NULL::TEXT
            ELSE normalized_email
        END AS new_email,
        CASE
            WHEN BTRIM(old_email) = '' THEN 'blank_email_to_null'
            WHEN normalized_count > 1 AND normalized_rank > 1 THEN
                'duplicate_case_insensitive_email_to_null'
            WHEN old_email IS DISTINCT FROM normalized_email THEN
                'normalize_email_lower_trim'
        END AS reason,
        client_snapshot
    FROM annotated_clients
    WHERE BTRIM(old_email) = ''
       OR (normalized_count > 1 AND normalized_rank > 1)
       OR old_email IS DISTINCT FROM normalized_email
)
INSERT INTO client_email_reconciliation_archive (
    migration_name,
    client_id,
    old_email,
    new_email,
    reason,
    client_snapshot
)
SELECT
    '166_reconcile_client_email_duplicates',
    client_id,
    old_email,
    new_email,
    reason,
    client_snapshot
FROM changes
ON CONFLICT (migration_name, client_id) DO NOTHING;

UPDATE clients c
SET
    email = NULL,
    updated_at = NOW()
FROM client_email_reconciliation_archive archive
WHERE archive.migration_name = '166_reconcile_client_email_duplicates'
  AND archive.reason IN (
      'blank_email_to_null',
      'duplicate_case_insensitive_email_to_null'
  )
  AND archive.client_id = c.id
  AND c.email IS DISTINCT FROM archive.new_email;

UPDATE clients
SET
    email = LOWER(BTRIM(email)),
    updated_at = NOW()
WHERE email IS NOT NULL
  AND BTRIM(email) <> ''
  AND email IS DISTINCT FROM LOWER(BTRIM(email));

CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_email_lower_not_blank
    ON clients (LOWER(BTRIM(email)))
    WHERE email IS NOT NULL
      AND BTRIM(email) <> '';

INSERT INTO _schema_versions (
    migration_name,
    migration_number,
    description,
    applied_by,
    checksum
)
VALUES (
    '166_reconcile_client_email_duplicates',
    166,
    'Reconcile client email duplicates and enforce normalized uniqueness',
    'migration-166',
    'tracked-by-migration-166'
)
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

DROP INDEX IF EXISTS uq_clients_email_lower_not_blank;

UPDATE clients c
SET
    email = archive.old_email,
    updated_at = NOW()
FROM client_email_reconciliation_archive archive
WHERE archive.migration_name = '166_reconcile_client_email_duplicates'
  AND archive.reason = 'normalize_email_lower_trim'
  AND archive.client_id = c.id;

UPDATE clients c
SET
    email = archive.old_email,
    updated_at = NOW()
FROM client_email_reconciliation_archive archive
WHERE archive.migration_name = '166_reconcile_client_email_duplicates'
  AND archive.reason IN (
      'blank_email_to_null',
      'duplicate_case_insensitive_email_to_null'
  )
  AND archive.client_id = c.id;

DELETE FROM _schema_versions
WHERE migration_name = '166_reconcile_client_email_duplicates';
