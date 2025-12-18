-- Migration: Team Timesheet System
-- Purpose: Track team member work hours (clock-in/clock-out)
-- Timezone: Asia/Makassar (Bali Time, UTC+8)
-- Created: 2025-11-17

-- Main timesheet table
CREATE TABLE IF NOT EXISTS team_timesheet (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    action_type VARCHAR(20) NOT NULL CHECK (action_type IN ('clock_in', 'clock_out')),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_timesheet_user ON team_timesheet(user_id);
CREATE INDEX IF NOT EXISTS idx_timesheet_date ON team_timesheet(DATE(timestamp AT TIME ZONE 'Asia/Makassar'));
CREATE INDEX IF NOT EXISTS idx_timesheet_action ON team_timesheet(action_type);
CREATE INDEX IF NOT EXISTS idx_timesheet_user_date ON team_timesheet(user_id, DATE(timestamp AT TIME ZONE 'Asia/Makassar'));

-- View: Daily work hours (Bali timezone)
CREATE OR REPLACE VIEW daily_work_hours AS
SELECT
    user_id,
    email,
    work_date,
    clock_in_bali,
    clock_out_bali,
    ROUND(CAST(EXTRACT(EPOCH FROM (clock_out_bali - clock_in_bali))/3600 AS NUMERIC), 2) as hours_worked
FROM (
    SELECT
        user_id,
        email,
        DATE((timestamp AT TIME ZONE 'Asia/Makassar')) as work_date,
        (timestamp AT TIME ZONE 'Asia/Makassar') as clock_in_bali,
        LEAD((timestamp AT TIME ZONE 'Asia/Makassar')) OVER (
            PARTITION BY user_id, DATE((timestamp AT TIME ZONE 'Asia/Makassar'))
            ORDER BY timestamp
        ) as clock_out_bali
    FROM team_timesheet
    WHERE action_type = 'clock_in'
) AS shifts
WHERE clock_out_bali IS NOT NULL;

-- View: Current online status (who is clocked in without clock-out)
CREATE OR REPLACE VIEW team_online_status AS
SELECT DISTINCT ON (user_id)
    user_id,
    email,
    timestamp AT TIME ZONE 'Asia/Makassar' as last_action_bali,
    action_type,
    CASE
        WHEN action_type = 'clock_in' THEN true
        ELSE false
    END as is_online
FROM team_timesheet
ORDER BY user_id, timestamp DESC;

-- View: Weekly summary
CREATE OR REPLACE VIEW weekly_work_summary AS
SELECT
    user_id,
    email,
    DATE_TRUNC('week', work_date) as week_start,
    COUNT(*) as days_worked,
    ROUND(SUM(hours_worked), 2) as total_hours,
    ROUND(AVG(hours_worked), 2) as avg_hours_per_day
FROM daily_work_hours
GROUP BY user_id, email, DATE_TRUNC('week', work_date);

-- View: Monthly summary
CREATE OR REPLACE VIEW monthly_work_summary AS
SELECT
    user_id,
    email,
    DATE_TRUNC('month', work_date) as month_start,
    COUNT(*) as days_worked,
    ROUND(SUM(hours_worked), 2) as total_hours,
    ROUND(AVG(hours_worked), 2) as avg_hours_per_day
FROM daily_work_hours
GROUP BY user_id, email, DATE_TRUNC('month', work_date);

-- Function: Auto-logout at 18:30 Bali time
CREATE OR REPLACE FUNCTION auto_logout_expired_sessions()
RETURNS TABLE(user_id VARCHAR, email VARCHAR, clock_in_time TIMESTAMPTZ, auto_logout_time TIMESTAMPTZ) AS $$
BEGIN
    -- Find users who clocked in but didn't clock out, and it's past 18:30 Bali time
    RETURN QUERY
    WITH latest_actions AS (
        SELECT DISTINCT ON (t.user_id)
            t.user_id,
            t.email,
            t.timestamp,
            t.action_type
        FROM team_timesheet t
        ORDER BY t.user_id, t.timestamp DESC
    ),
    expired_sessions AS (
        SELECT
            la.user_id,
            la.email,
            la.timestamp as clock_in_time,
            (DATE(la.timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00') AT TIME ZONE 'Asia/Makassar' as target_logout
        FROM latest_actions la
        WHERE la.action_type = 'clock_in'
          AND NOW() AT TIME ZONE 'Asia/Makassar' > (DATE(la.timestamp AT TIME ZONE 'Asia/Makassar') + TIME '18:30:00')
    ),
    inserted AS (
        INSERT INTO team_timesheet (user_id, email, action_type, timestamp, notes)
        SELECT
            es.user_id,
            es.email,
            'clock_out',
            es.target_logout,
            'Auto-logout at 18:30 Bali time'
        FROM expired_sessions es
        RETURNING user_id, email, timestamp
    )
    SELECT
        i.user_id::VARCHAR,
        i.email::VARCHAR,
        es.clock_in_time,
        i.timestamp as auto_logout_time
    FROM inserted i
    JOIN expired_sessions es ON i.user_id = es.user_id;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE team_timesheet IS 'Team work hours tracking (clock-in/clock-out only, Bali timezone UTC+8)';
COMMENT ON COLUMN team_timesheet.action_type IS 'Either clock_in or clock_out';
COMMENT ON COLUMN team_timesheet.metadata IS 'JSON: {ip_address, user_agent, auto_logout: bool}';
COMMENT ON VIEW daily_work_hours IS 'Calculated daily hours in Bali timezone';
COMMENT ON VIEW team_online_status IS 'Current online/offline status of team members';
COMMENT ON FUNCTION auto_logout_expired_sessions IS 'Auto-logout users who forgot to clock out by 18:30 Bali time';
