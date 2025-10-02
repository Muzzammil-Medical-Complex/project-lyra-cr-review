/*
Database migration to initialize core personality and interaction tables
for the AI Companion System.
*/
-- Enable UUID extension for generating unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create personality_state table to store Big Five traits and PAD emotional states
CREATE TABLE personality_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Multi-User Scoping
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',

    -- Big Five (OCEAN) traits - FIXED at user creation (0.0 to 1.0)
    openness FLOAT NOT NULL CHECK (openness BETWEEN 0 AND 1),
    conscientiousness FLOAT NOT NULL CHECK (conscientiousness BETWEEN 0 AND 1),
    extraversion FLOAT NOT NULL CHECK (extraversion BETWEEN 0 AND 1),
    agreeableness FLOAT NOT NULL CHECK (agreeableness BETWEEN 0 AND 1),
    neuroticism FLOAT NOT NULL CHECK (neuroticism BETWEEN 0 AND 1),

    -- PAD emotional state - DYNAMIC per interaction (-1.0 to 1.0)
    pleasure FLOAT NOT NULL CHECK (pleasure BETWEEN -1 AND 1),
    arousal FLOAT NOT NULL CHECK (arousal BETWEEN -1 AND 1),
    dominance FLOAT NOT NULL CHECK (dominance BETWEEN -1 AND 1),

    -- Computed emotion label from PAD values
    emotion_label VARCHAR(50),

    -- Version tracking for state evolution
    is_current BOOLEAN DEFAULT TRUE,

    -- Long-term PAD baseline that drifts over time
    pad_baseline JSONB DEFAULT '{"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0}',

    -- Session context
    session_id UUID,
    trigger_event VARCHAR(100) -- What caused this state change
);

-- Create interactions table for comprehensive interaction logging
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Multi-User Scoping
    user_id VARCHAR(100) NOT NULL,

    -- Message content and metadata
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    session_id UUID NOT NULL,

    -- Personality context at interaction time
    pad_before JSONB, -- PAD state before interaction
    pad_after JSONB,  -- PAD state after interaction
    emotion_before VARCHAR(50),
    emotion_after VARCHAR(50),

    -- Performance and quality metrics
    response_time_ms INTEGER,
    token_count INTEGER,
    llm_model_used VARCHAR(100),

    -- Proactive conversation metadata
    is_proactive BOOLEAN DEFAULT FALSE,
    proactive_trigger VARCHAR(100), -- timing_threshold, need_satisfaction, etc.
    proactive_score FLOAT, -- Calculated urgency score

    -- Memory integration
    memories_retrieved INTEGER DEFAULT 0,
    memories_stored INTEGER DEFAULT 0,

    -- Error tracking
    error_occurred BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    fallback_used BOOLEAN DEFAULT FALSE,

    -- Security
    security_check_passed BOOLEAN DEFAULT TRUE,
    security_threat_detected VARCHAR(100),

    -- User engagement metrics
    user_initiated BOOLEAN DEFAULT TRUE,
    conversation_length INTEGER DEFAULT 1, -- Messages in this conversation
    user_satisfaction_implied FLOAT -- Inferred from response patterns
);

-- Create indexes for performance optimization with multi-user queries
CREATE INDEX idx_personality_user_current ON personality_state(user_id) WHERE is_current = true;
CREATE INDEX idx_personality_timeline ON personality_state(user_id, timestamp);
CREATE INDEX idx_interactions_user_recent ON interactions(user_id, timestamp DESC);
CREATE INDEX idx_interactions_session ON interactions(session_id);
CREATE INDEX idx_interactions_proactive ON interactions(user_id, is_proactive, timestamp) WHERE is_proactive = true;

-- JSON field indexes for PAD queries
CREATE INDEX idx_personality_pad_baseline ON personality_state USING GIN(pad_baseline);
CREATE INDEX idx_interactions_pad_before ON interactions USING GIN (pad_before);
CREATE INDEX idx_interactions_pad_after ON interactions USING GIN (pad_after);

-- Insert a default personality state for testing
INSERT INTO personality_state (
    user_id, 
    openness, 
    conscientiousness, 
    extraversion, 
    agreeableness, 
    neuroticism,
    pleasure,
    arousal,
    dominance,
    emotion_label,
    is_current
) VALUES (
    'default_user',
    0.5,  -- openness
    0.5,  -- conscientiousness
    0.5,  -- extraversion
    0.5,  -- agreeableness
    0.5,  -- neuroticism
    0.0,  -- pleasure
    0.0,  -- arousal
    0.0,  -- dominance
    'neutral',
    true
);