-- Migration 303: the VOA issuance price returns to 750.000 IDR
--
-- Ruled by the owner on 2026-08-31, reversing his own 2026-07-24 directive.
-- The extension is NOT touched: it stays 850.000 IDR, which is what both the
-- sheet and this table already say.
--
--   practice_types.code = 'visa_b1_voa'  base_price 790000 -> 750000
--
-- WHY A FORWARD MIGRATION AND NOT A REVERT OF 302
-- =============================================================================
--   302 is not a file that can be deleted. It was APPLIED in production at
--   2026-08-31 03:51:44 UTC, by the release_command of the fly deploy that the
--   merge of #5407 triggered on its own (fly-deploy.yml runs on any push to
--   main touching apps/backend-rag/**). `public.schema_migrations` records it,
--   so the runner will never execute anything numbered 302 again. Removing the
--   file would leave production at 790000 with nothing in the tree explaining
--   why, and would fail a fresh environment differently from the live one.
--
--   Its ROLLBACK section is not the instrument either: the runner applies
--   forward sections in order and only reads a ROLLBACK on an explicit
--   teardown. Ordinary deploys would never see it.
--
-- WHY THE PRICE MOVED TWICE IN ONE DAY
-- =============================================================================
--   The 790.000 figure was the owner's directive of 2026-07-24 (commit
--   80dcb24068, PR #3037). That commit also asserted "there is no stale DB
--   base_price to fix here" -- it had checked the code `visa_voa`, which does
--   not exist in this database, instead of `visa_b1_voa`, which does. So the
--   sheet moved to 790.000 in July and the table stayed at 750.000 from
--   migration 221 (2026-06-09) onward, and the two stores disagreed for two
--   months without anything noticing. 302 closed that divergence on the 790
--   side; hours later the owner ruled the figure itself should be 750.000, so
--   this migration closes it again on the other side. The DIVERGENCE was the
--   defect; which of the two numbers is right is a pricing decision, and it
--   is his.
--
-- SCOPE
-- =============================================================================
--   One column of one row. No schema change, no ownership transfer, no grant.
--   Idempotent: code-scoped and value-guarded, so a rerun updates zero rows
--   rather than churning updated_at.
--
--   Deliberately NOT touched: `ext_b1_voa` (already 850000, set by 221), and
--   the five is_active = false rows whose prices merely look implausible.

UPDATE practice_types
   SET base_price = 750000,
       updated_at = CURRENT_TIMESTAMP
 WHERE code = 'visa_b1_voa'
   AND base_price IS DISTINCT FROM 750000;

-- Postcondition: refuse to record this migration as applied unless the row is
-- what the owner ruled. A silent no-op here would leave the CRM quoting
-- 790.000 while the migration log claimed the reversal had landed.
DO $$
DECLARE
    current_price numeric;
BEGIN
    SELECT base_price INTO current_price
      FROM practice_types
     WHERE code = 'visa_b1_voa';

    IF current_price IS NULL THEN
        RAISE NOTICE 'practice_types row visa_b1_voa is absent -- skipping; this database has not applied migration 221';
        RETURN;
    END IF;

    IF current_price IS DISTINCT FROM 750000 THEN
        RAISE EXCEPTION
            'migration 303: practice_types.visa_b1_voa is % , expected 750000 -- the CRM would keep quoting the superseded price while this migration recorded success',
            current_price;
    END IF;
END;
$$;

-- === ROLLBACK ===

-- Reinstates the superseded 2026-07-24 figure. Exists for local/CI teardown,
-- not as an operational option: running it puts the CRM back at a price the
-- owner has explicitly reversed.
UPDATE practice_types
   SET base_price = 790000,
       updated_at = CURRENT_TIMESTAMP
 WHERE code = 'visa_b1_voa';
