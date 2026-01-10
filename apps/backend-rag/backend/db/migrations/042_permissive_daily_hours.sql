-- Migration: Make Daily Hours View Permissive
-- Purpose: Include active (incomplete) shifts in the view so they appear in reports.
-- Created: 2026-01-06

CREATE OR REPLACE VIEW daily_work_hours AS
SELECT
    user_id,
    email,
    DATE(clock_in_bali) as work_date,
    clock_in_bali,
    CASE
        WHEN next_action_type = 'clock_out' THEN clock_out_bali
        ELSE NULL
    END as clock_out_bali,
    CASE
        WHEN next_action_type = 'clock_out' THEN ROUND(CAST(EXTRACT(EPOCH FROM (clock_out_bali - clock_in_bali))/3600 AS NUMERIC), 2)
        ELSE NULL
    END as hours_worked
FROM (
    SELECT
        user_id,
        email,
        (timestamp AT TIME ZONE 'Asia/Makassar') as clock_in_bali,
        LEAD((timestamp AT TIME ZONE 'Asia/Makassar')) OVER (
            PARTITION BY user_id 
            ORDER BY timestamp
        ) as clock_out_bali,
        action_type,
        LEAD(action_type) OVER (
            PARTITION BY user_id
            ORDER BY timestamp
        ) as next_action_type
    FROM team_timesheet
) AS shifts
WHERE action_type = 'clock_in';

COMMENT ON VIEW daily_work_hours IS 'Daily hours v3: Includes active/incomplete sessions for visibility';
