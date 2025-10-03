/*
Database migration for memory consistency management and conflict resolution
for the AI Companion System.
*/
-- Create memory_conflicts table to track contradictions and inconsistencies
CREATE TABLE memory_conflicts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,

    -- Conflict identification
    conflict_type VARCHAR(50) NOT NULL, -- "factual_contradiction", "timeline_inconsistency", "preference_conflict"
    description TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),

    -- Memory references
    primary_memory_id VARCHAR(100), -- Reference to Qdrant memory
    conflicting_memory_id VARCHAR(100),
    related_memory_ids JSONB DEFAULT '[]', -- Additional related memories

    -- Resolution tracking
    status VARCHAR(20) DEFAULT 'detected', -- "detected", "investigating", "resolved", "ignored"
    resolution_method VARCHAR(50), -- "user_clarification", "temporal_precedence", "confidence_based"
    resolution_notes TEXT,

    -- Timestamps
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Context
    conversation_context JSONB, -- When/how conflict was discovered
    user_notified BOOLEAN DEFAULT FALSE
);

-- Create indexes for performance optimization
CREATE INDEX idx_memory_conflicts_user ON memory_conflicts(user_id);
CREATE INDEX idx_memory_conflicts_status ON memory_conflicts(status);
CREATE INDEX idx_memory_conflicts_detected ON memory_conflicts(detected_at);

-- Insert sample memory conflicts for testing
INSERT INTO memory_conflicts (user_id, conflict_type, description, confidence, status, resolution_notes) VALUES
('default_user', 'preference_conflict', 'User mentioned preferring coffee in one interaction and tea in another', 0.7, 'detected', 'Need to clarify user preference'),
('default_user', 'factual_contradiction', 'User stated different ages in separate conversations', 0.8, 'investigating', 'Checking for context of different possible meanings');