-- 207_team_admin_runtime_grants.sql
-- Runtime read grants for team/admin dashboard endpoints.
--
-- Live symptom fixed by this migration:
-- - /api/admin/team-activity/overview denied SELECT on conversations
-- - /api/admin/team-activity/team-stats reads v_messages and activity rollups
-- - /api/team/my-status denied SELECT on team_online_status
--
-- The objects are historical/prod-owned in some environments, so every grant is
-- guarded with to_regclass(). The runtime role is absent in CI test databases,
-- so the whole migration is guarded on pg_roles.
--
-- In production this migration is executed by the runtime role. That role can
-- verify its existing privileges, but cannot grant privileges on objects owned
-- by other roles. If owner-level grants are still missing, fail with a precise
-- manual-remediation message instead of a raw PostgreSQL permission error.

DO $grant_block$
DECLARE
    runtime_role constant text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    read_objects text[] := ARRAY[
        'public.conversations',
        'public.v_messages',
        'public.team_online_status',
        'public.daily_work_hours',
        'public.weekly_work_summary',
        'public.monthly_work_summary',
        'public.team_timesheet',
        'public.team_members',
        'public.activity_log',
        'public.email_activity_log',
        'public.knowledge_activity_log',
        'public.kg_nodes',
        'public.kg_edges'
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
                EXECUTE format('GRANT SELECT ON TABLE %s TO %I', object_reg, runtime_role);
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
    END LOOP;
END
$grant_block$;

-- === ROLLBACK ===
DO $revoke_block$
DECLARE
    runtime_role text := 'backend_rag_v2';
    object_name text;
    object_reg regclass;
    read_objects text[] := ARRAY[
        'public.conversations',
        'public.v_messages',
        'public.team_online_status',
        'public.daily_work_hours',
        'public.weekly_work_summary',
        'public.monthly_work_summary',
        'public.team_timesheet',
        'public.team_members',
        'public.activity_log',
        'public.email_activity_log',
        'public.knowledge_activity_log',
        'public.kg_nodes',
        'public.kg_edges'
    ];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
        RETURN;
    END IF;

    FOREACH object_name IN ARRAY read_objects LOOP
        object_reg := to_regclass(object_name);

        IF object_reg IS NOT NULL THEN
            EXECUTE format('REVOKE SELECT ON TABLE %s FROM %I', object_reg, runtime_role);
        END IF;
    END LOOP;
END
$revoke_block$;
