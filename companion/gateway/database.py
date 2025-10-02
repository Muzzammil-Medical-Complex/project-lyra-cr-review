"""
Database manager for the AI Companion System.
Handles connection pooling, user-scoped queries, and transaction management.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
import asyncpg
import re
from contextlib import asynccontextmanager
from datetime import datetime

from .config import Settings
from .utils.query_executor import QueryExecutor


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and user-scoped queries for the AI Companion System.
    Provides connection pooling, transaction management, and safe user data isolation.
    """

    def __init__(self, database_url: str, settings: Optional[Settings] = None):
        self.database_url = database_url
        self.pool = None
        self._initialized = False
        self.settings = settings or Settings()
    
    async def initialize(self):
        """Initialize the database connection pool."""
        if self._initialized:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=self.settings.db_pool_min_size,
                max_size=self.settings.db_pool_max_size,
                command_timeout=60
            )
            self._initialized = True
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise
    
    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_transaction(self):
        """Context manager for database transactions."""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield DatabaseTransaction(connection)
    
    async def health_check(self) -> bool:
        """Check if the database is accessible."""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def execute_user_query(self, user_id: str, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute a query that is automatically scoped to a specific user.
        This method safely injects the user_id into the query to ensure proper multi-user isolation.

        WARNING: This method uses regex-based SQL manipulation which is fragile and insecure.
        See QueryExecutor for refactoring recommendations.
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        async with self.pool.acquire() as conn:
            return await QueryExecutor.execute_scoped_query(conn, query, user_id, params)

    async def execute_admin_query(self, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute an admin query that bypasses user scoping.

        ⚠️  WARNING: This method is for admin/system queries only.
        Use execute_user_query() for normal user-scoped operations.
        """
        if not self.pool:
            raise RuntimeError("Database not initialized")

        async with self.pool.acquire() as conn:
            return await QueryExecutor.execute_admin_query(conn, query, params)

    # Methods for specific user-scoped operations
    
    async def get_user_profile(self, user_id: str):
        """Get user profile by user_id with proper scoping."""
        query = "SELECT * FROM user_profiles WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result[0] if result else None

    async def get_user_needs(self, user_id: str):
        """Get user needs by user_id with proper scoping."""
        query = "SELECT * FROM needs WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result

    async def get_user_quirks(self, user_id: str):
        """Get user quirks by user_id with proper scoping."""
        query = "SELECT * FROM quirks WHERE user_id = $1 AND is_active = true"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result

    async def get_user_interactions(self, user_id: str, limit: int = 10):
        """Get user interactions by user_id with proper scoping."""
        query = "SELECT * FROM interactions WHERE user_id = $1 ORDER BY timestamp DESC LIMIT $2"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id, limit)
            return result

    async def get_personality_state(self, user_id: str):
        """Get current personality state for user."""
        query = "SELECT * FROM personality_state WHERE user_id = $1 AND is_current = true"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result[0] if result else None

    async def get_active_quirks(self, user_id: str):
        """Get active quirks for user."""
        query = "SELECT * FROM quirks WHERE user_id = $1 AND is_active = true"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result

    async def get_urgent_needs(self, user_id: str):
        """Get urgent needs for user."""
        query = "SELECT * FROM needs WHERE user_id = $1 AND current_level > trigger_threshold"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id)
            return result

    async def log_interaction(self, interaction) -> bool:
        """Log an interaction with proper user scoping."""
        query = """
        INSERT INTO interactions (
            user_id, user_message, agent_response, session_id,
            pad_before, pad_after, emotion_before, emotion_after,
            response_time_ms, token_count, llm_model_used,
            is_proactive, proactive_trigger, proactive_score,
            memories_retrieved, memories_stored,
            error_occurred, error_message, fallback_used,
            security_check_passed, security_threat_detected,
            user_initiated, conversation_length, user_satisfaction_implied
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                  $11, $12, $13, $14, $15, $16, $17, $18, $19,
                  $20, $21, $22, $23, $24) RETURNING id
        """
        params = (
            interaction.user_id,
            interaction.user_message,
            interaction.agent_response,
            interaction.session_id,
            interaction.pad_before,
            interaction.pad_after,
            interaction.emotion_before,
            interaction.emotion_after,
            interaction.response_time_ms,
            interaction.token_count,
            interaction.llm_model_used,
            interaction.is_proactive,
            interaction.proactive_trigger,
            interaction.proactive_score,
            interaction.memories_retrieved,
            interaction.memories_stored,
            interaction.error_occurred,
            interaction.error_message,
            interaction.fallback_used,
            interaction.security_check_passed,
            interaction.security_threat_detected,
            interaction.user_initiated,
            interaction.conversation_length,
            interaction.user_satisfaction_implied
        )

        try:
            # Use direct pool execution to avoid duplicate user_id injection
            # INSERT already has explicit user_id in params
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow(query, *params)
            return True
        except Exception as e:
            logger.error(f"Error logging interaction for user {interaction.user_id}: {e}")
            return False

    async def get_recent_interaction_stats(self, user_id: str, days: int = 7):
        """Get recent interaction statistics for a user."""
        # Validate days parameter
        days = int(days)

        query = """
        SELECT
            COUNT(*) as total_interactions,
            AVG(conversation_length) as avg_conversation_length,
            COUNT(*) FILTER (WHERE is_proactive = true) * 1.0 / NULLIF(COUNT(*), 0) as proactive_response_rate,
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 3600 as hours_span,
            COUNT(*) FILTER (WHERE user_initiated = false) * 1.0 / NULLIF(COUNT(*), 0) as user_initiation_ratio,
            EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 as hours_since_last_interaction
        FROM interactions
        WHERE user_id = $1 AND timestamp > NOW() - make_interval(days => $2)
        """

        # Use direct pool execution to avoid user_id duplication
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, user_id, days)

        if result:
            return {
                'total_interactions': result[0]['total_interactions'],
                'avg_conversation_length': float(result[0]['avg_conversation_length'] or 0),
                'proactive_response_rate': float(result[0]['proactive_response_rate'] or 0),
                'hours_span': float(result[0]['hours_span'] or 0),
                'user_initiation_ratio': float(result[0]['user_initiation_ratio'] or 0),
                'hours_since_last_interaction': float(result[0]['hours_since_last_interaction'] or 0)
            }
        return {}

    # Additional utility methods for user-scoped operations
    
    async def get_last_proactive_conversation(self, user_id: str):
        """Get the last proactive conversation for a user."""
        query = """
        SELECT * FROM interactions
        WHERE is_proactive = true
        ORDER BY timestamp DESC LIMIT 1
        """
        query = """
        SELECT 
            COUNT(*) as total_interactions,
            AVG(conversation_length) as avg_conversation_length,
            COUNT(*) FILTER (WHERE is_proactive = true) * 1.0 / COUNT(*) as proactive_response_rate,
            EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) / 3600 as hours_span,
            COUNT(*) FILTER (WHERE user_initiated = false) * 1.0 / COUNT(*) as user_initiation_ratio,
            EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 as hours_since_last_interaction
        FROM interactions 
        WHERE user_id = $1 AND timestamp > NOW() - INTERVAL '1 day' * $2
        """
        result = await self.execute_user_query(user_id, query, (days,))
        return result[0] if result else None

    async def get_proactive_count_today(self, user_id: str) -> int:
        """Get the number of proactive conversations for a user today."""
        query = """
        SELECT COUNT(*) as count FROM interactions
        WHERE is_proactive = true
        AND DATE(timestamp) = CURRENT_DATE
        """
        result = await self.execute_user_query(user_id, query, ())
        return result[0]['count'] if result else 0

    async def get_last_user_activity(self, user_id: str):
        """Get the last activity timestamp for a user."""
        query = "SELECT MAX(timestamp) as last_activity FROM interactions"
        result = await self.execute_user_query(user_id, query, ())
        return result[0]['last_activity'] if result and result[0]['last_activity'] else None

    async def get_user_activity_patterns(self, user_id: str):
        """Get user activity patterns for proactive timing."""
        query = """
        SELECT
            EXTRACT(HOUR FROM timestamp) as hour,
            COUNT(*) as count
        FROM interactions
        WHERE timestamp > NOW() - INTERVAL '30 days'
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY hour
        """
        result = await self.execute_user_query(user_id, query, ())
        
        # Normalize hourly activity to 0-1 scale
        if result:
            max_count = max(row['count'] for row in result) if result else 1
            hourly_activity = {str(row['hour']): row['count'] / max_count for row in result}
        else:
            hourly_activity = {str(i): 0.0 for i in range(24)}
        
        # For now, return just hourly activity - weekly would be similar
        return {'hourly': hourly_activity}

    async def get_active_users_for_reflection(self, days: int = 7) -> List[str]:
        """Get user IDs of users active in the last N days."""
        query = f"""
        SELECT DISTINCT user_id FROM interactions
        WHERE timestamp > NOW() - INTERVAL '{days} days'
        ORDER BY timestamp DESC
        """
        result = await self.pool.fetch(query)
        return [row['user_id'] for row in result]

    async def store_reflection_report(self, report: Dict[str, Any]) -> bool:
        """Store reflection report (stub implementation)."""
        logger.info(f"Storing reflection report for user {report.get('user_id', 'unknown')}")

    async def log_reflection_error(self, user_id: str, error: str) -> bool:
        """Log reflection error (stub implementation)."""
        logger.error(f"Reflection error for user {user_id}: {error}")
        return True

    async def log_proactive_decision(self, user_id: str, score: Any) -> bool:
        """Log proactive conversation decision (stub implementation)."""
        logger.info(f"Proactive decision for user {user_id}: score={score.total_score:.3f}, "
                   f"should_initiate={score.should_initiate}, reason={score.reason}")
        return True

    async def log_proactive_error(self, user_id: str, error: str) -> bool:
        """Log proactive conversation error (stub implementation)."""
        logger.error(f"Proactive error for user {user_id}: {error}")
        return True

    async def get_recent_proactive_decline(self, user_id: str, hours: int = 24) -> Optional[Dict[str, Any]]:
        """
        Get recent proactive conversation decline/ignore by user (stub implementation).

        Returns the most recent decline event if one occurred within the specified time window.
        A decline could be:
        - User explicitly declining a proactive message
        - User ignoring a proactive message (no response within timeout)
        - User indicating they don't want to be contacted

        Args:
            user_id: The user ID to check
            hours: Time window in hours to check for declines (default 24)

        Returns:
            Dict with decline details if found, None otherwise
        """
        # TODO: Implement proper decline tracking table
        # For now, return None (no recent declines) as a safe default
        # This allows proactive messaging to proceed unless explicitly tracked
        logger.debug(f"Checking for recent proactive declines for user {user_id} in last {hours}h")
        return None

    async def mark_memory_consolidated(self, user_id: str, episodic_id: str, semantic_id: str) -> bool:
        """Mark memory as consolidated (stub implementation)."""
        logger.debug(f"Marking memory {episodic_id} as consolidated to {semantic_id}")
        return True

    async def get_quirk_reinforcements(self, user_id: str, quirk_id: str, days: int) -> List[Dict[str, Any]]:
        """Get quirk reinforcements (stub implementation)."""
        return []

    async def update_quirk_metrics(self, quirk_id: str, strength: float, confidence: float) -> bool:
        """Update quirk metrics (stub implementation)."""
        return True

    async def deactivate_quirk(self, quirk_id: str) -> bool:
        """Deactivate a quirk (stub implementation)."""
        return True

    async def update_need_level(self, user_id: str, need_type: str, new_level: float) -> bool:
        """Update psychological need level (stub implementation)."""
        return True

    async def get_pad_state_history(self, user_id: str, days: int) -> List[Dict[str, Any]]:
        """Get PAD state history (stub implementation)."""
        return []

    async def store_conversation_pattern(self, user_id: str, pattern: Dict[str, Any]) -> bool:
        """Store conversation pattern (stub implementation)."""
        return True

    async def update_user_reflection_stats(self, user_id: str, stats: Dict[str, Any]) -> bool:
        """Update user reflection statistics (stub implementation)."""
        return True

    async def get_unconsolidated_memories(self, user_id: str, hours: int) -> List[Dict[str, Any]]:
        """Get unconsolidated memories (stub implementation)."""
        return []

    async def get_detailed_activity_patterns(self, user_id: str) -> List[Dict[str, Any]]:
        """Get detailed activity patterns for proactive timing (stub implementation)."""
        return []

    async def get_all_users(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Get a paginated list of all users."""
        query = "SELECT * FROM user_profiles ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, limit, skip)
            return [dict(row) for row in result]

    async def get_total_user_count(self) -> int:
        """Get the total count of users in the system."""
        query = "SELECT COUNT(*) as count FROM user_profiles"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query)
            return result if result else 0

    async def get_active_users_count(self, since: datetime) -> int:
        """Get the count of active users since a specific timestamp."""
        query = """
        SELECT COUNT(DISTINCT user_id) as count FROM interactions
        WHERE timestamp > $1
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, since)
            return result if result else 0

    async def get_total_interaction_count(self) -> int:
        """Get the total count of interactions in the system."""
        query = "SELECT COUNT(*) as count FROM interactions"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query)
            return result if result else 0

    async def get_interaction_count_since(self, since: datetime) -> int:
        """Get the count of interactions since a specific timestamp."""
        query = "SELECT COUNT(*) as count FROM interactions WHERE timestamp > $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, since)
            return result if result else 0

    async def get_security_incidents(self, limit: int = 50, offset: int = 0,
                                    severity: Optional[str] = None,
                                    status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get security incidents with optional filtering."""
        query = "SELECT * FROM security_incidents WHERE 1=1"
        params = []
        param_index = 1

        if severity:
            query += f" AND severity = ${param_index}"
            params.append(severity)
            param_index += 1

        if status:
            query += f" AND status = ${param_index}"
            params.append(status)
            param_index += 1

        query += f" ORDER BY detected_at DESC LIMIT ${param_index} OFFSET ${param_index + 1}"
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            result = await conn.fetch(query, *params)
            return [dict(row) for row in result]

    async def cleanup_inactive_users(self, tx=None) -> int:
        """Clean up inactive users based on retention policy (users inactive for >365 days)."""
        query = """
        UPDATE user_profiles
        SET status = 'inactive'
        WHERE user_id IN (
            SELECT user_id FROM user_profiles
            WHERE status = 'active'
            AND user_id NOT IN (
                SELECT DISTINCT user_id FROM interactions
                WHERE timestamp > NOW() - make_interval(days => 365)
            )
        )
        """
        if tx:
            # Use the provided transaction
            result = await tx.execute(query)
        else:
            # Use regular connection from pool
            async with self.pool.acquire() as conn:
                result = await conn.execute(query)
        
        # Extract the number of rows affected from the result
        # PostgreSQL returns "UPDATE N" where N is the number of rows
        affected = 0
        if result and result.startswith('UPDATE'):
            affected = int(result.split(' ')[1]) if len(result.split(' ')) > 1 else 0
        return affected

    # @staticmethod
    # def get_instance():
    #     """Get the singleton instance of the DatabaseManager"""
    #     # This would be implemented properly in a real application
    #     # For now, return None to trigger dependency injection
    #     return None


class DatabaseTransaction:
    """
    Wrapper for database transactions that provides user-scoped query execution.
    Uses QueryExecutor for shared query injection logic.
    """

    def __init__(self, connection):
        self.connection = connection

    async def execute_user_query(self, user_id: str, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a user-scoped query within this transaction."""
        return await QueryExecutor.execute_scoped_query(self.connection, query, user_id, params)

    async def execute_admin_query(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute an admin query within this transaction (bypasses user scoping)."""
        return await QueryExecutor.execute_admin_query(self.connection, query, params)

    async def execute(self, query: str, *args) -> Any:
        """Execute an arbitrary query within this transaction (bypasses user scoping like admin query)."""
        return await self.connection.execute(query, *args)

    async def commit(self):
        """Commit the transaction."""
        # Transaction is managed by the async context manager, so we don't need to explicitly commit
        pass

    async def rollback(self):
        """Rollback the transaction."""
        # Transaction is managed by the async context manager, so we don't need to explicitly rollback
        pass
