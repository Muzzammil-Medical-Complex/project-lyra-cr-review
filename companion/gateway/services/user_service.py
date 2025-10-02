"""
User service for the AI Companion System.
Handles user lifecycle management, profile creation, and transactional operations.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ..database import DatabaseManager
from ..models.user import UserProfile
from ..models.personality import PersonalitySnapshot
from ..models.interaction import InteractionRecord
from ..services.letta_service import LettaService
from ..services.personality_engine import PersonalityEngine
from ..utils.exceptions import UserCreationError, UserNotFoundError


logger = logging.getLogger(__name__)


class UserService:
    """
    Manages the complete user lifecycle for the AI Companion System.
    Handles user profile creation, initialization, and state management.
    """
    
    def __init__(self, db: DatabaseManager, letta_service: LettaService, personality_engine: PersonalityEngine):
        self.db = db
        self.letta_service = letta_service
        self.personality_engine = personality_engine
    
    async def create_user(self, discord_id: str) -> UserProfile:
        """
        Transactional user creation with rollback on any failure
        """
        async with self.db.get_transaction() as tx:
            # Initialize flag to track whether agent was created
            created_agent = False
            agent_id = None
            
            try:
                # Step 1: Create user_profiles record
                user_profile = UserProfile(
                    user_id=discord_id,
                    discord_username="",  # Will be updated on first message
                    status="active",
                    initialization_completed=False,
                    personality_initialized=False
                )
                profile_id = await tx.insert_user_profile(user_profile)

                # Step 2: Initialize personality (Big Five + PAD baseline)
                personality_data = await self.personality_engine.initialize_personality(discord_id)
                if not personality_data:
                    raise UserCreationError("Failed to initialize personality")

                # Step 3: Create Letta agent with personality injection
                agent_id = await self.letta_service.create_agent(
                    user_id=discord_id,
                    personality_data=personality_data
                )
                if not agent_id:
                    raise UserCreationError("Failed to create Letta agent")
                
                # Mark that agent was successfully created
                created_agent = True

                # Step 4: Update user profile with agent mapping
                await tx.update_user_profile(profile_id, {
                    'letta_agent_id': agent_id,
                    'personality_initialized': True,
                    'initialization_completed': True
                })

                # Step 5: Initialize psychological needs
                await self._initialize_psychological_needs(discord_id, tx)

                await tx.commit()
                user_profile = await self.get_user_profile(discord_id)
                return user_profile

            except Exception as e:
                await tx.rollback()
                # Cleanup any partially created Letta agent
                if created_agent:
                    try:
                        await self.letta_service.delete_agent(agent_id)
                    except Exception as cleanup_error:
                        logger.error(f"Failed to cleanup agent {agent_id} after user creation failure: {cleanup_error}")
                raise UserCreationError(f"User creation failed: {str(e)}")

    async def _initialize_psychological_needs(self, user_id: str, tx):
        """
        Initialize the psychological needs for a new user
        """
        from ..models.personality import PsychologicalNeed
        
        default_needs = [
            PsychologicalNeed(need_type="social", current_level=0.5, baseline_level=0.5),
            PsychologicalNeed(need_type="validation", current_level=0.5, baseline_level=0.5),
            PsychologicalNeed(need_type="intellectual", current_level=0.5, baseline_level=0.5),
            PsychologicalNeed(need_type="creative", current_level=0.5, baseline_level=0.5),
            PsychologicalNeed(need_type="rest", current_level=0.5, baseline_level=0.5)
        ]
        
        for need in default_needs:
            await tx.insert_need(user_id, need)

    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Retrieve a user profile by user_id
        """
        try:
            record = await self.db.get_user_profile(user_id)
            if record:
                # Convert asyncpg.Record to UserProfile model
                return UserProfile(**dict(record))
            return None
        except Exception as e:
            logger.error(f"Error retrieving user profile for {user_id}: {e}")
            return None

    async def get_user_by_discord_username(self, discord_username: str) -> Optional[UserProfile]:
        """
        Retrieve a user profile by Discord username
        """
        try:
            return await self.db.get_user_by_discord_username(discord_username)
        except Exception as e:
            logger.error(f"Error retrieving user by Discord username {discord_username}: {e}")
            return None

    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user profile fields
        """
        try:
            return await self.db.update_user_profile(user_id, updates)
        except Exception as e:
            logger.error(f"Error updating user profile for {user_id}: {e}")
            return False

    async def delete_user(self, user_id: str) -> bool:
        """
        Transactionally mark a user as deleted and deactivate their account
        """
        try:
            # First, get the user profile to check for agent ID
            user_profile = await self.get_user_profile(user_id)
            if not user_profile:
                logger.warning(f"User {user_id} not found for deletion")
                return False
                
            agent_id = user_profile.letta_agent_id
            
            # Open a database transaction for atomic operations
            async with self.db.get_transaction() as tx:
                # Update user status to deleted within the transaction
                updates = {
                    'status': 'deleted',
                    'last_active': datetime.utcnow()
                }
                
                # Update user profile within transaction
                await tx.execute_user_query(
                    user_id,
                    """
                    UPDATE user_profiles 
                    SET status=$1, last_active=$2 
                    WHERE user_id=$3
                    """,
                    (updates['status'], updates['last_active'], user_id)
                )
                
                # Commit the transaction
                await tx.commit()
            
            # After successful DB commit, delete the associated Letta agent
            # If this fails, we can't rollback the DB changes, but we should log the error
            if agent_id:
                try:
                    await self.letta_service.delete_agent(agent_id)
                except Exception as agent_error:
                    logger.error(f"Failed to delete agent {agent_id} for user {user_id} after DB update: {agent_error}")
                    # In a production system, you might want to schedule a retry or have a compensating action
                    # For now, we still return True since the main operation (user deletion) succeeded
                    return True
            
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

    async def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate a user account without deleting it
        """
        try:
            updates = {
                'status': 'inactive',
                'last_active': datetime.utcnow()
            }
            return await self.update_user_profile(user_id, updates)
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False

    async def reactivate_user(self, user_id: str) -> bool:
        """
        Reactivate a user account
        """
        try:
            updates = {
                'status': 'active',
                'last_active': datetime.utcnow()
            }
            return await self.update_user_profile(user_id, updates)
        except Exception as e:
            logger.error(f"Error reactivating user {user_id}: {e}")
            return False

    async def update_user_status(self, user_id: str, new_status: str, reason: Optional[str] = None) -> Optional[UserProfile]:
        """
        Update the status of a user account
        """
        valid_statuses = ['active', 'inactive', 'suspended', 'deleted']
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Valid statuses: {valid_statuses}")
        
        try:
            updates = {
                'status': new_status,
                'last_active': datetime.utcnow()
            }
            if reason:
                updates['status_change_reason'] = reason
            
            success = await self.update_user_profile(user_id, updates)
            if success:
                return await self.get_user_profile(user_id)
            else:
                return None
        except Exception as e:
            logger.error(f"Error updating status for user {user_id}: {e}")
            return None

    async def get_all_users(self, skip: int = 0, limit: int = 50) -> List[UserProfile]:
        """
        Get a paginated list of all users
        """
        try:
            return await self.db.get_all_users(skip=skip, limit=limit)
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    async def get_total_user_count(self) -> int:
        """
        Get the total count of users in the system
        """
        try:
            return await self.db.get_total_user_count()
        except Exception as e:
            logger.error(f"Error getting total user count: {e}")
            return 0

    async def get_active_users_count(self, hours: int = None, days: int = None) -> int:
        """
        Get the count of active users in the specified time range
        """
        try:
            if hours:
                since = datetime.utcnow() - timedelta(hours=hours)
            elif days:
                since = datetime.utcnow() - timedelta(days=days)
            else:
                since = datetime.utcnow() - timedelta(hours=24)  # Default to 24 hours
            
            return await self.db.get_active_users_count(since=since)
        except Exception as e:
            logger.error(f"Error getting active users count: {e}")
            return 0

    async def log_interaction(self, interaction: InteractionRecord) -> bool:
        """
        Log an interaction between user and AI companion
        """
        try:
            return await self.db.log_interaction(interaction)
        except Exception as e:
            logger.error(f"Error logging interaction for user {interaction.user_id}: {e}")
            return False

    async def get_recent_interactions(self, user_id: str, limit: int = 10) -> List[InteractionRecord]:
        """
        Get recent interactions for a user
        """
        try:
            return await self.db.get_user_interactions(user_id, limit=limit)
        except Exception as e:
            logger.error(f"Error getting recent interactions for user {user_id}: {e}")
            return []

    async def get_total_interaction_count(self) -> int:
        """
        Get the total count of interactions in the system
        """
        try:
            return await self.db.get_total_interaction_count()
        except Exception as e:
            logger.error(f"Error getting total interaction count: {e}")
            return 0

    async def get_recent_interaction_count(self, hours: int = 24) -> int:
        """
        Get the count of interactions in the specified time range
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            return await self.db.get_interaction_count_since(since)
        except Exception as e:
            logger.error(f"Error getting recent interaction count: {e}")
            return 0

    async def get_session_by_id(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific conversation session by ID
        """
        try:
            return await self.db.get_session_by_id(user_id, session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id} for user {user_id}: {e}")
            return None

    async def get_most_recent_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent conversation session for a user
        """
        try:
            return await self.db.get_most_recent_session(user_id)
        except Exception as e:
            logger.error(f"Error getting most recent session for user {user_id}: {e}")
            return None

    async def end_session(self, user_id: str, session_id: str) -> bool:
        """
        Mark a conversation session as ended
        """
        try:
            return await self.db.end_session(user_id, session_id)
        except Exception as e:
            logger.error(f"Error ending session {session_id} for user {user_id}: {e}")
            return False

    async def log_security_incident(self, user_id: str, incident_type: str, severity: str, 
                                   detected_content: str, confidence: float) -> bool:
        """
        Log a security incident for a user
        """
        try:
            return await self.db.log_security_incident(
                user_id=user_id,
                incident_type=incident_type,
                severity=severity,
                detected_content=detected_content,
                confidence=confidence
            )
        except Exception as e:
            logger.error(f"Error logging security incident for user {user_id}: {e}")
            return False

    async def get_security_incidents(self, limit: int = 50, offset: int = 0, 
                                    severity: Optional[str] = None, 
                                    status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get security incidents with optional filtering
        """
        try:
            return await self.db.get_security_incidents(
                limit=limit,
                offset=offset,
                severity=severity,
                status=status
            )
        except Exception as e:
            logger.error(f"Error getting security incidents: {e}")
            return []

    async def cleanup_inactive_users(self, tx=None) -> int:
        """
        Clean up inactive users based on retention policy
        """
        try:
            return await self.db.cleanup_inactive_users(tx=tx)
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0

    async def health_check(self) -> bool:
        """
        Perform a health check on the user service
        """
        try:
            # Check if we can connect to the database
            await self.db.health_check()
            return True
        except Exception as e:
            logger.error(f"User service health check failed: {e}")
            return False
