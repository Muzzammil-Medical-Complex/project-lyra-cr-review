"""
Personality management service for the AI Companion System.

This module manages all interactions with the personality_state table in the database,
handling PAD emotional state updates and nightly baseline drift calculations.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from ..models.personality import BigFiveTraits, PADState, Quirk, PsychologicalNeed, PersonalitySnapshot
from ..models.interaction import EmotionalImpact
from ..database import DatabaseManager
from ..utils.exceptions import PersonalityEngineError, UserNotFoundError


class PersonalityEngine:
    """
    Manages personality states including Big Five traits, PAD emotional states,
    quirks, and psychological needs with proper user scoping.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the personality engine with database manager.
        
        Args:
            db_manager: Database manager for user-scoped queries
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
    
    async def initialize_personality(self, user_id: str) -> PersonalitySnapshot:
        """
        Initialize a new user's personality with default Big Five traits and PAD state.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Initial personality snapshot
            
        Raises:
            PersonalityEngineError: If initialization fails
        """
        try:
            # Generate default Big Five traits (randomized in a full implementation)
            big_five = BigFiveTraits(
                openness=0.5,
                conscientiousness=0.5,
                extraversion=0.5,
                agreeableness=0.5,
                neuroticism=0.5
            )
            
            # Generate default PAD state
            initial_pad = PADState(
                pleasure=0.0,
                arousal=0.0,
                dominance=0.0
            )
            
            # Create initial personality state record
            query = """
                INSERT INTO personality_state
                (user_id, openness, conscientiousness, extraversion, agreeableness, neuroticism,
                 pleasure, arousal, dominance, emotion_label, pad_baseline)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """
            
            params = (
                user_id,
                big_five.openness,
                big_five.conscientiousness,
                big_five.extraversion,
                big_five.agreeableness,
                big_five.neuroticism,
                initial_pad.pleasure,
                initial_pad.arousal,
                initial_pad.dominance,
                initial_pad.to_emotion_octant(),
                initial_pad.model_dump_json()
            )
            
            result = await self.db.execute_user_query(user_id, query, params)
            if not result:
                raise PersonalityEngineError(
                    message="Failed to create initial personality state",
                    operation="initialize_personality"
                )
            
            # Mark as current state
            state_id = result[0]['id']
            await self.db.execute_user_query(
                user_id,
                "UPDATE personality_state SET is_current = TRUE WHERE id = $1",
                (state_id,)
            )
            
            # Initialize default quirks
            await self._initialize_default_quirks(user_id)
            
            # Initialize default psychological needs
            await self._initialize_default_needs(user_id)
            
            return await self.get_personality_snapshot(user_id)
            
        except Exception as e:
            self.logger.error(f"Personality initialization failed for user {user_id}: {e}")
            raise PersonalityEngineError(
                message=f"Personality initialization failed: {str(e)}",
                operation="initialize_personality"
            )
    
    async def _initialize_default_quirks(self, user_id: str):
        """
        Initialize default quirks for a new user.
        
        Args:
            user_id: Discord user ID
        """
        default_quirks = [
            Quirk(
                user_id=user_id,
                name="curious_questioner",
                category="behavior",
                description="Frequently asks follow-up questions to learn more",
                strength=0.1,
                confidence=0.1
            ),
            Quirk(
                user_id=user_id,
                name="empathetic_responder",
                category="speech_pattern",
                description="Often responds with empathy and emotional understanding",
                strength=0.1,
                confidence=0.1
            )
        ]
        
        for quirk in default_quirks:
            query = """
                INSERT INTO quirks
                (user_id, name, category, description, strength, confidence)
                VALUES ($1, $2, $3, $4, $5, $6)
            """
            params = (
                user_id,
                quirk.name,
                quirk.category,
                quirk.description,
                quirk.strength,
                quirk.confidence
            )
            await self.db.execute_user_query(user_id, query, params)
    
    async def _initialize_default_needs(self, user_id: str):
        """
        Initialize default psychological needs for a new user.
        
        Args:
            user_id: Discord user ID
        """
        default_needs = [
            PsychologicalNeed(
                need_type="social",
                current_level=0.5,
                baseline_level=0.5,
                decay_rate=0.03
            ),
            PsychologicalNeed(
                need_type="intellectual",
                current_level=0.5,
                baseline_level=0.5,
                decay_rate=0.02
            ),
            PsychologicalNeed(
                need_type="creative",
                current_level=0.5,
                baseline_level=0.5,
                decay_rate=0.015
            ),
            PsychologicalNeed(
                need_type="rest",
                current_level=0.5,
                baseline_level=0.5,
                decay_rate=0.04
            ),
            PsychologicalNeed(
                need_type="validation",
                current_level=0.5,
                baseline_level=0.5,
                decay_rate=0.025
            )
        ]
        
        for need in default_needs:
            query = """
                INSERT INTO needs
                (user_id, need_type, current_level, baseline_level, decay_rate)
                VALUES ($1, $2, $3, $4, $5)
            """
            params = (
                user_id,
                need.need_type,
                need.current_level,
                need.baseline_level,
                need.decay_rate
            )
            await self.db.execute_user_query(user_id, query, params)
    
    async def get_current_pad_state(self, user_id: str) -> Optional[PADState]:
        """
        Get the current PAD emotional state for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Current PAD state or None if not found
        """
        query = """
            SELECT pleasure, arousal, dominance, emotion_label, pad_baseline
            FROM personality_state
            WHERE user_id = $1 AND is_current = TRUE
            LIMIT 1
        """
        
        try:
            result = await self.db.execute_user_query(user_id, query, (user_id,))
            if not result:
                return None
            
            row = result[0]
            return PADState(
                pleasure=row['pleasure'],
                arousal=row['arousal'],
                dominance=row['dominance'],
                emotion_label=row['emotion_label'],
                pad_baseline=row['pad_baseline']
            )
        except Exception as e:
            self.logger.error(f"Failed to get current PAD state for user {user_id}: {e}")
            return None
    
    async def get_personality_snapshot(self, user_id: str) -> Optional[PersonalitySnapshot]:
        """
        Get a complete personality snapshot for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Personality snapshot including Big Five traits, PAD state, quirks, and needs
        """
        try:
            # Get current personality state
            personality_query = """
                SELECT openness, conscientiousness, extraversion, agreeableness, neuroticism,
                       pleasure, arousal, dominance, emotion_label, pad_baseline
                FROM personality_state
                WHERE user_id = $1 AND is_current = TRUE
                LIMIT 1
            """
            
            personality_result = await self.db.execute_user_query(
                user_id, personality_query, (user_id,), fetch=True
            )
            
            if not personality_result:
                return None
            
            row = personality_result[0]
            
            # Get active quirks
            quirks_query = """
                SELECT id, name, category, description, strength, confidence
                FROM quirks
                WHERE user_id = $1 AND is_active = TRUE
            """
            
            quirks_result = await self.db.execute_user_query(
                user_id, quirks_query, (user_id,), fetch=True
            )
            
            active_quirks = [
                Quirk(
                    id=str(quirk_row['id']),
                    user_id=user_id,
                    name=quirk_row['name'],
                    category=quirk_row['category'],
                    description=quirk_row['description'],
                    strength=quirk_row['strength'],
                    confidence=quirk_row['confidence']
                )
                for quirk_row in quirks_result
            ]
            
            # Get psychological needs
            needs_query = """
                SELECT need_type, current_level, baseline_level, decay_rate,
                       last_satisfied, trigger_threshold, satisfaction_rate
                FROM needs
                WHERE user_id = $1
            """
            
            needs_result = await self.db.execute_user_query(
                user_id, needs_query, (user_id,), fetch=True
            )
            
            psychological_needs = [
                PsychologicalNeed(
                    need_type=need_row['need_type'],
                    current_level=need_row['current_level'],
                    baseline_level=need_row['baseline_level'],
                    decay_rate=need_row['decay_rate'],
                    last_satisfied=need_row['last_satisfied'],
                    trigger_threshold=need_row['trigger_threshold'],
                    satisfaction_rate=need_row['satisfaction_rate']
                )
                for need_row in needs_result
            ]
            
            return PersonalitySnapshot(
                user_id=user_id,
                big_five=BigFiveTraits(
                    openness=row['openness'],
                    conscientiousness=row['conscientiousness'],
                    extraversion=row['extraversion'],
                    agreeableness=row['agreeableness'],
                    neuroticism=row['neuroticism']
                ),
                current_pad=PADState(
                    pleasure=row['pleasure'],
                    arousal=row['arousal'],
                    dominance=row['dominance'],
                    emotion_label=row['emotion_label'],
                    pad_baseline=row['pad_baseline']
                ),
                active_quirks=active_quirks,
                needs=psychological_needs
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get personality snapshot for user {user_id}: {e}")
            return None
    
    async def update_pad_state(self, user_id: str, delta: PADState) -> PADState:
        """
        Update the PAD emotional state for a user with the given delta.
        
        Args:
            user_id: Discord user ID
            delta: PAD state changes to apply
            
        Returns:
            Updated PAD state
            
        Raises:
            PersonalityEngineError: If update fails
            UserNotFoundError: If user personality state not found
        """
        try:
            # Get current personality state
            current_state = await self.get_current_pad_state(user_id)
            if not current_state:
                raise UserNotFoundError(user_id=user_id, message="Personality state not found")
            
            # Apply delta with clamping
            new_pleasure = max(-1.0, min(1.0, current_state.pleasure + delta.pleasure))
            new_arousal = max(-1.0, min(1.0, current_state.arousal + delta.arousal))
            new_dominance = max(-1.0, min(1.0, current_state.dominance + delta.dominance))
            
            # Create new PAD state
            new_pad_state = PADState(
                pleasure=new_pleasure,
                arousal=new_arousal,
                dominance=new_dominance
            )
            
            # Archive current state
            archive_query = """
                UPDATE personality_state
                SET is_current = FALSE
                WHERE user_id = $1 AND is_current = TRUE
            """
            await self.db.execute_user_query(user_id, archive_query, (user_id,))
            
            # Insert new state
            insert_query = """
                INSERT INTO personality_state
                (user_id, openness, conscientiousness, extraversion, agreeableness, neuroticism,
                 pleasure, arousal, dominance, emotion_label, pad_baseline, is_current)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)
                RETURNING id
            """
            
            insert_params = (
                user_id,
                current_state.pad_baseline['openness'],
                current_state.pad_baseline['conscientiousness'],
                current_state.pad_baseline['extraversion'],
                current_state.pad_baseline['agreeableness'],
                current_state.pad_baseline['neuroticism'],
                new_pad_state.pleasure,
                new_pad_state.arousal,
                new_pad_state.dominance,
                new_pad_state.to_emotion_octant(),
                current_state.pad_baseline.model_dump_json() if hasattr(current_state.pad_baseline, 'model_dump_json') else current_state.pad_baseline,
            )
            
            result = await self.db.execute_user_query(user_id, insert_query, insert_params)
            if not result:
                raise PersonalityEngineError(
                    message="Failed to update personality state",
                    operation="update_pad_state"
                )
            
            return new_pad_state
            
        except UserNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"PAD state update failed for user {user_id}: {e}")
            raise PersonalityEngineError(
                message=f"PAD state update failed: {str(e)}",
                operation="update_pad_state"
            )
    
    async def apply_pad_baseline_drift(self, user_id: str, drift_rate: float = 0.01) -> PADState:
        """
        Apply nightly PAD baseline drift using the precise mathematical formula.
        
        Formula: new_baseline = current_baseline + (average_interaction_pad - current_baseline) * drift_rate
        
        Args:
            user_id: Discord user ID
            drift_rate: Maximum change rate per day (default 0.01 = 1%)
            
        Returns:
            Updated PAD baseline state
            
        Raises:
            PersonalityEngineError: If drift calculation fails
        """
        try:
            # Get current personality state
            current_personality = await self.get_personality_snapshot(user_id)
            if not current_personality:
                raise UserNotFoundError(user_id=user_id, message="Personality state not found")
            
            current_baseline = current_personality.current_pad.pad_baseline
            
            # Get all user interactions from last 7 days
            interactions_query = """
                SELECT pad_after
                FROM interactions
                WHERE user_id = $1 AND timestamp >= NOW() - INTERVAL '7 days'
            """
            
            interactions_result = await self.db.execute_user_query(
                user_id, interactions_query, (user_id,), fetch=True
            )
            
            if len(interactions_result) < 5:  # Need minimum data
                return current_baseline
            
            # Calculate average PAD state from interactions
            total_pleasure = sum(row['pad_after']['pleasure'] for row in interactions_result)
            total_arousal = sum(row['pad_after']['arousal'] for row in interactions_result)
            total_dominance = sum(row['pad_after']['dominance'] for row in interactions_result)
            
            count = len(interactions_result)
            average_interaction_pad = PADState(
                pleasure=total_pleasure / count,
                arousal=total_arousal / count,
                dominance=total_dominance / count
            )
            
            # Apply drift formula
            new_baseline = PADState(
                pleasure=current_baseline.pleasure + (average_interaction_pad.pleasure - current_baseline.pleasure) * drift_rate,
                arousal=current_baseline.arousal + (average_interaction_pad.arousal - current_baseline.arousal) * drift_rate,
                dominance=current_baseline.dominance + (average_interaction_pad.dominance - current_baseline.dominance) * drift_rate
            )
            
            # Clamp to valid ranges (-1.0 to 1.0)
            new_baseline.pleasure = max(-1.0, min(1.0, new_baseline.pleasure))
            new_baseline.arousal = max(-1.0, min(1.0, new_baseline.arousal))
            new_baseline.dominance = max(-1.0, min(1.0, new_baseline.dominance))
            
            # Update personality state with new baseline
            update_query = """
                UPDATE personality_state
                SET pad_baseline = $1
                WHERE user_id = $2 AND is_current = TRUE
            """
            
            update_params = (
                new_baseline.model_dump_json(),
                user_id
            )
            
            await self.db.execute_user_query(user_id, update_query, update_params)
            
            return new_baseline
            
        except UserNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"PAD baseline drift failed for user {user_id}: {e}")
            raise PersonalityEngineError(
                message=f"PAD baseline drift failed: {str(e)}",
                operation="apply_pad_baseline_drift"
            )
    
    async def update_quirk_strength(self, user_id: str, quirk_name: str, strength_delta: float) -> bool:
        """
        Update the strength of a specific quirk.
        
        Args:
            user_id: Discord user ID
            quirk_name: Name of the quirk to update
            strength_delta: Change in quirk strength
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current quirk strength
            query = """
                SELECT strength FROM quirks
                WHERE user_id = $1 AND name = $2 AND is_active = TRUE
                LIMIT 1
            """
            
            result = await self.db.execute_user_query(user_id, query, (user_id, quirk_name))
            if not result:
                return False
            
            current_strength = result[0]['strength']
            new_strength = max(0.0, min(1.0, current_strength + strength_delta))
            
            # Update quirk strength
            update_query = """
                UPDATE quirks
                SET strength = $1, last_reinforced = NOW()
                WHERE user_id = $2 AND name = $3
            """
            
            update_params = (new_strength, user_id, quirk_name)
            await self.db.execute_user_query(user_id, update_query, update_params)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update quirk strength for user {user_id}, quirk {quirk_name}: {e}")
            return False
    
    async def update_need_level(self, user_id: str, need_type: str, level_delta: float) -> bool:
        """
        Update the level of a specific psychological need.
        
        Args:
            user_id: Discord user ID
            need_type: Type of need to update
            level_delta: Change in need level
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            update_query = """
                UPDATE needs
                SET current_level = GREATEST(0.0, LEAST(1.0, current_level + $1)),
                    last_updated = NOW()
                WHERE user_id = $2 AND need_type = $3
            """
            
            update_params = (level_delta, user_id, need_type)
            await self.db.execute_user_query(user_id, update_query, update_params)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update need level for user {user_id}, need {need_type}: {e}")
            return False
