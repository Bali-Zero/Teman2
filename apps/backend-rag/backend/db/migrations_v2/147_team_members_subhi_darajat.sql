-- ============================================================
-- 147_team_members_subhi_darajat.sql
-- Onboard Subhi Darajat into team_members table
-- Date: 2026-04-30
--
-- Subhi Darajat joins as Growth Systems Owner (Organic Acquisition &
-- Conversion) on 2026-04-30. Probation: 90 days (until 2026-07-29).
-- Office: Kuta, full-time.
--
-- This migration only inserts the team_members row. RBAC grants
-- (CRM read-only on assigned, GA4 viewer, GSC viewer, Vercel viewer)
-- are external (Google admin / Vercel dashboard) and not represented
-- in this schema. See ~/.claude/projects/-Users-nuzantara/memory/
-- subhi-rbac-permissions.md for the full access matrix.
--
-- HR enrollment (hr_employees, hr_leave_balances) is intentionally
-- DEFERRED until probation conversion (~2026-07-30), per
-- project_subhi_offer.md decision: "no BPJS/THR during probation".
--
-- pin_hash: real bcrypt hash (cost=12) of a 6-digit numeric temporary PIN
-- generated cryptographically (secrets.randbelow). The clear-text PIN is
-- communicated to Subhi out-of-band (WhatsApp, in person Day 1) and is
-- NOT stored anywhere in this repo. Subhi MUST change PIN at first login
-- via the admin set-pin endpoint (POST /api/admin/users/{id}/set-pin)
-- after Antonello reissues the call OR via a self-service change-pin
-- flow if/when one is implemented.
--
-- Why bcrypt cost=12: matches the gensalt() default in
-- backend/app/routers/auth.py:71 (verify_password) and
-- backend/services/portal/invite_service.py:198 (PIN setting for clients).
-- Consistent with existing team_members rows.
--
-- Idempotent: ON CONFLICT DO NOTHING on email unique constraint.
-- Safe to re-run. Re-running does NOT overwrite a manually-rotated PIN.
-- ============================================================

INSERT INTO team_members (
    id,
    email,
    full_name,
    name,
    pin_hash,
    role,
    department,
    language,
    active,
    personalized_response,
    failed_attempts,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid()::text,
    'subhi@balizero.com',
    'Subhi Darajat',
    'Subhi Darajat',
    '$2b$12$RnEY5lh0n1Ls3pLkqzAmY.jWKdrNjqDEpBehlhxQM53/NZBsI/Sf2',
    'member',
    'growth',
    'id',
    TRUE,
    FALSE,
    0,
    '2026-04-30 09:30:00+08'::timestamptz,
    NOW()
)
ON CONFLICT (email) DO NOTHING;

-- === ROLLBACK ===
DELETE FROM team_members WHERE email = 'subhi@balizero.com';
