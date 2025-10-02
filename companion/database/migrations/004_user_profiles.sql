/*
Database migration for multi-user management with Letta agent mapping and user lifecycle
for the AI Companion System.
*/
-- Create user_profiles table to manage complete user lifecycle
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL UNIQUE, -- Discord user ID

    -- Basic user info
    discord_username VARCHAR(100),
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Letta integration
    letta_agent_id VARCHAR(100) UNIQUE, -- Maps to Letta agent
    letta_user_id VARCHAR(100), -- Letta's internal user ID

    -- User lifecycle
    status VARCHAR(20) DEFAULT 'active', -- "active", "inactive", "suspended", "deleted"
    initialization_completed BOOLEAN DEFAULT FALSE,
    personality_initialized BOOLEAN DEFAULT FALSE,

    -- Preferences and settings
    preferences JSONB DEFAULT '{}', -- User customization options
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferred_language VARCHAR(10) DEFAULT 'en',

    -- Usage statistics
    total_interactions INTEGER DEFAULT 0,
    total_proactive_conversations INTEGER DEFAULT 0,
    average_session_length_minutes FLOAT,

    -- Privacy and consent
    data_retention_days INTEGER DEFAULT 365,
    analytics_consent BOOLEAN DEFAULT TRUE,
    proactive_messaging_enabled BOOLEAN DEFAULT TRUE
);

-- Create indexes for performance optimization
CREATE INDEX idx_user_profiles_status ON user_profiles(status);
CREATE INDEX idx_user_profiles_last_active ON user_profiles(last_active);
CREATE INDEX idx_user_profiles_letta_agent ON user_profiles(letta_agent_id);

-- Insert default user profile for testing
INSERT INTO user_profiles (user_id, discord_username, status, initialization_completed, personality_initialized) VALUES
('default_user', 'DefaultUser', 'active', true, true);