-- Migration 229: align team_members.avatar with the frontend roster SSOT (2026-06-15).
--
-- The CRM/portal renders team_members.avatar to clients (assigned-consultant avatar,
-- portal.py -> "avatar_url"). Those values had drifted: several pointed at .png files
-- removed by the 2026-06-15 team-photo refresh (adit/ari/dea/krisna/sahira.png -> .jpg)
-- and ruslana pointed at the deleted legacy /avatars/team directory. This realigns every
-- Bali Zero teammate to the canonical /static/team/<slug>.jpg paths in
-- apps/mouth/src/data/team-roster.ts (single source of truth).
--
-- Idempotent, single column, specific emails only. Email targets verified live 2026-06-15
-- (prefix drift: ari->ari.firda, veronika->tax, angel->angel.tax, dewaayu->dewaayu.tax,
-- faisha->faysha.tax). Apply on the Pro like 212-228:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev -f .../229_team_avatars_align_roster.sql
-- === FORWARD ===

UPDATE team_members AS t SET avatar = v.avatar
FROM (VALUES
    ('zainal@balizero.com',     '/static/team/zainal-ceo.jpg'),
    ('ruslana@balizero.com',    '/static/team/ruslana.jpg'),
    ('adit@balizero.com',       '/static/team/adit.jpg'),
    ('ari.firda@balizero.com',  '/static/team/ari.jpg'),
    ('krisna@balizero.com',     '/static/team/krisna.jpg'),
    ('dea@balizero.com',        '/static/team/dea.jpg'),
    ('surya@balizero.com',      '/static/team/surya.jpg'),
    ('candra@balizero.com',     '/static/team/candra.jpg'),
    ('damar@balizero.com',      '/static/team/damar.jpg'),
    ('tax@balizero.com',        '/static/team/veronika.jpg'),
    ('angel.tax@balizero.com',  '/static/team/angel.jpg'),
    ('dewaayu.tax@balizero.com','/static/team/dewaayu.jpg'),
    ('faysha.tax@balizero.com', '/static/team/faisha.jpg'),
    ('asya@balizero.com',       '/static/team/asya.jpg'),
    ('sahira@balizero.com',     '/static/team/sahira.jpg'),
    ('subhi@balizero.com',      '/static/team/subhi.jpg')
) AS v(email, avatar)
WHERE t.email = v.email;

-- Members with no real photo yet -> clear stale/placeholder avatar so UI shows initials
-- instead of requesting a removed file (Kadek/Vino/Rina, as of 2026-06-15).
UPDATE team_members SET avatar = NULL
WHERE email IN ('kadek.tax@balizero.com', 'vino@balizero.com', 'rina@balizero.com')
  AND avatar IS NOT NULL;

-- === ROLLBACK ===
-- No safe automatic rollback (prior avatars were drifted/broken). Restore from DB backup
-- if a revert is ever required.
