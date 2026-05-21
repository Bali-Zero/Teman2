-- migration 191: whatsapp export staging
--
-- Local WhatsApp export backfill staging only. These tables intentionally keep
-- raw export paths backstage in DB and do not write directly into CRM tables.
-- Later APIs must expose only safe basenames and masked fields.
--
-- Wave 1 decisions:
-- - YOPO canonical batch is nested folder only.
-- - INVOICE BALI ZERO and E ITK ONLINE are separate future batches.
-- - No auto-create CRM from vCards.
-- - No LID auto-normalization from exports.
-- - Review actions require an audit trail.

CREATE TABLE IF NOT EXISTS whatsapp_export_batches (
    id BIGSERIAL PRIMARY KEY,
    source_root TEXT NOT NULL,
    source_label TEXT,
    source_hash TEXT NOT NULL UNIQUE,
    chat_title TEXT,
    canonical_chat_path TEXT,
    status TEXT NOT NULL DEFAULT 'parsed'
        CHECK (status IN ('parsed', 'reviewing', 'completed', 'failed', 'archived')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS whatsapp_export_contacts_staging (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES whatsapp_export_batches(id) ON DELETE CASCADE,
    source_file TEXT,
    source_relpath TEXT NOT NULL,
    display_name TEXT,
    phone_raw TEXT,
    phone_canonical TEXT,
    waid TEXT,
    matched_client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    matched_whatsapp_contact_id BIGINT REFERENCES whatsapp_contacts(id) ON DELETE SET NULL,
    match_confidence NUMERIC(5,4)
        CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    match_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    duplicate_group_key TEXT,
    is_team_candidate BOOLEAN NOT NULL DEFAULT false,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'ignored')),
    approved_client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    rejected_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_whatsapp_export_contacts_batch_relpath_phone
    ON whatsapp_export_contacts_staging (
        batch_id,
        source_relpath,
        COALESCE(phone_canonical, '')
    );

CREATE TABLE IF NOT EXISTS whatsapp_export_messages_staging (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES whatsapp_export_batches(id) ON DELETE CASCADE,
    source_relpath TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    message_date TIMESTAMPTZ,
    sender_display_name TEXT,
    body TEXT,
    body_excerpt TEXT,
    has_attachments BOOLEAN NOT NULL DEFAULT false,
    attachment_relpaths JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'ignored')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_whatsapp_export_messages_batch_relpath_index
    ON whatsapp_export_messages_staging (batch_id, source_relpath, message_index);

CREATE TABLE IF NOT EXISTS whatsapp_export_documents_staging (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL REFERENCES whatsapp_export_batches(id) ON DELETE CASCADE,
    source_relpath TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_ext TEXT,
    file_size_bytes BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    sha256 TEXT,
    document_category TEXT,
    inferred_service_type TEXT,
    inferred_person_name TEXT,
    inferred_company_name TEXT,
    inferred_sponsor_company TEXT,
    inferred_document_date DATE,
    match_confidence NUMERIC(5,4)
        CHECK (match_confidence IS NULL OR (match_confidence >= 0 AND match_confidence <= 1)),
    match_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    matched_practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
    contains_sensitive_data BOOLEAN NOT NULL DEFAULT true,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'approved', 'rejected', 'ignored')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_whatsapp_export_documents_batch_relpath
    ON whatsapp_export_documents_staging (batch_id, source_relpath);

CREATE TABLE IF NOT EXISTS whatsapp_export_review_actions (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL
        CHECK (entity_type IN ('contact', 'message', 'document', 'batch')),
    entity_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    actor_email TEXT,
    previous_status TEXT
        CHECK (previous_status IS NULL OR previous_status IN ('pending', 'approved', 'rejected', 'ignored')),
    new_status TEXT
        CHECK (new_status IS NULL OR new_status IN ('pending', 'approved', 'rejected', 'ignored')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_batches_status
    ON whatsapp_export_batches (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_batch
    ON whatsapp_export_contacts_staging (batch_id);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_review_confidence
    ON whatsapp_export_contacts_staging (review_status, match_confidence DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_phone_canonical
    ON whatsapp_export_contacts_staging (phone_canonical)
    WHERE phone_canonical IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_matched_client
    ON whatsapp_export_contacts_staging (matched_client_id)
    WHERE matched_client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_matched_whatsapp_contact
    ON whatsapp_export_contacts_staging (matched_whatsapp_contact_id)
    WHERE matched_whatsapp_contact_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_approved_client
    ON whatsapp_export_contacts_staging (approved_client_id)
    WHERE approved_client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_contacts_duplicate_group
    ON whatsapp_export_contacts_staging (duplicate_group_key)
    WHERE duplicate_group_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_messages_batch
    ON whatsapp_export_messages_staging (batch_id);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_messages_review
    ON whatsapp_export_messages_staging (review_status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_messages_date
    ON whatsapp_export_messages_staging (message_date)
    WHERE message_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_documents_batch
    ON whatsapp_export_documents_staging (batch_id);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_documents_review_confidence
    ON whatsapp_export_documents_staging (review_status, match_confidence DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_documents_matched_client
    ON whatsapp_export_documents_staging (matched_client_id)
    WHERE matched_client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_documents_matched_practice
    ON whatsapp_export_documents_staging (matched_practice_id)
    WHERE matched_practice_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_documents_sha256
    ON whatsapp_export_documents_staging (sha256)
    WHERE sha256 IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_review_actions_entity
    ON whatsapp_export_review_actions (entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_whatsapp_export_review_actions_actor
    ON whatsapp_export_review_actions (actor_email, created_at DESC)
    WHERE actor_email IS NOT NULL;

-- === ROLLBACK ===

DROP INDEX IF EXISTS ix_whatsapp_export_review_actions_actor;
DROP INDEX IF EXISTS ix_whatsapp_export_review_actions_entity;
DROP INDEX IF EXISTS ix_whatsapp_export_documents_sha256;
DROP INDEX IF EXISTS ix_whatsapp_export_documents_matched_practice;
DROP INDEX IF EXISTS ix_whatsapp_export_documents_matched_client;
DROP INDEX IF EXISTS ix_whatsapp_export_documents_review_confidence;
DROP INDEX IF EXISTS ix_whatsapp_export_documents_batch;
DROP INDEX IF EXISTS ix_whatsapp_export_messages_date;
DROP INDEX IF EXISTS ix_whatsapp_export_messages_review;
DROP INDEX IF EXISTS ix_whatsapp_export_messages_batch;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_duplicate_group;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_approved_client;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_matched_whatsapp_contact;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_matched_client;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_phone_canonical;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_review_confidence;
DROP INDEX IF EXISTS ix_whatsapp_export_contacts_batch;
DROP INDEX IF EXISTS ix_whatsapp_export_batches_status;
DROP INDEX IF EXISTS ux_whatsapp_export_documents_batch_relpath;
DROP INDEX IF EXISTS ux_whatsapp_export_messages_batch_relpath_index;
DROP INDEX IF EXISTS ux_whatsapp_export_contacts_batch_relpath_phone;
DROP TABLE IF EXISTS whatsapp_export_review_actions;
DROP TABLE IF EXISTS whatsapp_export_documents_staging;
DROP TABLE IF EXISTS whatsapp_export_messages_staging;
DROP TABLE IF EXISTS whatsapp_export_contacts_staging;
DROP TABLE IF EXISTS whatsapp_export_batches;
