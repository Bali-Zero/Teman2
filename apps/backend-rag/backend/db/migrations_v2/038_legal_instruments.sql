-- Migration 038: Legal instruments registry for NB Verified Generation Pipeline
-- Tracks T0/T1 normative sources: status, conflicts, vigenza

CREATE TABLE IF NOT EXISTS legal_instruments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id   VARCHAR(100) NOT NULL UNIQUE,
    instrument_type VARCHAR(50)  NOT NULL,           -- 'UU', 'PP', 'Permenkumham', 'Permen', 'SE', 'Juklak'
    tier            SMALLINT     NOT NULL DEFAULT 0, -- 0=Primary law, 1=Official interpretation
    domain          VARCHAR(50)  NOT NULL,           -- 'immigration', 'company', 'tax', 'property'
    title           TEXT         NOT NULL,
    number          VARCHAR(50),
    year            SMALLINT,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',  -- 'active', 'superseded', 'partially_superseded', 'revoked'
    vigore_date     DATE,
    revoked_by      VARCHAR(100),
    conflict_note   TEXT,
    source_url      TEXT,
    source_file     TEXT,
    nb_uploaded     BOOLEAN NOT NULL DEFAULT FALSE,
    nb_uploaded_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legal_inst_domain_status ON legal_instruments(domain, status);
CREATE INDEX IF NOT EXISTS idx_legal_inst_type          ON legal_instruments(instrument_type, year DESC);
CREATE INDEX IF NOT EXISTS idx_legal_inst_nb_uploaded   ON legal_instruments(nb_uploaded) WHERE NOT nb_uploaded;

CREATE OR REPLACE FUNCTION legal_instruments_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER legal_instruments_updated_at
    BEFORE UPDATE ON legal_instruments
    FOR EACH ROW EXECUTE FUNCTION legal_instruments_set_updated_at();

-- Seed: Immigration domain T0+T1 sources
INSERT INTO legal_instruments
    (instrument_id, instrument_type, tier, domain, title, number, year, status, vigore_date, source_url)
VALUES
    ('UU-6-2011',
     'UU', 0, 'immigration',
     'Undang-Undang No. 6 Tahun 2011 tentang Keimigrasian',
     '6/2011', 2011, 'active', '2011-05-05',
     'https://peraturan.bpk.go.id/Details/39480'),
    ('PP-31-2013',
     'PP', 0, 'immigration',
     'PP No. 31 Tahun 2013 tentang Peraturan Pelaksanaan UU Keimigrasian',
     '31/2013', 2013, 'active', '2013-05-02',
     'https://peraturan.bpk.go.id/Details/5173'),
    ('Permenkumham-22-2023',
     'Permenkumham', 1, 'immigration',
     'Permenkumham No. 22 Tahun 2023 tentang Visa dan Izin Tinggal',
     '22/2023', 2023, 'partially_superseded', '2023-08-01',
     'https://peraturan.bpk.go.id/Details/275012'),
    ('Permen-Imipas-3-2025',
     'Permen', 1, 'immigration',
     'Peraturan Menteri Imigrasi No. 3 Tahun 2025',
     '3/2025', 2025, 'active', '2025-02-01',
     NULL),
    ('SE-Kemnaker-3-836-2026',
     'SE', 1, 'immigration',
     'Surat Edaran Kemnaker No. SE-3/836/2026 tentang TKA',
     'SE-3/836', 2026, 'active', '2026-01-15',
     NULL)
ON CONFLICT (instrument_id) DO NOTHING;

-- Mark the conflict: Permenkumham-22-2023 partially superseded by Permen-Imipas-3-2025
UPDATE legal_instruments
SET
    revoked_by    = 'Permen-Imipas-3-2025',
    conflict_note = 'Le disposizioni sui visti multipli entry di Permenkumham 22/2023 sono state superate da Permen Imipas 3/2025 entrata in vigore il 01-02-2025. Le disposizioni su KITAS e KITAP rimangono in vigore fino a nuova normativa.'
WHERE instrument_id = 'Permenkumham-22-2023';
