-- Migration 006: Add system logging table and performance-critical indexes

-- System logging table for background jobs and errors
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    log_type VARCHAR(50) NOT NULL,
    job_name VARCHAR(100),
    error_message TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_logs_type_time ON system_logs(log_type, timestamp DESC);
COMMENT ON TABLE system_logs IS 'System-wide logging for background jobs, errors, and health checks.';

-- Add missing performance indexes to existing tables
CREATE INDEX IF NOT EXISTS idx_interactions_user_proactive_time ON interactions(user_id, is_proactive, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_quirks_user_active_strength ON quirks(user_id, is_active, strength DESC);
CREATE INDEX IF NOT EXISTS idx_needs_user_urgent ON needs(user_id, current_level DESC) WHERE current_level > trigger_threshold;

-- Add foreign key constraints for data integrity
-- Note: This assumes personality_snapshot_id was intended but not implemented. If not, this can be omitted.
-- ALTER TABLE interactions
--     ADD CONSTRAINT fk_interactions_personality
--     FOREIGN KEY (personality_snapshot_id)
--     REFERENCES personality_state(id)
--     ON DELETE SET NULL;
