-- 170_wr2_draft_lease.sql
-- Adds per-draft CAS lease to war_room_drafts.
-- Two columns: lease_owner (PID@host string) + lease_acquired_at (timestamptz).
-- Used by canva_renderer_v2 orchestrator to prevent double-processing.
-- Numbered 170 because 169 was concurrently claimed by 169_crm_workspace_ai_snapshots.sql
-- on main (cicatrix STRUCTURAL 2026-04-29 P0-7 number-collision pattern).

ALTER TABLE war_room_drafts
  ADD COLUMN IF NOT EXISTS lease_owner text,
  ADD COLUMN IF NOT EXISTS lease_acquired_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_war_room_drafts_lease_recovery
  ON war_room_drafts (lease_acquired_at)
  WHERE status = 'rendering' AND lease_acquired_at IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_war_room_drafts_lease_recovery;
ALTER TABLE war_room_drafts
  DROP COLUMN IF EXISTS lease_acquired_at,
  DROP COLUMN IF EXISTS lease_owner;
