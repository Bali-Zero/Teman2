-- Migration 004: Fix Profile Photos Schema
-- Add missing profile photo columns to users table

-- Add profile_photo_url and profile_photo_updated_at to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS profile_photo_url TEXT,
ADD COLUMN IF NOT EXISTS profile_photo_updated_at TIMESTAMP WITH TIME ZONE;

-- Add index for faster lookup if needed (optional, as primary key is user_id)
CREATE INDEX IF NOT EXISTS idx_users_profile_photo_updated_at ON users(profile_photo_updated_at DESC);

-- Add comments for documentation
COMMENT ON COLUMN users.profile_photo_url IS 'URL or base64 data of the user''s profile photo';
COMMENT ON COLUMN users.profile_photo_updated_at IS 'Timestamp of the last profile photo update';

-- Verify the migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('profile_photo_url', 'profile_photo_updated_at');
