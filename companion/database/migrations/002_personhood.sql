/*
Database migration for dynamic personality components that evolve based on user interactions
for the AI Companion System.
*/
-- Create quirks table to track behavioral patterns, speech quirks, and preferences
CREATE TABLE quirks (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,

    -- Quirk identification
    name VARCHAR(100) NOT NULL, -- "uses_emoji_frequently", "prefers_short_responses"
    category VARCHAR(50) NOT NULL, -- "speech_pattern", "behavior", "preference"
    description TEXT NOT NULL,

    -- Evolution tracking
    strength FLOAT NOT NULL DEFAULT 0.0 CHECK (strength BETWEEN 0 AND 1),
    first_observed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_reinforced TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Usage statistics
    observation_count INTEGER DEFAULT 1,
    reinforcement_count INTEGER DEFAULT 0,
    decay_rate FLOAT DEFAULT 0.05, -- How quickly quirk fades without reinforcement

    -- Status tracking
    is_active BOOLEAN DEFAULT TRUE,
    confidence FLOAT DEFAULT 0.1, -- How certain we are this is a real pattern

    -- Examples and context
    examples JSONB DEFAULT '[]', -- Store example interactions that demonstrate this quirk
    context_triggers JSONB DEFAULT '[]', -- Situations that activate this quirk

    UNIQUE(user_id, name) -- One quirk per name per user
);

-- Create needs table to track psychological needs with decay and satisfaction mechanics
CREATE TABLE needs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,

    -- Need identification
    need_type VARCHAR(50) NOT NULL, -- "social", "intellectual", "creative", "rest", "validation"
    current_level FLOAT NOT NULL DEFAULT 0.5 CHECK (current_level BETWEEN 0 AND 1),
    baseline_level FLOAT NOT NULL DEFAULT 0.5 CHECK (baseline_level BETWEEN 0 AND 1),

    -- Temporal mechanics
    last_satisfied TIMESTAMPTZ,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decay_rate FLOAT NOT NULL DEFAULT 0.02, -- How quickly need increases per hour
    satisfaction_rate FLOAT NOT NULL DEFAULT 0.1, -- How much interaction satisfies

    -- Pattern tracking
    satisfaction_pattern JSONB DEFAULT '{}', -- When this need is typically satisfied
    trigger_threshold FLOAT DEFAULT 0.8, -- When need becomes urgent for proactive conversation

    -- Behavioral influence
    influence_on_mood FLOAT DEFAULT 0.1, -- How much this need affects PAD state
    proactive_weight FLOAT DEFAULT 1.0, -- Priority for proactive conversation

    UNIQUE(user_id, need_type)
);

-- Create indexes for performance optimization
CREATE INDEX idx_quirks_user_active ON quirks(user_id, is_active);
CREATE INDEX idx_quirks_strength ON quirks(user_id, strength DESC) WHERE is_active = true;
CREATE INDEX idx_quirks_category ON quirks(user_id, category);

CREATE INDEX idx_needs_user ON needs(user_id);
CREATE INDEX idx_needs_urgent ON needs(user_id, current_level DESC) WHERE current_level > 0.8;
CREATE INDEX idx_needs_updated ON needs(last_updated);

-- Insert default quirks and needs for testing
INSERT INTO quirks (user_id, name, category, description, strength, confidence, is_active) VALUES
('default_user', 'uses_positive_emojis', 'speech_pattern', 'Tends to use positive emojis in messages', 0.3, 0.7, true),
('default_user', 'prefers_short_responses', 'behavior', 'Prefers concise responses', 0.5, 0.6, true);

INSERT INTO needs (user_id, need_type, current_level, baseline_level, decay_rate, satisfaction_rate, trigger_threshold, proactive_weight) VALUES
('default_user', 'social', 0.5, 0.5, 0.03, 0.1, 0.8, 1.0),
('default_user', 'intellectual', 0.5, 0.5, 0.02, 0.1, 0.8, 1.0),
('default_user', 'validation', 0.5, 0.5, 0.025, 0.1, 0.8, 1.0);