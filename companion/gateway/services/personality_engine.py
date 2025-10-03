"""
Personality management service for the AI Companion System.

This module manages all interactions with the personality_state table in the database,
handling PAD emotional state updates and nightly baseline drift calculations.
"""

import asyncio
import json
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
            # Create initial personality state record within a transaction
            async with self.db.get_transaction() as tx:
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

                row = await tx.connection.fetchrow(query, *params)
                if row is None:
                    raise PersonalityEngineError(
                        message="Failed to create initial personality state",
                        operation="initialize_personality"
                    )

                # Mark as current state
                state_id = row["id"]
                await tx.execute(
                    "UPDATE personality_state SET is_current = TRUE WHERE id = $1",
                    state_id
                )
                
                # Initialize default quirks
                await self._initialize_default_quirks_tx(user_id, tx)
                
                # Initialize default psychological needs
                await self._initialize_default_needs_tx(user_id, tx)
                
                # Commit happens automatically when exiting the transaction context
                
            return await self.get_personality_snapshot(user_id)
            
        except Exception as e:
            self.logger.exception("Personality initialization failed for user %s", user_id)
            raise PersonalityEngineError(
                message=f"Personality initialization failed: {e!s}",
                operation="initialize_personality"
            ) from e
    
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

    async def _initialize_default_quirks_tx(self, user_id: str, tx):
        """
        Initialize default quirks for a new user within a transaction.
        
        Args:
            user_id: Discord user ID
            tx: Database transaction
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
            await tx.execute(query, *params)
    
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

    async def _initialize_default_needs_tx(self, user_id: str, tx):
        """
        Initialize default psychological needs for a new user within a transaction.
        
        Args:
            user_id: Discord user ID
            tx: Database transaction
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
            await tx.execute(query, *params)
    
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
                emotion_label=row['emotion_label']
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
                user_id, personality_query, (user_id,)
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
                user_id, quirks_query, (user_id,)
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
                       trigger_threshold, satisfaction_rate
                FROM needs
                WHERE user_id = $1
            """

            needs_result = await self.db.execute_user_query(
                user_id, needs_query, (user_id,)
            )

            psychological_needs = [
                PsychologicalNeed(
                    need_type=need_row['need_type'],
                    current_level=need_row['current_level'],
                    baseline_level=need_row['baseline_level'],
                    decay_rate=need_row['decay_rate'],
                    trigger_threshold=need_row['trigger_threshold'],
                    satisfaction_rate=need_row['satisfaction_rate']
                )
                for need_row in needs_result
            ]
            
            # Parse pad_baseline from database (stored as JSON)
            pad_baseline_data = row['pad_baseline']
            if isinstance(pad_baseline_data, str):
                pad_baseline_dict = json.loads(pad_baseline_data)
            elif isinstance(pad_baseline_data, dict):
                pad_baseline_dict = pad_baseline_data
            else:
                # Fallback to neutral baseline
                pad_baseline_dict = {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0}

            pad_baseline = PADState(**pad_baseline_dict)

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
                    emotion_label=row['emotion_label']
                ),
                pad_baseline=pad_baseline,
                active_quirks=active_quirks,
                psychological_needs=psychological_needs
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
            # Get current personality snapshot (includes Big Five traits and PAD baseline)
            current_snapshot = await self.get_personality_snapshot(user_id)
            if not current_snapshot:
                raise UserNotFoundError(user_id=user_id, message="Personality state not found")

            # Apply delta with clamping
            new_pleasure = max(-1.0, min(1.0, current_snapshot.current_pad.pleasure + delta.pleasure))
            new_arousal = max(-1.0, min(1.0, current_snapshot.current_pad.arousal + delta.arousal))
            new_dominance = max(-1.0, min(1.0, current_snapshot.current_pad.dominance + delta.dominance))

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

            # Insert new state (preserving Big Five traits and PAD baseline)
            insert_query = """
                INSERT INTO personality_state
                (user_id, openness, conscientiousness, extraversion, agreeableness, neuroticism,
                 pleasure, arousal, dominance, emotion_label, pad_baseline, is_current)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)
                RETURNING id
            """

            # Normalize pad_baseline to JSON string
            if isinstance(current_snapshot.pad_baseline, PADState):
                pad_baseline_json = current_snapshot.pad_baseline.model_dump_json()
            elif isinstance(current_snapshot.pad_baseline, dict):
                pad_baseline_json = PADState(**current_snapshot.pad_baseline).model_dump_json()
            elif isinstance(current_snapshot.pad_baseline, str):
                pad_baseline_json = current_snapshot.pad_baseline
            else:
                # Fallback: create baseline from current PAD state
                pad_baseline_json = PADState(
                    pleasure=current_snapshot.current_pad.pleasure,
                    arousal=current_snapshot.current_pad.arousal,
                    dominance=current_snapshot.current_pad.dominance
                ).model_dump_json()

            insert_params = (
                user_id,
                current_snapshot.big_five.openness,
                current_snapshot.big_five.conscientiousness,
                current_snapshot.big_five.extraversion,
                current_snapshot.big_five.agreeableness,
                current_snapshot.big_five.neuroticism,
                new_pad_state.pleasure,
                new_pad_state.arousal,
                new_pad_state.dominance,
                new_pad_state.to_emotion_octant(),
                pad_baseline_json,
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

            # Access baseline from the top-level field, not from current_pad
            current_baseline = current_personality.pad_baseline
            if not current_baseline:
                self.logger.warning(f"No baseline PAD state found for user {user_id}, skipping drift")
                return current_personality.current_pad
            
            # Get all user interactions from last 7 days
            interactions_query = """
                SELECT pad_after
                FROM interactions
                WHERE user_id = $1 AND timestamp >= NOW() - INTERVAL '7 days'
            """
            
            interactions_result = await self.db.execute_user_query(
                user_id, interactions_query, (user_id,)
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
    async def get_personality_history(self, user_id: str, days: int = 30) -> list[PersonalitySnapshot]:
        """
        Get historical personality snapshots for a user.

        Args:
            user_id: Discord user ID
            days: Number of days of history to retrieve (default 30)

        Returns:
            List of PersonalitySnapshot objects ordered by most recent first
        """
        try:
            query = """
                SELECT id, user_id, openness, conscientiousness, extraversion, agreeableness, neuroticism,
                       pleasure, arousal, dominance, emotion_label, pad_baseline, is_current, created_at
                FROM personality_state
                WHERE user_id = $1 AND created_at >= NOW() - make_interval(days => $2)
                ORDER BY created_at DESC
            """

            rows = await self.db.execute_user_query(user_id, query, (user_id, days))

            history = []
            for row in rows:
                # Parse PAD baseline
                pad_baseline_data = row['pad_baseline']
                if isinstance(pad_baseline_data, str):
                    pad_baseline_dict = json.loads(pad_baseline_data)
                elif isinstance(pad_baseline_data, dict):
                    pad_baseline_dict = pad_baseline_data
                else:
                    pad_baseline_dict = {'pleasure': 0.0, 'arousal': 0.0, 'dominance': 0.0}

                pad_baseline = PADState(**pad_baseline_dict)

                snapshot = PersonalitySnapshot(
                    user_id=row['user_id'],
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
                        pad_baseline=pad_baseline
                    ),
                    active_quirks=[],  # Not including quirks in history for performance
                    psychological_needs=[]  # Not including needs in history for performance
                )
                history.append(snapshot)

            return history

        except Exception as e:
            self.logger.error(f"Failed to get personality history for user {user_id}: {e}")
            return []

    async def get_active_quirks(self, user_id: str) -> list[Quirk]:
        """
        Get all active quirks for a user.

        Args:
            user_id: Discord user ID

        Returns:
            List of active Quirk objects
        """
        try:
            query = """
                SELECT id, name, category, description, strength, confidence
                FROM quirks
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY strength DESC
            """

            rows = await self.db.execute_user_query(user_id, query, (user_id,))

            quirks = [
                Quirk(
                    id=str(row['id']),
                    user_id=user_id,
                    name=row['name'],
                    category=row['category'],
                    description=row['description'],
                    strength=row['strength'],
                    confidence=row['confidence']
                )
                for row in rows
            ]

            return quirks

        except Exception as e:
            self.logger.error(f"Failed to get active quirks for user {user_id}: {e}")
            return []

    async def get_all_quirks(self, user_id: str) -> list[Quirk]:
        """
        Get all quirks (active and inactive) for a user.

        Args:
            user_id: Discord user ID

        Returns:
            List of all Quirk objects
        """
        try:
            query = """
                SELECT id, name, category, description, strength, confidence
                FROM quirks
                WHERE user_id = $1
                ORDER BY is_active DESC, strength DESC
            """

            rows = await self.db.execute_user_query(user_id, query, (user_id,))

            quirks = [
                Quirk(
                    id=str(row['id']),
                    user_id=user_id,
                    name=row['name'],
                    category=row['category'],
                    description=row['description'],
                    strength=row['strength'],
                    confidence=row['confidence']
                )
                for row in rows
            ]

            return quirks

        except Exception as e:
            self.logger.error(f"Failed to get all quirks for user {user_id}: {e}")
            return []

    async def get_user_needs(self, user_id: str) -> list[PsychologicalNeed]:
        """
        Get all psychological needs for a user.

        Args:
            user_id: Discord user ID

        Returns:
            List of PsychologicalNeed objects
        """
        try:
            query = """
                SELECT need_type, current_level, baseline_level, decay_rate,
                       trigger_threshold, satisfaction_rate
                FROM needs
                WHERE user_id = $1
                ORDER BY current_level DESC
            """

            rows = await self.db.execute_user_query(user_id, query, (user_id,))

            needs = [
                PsychologicalNeed(
                    need_type=row['need_type'],
                    current_level=row['current_level'],
                    baseline_level=row['baseline_level'],
                    decay_rate=row['decay_rate'],
                    trigger_threshold=row['trigger_threshold'],
                    satisfaction_rate=row['satisfaction_rate']
                )
                for row in rows
            ]

            return needs

        except Exception as e:
            self.logger.error(f"Failed to get user needs for user {user_id}: {e}")
            return []

    async def get_evolution_metrics(self, user_id: str) -> Dict[str, Any]:
        """
        Get personality evolution metrics for a user.

        Args:
            user_id: Discord user ID

        Returns:
            Dictionary containing evolution metrics
        """
        try:
            # Get recent personality history
            history = await self.get_personality_history(user_id, days=30)

            if len(history) < 2:
                return {
                    "status": "insufficient_data",
                    "message": "Need at least 2 personality snapshots to calculate evolution metrics"
                }

            # Calculate PAD stability (variance)
            pad_values = {
                'pleasure': [s.current_pad.pleasure for s in history],
                'arousal': [s.current_pad.arousal for s in history],
                'dominance': [s.current_pad.dominance for s in history]
            }

            import statistics
            stability = {
                'pleasure_variance': statistics.variance(pad_values['pleasure']) if len(pad_values['pleasure']) > 1 else 0.0,
                'arousal_variance': statistics.variance(pad_values['arousal']) if len(pad_values['arousal']) > 1 else 0.0,
                'dominance_variance': statistics.variance(pad_values['dominance']) if len(pad_values['dominance']) > 1 else 0.0
            }

            # Calculate overall stability score (inverse of average variance)
            avg_variance = (stability['pleasure_variance'] + stability['arousal_variance'] + stability['dominance_variance']) / 3
            stability_score = max(0.0, 1.0 - avg_variance)  # Higher score = more stable

            # Get quirk evolution metrics
            quirks = await self.get_active_quirks(user_id)
            quirk_metrics = {
                'total_quirks': len(quirks),
                'average_strength': sum(q.strength for q in quirks) / len(quirks) if quirks else 0.0,
                'average_confidence': sum(q.confidence for q in quirks) / len(quirks) if quirks else 0.0
            }

            # Get needs metrics
            needs = await self.get_user_needs(user_id)
            needs_metrics = {
                'total_needs': len(needs),
                'average_level': sum(n.current_level for n in needs) / len(needs) if needs else 0.0,
                'needs_above_threshold': sum(1 for n in needs if n.current_level >= n.trigger_threshold)
            }

            return {
                "status": "success",
                "stability_score": stability_score,
                "stability_details": stability,
                "quirk_metrics": quirk_metrics,
                "needs_metrics": needs_metrics,
                "snapshots_analyzed": len(history)
            }

        except Exception as e:
            self.logger.error(f"Failed to get evolution metrics for user {user_id}: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def override_pad_state(self, user_id: str, pad_state: PADState) -> Optional[PersonalitySnapshot]:
        """
        Manually override the current PAD state for a user.

        Args:
            user_id: Discord user ID
            pad_state: New PAD state to apply

        Returns:
            Updated PersonalitySnapshot or None on failure
        """
        try:
            update_query = """
                UPDATE personality_state
                SET pleasure = $1, arousal = $2, dominance = $3,
                    emotion_label = $4, updated_at = NOW()
                WHERE user_id = $5 AND is_current = TRUE
            """

            emotion_label = pad_state.to_emotion_octant()
            params = (pad_state.pleasure, pad_state.arousal, pad_state.dominance, emotion_label, user_id)

            await self.db.execute_user_query(user_id, update_query, params)

            # Return updated snapshot
            return await self.get_personality_snapshot(user_id)

        except Exception as e:
            self.logger.error(f"Failed to override PAD state for user {user_id}: {e}")
            return None

    async def get_personality_baseline(self, user_id: str) -> Optional[PersonalitySnapshot]:
        """
        Get the baseline personality state for a user (essentially the current snapshot).

        Args:
            user_id: Discord user ID

        Returns:
            Current PersonalitySnapshot or None
        """
        return await self.get_personality_snapshot(user_id)

    async def get_big_five_traits(self, user_id: str) -> Optional[BigFiveTraits]:
        """
        Get the Big Five personality traits for a user.

        Args:
            user_id: Discord user ID

        Returns:
            BigFiveTraits object or None
        """
        try:
            query = """
                SELECT openness, conscientiousness, extraversion, agreeableness, neuroticism
                FROM personality_state
                WHERE user_id = $1 AND is_current = TRUE
            """

            rows = await self.db.execute_user_query(user_id, query, (user_id,))

            if not rows:
                return None

            row = rows[0]
            return BigFiveTraits(
                openness=row['openness'],
                conscientiousness=row['conscientiousness'],
                extraversion=row['extraversion'],
                agreeableness=row['agreeableness'],
                neuroticism=row['neuroticism']
            )

        except Exception as e:
            self.logger.error(f"Failed to get Big Five traits for user {user_id}: {e}")
            return None


    async def get_personality_stability(self, user_id: str, days: int = 14) -> float:
        """
        Calculate personality stability score based on PAD variance over time.

        Args:
            user_id: Discord user ID
            days: Number of days to analyze (default 14)

        Returns:
            Stability score from 0.0 (unstable) to 1.0 (very stable)
        """
        try:
            history = await self.get_personality_history(user_id, days=days)

            if len(history) < 2:
                return 1.0  # Assume stable if not enough data

            # Calculate variance for each PAD dimension
            import statistics
            pleasure_values = [s.current_pad.pleasure for s in history]
            arousal_values = [s.current_pad.arousal for s in history]
            dominance_values = [s.current_pad.dominance for s in history]

            pleasure_variance = statistics.variance(pleasure_values) if len(pleasure_values) > 1 else 0.0
            arousal_variance = statistics.variance(arousal_values) if len(arousal_values) > 1 else 0.0
            dominance_variance = statistics.variance(dominance_values) if len(dominance_values) > 1 else 0.0

            # Average variance
            avg_variance = (pleasure_variance + arousal_variance + dominance_variance) / 3.0

            # Convert variance to stability score (inverse relationship)
            # Variance of 0 = stability 1.0, higher variance = lower stability
            stability_score = max(0.0, min(1.0, 1.0 - (avg_variance * 2.0)))

            return stability_score

        except Exception as e:
            self.logger.error(f"Failed to calculate personality stability for user {user_id}: {e}")
            return 0.5  # Return neutral stability on error
