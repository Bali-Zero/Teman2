-- Migration 032: Messaging Users - Unified Identity Across Channels
--
-- Purpose: Map phone numbers and Telegram chat IDs to users (team + portal clients) for:
-- 1. Cross-channel conversation history (WhatsApp + Telegram + Web unified)
-- 2. Direct notifications (Telegram/WhatsApp chat_id for replies)
-- 3. User recognition across channels
--
-- Author: Zero
-- Date: 2026-01-17

-- Create messaging_users table
CREATE TABLE IF NOT EXISTS messaging_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity mapping (universal: team members + portal clients)
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,

    -- Channel identifiers
    phone TEXT UNIQUE,  -- WhatsApp phone (normalized, no + prefix)
    telegram_chat_id BIGINT UNIQUE,  -- Telegram numeric chat ID

    -- Channel type
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp', 'telegram')),

    -- Display info
    display_name TEXT,  -- Name from WhatsApp profile or Telegram

    -- Status
    verified BOOLEAN DEFAULT FALSE,  -- Whether association was confirmed
    active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_message_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT phone_or_telegram_required CHECK (
        (phone IS NOT NULL AND channel = 'whatsapp') OR
        (telegram_chat_id IS NOT NULL AND channel = 'telegram')
    )
);

-- Indexes for fast lookups
CREATE INDEX idx_messaging_users_phone ON messaging_users(phone) WHERE phone IS NOT NULL;
CREATE INDEX idx_messaging_users_telegram ON messaging_users(telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;
CREATE INDEX idx_messaging_users_user_id ON messaging_users(user_id);
CREATE INDEX idx_messaging_users_active ON messaging_users(active) WHERE active = TRUE;

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_messaging_users_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER messaging_users_updated_at
    BEFORE UPDATE ON messaging_users
    FOR EACH ROW
    EXECUTE FUNCTION update_messaging_users_timestamp();

-- Comments
COMMENT ON TABLE messaging_users IS 'Maps messaging channel identifiers (phone, telegram_chat_id) to user_profiles (team members + portal clients) for unified identity';
COMMENT ON COLUMN messaging_users.user_id IS 'Reference to user_profiles.id (supports both team members and portal clients)';
COMMENT ON COLUMN messaging_users.phone IS 'WhatsApp phone number (normalized without + prefix, e.g. 628123456789)';
COMMENT ON COLUMN messaging_users.telegram_chat_id IS 'Telegram numeric chat ID from message.chat.id';
COMMENT ON COLUMN messaging_users.channel IS 'Primary channel type for this mapping (whatsapp or telegram)';
COMMENT ON COLUMN messaging_users.verified IS 'True if user confirmed association (e.g. via PIN or admin approval)';
COMMENT ON COLUMN messaging_users.last_message_at IS 'Timestamp of last message from this channel (for activity tracking)';
