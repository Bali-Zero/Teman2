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
-- pin_hash: locked placeholder ('!locked-pending-day1-pin-set').
-- bcrypt verification of any user-supplied PIN against this string
-- always returns False, so PIN login is blocked until Day 1 when
-- Antonello (admin) sets a real bcrypt hash via the auth admin
-- endpoint. SSO/OAuth login paths bypass pin_hash and remain
-- available.
--
-- Idempotent: ON CONFLICT DO NOTHING on email unique constraint.
-- Safe to re-run.
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
    '!locked-pending-day1-pin-set',
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
