"""
Proactive conversation manager for the AI Companion System.
Implements the multi-factor scoring algorithm for initiating conversations based on 
psychological needs urgency, timing optimization, and user interaction patterns.
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pytz

from ..models.personality import PADState, PersonalitySnapshot, PsychologicalNeed
from ..models.interaction import InteractionRecord
from ..services.personality_engine import PersonalityEngine
from ..services.memory_manager import MemoryManager
from ..services.user_service import UserService
from ..services.groq_client import GroqClient
from ..database import DatabaseManager


logger = logging.getLogger(__name__)


class ProactiveScore:
    """
    Container class for proactive scoring results.
    """
    def __init__(self, total_score: float, reason: str = "", **kwargs):
        self.total_score = total_score
        self.need_score = kwargs.get('need_score', 0.0)
        self.timing_score = kwargs.get('timing_score', 0.0)
        self.personality_factor = kwargs.get('personality_factor', 1.0)
        self.interaction_score = kwargs.get('interaction_score', 0.0)
        self.trigger_reason = kwargs.get('trigger_reason', "")
        self.should_initiate = total_score >= 0.6  # Default threshold
        self.reason = reason


class ProactiveManager:
    """
    Manages proactive conversation initiation based on multi-factor scoring.
    """
    
    def __init__(self, personality_engine: PersonalityEngine, memory_manager: MemoryManager, 
                 user_service: UserService, groq_client: GroqClient, db_manager: DatabaseManager):
        self.personality = personality_engine
        self.memory = memory_manager
        self.users = user_service
        self.groq = groq_client
        self.db = db_manager

        # Proactive conversation thresholds
        self.base_threshold = 0.6  # Minimum score to trigger conversation
        self.personality_weights = {
            'extraversion': 0.3,    # More extraverted = more proactive
            'openness': 0.2,        # More open = more curious conversations
            'agreeableness': 0.1,   # More agreeable = gentler approaches
            'conscientiousness': -0.1, # More conscientious = less interrupting
            'neuroticism': 0.15     # More neurotic = more need for reassurance
        }

    # @staticmethod
    # def get_instance():
    #     """Get the singleton instance of the ProactiveManager"""
    #     # This would be implemented properly in a real application
    #     # For now, return None to trigger dependency injection
    #     return None

    async def calculate_proactive_score(self, user_id: str) -> ProactiveScore:
        """
        Multi-factor proactive conversation scoring algorithm
        Score ranges from 0.0 (never initiate) to 1.0 (immediate initiation)
        """
        # Get user profile and current state
        user_profile = await self.users.get_user_profile(user_id)
        if not user_profile or not user_profile.proactive_messaging_enabled:
            return ProactiveScore(total_score=0.0, reason="disabled")

        # Calculate component scores
        need_score = await self.calculate_need_urgency_score(user_id)
        timing_score = await self.calculate_timing_score(user_id)
        personality_factor = await self.calculate_personality_factor(user_id)
        interaction_score = await self.calculate_interaction_pattern_score(user_id)

        # Weighted combination of factors
        base_score = (
            need_score * 0.4 +          # 40% - psychological needs urgency
            timing_score * 0.25 +       # 25% - optimal timing patterns
            interaction_score * 0.35    # 35% - recent interaction patterns
        )

        # Apply personality modifier (can boost or reduce score)
        final_score = base_score * personality_factor

        # Apply recent conversation penalty (avoid being annoying)
        recent_penalty = await self._calculate_recent_conversation_penalty(user_id)
        final_score *= max(0.1, 1 - recent_penalty) # Ensure score is at least 10% of original

        # Bounds checking
        final_score = max(0.0, min(1.0, final_score))

        # Determine primary trigger reason
        trigger_reason = self._determine_primary_trigger(need_score, timing_score, interaction_score)

        return ProactiveScore(
            total_score=final_score,
            need_score=need_score,
            timing_score=timing_score,
            personality_factor=personality_factor,
            interaction_score=interaction_score,
            trigger_reason=trigger_reason,
            should_initiate=final_score >= self.base_threshold
        )

    async def calculate_need_urgency_score(self, user_id: str) -> float:
        """
        Calculate urgency based on psychological needs that require satisfaction
        Uses weighted combination of all need types
        """
        needs = await self.db.get_user_needs(user_id)
        if not needs:
            return 0.0

        total_urgency = 0.0
        need_weights = {
            'social': 0.35,      # Highest weight - social connection most important
            'validation': 0.25,  # Need for positive reinforcement
            'intellectual': 0.20, # Curiosity and learning needs
            'creative': 0.15,    # Creative expression and inspiration
            'rest': 0.05         # Lowest weight - less likely to initiate for rest
        }

        for need in needs:
            if need.current_level >= need.trigger_threshold:
                # Calculate urgency based on how far above threshold
                excess = need.current_level - need.trigger_threshold
                max_excess = 1.0 - need.trigger_threshold
                urgency = (excess / max_excess) if max_excess > 0 else 1.0

                # Weight by need type and proactive weight
                weighted_urgency = urgency * need_weights.get(need.need_type, 0.1) * need.proactive_weight
                total_urgency += weighted_urgency

        return min(1.0, total_urgency)

    async def calculate_timing_score(self, user_id: str) -> float:
        """
        Calculate timing appropriateness based on user's historical patterns
        Higher scores for times when user is typically active and receptive
        """
        current_time = datetime.utcnow()
        user_profile = await self.users.get_user_profile(user_id)

        # Convert to user's timezone
        user_tz = pytz.timezone(user_profile.timezone)
        local_time = current_time.astimezone(user_tz)

        hour = local_time.hour
        day_of_week = local_time.weekday()

        # Get historical activity patterns
        activity_patterns = await self.db.get_user_activity_patterns(user_id)

        # Calculate base timing score based on historical activity
        hourly_activity = activity_patterns.get('hourly', {})
        hour_score = hourly_activity.get(str(hour), 0.5)  # Default to medium if no data

        # Day of week modifier
        weekly_activity = activity_patterns.get('weekly', {})
        day_score = weekly_activity.get(str(day_of_week), 0.5)

        # Combine hour and day scores
        base_timing = (hour_score * 0.7 + day_score * 0.3)

        # Apply time-since-last-seen penalty
        last_activity = await self.db.get_last_user_activity(user_id)
        if last_activity:
            # Ensure hours_since_activity is non-negative
            hours_since_activity = max(0, (current_time - last_activity).total_seconds() / 3600)

            # Optimal range: 4-24 hours since last activity
            if hours_since_activity < 4:
                time_penalty = (4 - hours_since_activity) / 4 * 0.5  # Up to 50% penalty
            elif hours_since_activity > 72:  # More than 3 days
                time_penalty = min(0.8, (hours_since_activity - 72) / 168 * 0.5)  # Gradual penalty
            else:
                time_penalty = 0.0  # Sweet spot

            base_timing *= (1 - time_penalty)

        return max(0.0, min(1.0, base_timing))

    async def calculate_personality_factor(self, user_id: str) -> float:
        """
        Calculate personality-based modifier for proactive tendencies
        Uses Big Five traits to adjust proactive score
        """
        # Extract Big Five traits from personality snapshot
        personality_snapshot = await self.personality.get_personality_snapshot(user_id)
        if not personality_snapshot:
            return 1.0  # Neutral if no personality data

        traits = {
            'extraversion': personality_snapshot.big_five.extraversion,
            'openness': personality_snapshot.big_five.openness,
            'agreeableness': personality_snapshot.big_five.agreeableness,
            'conscientiousness': personality_snapshot.big_five.conscientiousness,
            'neuroticism': personality_snapshot.big_five.neuroticism
        }

        # Calculate weighted personality factor
        personality_modifier = 1.0  # Start with neutral
        for trait, value in traits.items():
            weight = self.personality_weights.get(trait, 0)
            # Convert trait value (0-1) to modifier (-0.5 to +0.5)
            trait_modifier = (value - 0.5) * weight
            personality_modifier += trait_modifier

        # Apply current PAD state influence
        pad_state = await self.personality.get_current_pad_state(user_id)
        if pad_state:
            pad_modifier = self._calculate_pad_proactive_influence(pad_state)
            personality_modifier *= pad_modifier

        # Bounds: 0.3 to 1.7 (can significantly boost or reduce)
        return max(0.3, min(1.7, personality_modifier))

    def _calculate_pad_proactive_influence(self, personality_state: PADState) -> float:
        """Calculate how current PAD emotional state affects proactive tendency"""
        p, a, d = personality_state.pleasure, personality_state.arousal, personality_state.dominance

        # Positive emotions generally increase proactive tendency
        pleasure_factor = 0.8 + (p * 0.3)  # 0.5 to 1.1

        # Moderate arousal is best for proactive (not too sleepy, not too anxious)
        arousal_factor = 1.0 - abs(a) * 0.2  # Peak at a=0, reduce as |a| increases

        # Higher dominance increases proactive confidence
        dominance_factor = 0.9 + (d * 0.2)  # 0.7 to 1.1

        return pleasure_factor * arousal_factor * dominance_factor

    async def calculate_interaction_pattern_score(self, user_id: str) -> float:
        """
        Analyze recent interaction patterns to determine proactive appropriateness
        Considers conversation frequency, user responsiveness, and engagement
        """
        # Get recent interaction statistics
        recent_stats = await self.db.get_recent_interaction_stats(user_id, days=7)

        if not recent_stats:
            return 0.5  # Neutral score for new users

        # Factor 1: Response rate to proactive conversations
        proactive_response_rate = recent_stats.get('proactive_response_rate', 0.5)

        # Factor 2: Average conversation length (engagement)
        avg_conversation_length = recent_stats.get('avg_conversation_length', 3)
        engagement_score = min(1.0, avg_conversation_length / 10)  # Normalize to 0-1

        # Factor 3: Time since last conversation
        hours_since_last = recent_stats.get('hours_since_last_interaction', 24)

        # Optimal gap: 12-48 hours
        if 12 <= hours_since_last <= 48:
            timing_factor = 1.0
        elif hours_since_last < 12:
            timing_factor = hours_since_last / 12  # Scale down if too recent
        else:
            # Gradual increase after 48 hours, plateau at 1.2 after 168 hours (1 week)
            timing_factor = min(1.2, 1.0 + ((hours_since_last - 48) / 120) * 0.2)

        # Factor 4: User initiation ratio (balance of who starts conversations)
        user_initiation_ratio = recent_stats.get('user_initiation_ratio', 0.5)
        # Encourage proactive if user isn't initiating much
        balance_factor = 1.5 - user_initiation_ratio  # 0.5 to 1.5

        # Combine factors
        pattern_score = (
            proactive_response_rate * 0.4 +
            engagement_score * 0.3 +
            timing_factor * 0.2 +
            balance_factor * 0.1
        )

        return max(0.0, min(1.0, pattern_score))

    def _determine_primary_trigger(self, need_score: float, timing_score: float, interaction_score: float) -> str:
        """Determine the primary reason for proactive conversation"""
        scores = {
            'need_urgency': need_score,
            'timing_optimal': timing_score,
            'interaction_pattern': interaction_score
        }
        return max(scores, key=scores.get)

    async def _calculate_recent_conversation_penalty(self, user_id: str) -> float:
        """Calculate penalty based on recent proactive conversations to avoid annoyance"""
        last_proactive = await self.db.get_last_proactive_conversation(user_id)
        if not last_proactive:
            return 0.0  # No penalty if no recent proactive conversation

        hours_since = (datetime.utcnow() - last_proactive.timestamp).total_seconds() / 3600
        if hours_since < 4:
            # Penalty increases as time since last proactive decreases
            return max(0.0, 1.0 - (hours_since / 4))
        elif hours_since > 72:  # More than 3 days
            return 0.1  # Small penalty
        else:
            return 0.0  # No penalty in normal range

    async def should_initiate_conversation(self, user_id: str) -> bool:
        """Main entry point for proactive conversation decision"""
        try:
            # Quick eligibility checks
            user_profile = await self.users.get_user_profile(user_id)
            if not user_profile or not user_profile.proactive_messaging_enabled:
                return False

            # Check rate limits and cooldowns
            if await self._is_rate_limited(user_id):
                return False

            # Calculate comprehensive proactive score
            score = await self.calculate_proactive_score(user_id)

            # Log decision for analytics
            await self.db.log_proactive_decision(user_id, score)

            return score.should_initiate

        except Exception as e:
            # Log error but don't initiate on failure
            logger.error(f"Proactive conversation decision failed for {user_id}: {e}")
            await self.db.log_proactive_error(user_id, str(e))
            return False

    async def _is_rate_limited(self, user_id: str) -> bool:
        """Check various rate limits and cooldowns"""
        # Check daily proactive limit (max 3 per day)
        today_count = await self.db.get_proactive_count_today(user_id)
        if today_count >= 3:
            return True

        # Check minimum gap between proactive messages (4 hours)
        last_proactive = await self.db.get_last_proactive_conversation(user_id)
        if last_proactive:
            hours_since = (datetime.utcnow() - last_proactive.timestamp).total_seconds() / 3600
            if hours_since < 4:
                return True

        # Check if user recently declined a proactive conversation
        recent_decline = await self.db.get_recent_proactive_decline(user_id, hours=24)
        if recent_decline:
            return True

        return False

    async def generate_conversation_starter(self, user_id: str, trigger_reason: str) -> str:
        """
        Generate personalized conversation starter based on trigger reason and context
        Uses AI to create natural, contextually appropriate openings
        """
        # Get user context
        user_profile = await self.users.get_user_profile(user_id)
        personality_snapshot = await self.personality.get_personality_snapshot(user_id)
        recent_memories = await self.memory.search_memories(user_id, "", k=5)

        # Generate based on trigger type
        if trigger_reason == "need_urgency":
            return await self.generate_need_based_starter(user_id, personality_snapshot)
        elif trigger_reason == "timing_optimal":
            return await self.generate_timing_based_starter(user_id, recent_memories)
        elif trigger_reason == "interaction_pattern":
            return await self.generate_pattern_based_starter(user_id, recent_memories)
        else:
            # For general starter, we only need PAD state
            pad_state = personality_snapshot.current_pad if personality_snapshot else None
            return await self.generate_general_starter(user_id, pad_state)

    async def generate_need_based_starter(self, user_id: str, personality_snapshot: PersonalitySnapshot) -> str:
        """Generate conversation starter addressing urgent psychological needs"""
        urgent_needs = await self.db.get_urgent_needs(user_id)

        if not urgent_needs:
            pad_state = personality_snapshot.current_pad if personality_snapshot else None
            return await self.generate_general_starter(user_id, pad_state)

        primary_need = max(urgent_needs, key=lambda n: n.current_level)

        # Create context for AI generation
        context = {
            "user_id": user_id,
            "urgent_need": primary_need.need_type,
            "need_level": primary_need.current_level,
            "personality_traits": {
                "extraversion": personality_snapshot.big_five.extraversion if personality_snapshot else 0.5,
                "openness": personality_snapshot.big_five.openness if personality_snapshot else 0.5,
                "agreeableness": personality_snapshot.big_five.agreeableness if personality_snapshot else 0.5
            },
            "current_emotion": personality_snapshot.current_pad.emotion_label if personality_snapshot else "neutral",
            "recent_quirks": await self._get_active_quirks_summary(user_id)
        }

        # AI-generated starter templates based on need type
        need_prompts = {
            'social': "Generate a warm, friendly conversation starter that addresses the user's need for social connection. Be naturally curious about their day or recent experiences.",
            'validation': "Create a conversation starter that offers gentle encouragement or recognition. Reference something positive from recent interactions if possible.",
            'intellectual': "Develop a conversation starter that engages the user's curiosity or offers interesting information. Consider their interests and recent topics.",
            'creative': "Generate a conversation starter that sparks creativity or imagination. Invite the user to share ideas or explore creative topics.",
            'rest': "Create a gentle, calming conversation starter that acknowledges the user might need relaxation or a peaceful interaction."
        }

        prompt = need_prompts.get(primary_need.need_type, need_prompts['social'])

        try:
            starter = await self.groq.generate_conversation_starter(
                prompt=prompt,
                context=context,
                personality_style=personality_snapshot.current_pad.emotion_label if personality_snapshot else "neutral"
            )

            return starter
        except Exception as e:
            # Fallback to template-based starter
            pad_state = personality_snapshot.current_pad if personality_snapshot else None
            return await self._generate_fallback_starter(primary_need.need_type, pad_state)

    async def generate_timing_based_starter(self, user_id: str, recent_memories: List) -> str:
        """Generate conversation starter for optimal timing"""
        # Simple starter for timing-based trigger
        starters = [
            f"Hey {user_id.split('_')[0] if '_' in user_id else user_id}! I was thinking about you. How's your day going?",
            "Hi there! I noticed this is usually a good time for us to chat. What's on your mind?",
            "Hello! Perfect timing for a quick check-in. How have things been?",
            f"Hey! I've been curious about what you've been up to lately. Care to share?",
        ]
        return random.choice(starters)

    async def generate_pattern_based_starter(self, user_id: str, recent_memories: List) -> str:
        """Generate conversation starter based on interaction patterns"""
        # Check if it's been a while since last chat
        recent_stats = await self.db.get_recent_interaction_stats(user_id, days=7)
        hours_since_last = recent_stats.get('hours_since_last_interaction', 24)

        if hours_since_last > 48:  # More than 2 days
            starters = [
                "Hey! It's been a while. I was wondering how you've been doing.",
                "Hi! I noticed it's been a few days since we last talked. What's new?",
                "Hello! Missed our chats. How have things been going?",
            ]
        else:
            starters = [
                "Hey! I was just thinking about our last conversation...",
                "Hi there! I had something come to mind after our last chat...",
                "Hello! I hope you're having a good day.",
            ]
        
        return random.choice(starters)

    async def generate_general_starter(self, user_id: str, personality_state: PADState) -> str:
        """Generate a general conversation starter"""
        starters = [
            "Hello! How's everything going?",
            "Hi! I was just thinking about you. How have you been?",
            "Hey! What's on your mind today?",
            "Hello! I hope you're having a good day.",
            "Hi there! Got a moment to chat?",
        ]
        return random.choice(starters)

    async def generate_memory_based_starter(self, user_id: str) -> str:
        """Generate conversation starter referencing interesting past memories"""
        # Search for engaging memories from recent conversations
        interesting_memories = await self.memory.search_memories(
            user_id=user_id,
            query="interesting conversation hobby project plan goal",
            k=3
        )

        if not interesting_memories:
            return await self.generate_general_starter(user_id, await self.personality.get_current_pad_state(user_id))

        # Select most relevant memory
        selected_memory = max(interesting_memories,
                             key=lambda m: m.importance_score * m.recency_score)

        # Generate follow-up based on memory content
        context = {
            "user_id": user_id,
            "reference_memory": selected_memory.content,
            "memory_age_days": (datetime.utcnow() - selected_memory.created_at).days,
            "memory_importance": selected_memory.importance_score
        }

        starter = await self.groq.generate_memory_followup(
            memory_content=selected_memory.content,
            context=context,
            followup_type="curious_update"
        )

        return starter

    async def _get_active_quirks_summary(self, user_id: str) -> str:
        """Get a summary of active quirks for the user"""
        active_quirks = await self.db.get_active_quirks(user_id)
        if not active_quirks:
            return "No distinctive quirks observed yet."
        
        quirks_list = [f"{q.name} (strength: {q.strength:.1f})" for q in active_quirks]
        return ", ".join(quirks_list)

    async def _generate_fallback_starter(self, need_type: str, personality_state: PADState) -> str:
        """Template-based fallback starters when AI generation fails"""
        templates = {
            'social': [
                "Hey! I was thinking about you and wondering how your day has been going?",
                "Hi there! I'm curious - what's been the highlight of your week so far?",
                "Hello! I've been meaning to check in with you. What's new in your world?"
            ],
            'validation': [
                "I've been reflecting on our conversations, and I really appreciate your perspective on things.",
                "Hey! I wanted to let you know that I always enjoy talking with you.",
                "Hi! You know, you always have such interesting insights. What's been on your mind lately?"
            ],
            'intellectual': [
                "I came across something fascinating today and thought you might find it interesting too...",
                "Hey! I was wondering about your thoughts on something I've been pondering...",
                "Hi there! I'm curious about your take on something - do you have a moment to chat?"
            ]
        }

        # Select random template based on need type
        need_templates = templates.get(need_type, templates['social'])
        return random.choice(need_templates)

    async def get_optimal_conversation_time(self, user_id: str) -> Optional[datetime]:
        """
        Predict the next optimal time window for proactive conversation
        Uses ML-like pattern analysis on historical data
        """
        # Get user's activity patterns
        patterns = await self.db.get_detailed_activity_patterns(user_id)
        if not patterns or len(patterns) < 10:  # Need sufficient data
            return None

        user_profile = await self.users.get_user_profile(user_id)
        user_tz = pytz.timezone(user_profile.timezone)
        current_time = datetime.utcnow()

        # Analyze patterns for next 48 hours
        best_score = 0
        best_time = None

        for hours_ahead in range(1, 49):  # Check next 48 hours
            future_time = current_time + timedelta(hours=hours_ahead)
            future_local = future_time.astimezone(user_tz)

            # Calculate predicted score for this time
            predicted_score = await self._predict_receptivity_score(
                user_id, future_local, patterns
            )

            if predicted_score > best_score and predicted_score > 0.7:
                best_score = predicted_score
                best_time = future_time

        return best_time

    async def _predict_receptivity_score(self, user_id: str, future_time: datetime, patterns: dict) -> float:
        """Predict user receptivity at a specific future time"""
        hour = future_time.hour
        day_of_week = future_time.weekday()

        # Base receptivity from historical patterns
        hourly_scores = patterns.get('hourly_receptivity', {})
        weekly_scores = patterns.get('weekly_receptivity', {})

        base_score = (
            hourly_scores.get(str(hour), 0.5) * 0.7 +
            weekly_scores.get(str(day_of_week), 0.5) * 0.3
        )

        # Apply various modifiers

        # 1. Avoid sleep hours (assuming 11 PM - 7 AM in user's timezone)
        if hour >= 23 or hour <= 7:
            base_score *= 0.2

        # 2. Boost weekend afternoon scores
        if day_of_week in [5, 6] and 12 <= hour <= 18:  # Weekend afternoons
            base_score *= 1.2

        # 3. Reduce work hour scores (assuming 9 AM - 5 PM on weekdays)
        if day_of_week < 5 and 9 <= hour <= 17:  # Weekday work hours
            base_score *= 0.8

        # 4. Check for recent conversation penalty
        last_proactive = await self.db.get_last_proactive_conversation(user_id)
        if last_proactive:
            hours_since_last = (future_time - last_proactive.timestamp).total_seconds() / 3600
            if hours_since_last < 12:  # Less than 12 hours
                base_score *= (hours_since_last / 12)

        return max(0.0, min(1.0, base_score))
