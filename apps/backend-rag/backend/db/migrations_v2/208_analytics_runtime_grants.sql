-- 208_analytics_runtime_grants.sql
-- Runtime grants for background analytics/attendance jobs.
--
-- Live symptoms fixed by this migration:
-- - AttendanceMonitor escalation scan denied access to attendance_late_incidents
-- - TeamTimesheetService auto-logout loop denied access to team_timesheet
--
-- These objects may be historical/prod-owned, and the runtime role may be
-- absent in CI databases. Keep every object lookup guarded and fail with a
-- precise owner/admin remediation message if production still needs a manual
-- grant.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    sequence_name text;
    sequence_reg regclass;
    function_name text;
    function_reg regprocedure;
    write_objects text[] := ARRAY[
        'public.attendance_late_incidents',
        'public.team_timesheet'
    ];
    execute_functions text[] := ARRAY[
        'public.auto_logout_expired_sessions()'
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

    FOREACH function_name IN ARRAY execute_functions LOOP
        function_reg := to_regprocedure(function_name);

        IF function_reg IS NULL THEN
            CONTINUE;
        END IF;

        IF NOT has_function_privilege(runtime_role, function_reg, 'EXECUTE') THEN
            BEGIN
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION %s TO %I',
                    function_reg,
                    runtime_role
                );
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE WARNING
                        'manual grant required: GRANT EXECUTE ON FUNCTION % TO %',
                        function_name,
                        runtime_role;
            END;
        END IF;

        IF NOT has_function_privilege(runtime_role, function_reg, 'EXECUTE') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing EXECUTE on function %; apply manual grant with an owner/admin role',
                function_name;
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
    function_name text;
    function_reg regprocedure;
    write_objects text[] := ARRAY[
        'public.attendance_late_incidents',
        'public.team_timesheet'
    ];
    execute_functions text[] := ARRAY[
        'public.auto_logout_expired_sessions()'
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

    FOREACH function_name IN ARRAY execute_functions LOOP
        function_reg := to_regprocedure(function_name);

        IF function_reg IS NOT NULL THEN
            EXECUTE format(
                'REVOKE EXECUTE ON FUNCTION %s FROM %I',
                function_reg,
                runtime_role
            );
        END IF;
    END LOOP;
END
$revoke_block$;
