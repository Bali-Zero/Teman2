-- Migration 003: Team Work Sessions Tracking
-- Tracks team member work hours and sends reports to ZERO

-- Table: team_work_sessions
CREATE TABLE IF NOT EXISTS team_work_sessions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    user_name VARCHAR(255) NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
    session_end TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    activities_count INTEGER DEFAULT 0,
    conversations_count INTEGER DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active', -- 'active' | 'completed'
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_work_sessions_user_id ON team_work_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_date ON team_work_sessions(session_start);
CREATE INDEX IF NOT EXISTS idx_work_sessions_status ON team_work_sessions(status);
CREATE INDEX IF NOT EXISTS idx_work_sessions_user_date ON team_work_sessions(user_id, session_start);

-- Table: team_daily_reports
CREATE TABLE IF NOT EXISTS team_daily_reports (
    id SERIAL PRIMARY KEY,
    report_date DATE NOT NULL UNIQUE,
    team_summary JSONB NOT NULL,
    total_hours FLOAT NOT NULL,
    total_conversations INTEGER DEFAULT 0,
    sent_to_zero BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for daily reports
CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON team_daily_reports(report_date DESC);

-- Comments
COMMENT ON TABLE team_work_sessions IS 'Tracks team member work sessions - all reports sent to ZERO';
COMMENT ON TABLE team_daily_reports IS 'Daily aggregated reports for ZERO dashboard';
COMMENT ON COLUMN team_work_sessions.status IS 'Session status: active (ongoing) or completed (finished)';
COMMENT ON COLUMN team_work_sessions.duration_minutes IS 'Total session duration in minutes';
COMMENT ON COLUMN team_work_sessions.activities_count IS 'Number of activities during session';
COMMENT ON COLUMN team_work_sessions.conversations_count IS 'Number of conversations handled';
