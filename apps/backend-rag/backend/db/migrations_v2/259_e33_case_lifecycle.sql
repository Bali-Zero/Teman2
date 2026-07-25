-- Migration 259: E33 Second Home case lifecycle (CRM backend, Fase 3.2).
--
-- Purpose:
--   Persistence for the E33 Second Home client case lifecycle modelled in
--   backend/services/crm/e33_lifecycle.py (stages FIT_MEMO → … → RENEWAL /
--   EPO / STATUS_CHANGE, with ITAP_EVAL gated off until the letter-006 Q7
--   reply). The coarse CRM practice status keeps flowing through
--   practice_state_machine.py; this table carries the E33-specific case
--   stages underneath an on_process practice (optional practice_id link).
--
-- NO-CUSTODY SOP (owner decision 2026-07-23):
--   Bali Zero NEVER holds client funds. The evidence JSONB stores REFERENCES
--   ONLY — document ids, kinds, issue/filing dates, confirmations — never
--   account numbers, balances or amounts. There are deliberately NO amount /
--   balance / account columns in this table. PII stays minimal per UU PDP:
--   the case links to the CRM client by id; names/passports live in clients.
--
-- Dependents:
--   dependent_code / principal_case_id model the dependent relationship
--   (candidate codes E31B/E31E/E31H/E31J, PENDING official confirmation —
--   enforced in code via the configurable DEFAULT_DEPENDENT_CODES, not in
--   this DDL, so a confirmed code change is a code edit, not a migration).
--
-- Day-90 gate:
--   guarantee_proof_deadline is a stored snapshot of entry/ITAS + 90 days,
--   refreshed by E33CaseRepository.save() on every write; the authoritative
--   computation stays in code (compute_guarantee_deadline). Alert schedule
--   (Day 30/60/75) is computed in code and delivered through the existing
--   compliance_alerts machinery — no alert state is duplicated here.

CREATE TABLE IF NOT EXISTS e33_cases (
    case_id                  TEXT PRIMARY KEY,
    client_id                INTEGER NOT NULL REFERENCES clients(id),
    practice_id              INTEGER REFERENCES practices(id),
    basis                    TEXT NOT NULL
                             CHECK (basis IN ('deposit', 'property')),
    stage                    TEXT NOT NULL
                             CHECK (stage IN (
                                 'fit_memo', 'bank_precheck', 'application',
                                 'payment', 'visa_issued', 'entry',
                                 'itas_active', 'guarantee_proof_due',
                                 'annual_maintenance', 'renewal',
                                 'epo', 'status_change', 'itap_eval'
                             )),
    owner_email              TEXT,
    entry_date               DATE,
    itas_date                DATE,
    guarantee_proof_deadline DATE,
    dependent_code           TEXT,
    principal_case_id        TEXT REFERENCES e33_cases(case_id),
    dependents               JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    stage_history            JSONB NOT NULL DEFAULT '[]'::jsonb,
    stayguard_eligible       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_e33_cases_client ON e33_cases (client_id);
CREATE INDEX IF NOT EXISTS idx_e33_cases_stage ON e33_cases (stage);
CREATE INDEX IF NOT EXISTS idx_e33_cases_guarantee_deadline
    ON e33_cases (guarantee_proof_deadline)
    WHERE guarantee_proof_deadline IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_e33_cases_principal ON e33_cases (principal_case_id)
    WHERE principal_case_id IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_e33_cases_principal;
DROP INDEX IF EXISTS idx_e33_cases_guarantee_deadline;
DROP INDEX IF EXISTS idx_e33_cases_stage;
DROP INDEX IF EXISTS idx_e33_cases_client;
DROP TABLE IF EXISTS e33_cases;
