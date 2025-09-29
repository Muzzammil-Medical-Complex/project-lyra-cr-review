"""
Reflection Agent for AI Companion System
Handles nightly memory consolidation, personality evolution, and pattern analysis.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from ..models.personality import PADState, Quirk, PsychologicalNeed
from ..models.memory import EpisodicMemory, SemanticMemory, MemoryTheme
from ..services.memory_manager import MemoryManager
from ..services.personality_engine import PersonalityEngine
from ..services.groq_client import GroqClient
from ..database import DatabaseManager

logger = logging.getLogger(__name__)

@dataclass
class ConsolidationResult:
    """Result of memory consolidation process"""
    user_id: str
    consolidated_count: int = 0
    themes_identified: List[MemoryTheme] = None
    errors: List[str] = None
    duration_seconds: float = 0.0

@dataclass
class PersonalityEvolutionResult:
    """Result of personality evolution process"""
    user_id: str
    pad_baseline_updated: bool = False
    quirks_evolved: int = 0
    needs_updated: int = 0
    errors: List[str] = None
    duration_seconds: float = 0.0

@dataclass
class BehavioralAnalysis:
    """Analysis of user behavioral patterns"""
    user_id: str
    interaction_count: int = 0
    emotional_volatility: float = 0.0
    communication_changes: List[str] = None
    detected_patterns: List[Dict[str, Any]] = None
    confidence: float = 0.0

@dataclass
class ReflectionReport:
    """Complete nightly reflection report"""
    start_time: datetime
    end_time: Optional[datetime] = None
    users_processed: int = 0
    consolidation_results: List[ConsolidationResult] = None
    personality_results: List[PersonalityEvolutionResult] = None
    errors: List[str] = None
    duration_seconds: float = 0.0

class ReflectionAgent:
    """
    Orchestrates nightly reflection processes including memory consolidation,
    personality evolution, and behavioral pattern analysis.
    """
    
    def __init__(self, memory: MemoryManager, personality: PersonalityEngine, 
                 groq: GroqClient, db: DatabaseManager):
        self.memory = memory
        self.personality = personality
        self.groq = groq
        self.db = db
        
        # Reflection processing parameters
        self.max_users_per_batch = 50
        self.consolidation_similarity_threshold = 0.7
        self.min_memories_for_theme = 3
        self.reflection_lookback_days = 7

    async def run_nightly_reflection(self) -> ReflectionReport:
        """
        Main entry point for nightly reflection process.
        Processes all active users in batches.
        """
        start_time = datetime.utcnow()
        report = ReflectionReport(
            start_time=start_time,
            consolidation_results=[],
            personality_results=[],
            errors=[]
        )
        
        try:
            # Get all active users for reflection
            active_users = await self.db.get_active_users(days=self.reflection_lookback_days)
            logger.info(f"Processing reflection for {len(active_users)} active users")
            
            # Process users in batches to avoid overwhelming the system
            user_batches = [
                active_users[i:i + self.max_users_per_batch] 
                for i in range(0, len(active_users), self.max_users_per_batch)
            ]
            
            users_processed = 0
            for batch_num, user_batch in enumerate(user_batches):
                logger.info(f"Processing batch {batch_num + 1}/{len(user_batches)} with {len(user_batch)} users")
                
                # Process users in parallel within batch
                tasks = [self.process_user_reflection(user_id) for user_id in user_batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect results
                for result in batch_results:
                    if isinstance(result, Exception):
                        error_msg = f"Batch processing error: {str(result)}"
                        report.errors.append(error_msg)
                        logger.error(error_msg)
                    else:
                        if result.consolidation_result:
                            report.consolidation_results.append(result.consolidation_result)
                        if result.personality_result:
                            report.personality_results.append(result.personality_result)
                        users_processed += 1
                
                # Brief pause between batches to avoid system overload
                if batch_num < len(user_batches) - 1:
                    await asyncio.sleep(5)  # 5 second pause
            
            report.users_processed = users_processed
            logger.info(f"Reflection completed for {users_processed} users")
            
        except Exception as e:
            error_msg = f"Nightly reflection failed: {str(e)}"
            report.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        finally:
            report.end_time = datetime.utcnow()
            report.duration_seconds = (report.end_time - start_time).total_seconds()
            
            # Log report summary
            await self.db.log_reflection_report(report)
        
        return report

    async def process_user_reflection(self, user_id: str) -> Dict[str, Any]:
        """
        Complete reflection process for a single user.
        """
        start_time = datetime.utcnow()
        result = {
            "user_id": user_id,
            "consolidation_result": None,
            "personality_result": None,
            "duration_seconds": 0.0
        }
        
        try:
            # 1. Memory Consolidation
            consolidation_result = await self.consolidate_user_memories(user_id)
            result["consolidation_result"] = consolidation_result
            
            # 2. Personality Evolution
            personality_result = await self.evolve_user_personality(user_id)
            result["personality_result"] = personality_result
            
            # 3. Pattern Analysis (for future use)
            # patterns = await self.detect_conversation_patterns(user_id)
            
            logger.info(f"Reflection completed for user {user_id}")
            
        except Exception as e:
            error_msg = f"Reflection failed for user {user_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Log error but continue with other users
            await self.db.log_reflection_error(user_id, str(e))
        
        finally:
            end_time = datetime.utcnow()
            result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        return result

    async def consolidate_user_memories(self, user_id: str) -> ConsolidationResult:
        """
        Consolidate episodic memories into semantic memories based on themes.
        """
        start_time = datetime.utcnow()
        result = ConsolidationResult(user_id=user_id, themes_identified=[], errors=[])
        
        try:
            # Get unconsolidated episodic memories from the last 24 hours
            recent_memories = await self.memory.get_recent_episodic_memories(
                user_id=user_id,
                hours=24
            )
            
            if len(recent_memories) < self.min_memories_for_theme:
                logger.info(f"Not enough memories for consolidation for user {user_id}")
                return result
            
            # Identify thematic clusters in memories
            memory_themes = await self.identify_memory_themes(user_id, recent_memories)
            result.themes_identified = memory_themes
            
            # Consolidate each theme into semantic memories
            consolidated_count = 0
            for theme in memory_themes:
                if len(theme.related_memories) >= self.min_memories_for_theme:
                    try:
                        semantic_memory = await self._consolidate_theme_to_semantic(user_id, theme)
                        
                        # Mark source memories as consolidated
                        for memory in theme.related_memories:
                            await self.db.mark_memory_consolidated(user_id, memory.id, semantic_memory.id)
                        
                        consolidated_count += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to consolidate theme '{theme.theme_name}': {str(e)}"
                        result.errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)
            
            result.consolidated_count = consolidated_count
            logger.info(f"Consolidated {consolidated_count} themes for user {user_id}")
            
        except Exception as e:
            error_msg = f"Memory consolidation failed for user {user_id}: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        finally:
            end_time = datetime.utcnow()
            result.duration_seconds = (end_time - start_time).total_seconds()
        
        return result

    async def identify_memory_themes(self, user_id: str, memories: List[EpisodicMemory]) -> List[MemoryTheme]:
        """
        Use AI to identify thematic clusters in episodic memories.
        """
        if len(memories) < self.min_memories_for_theme:
            return []
        
        # Extract memory contents for analysis
        memory_contents = [memory.content for memory in memories]
        
        # Use Groq for thematic analysis
        try:
            theme_analysis = await self.groq.analyze_memory_themes(
                memories=memory_contents,
                user_context={"user_id": user_id}
            )
            
            themes = []
            for theme_data in theme_analysis.get("themes", []):
                # Map memories to theme based on indices
                theme_memories = []
                for idx in theme_data.get("memory_indices", []):
                    if 0 <= idx < len(memories):
                        theme_memories.append(memories[idx])
                
                if theme_memories:  # Only create theme if it has memories
                    theme = MemoryTheme(
                        theme_name=theme_data["theme_name"],
                        description=theme_data["description"],
                        confidence=theme_data["confidence"],
                        related_memories=theme_memories
                    )
                    themes.append(theme)
            
            # Sort themes by confidence
            themes.sort(key=lambda t: t.confidence, reverse=True)
            return themes[:5]  # Limit to top 5 themes
            
        except Exception as e:
            logger.error(f"Theme identification failed for user {user_id}: {str(e)}", exc_info=True)
            return []

    async def _consolidate_theme_to_semantic(self, user_id: str, theme: MemoryTheme) -> SemanticMemory:
        """
        Convert a thematic cluster of episodic memories into a single semantic memory.
        """
        # Generate consolidated content using AI
        consolidated_content = await self.groq.generate_semantic_summary(
            theme_name=theme.theme_name,
            memories=[m.content for m in theme.related_memories],
            context={"user_id": user_id}
        )
        
        # Calculate consolidated importance score (average of source memories)
        total_importance = sum(m.importance_score for m in theme.related_memories)
        avg_importance = total_importance / len(theme.related_memories) if theme.related_memories else 0.5
        # Boost importance for consolidated memories
        final_importance = min(1.0, avg_importance * 1.2)
        
        # Store semantic memory
        semantic_memory = SemanticMemory(
            user_id=user_id,
            content=consolidated_content,
            importance_score=final_importance,
            theme_name=theme.theme_name,
            source_count=len(theme.related_memories),
            created_at=datetime.utcnow()
        )
        
        await self.memory.store_semantic_memory(user_id, semantic_memory)
        return semantic_memory

    async def evolve_user_personality(self, user_id: str) -> PersonalityEvolutionResult:
        """
        Analyze and apply personality evolution based on recent behavioral patterns.
        """
        start_time = datetime.utcnow()
        result = PersonalityEvolutionResult(user_id=user_id, errors=[])
        
        try:
            # Get current personality state
            current_personality = await self.personality.get_personality_snapshot(user_id)
            if not current_personality:
                result.errors.append("No personality data found")
                return result
            
            # Analyze behavioral changes over the reflection period
            behavioral_analysis = await self.analyze_behavioral_changes(user_id)
            
            # Apply PAD baseline drift based on recent emotional patterns
            pad_updated = await self._apply_pad_baseline_drift(user_id, behavioral_analysis)
            result.pad_baseline_updated = pad_updated
            
            # Evolve quirks based on usage patterns
            quirk_changes = await self.update_quirk_strengths(user_id)
            result.quirks_evolved = quirk_changes
            
            # Update psychological needs based on satisfaction patterns
            needs_updated = await self._update_psychological_needs(user_id, behavioral_analysis)
            result.needs_updated = needs_updated
            
            logger.info(f"Personality evolution completed for user {user_id}")
            
        except Exception as e:
            error_msg = f"Personality evolution failed for user {user_id}: {str(e)}"
            result.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        finally:
            end_time = datetime.utcnow()
            result.duration_seconds = (end_time - start_time).total_seconds()
        
        return result

    async def analyze_behavioral_changes(self, user_id: str) -> BehavioralAnalysis:
        """
        Deep analysis of behavioral changes over the reflection period.
        """
        # Get interactions from the last 7 days for trend analysis
        recent_interactions = await self.db.get_user_interactions(user_id, days=self.reflection_lookback_days)
        
        if len(recent_interactions) < 5:
            return BehavioralAnalysis(user_id=user_id, interaction_count=len(recent_interactions))
        
        # Calculate emotional volatility (standard deviation of pleasure values)
        pleasure_values = [i.pad_after.pleasure for i in recent_interactions if i.pad_after]
        if pleasure_values:
            mean_pleasure = sum(pleasure_values) / len(pleasure_values)
            variance = sum((p - mean_pleasure) ** 2 for p in pleasure_values) / len(pleasure_values)
            emotional_volatility = variance ** 0.5
        else:
            emotional_volatility = 0.0
        
        # Detect communication changes (message length trends)
        message_lengths = [len(i.user_message) for i in recent_interactions if i.user_message]
        communication_changes = []
        if len(message_lengths) > 2:
            # Simple trend detection
            first_half = message_lengths[:len(message_lengths)//2]
            second_half = message_lengths[len(message_lengths)//2:]
            
            avg_first = sum(first_half) / len(first_half) if first_half else 0
            avg_second = sum(second_half) / len(second_half) if second_half else 0
            
            if avg_second > avg_first * 1.2:
                communication_changes.append("User messages becoming longer")
            elif avg_second < avg_first * 0.8:
                communication_changes.append("User messages becoming shorter")
        
        return BehavioralAnalysis(
            user_id=user_id,
            interaction_count=len(recent_interactions),
            emotional_volatility=emotional_volatility,
            communication_changes=communication_changes,
            confidence=min(1.0, len(recent_interactions) / 20.0)  # Confidence based on data amount
        )

    async def update_quirk_strengths(self, user_id: str) -> int:
        """
        Update quirk strengths based on recent usage and reinforcement patterns.
        Returns number of quirks updated.
        """
        active_quirks = await self.db.get_active_quirks(user_id)
        if not active_quirks:
            return 0
        
        quirks_updated = 0
        
        for quirk in active_quirks:
            # Calculate reinforcement frequency over reflection period
            recent_reinforcements = await self.db.get_quirk_reinforcements(
                quirk.id, hours=24
            )
            
            # Calculate new strength based on usage
            old_strength = quirk.strength
            if recent_reinforcements > 0:
                # Strengthen quirk based on usage (diminishing returns)
                strength_increase = min(0.1, recent_reinforcements * 0.02)
                new_strength = min(1.0, old_strength + strength_increase)
            else:
                # Apply decay for unused quirks
                decay_amount = quirk.decay_rate * (24 / 24)  # Daily decay rate
                new_strength = max(0.0, old_strength - decay_amount)
            
            # Update confidence based on consistency
            confidence_change = self._calculate_quirk_confidence_change(quirk, recent_reinforcements)
            new_confidence = max(0.0, min(1.0, quirk.confidence + confidence_change))
            
            # Apply updates if significant changes
            if abs(new_strength - old_strength) > 0.01 or abs(new_confidence - quirk.confidence) > 0.01:
                await self.db.update_quirk_metrics(
                    quirk.id, new_strength, new_confidence
                )
                quirks_updated += 1
            
            # Deactivate very weak quirks
            if new_strength < 0.05:
                await self.db.deactivate_quirk(quirk.id)
        
        return quirks_updated

    async def detect_conversation_patterns(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Detect recurring patterns in conversation style, timing, and content.
        """
        # Get conversation data from the last 14 days
        interactions = await self.db.get_user_interactions(user_id, days=14)
        
        if len(interactions) < 10:
            return []
        
        # Simple pattern detection based on time of day
        hourly_counts = [0] * 24
        for interaction in interactions:
            hour = interaction.timestamp.hour
            hourly_counts[hour] += 1
        
        # Find peak hours (most active times)
        max_count = max(hourly_counts) if hourly_counts else 1
        peak_hours = [i for i, count in enumerate(hourly_counts) if count > max_count * 0.7]
        
        patterns = []
        if peak_hours:
            patterns.append({
                "type": "temporal_preference",
                "description": f"User most active during hours: {', '.join(map(str, peak_hours))}",
                "confidence": min(1.0, len(peak_hours) / 5.0)
            })
        
        # Proactive conversation pattern
        proactive_count = sum(1 for i in interactions if i.is_proactive)
        proactive_ratio = proactive_count / len(interactions) if interactions else 0
        
        if proactive_ratio > 0.3:
            patterns.append({
                "type": "proactive_engagement",
                "description": f"User responds well to proactive conversations ({proactive_ratio:.1%})",
                "confidence": proactive_ratio
            })
        
        return patterns

    async def _apply_pad_baseline_drift(self, user_id: str, behavioral_analysis: BehavioralAnalysis) -> bool:
        """
        Apply PAD baseline drift based on recent emotional patterns.
        """
        try:
            # Get all user interactions from last 7 days
            recent_interactions = await self.db.get_user_interactions(user_id, days=7)
            
            if len(recent_interactions) < 5:  # Need minimum data
                return False
            
            # Calculate average PAD state from interactions
            total_pleasure = sum(i.pad_after.pleasure for i in recent_interactions if i.pad_after)
            total_arousal = sum(i.pad_after.arousal for i in recent_interactions if i.pad_after)
            total_dominance = sum(i.pad_after.dominance for i in recent_interactions if i.pad_after)
            
            count = len([i for i in recent_interactions if i.pad_after])
            if count == 0:
                return False
            
            average_interaction_pad = PADState(
                pleasure=total_pleasure / count,
                arousal=total_arousal / count,
                dominance=total_dominance / count
            )
            
            # Apply drift formula: 0.01 = 1% maximum change per day
            drift_rate = 0.01
            current_baseline = await self.personality.get_pad_baseline(user_id)
            
            if not current_baseline:
                # Initialize baseline if it doesn't exist
                await self.personality.set_pad_baseline(user_id, average_interaction_pad)
                return True
            
            new_baseline = PADState(
                pleasure=current_baseline.pleasure + (average_interaction_pad.pleasure - current_baseline.pleasure) * drift_rate,
                arousal=current_baseline.arousal + (average_interaction_pad.arousal - current_baseline.arousal) * drift_rate,
                dominance=current_baseline.dominance + (average_interaction_pad.dominance - current_baseline.dominance) * drift_rate
            )
            
            # Clamp to valid ranges (-1.0 to 1.0)
            new_baseline.pleasure = max(-1.0, min(1.0, new_baseline.pleasure))
            new_baseline.arousal = max(-1.0, min(1.0, new_baseline.arousal))
            new_baseline.dominance = max(-1.0, min(1.0, new_baseline.dominance))
            
            # Update baseline
            await self.personality.set_pad_baseline(user_id, new_baseline)
            return True
            
        except Exception as e:
            logger.error(f"PAD baseline drift failed for user {user_id}: {str(e)}", exc_info=True)
            return False

    async def _update_psychological_needs(self, user_id: str, behavioral_analysis: BehavioralAnalysis) -> int:
        """
        Update psychological needs based on satisfaction patterns.
        Returns number of needs updated.
        """
        needs = await self.db.get_user_needs(user_id)
        if not needs:
            return 0
        
        needs_updated = 0
        
        for need in needs:
            # Simple need update logic based on recent interactions
            # In a real implementation, this would be more sophisticated
            old_level = need.current_level
            
            # Adjust need level based on behavioral analysis
            if behavioral_analysis.emotional_volatility > 0.3:
                # High volatility might indicate unmet needs
                need.current_level = min(1.0, need.current_level + 0.05)
            else:
                # Stable emotions might indicate satisfied needs
                need.current_level = max(0.0, need.current_level - 0.02)
            
            # Update if significant change
            if abs(need.current_level - old_level) > 0.01:
                await self.db.update_user_need_level(user_id, need.need_type, need.current_level)
                needs_updated += 1
        
        return needs_updated

    def _calculate_quirk_confidence_change(self, quirk: Quirk, recent_reinforcements: int) -> float:
        """
        Calculate confidence change for a quirk based on recent reinforcements.
        """
        if recent_reinforcements > 0:
            # Increase confidence with positive reinforcement
            return min(0.1, recent_reinforcements * 0.01)
        else:
            # Decrease confidence without reinforcement
            return -0.02

    def _calculate_temporal_span(self, memories: List[EpisodicMemory]) -> timedelta:
        """
        Calculate the time span covered by a list of memories.
        """
        if not memories:
            return timedelta()
        
        timestamps = [m.created_at for m in memories if m.created_at]
        if not timestamps:
            return timedelta()
        
        return max(timestamps) - min(timestamps)
