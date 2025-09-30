"""
Nightly reflection agent for the AI Companion System.
Handles memory consolidation, personality evolution, and behavioral pattern analysis.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import logging

from ..models.memory import Memory, MemoryTheme, ConsolidationResult
from ..models.personality import (
    PersonalitySnapshot, PADState, Quirk, QuirkEvolutionResult, 
    PersonalityEvolutionResult, PsychologicalNeed
)
from ..models.interaction import InteractionRecord


class MemoryTheme:
    """Represents a thematic cluster of related memories"""
    def __init__(self, theme_name: str, description: str, confidence: float, 
                 related_memories: List[Memory], temporal_span: timedelta, 
                 importance_score: float):
        self.theme_name = theme_name
        self.description = description
        self.confidence = confidence
        self.related_memories = related_memories
        self.temporal_span = temporal_span
        self.importance_score = importance_score


class BehavioralAnalysis:
    """Analysis of behavioral changes over a reflection period"""
    def __init__(self, user_id: str, status: str = "normal", **kwargs):
        self.user_id = user_id
        self.status = status
        self.analysis_period_days = kwargs.get('analysis_period_days', 7)
        self.interaction_count = kwargs.get('interaction_count', 0)
        self.detected_changes = kwargs.get('detected_changes', [])
        self.change_confidence = kwargs.get('change_confidence', 0.0)
        self.quantitative_metrics = kwargs.get('quantitative_metrics', {})
        self.emotional_stability = kwargs.get('emotional_stability', 0.0)
        self.communication_evolution = kwargs.get('communication_evolution', {})


class QuirkUpdate:
    """Represents an update to a user quirk"""
    def __init__(self, quirk_id: str, quirk_name: str, **kwargs):
        self.quirk_id = quirk_id
        self.quirk_name = quirk_name
        self.old_strength = kwargs.get('old_strength', 0.0)
        self.new_strength = kwargs.get('new_strength', 0.0)
        self.old_confidence = kwargs.get('old_confidence', 0.0)
        self.new_confidence = kwargs.get('new_confidence', 0.0)
        self.reinforcement_count = kwargs.get('reinforcement_count', 0)
        self.action = kwargs.get('action', 'update')
        self.reason = kwargs.get('reason', '')


class EmotionalTrendAnalysis:
    """Analysis of emotional state trends over time"""
    def __init__(self, user_id: str, **kwargs):
        self.user_id = user_id
        self.status = kwargs.get('status', 'normal')
        self.analysis_period_days = kwargs.get('analysis_period_days', 14)
        self.data_points = kwargs.get('data_points', 0)
        self.pleasure_trend = kwargs.get('pleasure_trend', 0.0)
        self.arousal_trend = kwargs.get('arousal_trend', 0.0)
        self.dominance_trend = kwargs.get('dominance_trend', 0.0)
        self.emotional_volatility = kwargs.get('emotional_volatility', 0.0)
        self.detected_cycles = kwargs.get('detected_cycles', [])
        self.ai_insights = kwargs.get('ai_insights', [])
        self.stability_score = kwargs.get('stability_score', 0.0)
        self.trend_confidence = kwargs.get('trend_confidence', 0.0)


class ConversationPattern:
    """Represents a recurring pattern in conversations"""
    def __init__(self, **kwargs):
        self.pattern_type = kwargs.get('pattern_type', '')
        self.description = kwargs.get('description', '')
        self.confidence = kwargs.get('confidence', 0.0)
        self.frequency = kwargs.get('frequency', 0.0)
        self.first_observed = kwargs.get('first_observed', None)
        self.strength = kwargs.get('strength', 0.0)
        self.metadata = kwargs.get('metadata', {})


class ReflectionReport:
    """Complete report of the reflection process"""
    def __init__(self, **kwargs):
        self.start_time = kwargs.get('start_time', datetime.utcnow())
        self.end_time = kwargs.get('end_time', None)
        self.total_duration = kwargs.get('total_duration', 0)
        self.system_insights = kwargs.get('system_insights', [])
        self.errors = kwargs.get('errors', [])
        self.summary_stats = kwargs.get('summary_stats', {})

    def add_batch_result(self, batch_num: int, total_users: int, successful_users: int, duration: float):
        """Add batch processing results to the report"""
        if not hasattr(self, 'batch_results'):
            self.batch_results = []
        self.batch_results.append({
            'batch_num': batch_num,
            'total_users': total_users,
            'successful_users': successful_users,
            'duration': duration
        })

    def add_error(self, error_msg: str):
        """Add an error to the report"""
        self.errors.append(error_msg)


class UserReflectionResult:
    """Result of reflection process for a single user"""
    def __init__(self, user_id: str, **kwargs):
        self.user_id = user_id
        self.start_time = kwargs.get('start_time', datetime.utcnow())
        self.end_time = kwargs.get('end_time', None)
        self.duration = kwargs.get('duration', 0)
        self.success = kwargs.get('success', False)
        self.error_message = kwargs.get('error_message', '')
        self.consolidation_result = kwargs.get('consolidation_result', None)
        self.personality_evolution = kwargs.get('personality_evolution', None)
        self.detected_patterns = kwargs.get('detected_patterns', [])
        self.emotional_trends = kwargs.get('emotional_trends', None)
        self.needs_analysis = kwargs.get('needs_analysis', None)
        self.insights = kwargs.get('insights', [])


class ReflectionAgent:
    """Manages nightly reflection process for personality evolution and memory consolidation."""
    
    def __init__(self, memory_manager, personality_engine, groq_client, db_manager):
        self.memory = memory_manager
        self.personality = personality_engine
        self.groq = groq_client
        self.db = db_manager

        # Reflection processing limits
        self.max_users_per_batch = 50
        self.max_memories_per_consolidation = 20
        self.consolidation_similarity_threshold = 0.7
        self.min_memories_for_insight = 5

    async def run_nightly_reflection(self) -> ReflectionReport:
        """
        Main nightly reflection process for all active users
        Runs daily at 3:00 AM server time, processes users in batches
        """
        start_time = datetime.utcnow()
        report = ReflectionReport(start_time=start_time)

        try:
            # Get all active users (activity within last 7 days)
            active_users = await self.db.get_active_users_for_reflection(days=7)

            # Process users in batches to avoid overwhelming the system
            user_batches = [active_users[i:i + self.max_users_per_batch]
                           for i in range(0, len(active_users), self.max_users_per_batch)]

            for batch_num, user_batch in enumerate(user_batches):
                batch_start = datetime.utcnow()
                batch_results = []

                # Process users in parallel within batch
                tasks = [self.process_user_reflection(user_id) for user_id in user_batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log batch completion
                batch_duration = (datetime.utcnow() - batch_start).total_seconds()
                successful_users = [r for r in batch_results if not isinstance(r, Exception)]

                report.add_batch_result(batch_num, len(user_batch), len(successful_users), batch_duration)

                # Brief pause between batches to avoid system overload
                if batch_num < len(user_batches) - 1:
                    await asyncio.sleep(30)

            # Generate system-wide insights
            report.system_insights = await self._generate_system_insights(report)

        except Exception as e:
            report.add_error(f"Reflection process failed: {str(e)}")
            logging.error(f"Nightly reflection failed: {e}")

        finally:
            report.end_time = datetime.utcnow()
            report.total_duration = (report.end_time - report.start_time).total_seconds()
            await self.db.store_reflection_report(report)

        return report

    async def process_user_reflection(self, user_id: str) -> UserReflectionResult:
        """
        Complete reflection process for a single user
        Includes memory consolidation, personality evolution, and pattern analysis
        """
        result = UserReflectionResult(user_id=user_id, start_time=datetime.utcnow())

        try:
            # 1. Memory Consolidation
            consolidation_result = await self.consolidate_user_memories(user_id)
            result.consolidation_result = consolidation_result

            # 2. Personality Evolution
            personality_result = await self.evolve_user_personality(user_id)
            result.personality_evolution = personality_result

            # 3. Pattern Analysis and Insights
            patterns = await self.detect_conversation_patterns(user_id)
            emotional_trends = await self.analyze_emotional_trends(user_id)
            needs_analysis = await self.identify_needs_satisfaction_patterns(user_id)

            result.detected_patterns = patterns
            result.emotional_trends = emotional_trends
            result.needs_analysis = needs_analysis

            # 4. Generate User Insights
            insights = await self.generate_user_insights(user_id, result)
            result.insights = insights

            # 5. Update User Statistics
            await self._update_user_reflection_stats(user_id, result)

            result.success = True

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logging.error(f"User reflection failed for {user_id}: {e}")
            await self.db.log_reflection_error(user_id, str(e))

        finally:
            result.end_time = datetime.utcnow()
            result.duration = (result.end_time - result.start_time).total_seconds()

        return result

    async def consolidate_user_memories(self, user_id: str) -> ConsolidationResult:
        """
        Advanced memory consolidation using AI-driven thematic analysis
        Converts episodic memories into structured semantic knowledge
        """
        result = ConsolidationResult(user_id=user_id)

        # Get unconsolidated episodic memories from last 24 hours
        recent_memories = await self.memory.get_unconsolidated_memories(
            user_id=user_id,
            hours=24,
            memory_type="episodic"
        )

        if len(recent_memories) < self.min_memories_for_insight:
            result.status = "insufficient_data"
            return result

        # Identify thematic clusters in memories
        memory_themes = await self.identify_memory_themes(user_id, recent_memories)
        result.identified_themes = memory_themes

        # Consolidate each theme into semantic memories
        consolidated_memories = []
        for theme in memory_themes:
            if len(theme.related_memories) >= 3:  # Minimum for consolidation
                try:
                    semantic_memory = await self._consolidate_theme_to_semantic(user_id, theme)
                    consolidated_memories.append(semantic_memory)

                    # Mark source memories as consolidated
                    for memory in theme.related_memories:
                        await self.db.mark_memory_consolidated(user_id, memory.id, semantic_memory.id)

                except Exception as e:
                    result.add_consolidation_error(theme.theme_name, str(e))

        result.consolidated_memories = consolidated_memories
        result.consolidation_count = len(consolidated_memories)

        # Generate insights from consolidated patterns
        if consolidated_memories:
            insights = await self.generate_insights_from_patterns(user_id, memory_themes)
            result.generated_insights = insights

        return result

    async def identify_memory_themes(self, user_id: str, memories: List[Memory]) -> List[MemoryTheme]:
        """
        Use AI to identify thematic clusters in episodic memories
        Groups related memories by semantic similarity and temporal patterns
        """
        if len(memories) < 3:
            return []

        # Use Groq for thematic analysis
        memory_contents = [memory.content for memory in memories]

        prompt = f"""
        Analyze the following list of memories from a user. Identify up to 5 thematic clusters.
        A theme requires at least 3 related memories. For each theme, provide a name, a brief description,
        a confidence score (0.0-1.0), an importance score (0.0-1.0), and the indices of the memories that belong to it.

        Memories (indexed):
        {chr(10).join([f'{i}: {mem.content}' for i, mem in enumerate(memories)])}

        Respond in JSON format:
        {{
          "identified_themes": [
            {{
              "theme_name": "string",
              "description": "string",
              "confidence": float,
              "importance_score": float,
              "memory_indices": [int]
            }}
          ]
        }}
        """
        
        thematic_analysis_data = await self.groq.analyze_json_response(prompt, max_tokens=1500)
        
        themes = []
        for theme_data in thematic_analysis_data.get("identified_themes", []):
            # Map memories to theme
            theme_memories = [memories[i] for i in theme_data.get("memory_indices", []) if i < len(memories)]
            
            theme = MemoryTheme(
                theme_name=theme_data.get("theme_name"),
                description=theme_data.get("description"),
                confidence=theme_data.get("confidence"),
                related_memories=theme_memories,
                temporal_span=self._calculate_temporal_span(theme_memories),
                importance_score=theme_data.get("importance_score")
            )
            themes.append(theme)

        # Sort themes by importance and confidence
        themes.sort(key=lambda t: t.importance_score * t.confidence, reverse=True)
        return themes

    def _calculate_temporal_span(self, memories: List[Memory]) -> timedelta:
        """Calculate the temporal span of a group of memories"""
        if not memories:
            return timedelta(0)
        
        timestamps = [m.created_at for m in memories if m.created_at]
        if not timestamps:
            return timedelta(0)
        
        return max(timestamps) - min(timestamps)

    async def _consolidate_theme_to_semantic(self, user_id: str, theme: MemoryTheme) -> Memory:
        """
        Convert a thematic cluster of episodic memories into a single semantic memory
        """
        # Generate consolidated content using AI
        prompt = f"""
        Consolidate the following related memories into a single, insightful semantic memory.
        The new memory should capture the core pattern, preference, or fact, abstracting away from specific events.

        Theme Description: {theme.description}
        Related Memories:
        {chr(10).join([f'- {m.content}' for m in theme.related_memories])}

        Respond with ONLY the consolidated semantic memory content as a single string.
        """
        
        consolidated_content = await self.groq.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )

        # Calculate consolidated importance score
        total_importance = sum(m.importance_score for m in theme.related_memories)
        avg_importance = total_importance / len(theme.related_memories)
        # Boost importance for consolidated memories
        final_importance = min(1.0, avg_importance * 1.3)

        # Create and store semantic memory
        semantic_memory_id = await self.memory.store_memory(
            user_id=user_id,
            content=consolidated_content,
            memory_type="semantic",
            importance_score=final_importance,
            metadata={
                "source_theme": theme.theme_name,
                "source_memory_count": len(theme.related_memories),
                "consolidation_date": datetime.utcnow().isoformat(),
                "temporal_span_days": theme.temporal_span.days
            }
        )

        return await self.memory.get_memory_by_id(user_id, semantic_memory_id)

    def _build_theme_consolidation_prompt(self, theme: MemoryTheme) -> str:
        """Build a prompt for consolidating a thematic cluster of memories"""
        return f"Consolidate these related memories into a single semantic memory: {theme.description}. Related memories: {'; '.join([m.content for m in theme.related_memories])}"

    async def evolve_user_personality(self, user_id: str) -> PersonalityEvolutionResult:
        """
        Analyze and apply personality evolution based on recent behavioral patterns
        Updates PAD baseline drift and quirk strengths
        """
        result = PersonalityEvolutionResult(user_id=user_id)

        # Get current personality state
        current_personality = await self.personality.get_current_pad_state(user_id)
        if not current_personality:
            result.status = "no_personality_data"
            return result

        # Analyze behavioral changes over the reflection period
        behavioral_analysis = await self.analyze_behavioral_changes(user_id)
        result.behavioral_analysis = behavioral_analysis

        # Apply PAD baseline drift based on recent emotional patterns
        drift_result = await self._apply_pad_baseline_drift(user_id, behavioral_analysis)
        result.pad_drift_applied = drift_result

        # Evolve quirks based on usage patterns
        quirk_evolution = await self.update_quirk_strengths(user_id)
        result.quirk_evolution = quirk_evolution

        # Update psychological needs based on satisfaction patterns
        needs_update = await self._update_psychological_needs(user_id, behavioral_analysis)
        result.needs_update = needs_update

        # Calculate personality stability metrics
        stability_metrics = await self._calculate_personality_stability(user_id, current_personality)
        result.stability_metrics = stability_metrics

        return result

    async def analyze_behavioral_changes(self, user_id: str) -> BehavioralAnalysis:
        """
        Deep analysis of behavioral changes over the reflection period
        Uses AI to identify shifts in communication patterns, interests, and emotional responses
        """
        # Get interactions from the last 7 days for trend analysis
        recent_interactions = await self.db.get_user_interactions(user_id, days=7)

        if len(recent_interactions) < 5:
            return BehavioralAnalysis(user_id=user_id, status="insufficient_data")

        # Analyze with AI for behavioral patterns
        behavioral_analysis = await self.groq.analyze_behavioral_changes(
            interactions=[{
                "content": i.user_message,
                "response": i.agent_response,
                "timestamp": i.timestamp.isoformat(),
                "pad_before": i.pad_before,
                "pad_after": i.pad_after,
                "emotion_before": i.emotion_before,
                "emotion_after": i.emotion_after
            } for i in recent_interactions],
            analysis_focus=[
                "communication_style_changes",
                "emotional_pattern_shifts",
                "interest_topic_evolution",
                "interaction_frequency_patterns",
                "response_length_changes"
            ]
        )

        # Calculate quantitative metrics
        metrics = self._calculate_behavioral_metrics(recent_interactions)

        return BehavioralAnalysis(
            user_id=user_id,
            analysis_period_days=7,
            interaction_count=len(recent_interactions),
            detected_changes=behavioral_analysis.detected_changes,
            change_confidence=behavioral_analysis.confidence,
            quantitative_metrics=metrics,
            emotional_stability=self._calculate_emotional_stability(recent_interactions),
            communication_evolution=behavioral_analysis.communication_evolution
        )

    def _calculate_behavioral_metrics(self, interactions: List[InteractionRecord]) -> Dict[str, Any]:
        """Calculate quantitative behavioral metrics from interactions"""
        if not interactions:
            return {}
        
        # Calculate average response length
        user_message_lengths = [len(i.user_message) for i in interactions]
        agent_response_lengths = [len(i.agent_response) for i in interactions]
        
        # Calculate timing patterns
        time_gaps = []
        for i in range(1, len(interactions)):
            gap = (interactions[i].timestamp - interactions[i-1].timestamp).total_seconds()
            time_gaps.append(gap)
        
        return {
            'avg_user_message_length': sum(user_message_lengths) / len(user_message_lengths) if user_message_lengths else 0,
            'avg_agent_response_length': sum(agent_response_lengths) / len(agent_response_lengths) if agent_response_lengths else 0,
            'avg_time_between_interactions_minutes': sum(time_gaps) / len(time_gaps) / 60 if time_gaps else 0,
            'total_interactions': len(interactions)
        }

    def _calculate_emotional_stability(self, interactions: List[InteractionRecord]) -> float:
        """Calculate emotional stability based on PAD state fluctuations"""
        if len(interactions) < 2:
            return 0.5  # Neutral stability for insufficient data
        
        # Calculate variance in emotional states
        pleasure_values = [i.pad_after['pleasure'] if isinstance(i.pad_after, dict) else i.pad_after.pleasure 
                          for i in interactions if i.pad_after]
        arousal_values = [i.pad_after['arousal'] if isinstance(i.pad_after, dict) else i.pad_after.arousal 
                         for i in interactions if i.pad_after]
        dominance_values = [i.pad_after['dominance'] if isinstance(i.pad_after, dict) else i.pad_after.dominance 
                           for i in interactions if i.pad_after]
        
        if not pleasure_values:
            return 0.5
        
        # Calculate standard deviation as inverse of stability
        def calculate_stability(values):
            if len(values) < 2:
                return 0.5
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            # Convert variance to stability (0-1 scale, where 1 = very stable)
            return max(0.0, min(1.0, 1.0 - min(0.9, variance * 2)))
        
        pleasure_stability = calculate_stability(pleasure_values)
        arousal_stability = calculate_stability(arousal_values)
        dominance_stability = calculate_stability(dominance_values)
        
        # Average the three dimensions
        return (pleasure_stability + arousal_stability + dominance_stability) / 3

    async def update_quirk_strengths(self, user_id: str) -> QuirkEvolutionResult:
        """
        Update quirk strengths based on recent usage and reinforcement patterns
        """
        result = QuirkEvolutionResult(user_id=user_id)

        active_quirks = await self.db.get_active_quirks(user_id)
        if not active_quirks:
            result.status = "no_quirks"
            return result

        quirk_updates = []

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

                quirk_updates.append(QuirkUpdate(
                    quirk_id=quirk.id,
                    quirk_name=quirk.name,
                    old_strength=old_strength,
                    new_strength=new_strength,
                    old_confidence=quirk.confidence,
                    new_confidence=new_confidence,
                    reinforcement_count=recent_reinforcements
                ))

            # Deactivate very weak quirks
            if new_strength < 0.05:
                await self.db.deactivate_quirk(quirk.id)
                quirk_updates.append(QuirkUpdate(
                    quirk_id=quirk.id,
                    quirk_name=quirk.name,
                    action="deactivated",
                    reason="strength_too_low"
                ))

        result.quirk_updates = quirk_updates
        result.total_quirks_processed = len(active_quirks)
        result.quirks_strengthened = len([u for u in quirk_updates if u.new_strength > u.old_strength])
        result.quirks_weakened = len([u for u in quirk_updates if u.new_strength < u.old_strength])

        return result

    def _calculate_quirk_confidence_change(self, quirk: Quirk, reinforcement_count: int) -> float:
        """Calculate how to update quirk confidence based on recent reinforcements"""
        if reinforcement_count > 0:
            # Increase confidence with positive reinforcement
            return 0.02 * reinforcement_count  # Small positive boost
        else:
            # Decrease confidence for lack of reinforcement
            return -0.01  # Small negative adjustment

    async def _apply_pad_baseline_drift(self, user_id: str, behavioral_analysis: BehavioralAnalysis) -> Dict[str, float]:
        """
        Apply PAD baseline drift based on recent emotional patterns
        Uses the formula: new_baseline = current_baseline + (average_interaction_pad - current_baseline) * 0.01
        """
        # Get all user interactions from last 7 days
        recent_interactions = await self.db.get_user_interactions(user_id, days=7)

        if len(recent_interactions) < 5:  # Need minimum data
            return {}

        # Calculate average PAD state from interactions
        total_pleasure = sum(i.pad_after['pleasure'] if isinstance(i.pad_after, dict) else i.pad_after.pleasure 
                            for i in recent_interactions if i.pad_after)
        total_arousal = sum(i.pad_after['arousal'] if isinstance(i.pad_after, dict) else i.pad_after.arousal 
                           for i in recent_interactions if i.pad_after)
        total_dominance = sum(i.pad_after['dominance'] if isinstance(i.pad_after, dict) else i.pad_after.dominance 
                             for i in recent_interactions if i.pad_after)

        count = len(recent_interactions)
        average_interaction_pad = PADState(
            pleasure=total_pleasure / count,
            arousal=total_arousal / count,
            dominance=total_dominance / count
        )

        # Get current baseline from personality engine
        current_baseline = await self.personality.get_current_pad_baseline(user_id)

        # Apply drift formula: 0.01 = 1% maximum change per day
        drift_rate = 0.01
        new_baseline = PADState(
            pleasure=current_baseline.pleasure + (average_interaction_pad.pleasure - current_baseline.pleasure) * drift_rate,
            arousal=current_baseline.arousal + (average_interaction_pad.arousal - current_baseline.arousal) * drift_rate,
            dominance=current_baseline.dominance + (average_interaction_pad.dominance - current_baseline.dominance) * drift_rate
        )

        # Clamp to valid ranges (-1.0 to 1.0)
        new_baseline.pleasure = max(-1.0, min(1.0, new_baseline.pleasure))
        new_baseline.arousal = max(-1.0, min(1.0, new_baseline.arousal))
        new_baseline.dominance = max(-1.0, min(1.0, new_baseline.dominance))

        # Update the baseline in personality engine
        await self.personality.update_pad_baseline(user_id, new_baseline)

        return {
            "old_pleasure": current_baseline.pleasure,
            "old_arousal": current_baseline.arousal,
            "old_dominance": current_baseline.dominance,
            "new_pleasure": new_baseline.pleasure,
            "new_arousal": new_baseline.arousal,
            "new_dominance": new_baseline.dominance
        }

    async def _update_psychological_needs(self, user_id: str, behavioral_analysis: BehavioralAnalysis) -> Dict[str, Any]:
        """Update psychological needs based on satisfaction patterns"""
        needs = await self.db.get_user_needs(user_id)
        updates = []
        
        for need in needs:
            # Adjust the need level based on interaction patterns
            # If the need was satisfied in recent interactions, decrease its current level
            satisfaction_events = [i for i in behavioral_analysis.detected_changes 
                                 if f"{need.need_type}_satisfaction" in i.get('type', '')]
            
            if satisfaction_events:
                # Lower the current level based on satisfaction
                new_level = max(need.baseline_level, need.current_level - need.satisfaction_rate)
                await self.db.update_need_level(user_id, need.need_type, new_level)
                updates.append({
                    "need_type": need.need_type,
                    "old_level": need.current_level,
                    "new_level": new_level,
                    "satisfaction_event_count": len(satisfaction_events)
                })
        
        return {
            "need_updates": updates,
            "total_needs_updated": len(updates)
        }

    async def _calculate_personality_stability(self, user_id: str, current_personality: PADState) -> Dict[str, float]:
        """Calculate personality stability metrics"""
        # Get historical personality data
        historical_data = await self.db.get_pad_state_history(user_id, days=30)
        
        if len(historical_data) < 2:
            return {"stability_score": 0.5, "volatility_pleasure": 0.0, "volatility_arousal": 0.0, "volatility_dominance": 0.0}
        
        # Calculate volatility (standard deviation)
        pleasure_values = [state.pleasure for state in historical_data]
        arousal_values = [state.arousal for state in historical_data]
        dominance_values = [state.dominance for state in historical_data]
        
        def calculate_volatility(values):
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            return variance ** 0.5  # Standard deviation
        
        pleasure_volatility = calculate_volatility(pleasure_values)
        arousal_volatility = calculate_volatility(arousal_values)
        dominance_volatility = calculate_volatility(dominance_values)
        
        # Calculate stability as inverse of volatility (with max limits)
        stability_score = 1.0 - min(0.8, (pleasure_volatility + arousal_volatility + dominance_volatility) / 3)
        
        return {
            "stability_score": max(0.0, min(1.0, stability_score)),
            "volatility_pleasure": pleasure_volatility,
            "volatility_arousal": arousal_volatility,
            "volatility_dominance": dominance_volatility
        }

    async def detect_conversation_patterns(self, user_id: str) -> List[ConversationPattern]:
        """
        Detect recurring patterns in conversation style, timing, and content
        """
        # Get conversation data from the last 14 days
        interactions = await self.db.get_user_interactions(user_id, days=14)

        if len(interactions) < 10:
            return []

        # Analyze patterns using AI
        pattern_analysis = await self.groq.detect_conversation_patterns(
            interactions=[{
                "timestamp": i.timestamp.isoformat(),
                "user_message_length": len(i.user_message),
                "agent_response_length": len(i.agent_response),
                "conversation_length": i.conversation_length,
                "is_proactive": i.is_proactive,
                "session_id": i.session_id,
                "time_of_day": i.timestamp.hour,
                "day_of_week": i.timestamp.weekday()
            } for i in interactions],
            pattern_types=[
                "temporal_patterns",      # When user prefers to chat
                "length_preferences",     # Short vs long conversations
                "topic_cycling",          # Recurring topics or themes
                "initiation_patterns",    # Who starts conversations
                "response_timing",        # How quickly user responds
                "emotional_cycles"        # Emotional state patterns
            ]
        )

        detected_patterns = []
        for pattern_data in pattern_analysis.patterns:
            pattern = ConversationPattern(
                pattern_type=pattern_data.pattern_type,
                description=pattern_data.description,
                confidence=pattern_data.confidence,
                frequency=pattern_data.frequency,
                first_observed=self._find_pattern_start_date(interactions, pattern_data),
                strength=pattern_data.strength,
                metadata=pattern_data.metadata
            )
            detected_patterns.append(pattern)

        # Filter patterns by confidence threshold
        significant_patterns = [p for p in detected_patterns if p.confidence > 0.6]

        # Store patterns for future reference
        for pattern in significant_patterns:
            await self.db.store_conversation_pattern(user_id, pattern)

        return significant_patterns

    def _find_pattern_start_date(self, interactions: List[InteractionRecord], pattern_data: Any) -> Optional[datetime]:
        """Find the first date a pattern was observed in interactions"""
        # This would be implemented based on the pattern matching algorithm
        if interactions:
            return interactions[0].timestamp  # Simplified implementation
        return None

    async def analyze_emotional_trends(self, user_id: str) -> EmotionalTrendAnalysis:
        """
        Analyze emotional state trends and patterns over time
        """
        # Get PAD state history over the last 14 days
        emotion_history = await self.db.get_pad_state_history(user_id, days=14)

        if len(emotion_history) < 5:
            return EmotionalTrendAnalysis(user_id=user_id, status="insufficient_data")

        # Calculate trend metrics
        pleasure_values = [e.pleasure for e in emotion_history]
        arousal_values = [e.arousal for e in emotion_history]
        dominance_values = [e.dominance for e in emotion_history]
        
        pleasure_trend = self._calculate_emotional_trend(pleasure_values)
        arousal_trend = self._calculate_emotional_trend(arousal_values)
        dominance_trend = self._calculate_emotional_trend(dominance_values)

        # Identify emotional volatility
        volatility = self._calculate_emotional_volatility(emotion_history)

        # Detect emotional cycles (daily, weekly patterns)
        cycles = await self._detect_emotional_cycles(emotion_history)

        # Generate insights about emotional patterns
        insights = await self.groq.analyze_emotional_patterns(
            emotion_data=[{
                "timestamp": e.timestamp.isoformat(),
                "pleasure": e.pleasure,
                "arousal": e.arousal,
                "dominance": e.dominance,
                "emotion_label": e.emotion_label
            } for e in emotion_history],
            trend_analysis={
                "pleasure_trend": pleasure_trend,
                "arousal_trend": arousal_trend,
                "dominance_trend": dominance_trend,
                "volatility": volatility
            }
        )

        return EmotionalTrendAnalysis(
            user_id=user_id,
            analysis_period_days=14,
            data_points=len(emotion_history),
            pleasure_trend=pleasure_trend,
            arousal_trend=arousal_trend,
            dominance_trend=dominance_trend,
            emotional_volatility=volatility,
            detected_cycles=cycles,
            ai_insights=insights.insights,
            stability_score=insights.stability_score,
            trend_confidence=insights.confidence
        )

    def _calculate_emotional_trend(self, values: List[float]) -> float:
        """Calculate the trend direction of emotional values"""
        if len(values) < 2:
            return 0.0
        
        # Simple linear trend calculation (slope of the line)
        n = len(values)
        sum_x = sum(range(n))
        sum_y = sum(values)
        sum_xy = sum(i * v for i, v in enumerate(values))
        sum_x2 = sum(i * i for i in range(n))
        
        # Calculate slope of the trend line
        if n * sum_x2 - sum_x * sum_x != 0:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            # Normalize to [-1, 1] range
            return max(-1.0, min(1.0, slope * 10))  # Scale factor to make it meaningful
        return 0.0

    def _calculate_emotional_volatility(self, emotion_history: List[PADState]) -> float:
        """Calculate emotional volatility based on PAD state fluctuations"""
        if len(emotion_history) < 2:
            return 0.0
        
        # Calculate standard deviation across all dimensions
        pleasure_values = [e.pleasure for e in emotion_history]
        arousal_values = [e.arousal for e in emotion_history]
        dominance_values = [e.dominance for e in emotion_history]
        
        def calculate_std_dev(values):
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            return variance ** 0.5
        
        pleasure_std = calculate_std_dev(pleasure_values)
        arousal_std = calculate_std_dev(arousal_values)
        dominance_std = calculate_std_dev(dominance_values)
        
        # Average the standard deviations
        return (pleasure_std + arousal_std + dominance_std) / 3

    async def _detect_emotional_cycles(self, emotion_history: List[PADState]) -> List[Dict[str, Any]]:
        """Detect cyclical patterns in emotional states"""
        # For now, return a placeholder - this would be implemented as a more complex algorithm
        # that can detect daily, weekly, or other periodic patterns in emotional data
        return []

    async def identify_needs_satisfaction_patterns(self, user_id: str) -> Dict[str, Any]:
        """Identify patterns in how psychological needs are satisfied"""
        # Get recent interactions and user needs
        interactions = await self.db.get_user_interactions(user_id, days=7)
        needs = await self.db.get_user_needs(user_id)
        
        patterns = {
            'needs_awareness': [],
            'satisfaction_events': [],
            'pattern_insights': []
        }
        
        for need in needs:
            # Find interactions where this need was likely satisfied
            # This would be based on content analysis and contextual understanding
            satisfaction_interactions = [
                i for i in interactions 
                if any(term in i.user_message.lower() for term in [need.need_type.lower()])
            ]
            
            patterns['needs_awareness'].append({
                'need_type': need.need_type,
                'current_level': need.current_level,
                'satisfaction_interactions_count': len(satisfaction_interactions)
            })
        
        return patterns

    async def generate_user_insights(self, user_id: str, result: UserReflectionResult) -> List[str]:
        """Generate insights about the user based on the reflection results"""
        insights = []
        
        # Add insights based on consolidation results
        if result.consolidation_result and result.consolidation_result.consolidated_memories:
            insights.append(f"Memory consolidation created {len(result.consolidation_result.consolidated_memories)} new semantic memories")
        
        # Add insights based on personality evolution
        if result.personality_evolution:
            if result.personality_evolution.quirk_evolution:
                evolution = result.personality_evolution.quirk_evolution
                insights.append(f"Evolved {evolution.total_quirks_processed} quirks: {evolution.quirks_strengthened} strengthened, {evolution.quirks_weakened} weakened")
        
        # Add insights based on emotional trends
        if result.emotional_trends:
            trends = result.emotional_trends
            if trends.pleasure_trend > 0.1:
                insights.append("Noticed positive trend in user's pleasure state")
            elif trends.pleasure_trend < -0.1:
                insights.append("Noticed negative trend in user's pleasure state")
        
        return insights

    async def _update_user_reflection_stats(self, user_id: str, result: UserReflectionResult) -> None:
        """Update user statistics based on reflection results"""
        stats = {
            "last_reflection_run": result.end_time,
            "reflection_duration_seconds": result.duration,
            "consolidation_count": result.consolidation_result.consolidation_count if result.consolidation_result else 0,
            "quirk_updates_count": result.personality_evolution.quirk_evolution.total_quirks_processed if result.personality_evolution and result.personality_evolution.quirk_evolution else 0
        }
        
        await self.db.update_user_reflection_stats(user_id, stats)

    async def generate_insights_from_patterns(self, user_id: str, themes: List[MemoryTheme]) -> List[str]:
        """Generate insights from identified memory themes and patterns"""
        insights = []
        
        for theme in themes:
            if theme.confidence > 0.7:
                insights.append(f"Detected significant pattern: {theme.theme_name} (confidence: {theme.confidence:.2f})")
        
        return insights

    async def _generate_system_insights(self, report: ReflectionReport) -> List[str]:
        """Generate system-wide insights from the reflection report"""
        insights = []
        
        if hasattr(report, 'batch_results') and report.batch_results:
            total_users = sum(batch['total_users'] for batch in report.batch_results)
            successful_users = sum(batch['successful_users'] for batch in report.batch_results)
            success_rate = successful_users / total_users if total_users > 0 else 0
            
            insights.append(f"Reflection success rate: {success_rate:.1%} ({successful_users}/{total_users} users)")
            insights.append(f"Total reflection time: {report.total_duration:.1f}s")
        
        return insights
