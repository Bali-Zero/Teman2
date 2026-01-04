-- Migration: Fix Daily Hours View logic
-- Purpose: Fix the logic that incorrectly filtered clock-out events in the daily_work_hours view
-- Created: 2026-01-05

-- Re-create the view with corrected logic for pairing clock-in/out events
CREATE OR REPLACE VIEW daily_work_hours AS
SELECT
    user_id,
    email,
    DATE(clock_in_bali) as work_date,
    clock_in_bali,
    clock_out_bali,
    ROUND(CAST(EXTRACT(EPOCH FROM (clock_out_bali - clock_in_bali))/3600 AS NUMERIC), 2) as hours_worked
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
WHERE action_type = 'clock_in' 
  AND next_action_type = 'clock_out'
  AND clock_out_bali IS NOT NULL;

-- Update comment
COMMENT ON VIEW daily_work_hours IS 'Calculated daily hours in Bali timezone (Fixed Logic v2: Pairs In/Out events)';
