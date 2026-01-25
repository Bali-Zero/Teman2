-- ================================================
-- Migration 000: Create user_profiles table
-- Purpose: Fix missing dependency for migration 025
-- ================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_profiles (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255), -- Alias for id
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'member',
    status VARCHAR(50) DEFAULT 'active',
    avatar VARCHAR(1024),
    language VARCHAR(10) DEFAULT 'en',
    tone VARCHAR(50) DEFAULT 'professional',
    complexity VARCHAR(50) DEFAULT 'medium',
    timezone VARCHAR(50) DEFAULT 'Asia/Bali',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);

COMMIT;
