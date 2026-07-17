-- 244_compliance_alerts_runtime_grants.sql
-- Runtime grants for compliance_alerts (m114) — closes a gap left by the
-- 207-211 runtime-grants campaign, which never covered this table.
--
-- Live symptom fixed by this migration:
-- - backend/services/intake/gate_evaluator.py::_count_deadlines() runs
--   `SELECT count(*) FROM compliance_alerts a JOIN clients c ON ...` as part
--   of evaluate_gate_status()'s single try-block (documents + late_note +
--   deadlines all computed inside ONE `pool.acquire()`). Without SELECT on
--   compliance_alerts, that query raises InsufficientPrivilegeError, the
--   surrounding try/except (F4 fail-OPEN contract) swallows it and returns
--   `_degraded(...)` — which zeroes ALL THREE sections, not just deadlines.
--   Symptom observed: backend/tests/app/routers/test_intake_gate_mirror.py
--   ::test_evaluator_mirror_mode_blocks_and_respects_staleness asserts
--   `result["sections"]["documents"]["count"] == 2` and gets 0, even though
--   the documents-section query itself never touched compliance_alerts.
-- - backend/services/compliance/alert_repository.py (AlertRepository) does
--   INSERT (persist generated alerts), SELECT (find_active_by_dedup_key /
--   get / list_by_client), and UPDATE (promote severity/days_until,
--   update_status + timestamp columns) against compliance_alerts. No
--   runtime code path DELETEs rows — only test-fixture teardown
--   (backend/tests/app/routers/test_compliance_alerts_router.py) does, under
--   the local `test` role, never under backend_rag_v2 in production. DELETE
--   is deliberately NOT granted here (least privilege — do not over-grant).
--
-- The object is historical/prod-owned in some environments, so the grant is
-- guarded with to_regclass(). The runtime role is absent in CI test
-- databases, so the whole migration is guarded on pg_roles (same pattern as
-- 207-211).
--
-- In production this migration is executed by the runtime role. That role
-- can verify its existing privileges, but cannot grant privileges on objects
-- owned by other roles. If owner-level grants are still missing, fail with a
-- precise manual-remediation message instead of a raw PostgreSQL permission
-- error.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    write_objects text[] := ARRAY[
        'public.compliance_alerts'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    IF NOT has_schema_privilege(runtime_role, 'public', 'USAGE') THEN
        BEGIN
            GRANT USAGE ON SCHEMA public TO backend_rag_v2;
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE WARNING
                    'manual grant required: GRANT USAGE ON SCHEMA public TO %',
                    runtime_role;
        END;
    END IF;

    IF NOT has_schema_privilege(runtime_role, 'public', 'USAGE') THEN
        RAISE EXCEPTION
            'backend_rag_v2 is missing USAGE on schema public; apply manual grant with an owner/admin role';
    END IF;

    FOREACH object_name IN ARRAY write_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NULL THEN
            CONTINUE;
        END IF;

        IF NOT (
            has_table_privilege(runtime_role, object_reg, 'SELECT')
            AND has_table_privilege(runtime_role, object_reg, 'INSERT')
            AND has_table_privilege(runtime_role, object_reg, 'UPDATE')
        ) THEN
            BEGIN
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE ON TABLE %s TO %I',
                    object_reg,
                    runtime_role
                );
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE WARNING
                        'manual grant required: GRANT SELECT, INSERT, UPDATE ON TABLE % TO %',
                        object_name,
                        runtime_role;
            END;
        END IF;

        IF NOT has_table_privilege(runtime_role, object_reg, 'SELECT') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing SELECT on %; apply manual grant with an owner/admin role',
                object_name;
        END IF;

        IF NOT has_table_privilege(runtime_role, object_reg, 'INSERT') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing INSERT on %; apply manual grant with an owner/admin role',
                object_name;
        END IF;

        IF NOT has_table_privilege(runtime_role, object_reg, 'UPDATE') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing UPDATE on %; apply manual grant with an owner/admin role',
                object_name;
        END IF;

        -- NOTE (fix244-seqbug): a sequence-grant sub-block used to live here,
        -- guarded on `pg_get_serial_sequence(object_name, 'id')`. It assumed
        -- that call returns NULL when the table has no `id` column — it does
        -- not; Postgres RAISEs "column ... does not exist" instead, which is
        -- not caught by any exception handler in this DO-block. Because
        -- compliance_alerts.alert_id is TEXT PRIMARY KEY (no `id` column,
        -- no serial/identity — see 114_compliance_alerts.sql) and
        -- write_objects here is only ever `public.compliance_alerts`, that
        -- call ALWAYS raised in any environment where `backend_rag_v2`
        -- exists (i.e. prod), aborting this DO-block on every apply attempt
        -- and failing the Fly release_command (`apply_all_pending`). The
        -- sub-block was genuinely dead code (table has no sequence to grant
        -- on), so it is removed rather than guarded — least-surface fix.
    END LOOP;
END
$grant_block$;

-- === ROLLBACK ===
DO $revoke_block$
DECLARE
    runtime_role text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    write_objects text[] := ARRAY[
        'public.compliance_alerts'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    FOREACH object_name IN ARRAY write_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NOT NULL THEN
            EXECUTE format(
                'REVOKE SELECT, INSERT, UPDATE ON TABLE %s FROM %I',
                object_reg,
                runtime_role
            );
        END IF;
    END LOOP;
END
$revoke_block$;
