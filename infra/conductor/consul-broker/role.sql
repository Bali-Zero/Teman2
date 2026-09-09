-- OFFLINE DBA REVIEW ONLY. The installer never executes this file.
-- Target: Pro local nuzantara_dev, after migrations 279, 306 and 307 are applied.
-- An existing role causes rollback: inspect its grants instead of overwriting it.
BEGIN;
CREATE ROLE nuzantara_consul LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE nuzantara_dev TO nuzantara_consul;
GRANT USAGE ON SCHEMA public TO nuzantara_consul;
GRANT SELECT, INSERT ON public.research_os_objects TO nuzantara_consul;
GRANT SELECT, INSERT, UPDATE ON public.autonomous_lab_runs,
    public.autonomous_lab_events_outbox, public.autonomous_lab_consul_leases
    TO nuzantara_consul;
GRANT USAGE, SELECT ON SEQUENCE public.research_os_objects_id_seq,
    public.autonomous_lab_events_outbox_event_id_seq TO nuzantara_consul;
ALTER ROLE nuzantara_consul SET search_path = pg_catalog, public;
ALTER ROLE nuzantara_consul SET statement_timeout = '10s';
ALTER ROLE nuzantara_consul SET lock_timeout = '2s';
-- PUBLIC grants can defeat an otherwise narrow role. Abort instead of changing
-- shared grants: the DBA must resolve that policy independently.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND n.nspname NOT LIKE 'pg_temp%'
          AND NOT (n.nspname = 'public' AND c.relname IN (
              'research_os_objects', 'autonomous_lab_runs',
              'autonomous_lab_events_outbox', 'autonomous_lab_consul_leases'))
          AND has_table_privilege('nuzantara_consul', c.oid,
              'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
    ) THEN
        RAISE EXCEPTION 'consul role inherits access outside approved metadata tables';
    END IF;
END $$;
COMMIT;
-- Set login material with the DBA's protected credential procedure; no password
-- belongs in this SQL, shell arguments, Git, logs, or the model-side environment.
