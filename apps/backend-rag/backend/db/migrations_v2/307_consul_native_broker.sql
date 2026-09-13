-- Native grants extend the existing Lab lease projection, not its scheduler.
-- Runtime-specific completion checks are fenced by the same lease generation.
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = public, pg_catalog;

ALTER TABLE public.autonomous_lab_consul_leases
    DROP CONSTRAINT autonomous_lab_consul_leases_resource_check,
    ADD CONSTRAINT autonomous_lab_consul_leases_resource_check
        CHECK (resource ~ '^(synthetic|native):[A-Za-z0-9][A-Za-z0-9_.:/-]{0,191}$'),
    ADD COLUMN native_completion_generation BIGINT
        CHECK (native_completion_generation IS NULL OR native_completion_generation > 0);

-- === ROLLBACK ===
-- Native rows require an explicit decision before reverting their schema.
-- This constraint fails safely if any native grant remains; no rows are deleted.
ALTER TABLE public.autonomous_lab_consul_leases
    DROP CONSTRAINT autonomous_lab_consul_leases_resource_check,
    ADD CONSTRAINT autonomous_lab_consul_leases_resource_check
        CHECK (resource ~ '^synthetic:[A-Za-z0-9][A-Za-z0-9_.:/-]{0,191}$'),
    DROP COLUMN native_completion_generation;
