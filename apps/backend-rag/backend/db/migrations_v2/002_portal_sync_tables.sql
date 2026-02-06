-- ================================================
-- Migration 002: Portal Sync Tables (Timeline/Taxes/Visa) + Visibility Flags
-- Created: 2026-02-02
-- Purpose:
--   - Add persistent, client-visible timeline events
--   - Add per-client tax obligations tracking
--   - Add per-client visa record tracking (optional, complements practices)
--   - Add client visibility flags to practices/documents for portal filtering
-- Idempotency: YES (uses IF NOT EXISTS / safe ALTERs)
-- Dependencies: 001_baseline_v2.sql (or legacy schema present)
-- ================================================

-- --------------------------------
-- Practices: portal visibility + client-safe summary
-- --------------------------------
ALTER TABLE public.practices
    ADD COLUMN IF NOT EXISTS client_visible BOOLEAN DEFAULT true;

ALTER TABLE public.practices
    ADD COLUMN IF NOT EXISTS client_summary TEXT;

CREATE INDEX IF NOT EXISTS idx_practices_client_visible
    ON public.practices (client_visible);

-- --------------------------------
-- Documents: ensure portal visibility + uploaded source
-- --------------------------------
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS client_visible BOOLEAN DEFAULT true;

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS uploaded_source VARCHAR(20) DEFAULT 'team';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_documents_uploaded_source'
          AND conrelid = 'public.documents'::regclass
    ) THEN
        ALTER TABLE public.documents
            ADD CONSTRAINT chk_documents_uploaded_source
                CHECK (uploaded_source IN ('team', 'client'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_client_visible
    ON public.documents (client_visible);

-- --------------------------------
-- Timeline Events (persistent, client-filtered)
-- --------------------------------
CREATE TABLE IF NOT EXISTS public.timeline_events (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT public.uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    practice_id INTEGER REFERENCES public.practices(id) ON DELETE SET NULL,

    event_type VARCHAR(30) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,

    client_visible BOOLEAN DEFAULT true,

    icon VARCHAR(50),
    color VARCHAR(20) DEFAULT 'info',
    action_url TEXT,
    action_label VARCHAR(100),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),

    CONSTRAINT chk_timeline_event_type CHECK (
        event_type IN (
            'deadline', 'milestone', 'document_request', 'document_received',
            'status_change', 'payment_due', 'appointment', 'reminder', 'completion'
        )
    ),
    CONSTRAINT chk_timeline_color CHECK (color IN ('info', 'warning', 'success', 'error'))
);

CREATE INDEX IF NOT EXISTS idx_timeline_events_client
    ON public.timeline_events (client_id);

CREATE INDEX IF NOT EXISTS idx_timeline_events_date
    ON public.timeline_events (event_date);

CREATE INDEX IF NOT EXISTS idx_timeline_events_visible
    ON public.timeline_events (client_visible);

-- --------------------------------
-- Tax Obligations (recurring / per-client deadlines)
-- --------------------------------
CREATE TABLE IF NOT EXISTS public.tax_obligations (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT public.uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
    -- company_id removed: clients with client_type='company' serve as company records

    tax_type VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    frequency VARCHAR(20) NOT NULL,

    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    due_date DATE NOT NULL,

    status VARCHAR(20) DEFAULT 'upcoming',
    amount_due NUMERIC(15, 2),
    amount_paid NUMERIC(15, 2),

    filing_document_id INTEGER REFERENCES public.documents(id) ON DELETE SET NULL,
    payment_proof_id INTEGER REFERENCES public.documents(id) ON DELETE SET NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_tax_obligations_tax_type CHECK (
        tax_type IN ('pph_21', 'pph_23', 'pph_4_2', 'ppn', 'spt_annual', 'npwp')
    ),
    CONSTRAINT chk_tax_obligations_frequency CHECK (
        frequency IN ('monthly', 'quarterly', 'annual', 'one_time')
    ),
    CONSTRAINT chk_tax_obligations_status CHECK (
        status IN ('upcoming', 'pending', 'filed', 'paid', 'overdue')
    )
);

CREATE INDEX IF NOT EXISTS idx_tax_obligations_client
    ON public.tax_obligations (client_id);

CREATE INDEX IF NOT EXISTS idx_tax_obligations_due_date
    ON public.tax_obligations (due_date);

CREATE INDEX IF NOT EXISTS idx_tax_obligations_status
    ON public.tax_obligations (status);

-- --------------------------------
-- Visa Records (optional structured visa tracking)
-- --------------------------------
CREATE TABLE IF NOT EXISTS public.visa_records (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT public.uuid_generate_v4(),
    client_id INTEGER NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,

    visa_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'none',

    issue_date DATE,
    expiry_date DATE,

    visa_number VARCHAR(100),
    sponsor_name VARCHAR(255),
    sponsor_type VARCHAR(20),

    practice_id INTEGER REFERENCES public.practices(id) ON DELETE SET NULL,
    visa_document_id INTEGER REFERENCES public.documents(id) ON DELETE SET NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_visa_records_visa_type CHECK (
        visa_type IN (
            'tourist', 'business', 'social', 'kitas_work', 'kitas_investor',
            'kitas_retirement', 'kitas_spouse', 'kitap', 'evoa'
        )
    ),
    CONSTRAINT chk_visa_records_status CHECK (
        status IN ('none', 'applied', 'processing', 'active', 'expiring_soon', 'expired', 'cancelled')
    ),
    CONSTRAINT chk_visa_records_sponsor_type CHECK (
        sponsor_type IS NULL OR sponsor_type IN ('company', 'individual')
    )
);

CREATE INDEX IF NOT EXISTS idx_visa_records_client
    ON public.visa_records (client_id);

CREATE INDEX IF NOT EXISTS idx_visa_records_status
    ON public.visa_records (status);

CREATE INDEX IF NOT EXISTS idx_visa_records_expiry
    ON public.visa_records (expiry_date);
