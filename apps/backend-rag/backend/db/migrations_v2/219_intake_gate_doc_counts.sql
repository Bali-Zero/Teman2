-- 219_intake_gate_doc_counts.sql
-- INTAKE login gate — Pro→Fly document-count mirror (anti-Surya gate-1 on Fly).
--
-- Gate-1 document PII lives ONLY on the Pro nuzantara_dev (Law 2 / UU-PDP). On
-- Fly the intake tables are empty, so the Fly gate evaluator cannot see how many
-- documents a worker has pending. This table mirrors a NON-PII signal — a per-
-- user pending-document COUNT (a single integer) — pushed by a Pro worker via
-- POST /api/bridge/intake-gate/doc-counts. Counts are not PII, so the mirror
-- respects sovereignty: no document content, no client identity, just an integer
-- keyed by the worker's own email.
--
-- The Fly gate evaluator reads this table for gate-1 (when INTAKE_GATE_USE_MIRROR
-- is set); the Pro evaluator queries the live local intake tables directly.

CREATE TABLE IF NOT EXISTS intake_gate_doc_counts (
    user_email      VARCHAR(255) PRIMARY KEY,
    pending_count   INTEGER NOT NULL DEFAULT 0 CHECK (pending_count >= 0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE intake_gate_doc_counts IS
    'Pro->Fly mirror of per-user pending intake-document counts for the login gate. Non-PII (integer only); source of truth is the Pro nuzantara_dev. updated_at lets the evaluator treat a stale row as 0 (graceful).';

-- === ROLLBACK ===
DROP TABLE IF EXISTS intake_gate_doc_counts;
