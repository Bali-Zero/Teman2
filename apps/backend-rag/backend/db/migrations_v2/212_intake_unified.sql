-- 212_intake_unified.sql — Unified document-intake (LOCAL Pro DB only)
-- Recepisce X1-X12 (04-0) + C1/C2/C3/C4/C5/C6 (03-panel).
-- Reference spec: research/operations/doc-intake-unified/05-final-spec.md section 2
-- PII 100% locale (Law 2 / UU-PDP): MAI applicare su Fly. Solo nuzantara_dev @127.0.0.1:5432.
-- === FORWARD ===

-- A. Registro IMMUTABILE blob fisici (append-only) — X1
CREATE TABLE IF NOT EXISTS document_instances (
    id                   BIGSERIAL PRIMARY KEY,
    blob_hash            CHAR(64)    NOT NULL,
    normalized_text_hash CHAR(64),
    phash                CHAR(16),
    pipeline_version     VARCHAR(32) NOT NULL,
    blob_path            TEXT        NOT NULL,
    byte_size            BIGINT,
    mime_type            VARCHAR(100),
    first_source         VARCHAR(8)  NOT NULL,
    first_source_ref     TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_di_source CHECK (first_source IN ('whatsapp','drive','zoho'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_di_blob_pipeline
    ON document_instances (blob_hash, pipeline_version);
CREATE INDEX IF NOT EXISTS idx_di_phash
    ON document_instances (phash, pipeline_version) WHERE phash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_di_text_hash
    ON document_instances (normalized_text_hash, pipeline_version) WHERE normalized_text_hash IS NOT NULL;

-- B. Coda di LAVORO unificata (mutabile) — X1
CREATE TABLE IF NOT EXISTS intake_queue (
    id                BIGSERIAL PRIMARY KEY,
    instance_id       BIGINT      NOT NULL REFERENCES document_instances(id) ON DELETE RESTRICT,
    source            VARCHAR(8)  NOT NULL,
    source_ref        TEXT        NOT NULL,
    blob_path         TEXT        NOT NULL,
    blob_hash         CHAR(64)    NOT NULL,
    text_hash         CHAR(64),
    phash             CHAR(16),
    client_id_hint    BIGINT,
    pipeline_version  VARCHAR(32) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    stage             VARCHAR(16),
    lease_owner       TEXT,
    lease_expires_at  TIMESTAMPTZ,
    attempts          INT NOT NULL DEFAULT 0,
    max_attempts      INT NOT NULL DEFAULT 5,
    next_visible_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error        TEXT,
    stage_output      JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedup_of          BIGINT REFERENCES intake_queue(id),
    near_dup_of       BIGINT REFERENCES intake_queue(id),
    near_dup_reason   VARCHAR(16),
    intake_key        TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_iq_source CHECK (source IN ('whatsapp','drive','zoho')),
    CONSTRAINT chk_iq_status CHECK (status IN
      ('pending','processing','ocr','classified','extracted',
       'review_pending','review_claimed','routed','rejected','done','dead','duplicate'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_iq_intake_key ON intake_queue (intake_key);
CREATE INDEX IF NOT EXISTS idx_iq_claimable
    ON intake_queue (next_visible_at, id)
    WHERE status IN ('pending','processing','ocr','classified','extracted');
CREATE INDEX IF NOT EXISTS idx_iq_review
    ON intake_queue (status, updated_at) WHERE status IN ('review_pending','review_claimed');
CREATE INDEX IF NOT EXISTS idx_iq_dead
    ON intake_queue (status, updated_at) WHERE status = 'dead';

-- C. Metriche per-stadio (append-only, osservabilita C6)
CREATE TABLE IF NOT EXISTS intake_stage_metrics (
    id          BIGSERIAL PRIMARY KEY,
    queue_id    BIGINT NOT NULL REFERENCES intake_queue(id) ON DELETE CASCADE,
    stage       VARCHAR(16) NOT NULL,
    latency_ms  INT,
    confidence  REAL,
    model       VARCHAR(80),
    ok          BOOLEAN,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- D. Routing proposal (P4 scrive, P5 legge) — X8/X9
CREATE TABLE IF NOT EXISTS document_routing_proposal (
    id               BIGSERIAL PRIMARY KEY,
    queue_id         BIGINT NOT NULL REFERENCES intake_queue(id) ON DELETE CASCADE,
    doc_index        INT NOT NULL DEFAULT 0,
    pipeline_version VARCHAR(32) NOT NULL,
    routing_key      TEXT NOT NULL,
    entity_resolution JSONB NOT NULL,
    routing          JSONB NOT NULL,
    commit_gate      JSONB NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'review_pending',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_rp_status CHECK (status IN ('review_pending','review_claimed','routed','rejected','dead'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rp_routing_key ON document_routing_proposal (routing_key);

-- E. Correzioni HITL (seme evolver) — P5
CREATE TABLE IF NOT EXISTS intake_corrections (
    id            BIGSERIAL PRIMARY KEY,
    queue_id      BIGINT      NOT NULL REFERENCES intake_queue(id) ON DELETE CASCADE,
    blob_hash     CHAR(64)    NOT NULL,
    doc_type      TEXT        NOT NULL,
    field_name    TEXT        NOT NULL,
    source        VARCHAR(8)  NOT NULL,
    ai_value      TEXT,
    human_value   TEXT,
    ai_confidence REAL,
    outcome       TEXT        NOT NULL,
    model_id      TEXT, model_version TEXT, stage TEXT,
    rule_passed   BOOLEAN,
    verified_by   TEXT        NOT NULL,
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_corrections_digest ON intake_corrections (doc_type, field_name, outcome);
CREATE INDEX IF NOT EXISTS idx_corrections_recent ON intake_corrections (verified_at);

-- F. updated_at trigger
CREATE OR REPLACE FUNCTION trg_intake_queue_touch() RETURNS trigger AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS t_intake_queue_touch ON intake_queue;
CREATE TRIGGER t_intake_queue_touch BEFORE UPDATE ON intake_queue
    FOR EACH ROW EXECUTE FUNCTION trg_intake_queue_touch();

-- G. cursore poll Zoho
INSERT INTO system_settings (key, value, updated_at)
VALUES ('zoho_intake_cursor', '{}', now()) ON CONFLICT (key) DO NOTHING;

COMMENT ON TABLE document_instances IS 'Immutable blob registry (X1). UNIQUE(blob_hash,pipeline_version) = exact cross-source dedup. PII local-only (Law 2).';
COMMENT ON TABLE intake_queue IS 'Unified work queue (X1). intake_key=sha256(source|source_ref|blob_hash|pipeline_version) (X7) UNIQUE. SKIP LOCKED claim via idx_iq_claimable. PII local-only (Law 2).';

-- === ROLLBACK ===
DROP TRIGGER IF EXISTS t_intake_queue_touch ON intake_queue;
DROP FUNCTION IF EXISTS trg_intake_queue_touch();
DROP TABLE IF EXISTS intake_corrections CASCADE;
DROP TABLE IF EXISTS document_routing_proposal CASCADE;
DROP TABLE IF EXISTS intake_stage_metrics CASCADE;
DROP TABLE IF EXISTS intake_queue CASCADE;
DROP TABLE IF EXISTS document_instances CASCADE;
DELETE FROM system_settings WHERE key = 'zoho_intake_cursor';
