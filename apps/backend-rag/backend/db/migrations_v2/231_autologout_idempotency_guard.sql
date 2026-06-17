-- 231_autologout_idempotency_guard.sql
--
-- Fix the auto-logout cron loop that wrote 174 duplicate clock_out rows for a
-- single team member (damar@balizero.com, 2026-06-15). Root cause:
-- `auto_logout_expired_sessions()` (called every 5 min by
-- TeamTimesheetService._auto_logout_loop) inserted a clock_out at a FIXED 18:30
-- Bali timestamp for any session whose latest action is clock_in and is past
-- 18:30 — with NO idempotency guard. The injected clock_out carries a timestamp
-- (18:30) that can be OLDER than an evening clock_in, so the user's "latest
-- action" stays clock_in and the predicate re-fires every tick, forever.
-- Symptom: 174 identical clock_out rows + "access denied" on absen because the
-- timesheet state is incoherent.
--
-- Fix: the function is owned by backend_rag_v2; this migration is the SSOT
-- (the function previously had no definition under migrations_v2/ — repo↔DB
-- drift, superscar #1). The guard: never insert a second auto-logout whose
-- timestamp equals that day's 18:30 target if one already exists. Idempotent
-- regardless of any later clock_in (the damar case). superscar #2 + #9.

CREATE OR REPLACE FUNCTION public.auto_logout_expired_sessions()
 RETURNS TABLE(out_user_id character varying, out_email character varying, out_clock_in_time timestamp with time zone, out_auto_logout_time timestamp with time zone)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    WITH latest_actions AS (
        SELECT DISTINCT ON (t.user_id)
            t.user_id AS la_user_id,
            t.email AS la_email,
            t.timestamp AS la_timestamp,
            t.action_type AS la_action_type
        FROM team_timesheet t
        ORDER BY t.user_id, t.timestamp DESC
    ),
    expired_sessions AS (
        SELECT
            la.la_user_id,
            la.la_email,
            la.la_timestamp as clock_in_time,
            (DATE(la.la_timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00') AT TIME ZONE 'Asia/Makassar' as target_logout
        FROM latest_actions la
        WHERE la.la_action_type = 'clock_in'
          AND NOW() AT TIME ZONE 'Asia/Makassar' > (DATE(la.la_timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00')
          AND NOT EXISTS (
              SELECT 1 FROM team_timesheet co
              WHERE co.user_id = la.la_user_id
                AND co.action_type = 'clock_out'
                AND co.timestamp = (DATE(la.la_timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00') AT TIME ZONE 'Asia/Makassar'
          )
    ),
    inserted AS (
        INSERT INTO team_timesheet (user_id, email, action_type, timestamp, notes)
        SELECT
            es.la_user_id, es.la_email, 'clock_out', es.target_logout, 'Auto-logout at 18:30 Bali time'
        FROM expired_sessions es
        RETURNING team_timesheet.user_id, team_timesheet.email, team_timesheet.timestamp
    )
    SELECT i.user_id::VARCHAR, i.email::VARCHAR, es.clock_in_time, i.timestamp
    FROM inserted i JOIN expired_sessions es ON i.user_id = es.la_user_id;
END;
$function$;

-- === ROLLBACK ===
-- Restore the pre-guard function (re-introduces the duplicate-insert bug; for
-- emergency revert only).
CREATE OR REPLACE FUNCTION public.auto_logout_expired_sessions()
 RETURNS TABLE(out_user_id character varying, out_email character varying, out_clock_in_time timestamp with time zone, out_auto_logout_time timestamp with time zone)
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN QUERY
    WITH latest_actions AS (
        SELECT DISTINCT ON (t.user_id)
            t.user_id, t.email, t.timestamp, t.action_type
        FROM team_timesheet t
        ORDER BY t.user_id, t.timestamp DESC
    ),
    expired_sessions AS (
        SELECT la.user_id, la.email, la.timestamp as clock_in_time,
            (DATE(la.timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00') AT TIME ZONE 'Asia/Makassar' as target_logout
        FROM latest_actions la
        WHERE la.action_type = 'clock_in'
          AND NOW() AT TIME ZONE 'Asia/Makassar' > (DATE(la.timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00')
    ),
    inserted AS (
        INSERT INTO team_timesheet (user_id, email, action_type, timestamp, notes)
        SELECT es.user_id, es.email, 'clock_out', es.target_logout, 'Auto-logout at 18:30 Bali time'
        FROM expired_sessions es
        RETURNING team_timesheet.user_id, team_timesheet.email, team_timesheet.timestamp
    )
    SELECT i.user_id::VARCHAR, i.email::VARCHAR, es.clock_in_time, i.timestamp
    FROM inserted i JOIN expired_sessions es ON i.user_id = es.user_id;
END;
$function$;
