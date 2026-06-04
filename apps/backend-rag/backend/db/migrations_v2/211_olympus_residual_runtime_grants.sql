-- 211_olympus_residual_runtime_grants.sql
-- Runtime grants for residual Olympus Guardian maintenance tasks.
--
-- Live symptoms fixed by this migration:
-- - sequence repair scan denied SELECT on query_clusters and x_monitored_tweets
-- - expired persistent session cleanup denied DELETE on persistent_sessions
--
-- Keep this guarded for CI/local databases. In production, fail with precise
-- remediation if the deploying role cannot apply the required owner grants.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    sequence_name text;
    sequence_reg regclass;
    read_objects text[] := ARRAY[
        'public.query_clusters',
        'public.x_monitored_tweets'
    ];
    write_objects text[] := ARRAY[
        'public.persistent_sessions'
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

    FOREACH object_name IN ARRAY read_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NULL THEN
            CONTINUE;
        END IF;

        IF NOT has_table_privilege(runtime_role, object_reg, 'SELECT') THEN
            BEGIN
                EXECUTE format(
                    'GRANT SELECT ON TABLE %s TO %I',
                    object_reg,
                    runtime_role
                );
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE WARNING
                        'manual grant required: GRANT SELECT ON TABLE % TO %',
                        object_name,
                        runtime_role;
            END;
        END IF;

        IF NOT has_table_privilege(runtime_role, object_reg, 'SELECT') THEN
            RAISE EXCEPTION
                'backend_rag_v2 is missing SELECT on %; apply manual grant with an owner/admin role',
                object_name;
        END IF;

        sequence_name := pg_get_serial_sequence(object_name, 'id');

        IF sequence_name IS NOT NULL THEN
            sequence_reg := to_regclass(sequence_name);

            IF sequence_reg IS NOT NULL
                AND NOT (
                    has_sequence_privilege(runtime_role, sequence_reg, 'USAGE')
                    AND has_sequence_privilege(runtime_role, sequence_reg, 'SELECT')
                    AND has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE')
                ) THEN
                BEGIN
                    EXECUTE format(
                        'GRANT USAGE, SELECT, UPDATE ON SEQUENCE %s TO %I',
                        sequence_reg,
                        runtime_role
                    );
                EXCEPTION
                    WHEN insufficient_privilege THEN
                        RAISE WARNING
                            'manual grant required: GRANT USAGE, SELECT, UPDATE ON SEQUENCE % TO %',
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

            IF sequence_reg IS NOT NULL
                AND NOT has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE') THEN
                RAISE EXCEPTION
                    'backend_rag_v2 is missing UPDATE on sequence %; apply manual grant with an owner/admin role',
                    sequence_name;
            END IF;
        END IF;
    END LOOP;

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
                    AND has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE')
                ) THEN
                BEGIN
                    EXECUTE format(
                        'GRANT USAGE, SELECT, UPDATE ON SEQUENCE %s TO %I',
                        sequence_reg,
                        runtime_role
                    );
                EXCEPTION
                    WHEN insufficient_privilege THEN
                        RAISE WARNING
                            'manual grant required: GRANT USAGE, SELECT, UPDATE ON SEQUENCE % TO %',
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

            IF sequence_reg IS NOT NULL
                AND NOT has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE') THEN
                RAISE EXCEPTION
                    'backend_rag_v2 is missing UPDATE on sequence %; apply manual grant with an owner/admin role',
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
    read_objects text[] := ARRAY[
        'public.query_clusters',
        'public.x_monitored_tweets'
    ];
    write_objects text[] := ARRAY[
        'public.persistent_sessions'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    FOREACH object_name IN ARRAY read_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NOT NULL THEN
            EXECUTE format(
                'REVOKE SELECT ON TABLE %s FROM %I',
                object_reg,
                runtime_role
            );
        END IF;

        sequence_name := pg_get_serial_sequence(object_name, 'id');

        IF sequence_name IS NOT NULL THEN
            sequence_reg := to_regclass(sequence_name);

            IF sequence_reg IS NOT NULL THEN
                EXECUTE format(
                    'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE %s FROM %I',
                    sequence_reg,
                    runtime_role
                );
            END IF;
        END IF;
    END LOOP;

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
                    'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE %s FROM %I',
                    sequence_reg,
                    runtime_role
                );
            END IF;
        END IF;
    END LOOP;
END
$revoke_block$;
