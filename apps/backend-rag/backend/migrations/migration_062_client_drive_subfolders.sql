-- Migration 062: Client Drive subfolders cache + system settings
-- Part of Auto-Land: Drive Upload → OCR → CRM Auto-Populate

-- Cache subfolder IDs to avoid repeated Drive API lookups
CREATE TABLE IF NOT EXISTS client_drive_subfolders (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    subfolder_name VARCHAR(50) NOT NULL,
    subfolder_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, subfolder_name)
);

CREATE INDEX IF NOT EXISTS idx_client_drive_subfolders_client ON client_drive_subfolders (client_id);

-- Key/value store for system-wide settings (e.g. Drive poll page token)
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE client_drive_subfolders IS 'Cache of Google Drive subfolder IDs per client';
COMMENT ON TABLE system_settings IS 'System-wide key/value settings store';
