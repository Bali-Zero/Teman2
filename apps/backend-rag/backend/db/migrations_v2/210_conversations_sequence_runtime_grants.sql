-- 210_conversations_sequence_runtime_grants.sql
-- Runtime grants for Olympus Guardian sequence repair on conversations.
--
-- Live symptom fixed by this migration:
-- - Olympus Guardian denied SELECT last_value on conversations_id_seq while
--   scanning public serial sequences.
--
-- Keep this guarded for CI/local databases. In production, fail with precise
-- remediation if the deploying role cannot apply the required owner grants.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    sequence_name constant text := 'public.conversations_id_seq';
    sequence_reg regclass;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    sequence_reg := to_regclass(sequence_name);

    IF sequence_reg IS NULL THEN
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

    IF NOT (
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

    IF NOT has_sequence_privilege(runtime_role, sequence_reg, 'USAGE') THEN
        RAISE EXCEPTION
            'backend_rag_v2 is missing USAGE on sequence %; apply manual grant with an owner/admin role',
            sequence_name;
    END IF;

    IF NOT has_sequence_privilege(runtime_role, sequence_reg, 'SELECT') THEN
        RAISE EXCEPTION
            'backend_rag_v2 is missing SELECT on sequence %; apply manual grant with an owner/admin role',
            sequence_name;
    END IF;

    IF NOT has_sequence_privilege(runtime_role, sequence_reg, 'UPDATE') THEN
        RAISE EXCEPTION
            'backend_rag_v2 is missing UPDATE on sequence %; apply manual grant with an owner/admin role',
            sequence_name;
    END IF;
END
$grant_block$;

-- === ROLLBACK ===
DO $revoke_block$
DECLARE
    runtime_role text := 'backend_rag_v2';
    sequence_name text := 'public.conversations_id_seq';
    sequence_reg regclass;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    sequence_reg := to_regclass(sequence_name);

    IF sequence_reg IS NOT NULL THEN
        EXECUTE format(
            'REVOKE USAGE, SELECT, UPDATE ON SEQUENCE %s FROM %I',
            sequence_reg,
            runtime_role
        );
    END IF;
END
$revoke_block$;
