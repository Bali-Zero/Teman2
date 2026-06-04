-- 209_memory_work_sessions_runtime_grants.sql
-- Runtime grants for memory facts and Olympus work-session maintenance.
--
-- Live symptoms fixed by this migration:
-- - MemoryService PostgreSQL load denied access to memory_facts during startup
-- - Olympus Guardian sequence repair denied access to team_work_sessions
--
-- These tables can be prod-owned by an owner/admin role while the app runs as
-- backend_rag_v2. Keep the migration guarded for CI/local databases, and fail
-- with a precise remediation message if production still needs owner grants.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    sequence_name text;
    sequence_reg regclass;
    write_objects text[] := ARRAY[
        'public.memory_facts',
        'public.team_work_sessions'
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
            AND has_table_privilege(runtime_role, object_reg, 'DELETE')
        ) THEN
            BEGIN
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %s TO %I',
                    object_reg,
                    runtime_role
                );
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE WARNING
                        'manual grant required: GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE % TO %',
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

        IF NOT has_table_privilege(runtime_role, object_reg, 'DELETE') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing DELETE on %; apply manual grant with an owner/admin role',
                object_name;
        END IF;

        sequence_name := pg_get_serial_sequence(object_name, 'id');

        IF sequence_name IS NOT NULL THEN
            sequence_reg := to_regclass(sequence_name);

            IF sequence_reg IS NOT NULL
                AND NOT (
                    has_sequence_privilege(runtime_role, sequence_reg, 'USAGE')
                    AND has_sequence_privilege(runtime_role, sequence_reg, 'SELECT')
                ) THEN
                BEGIN
                    EXECUTE format(
                        'GRANT USAGE, SELECT ON SEQUENCE %s TO %I',
                        sequence_reg,
                        runtime_role
                    );
                EXCEPTION
                    WHEN insufficient_privilege THEN
                        RAISE WARNING
                            'manual grant required: GRANT USAGE, SELECT ON SEQUENCE % TO %',
                            sequence_name,
                            runtime_role;
                END;
            END IF;

            IF sequence_reg IS NOT NULL
                AND NOT has_sequence_privilege(runtime_role, sequence_reg, 'USAGE') THEN
                RAISE EXCEPTION
                    'backend_rag_v2 is missing USAGE on sequence %; apply manual grant with an owner/admin role',
                    sequence_name;
            END IF;

            IF sequence_reg IS NOT NULL
                AND NOT has_sequence_privilege(runtime_role, sequence_reg, 'SELECT') THEN
                RAISE EXCEPTION
                    'backend_rag_v2 is missing SELECT on sequence %; apply manual grant with an owner/admin role',
                    sequence_name;
            END IF;
        END IF;
    END LOOP;
END
$grant_block$;

-- === ROLLBACK ===
DO $revoke_block$
DECLARE
    runtime_role text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    sequence_name text;
    sequence_reg regclass;
    write_objects text[] := ARRAY[
        'public.memory_facts',
        'public.team_work_sessions'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    FOREACH object_name IN ARRAY write_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NOT NULL THEN
            EXECUTE format(
                'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLE %s FROM %I',
                object_reg,
                runtime_role
            );
        END IF;

        sequence_name := pg_get_serial_sequence(object_name, 'id');

        IF sequence_name IS NOT NULL THEN
            sequence_reg := to_regclass(sequence_name);

            IF sequence_reg IS NOT NULL THEN
                EXECUTE format(
                    'REVOKE USAGE, SELECT ON SEQUENCE %s FROM %I',
                    sequence_reg,
                    runtime_role
                );
            END IF;
        END IF;
    END LOOP;
END
$revoke_block$;
