"""
Proactive Manager for AI Companion System
Handles intelligent initiation of conversations based on user needs, timing, and patterns.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
import pytz
import random

from ..models.personality import PADState
from ..models.interaction import ProactiveScore
from ..services.personality_engine import PersonalityEngine
from ..services.memory_manager import MemoryManager
from ..services.user_service import UserService
from ..services.groq_client import GroqClient
from ..database import DatabaseManager

logger = logging.getLogger(__name__)

class ProactiveManager:
    """
    Manages proactive conversation initiation with multi-factor scoring
    """
    
    def __init__(self, db: DatabaseManager, personality: PersonalityEngine, 
                 memory: MemoryManager, users: UserService, groq: GroqClient):
        self.db = db
        self.personality = personality
        self.memory = memory
        self.users = users
        self.groq = groq
        
        # Proactive conversation thresholds
        self.base_threshold = 0.6  # Minimum score to trigger conversation
        self.personality_weights = {
            'extraversion': 0.3,    # More extraverted = more proactive
            'openness': 0.2,        # More open = more curious conversations
            'agreeableness': -0.1,   # More agreeable = gentler approaches
            'conscientiousness': -0.1, # More conscientious = less interrupting
            'neuroticism': 0.15     # More neurotic = more need for reassurance
        }

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
        final_score *= (1 - recent_penalty)

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
            await self.db.log_proactive_error(user_id, str(e))
            return False

    async def generate_conversation_starter(self, user_id: str, trigger_reason: str) -> str:
        """
        Generate personalized conversation starter based on trigger reason and context
        Uses AI to create natural, contextually appropriate openings
        """
        # Get user context
        user_profile = await self.users.get_user_profile(user_id)
        personality_state = await self.personality.get_current_pad_state(user_id)
        recent_memories = await self.memory.search_memories(user_id, "", k=5)

        # Generate based on trigger type
        if trigger_reason == "need_urgency":
            return await self.generate_need_based_starter(user_id, personality_state)
        elif trigger_reason == "timing_optimal":
            return await self.generate_timing_based_starter(user_id, recent_memories)
        elif trigger_reason == "interaction_pattern":
            return await self.generate_pattern_based_starter(user_id, recent_memories)
        else:
            return await self.generate_general_starter(user_id, personality_state)

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
            hours_since_activity = (current_time - last_activity).total_seconds() / 3600

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
        personality_state = await self.personality.get_current_pad_state(user_id)
        if not personality_state:
            return 1.0  # Neutral if no personality data

        # Extract Big Five traits
        traits = {
            'extraversion': personality_state.extraversion,
            'openness': personality_state.openness,
            'agreeableness': personality_state.agreeableness,
            'conscientiousness': personality_state.conscientiousness,
            'neuroticism': personality_state.neuroticism
        }

        # Calculate weighted personality factor
        personality_modifier = 1.0  # Start with neutral
        for trait, value in traits.items():
            weight = self.personality_weights.get(trait, 0)
            # Convert trait value (0-1) to modifier (-0.5 to +0.5)
            trait_modifier = (value - 0.5) * weight
            personality_modifier += trait_modifier

        # Apply current PAD state influence
        pad_modifier = self._calculate_pad_proactive_influence(personality_state)
        personality_modifier *= pad_modifier

        # Bounds: 0.3 to 1.7 (can significantly boost or reduce)
        return max(0.3, min(1.7, personality_modifier))

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
        ) / 1.0

        return max(0.0, min(1.0, pattern_score))

    async def generate_need_based_starter(self, user_id: str, personality_state) -> str:
        """Generate conversation starter addressing urgent psychological needs"""
        urgent_needs = await self.db.get_urgent_needs(user_id)

        if not urgent_needs:
            return await self.generate_general_starter(user_id, personality_state)

        primary_need = max(urgent_needs, key=lambda n: n.current_level)

        # Create context for AI generation
        context = {
            "user_id": user_id,
            "urgent_need": primary_need.need_type,
            "need_level": primary_need.current_level,
            "personality_traits": {
                "extraversion": personality_state.extraversion,
                "openness": personality_state.openness,
                "agreeableness": personality_state.agreeableness
            },
            "current_emotion": personality_state.emotion_label,
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
                personality_style=personality_state.emotion_label
            )

            return starter
        except Exception as e:
            # Fallback to template-based starter
            return await self._generate_fallback_starter(primary_need.need_type, personality_state)

    async def generate_memory_based_starter(self, user_id: str) -> str:
        """Generate conversation starter referencing interesting past memories"""
        # Search for engaging memories from recent conversations
        interesting_memories = await self.memory.search_memories(
            user_id=user_id,
            query="interesting conversation hobby project plan goal",
            k=3
        )

        if not interesting_memories:
            return await self.generate_general_starter(user_id, None)

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

    async def generate_general_starter(self, user_id: str, personality_state) -> str:
        """Generate a general conversation starter based on personality"""
        if personality_state:
            # Use personality to influence starter
            if personality_state.extraversion > 0.7:
                return "Hey! I've been thinking about our last conversation and wanted to catch up. What's new with you?"
            elif personality_state.openness > 0.7:
                return "I came across something interesting today and thought you might find it fascinating. Want to hear about it?"
            elif personality_state.neuroticism > 0.6:
                return "I hope you're doing okay. I've been thinking about how you've been feeling lately."
            else:
                return "Hi there! I was just thinking about you and wondering how your day has been going."
        else:
            return "Hello! I was thinking about you and wanted to check in. How are you doing today?"

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

    async def update_proactive_statistics(self, user_id: str, conversation_success: bool) -> None:
        """Update proactive conversation statistics for learning"""
        await self.db.update_proactive_stats(user_id, conversation_success)

    def _calculate_pad_proactive_influence(self, personality_state) -> float:
        """Calculate how current PAD emotional state affects proactive tendency"""
        p, a, d = personality_state.pleasure, personality_state.arousal, personality_state.dominance

        # Positive emotions generally increase proactive tendency
        pleasure_factor = 0.8 + (p * 0.3)  # 0.5 to 1.1

        # Moderate arousal is best for proactive (not too sleepy, not too anxious)
        arousal_factor = 1.0 - abs(a) * 0.2  # Peak at a=0, reduce as |a| increases

        # Higher dominance increases proactive confidence
        dominance_factor = 0.9 + (d * 0.2)  # 0.7 to 1.1

        return pleasure_factor * arousal_factor * dominance_factor

    def _determine_primary_trigger(self, need_score: float, timing_score: float, interaction_score: float) -> str:
        """Determine the primary reason for proactive conversation trigger"""
        scores = {
            "need_urgency": need_score,
            "timing_optimal": timing_score,
            "interaction_pattern": interaction_score
        }
        
        return max(scores, key=scores.get)

    async def _calculate_recent_conversation_penalty(self, user_id: str) -> float:
        """Calculate penalty based on recent proactive conversations"""
        last_proactive = await self.db.get_last_proactive_conversation(user_id)
        if last_proactive:
            hours_since = (datetime.utcnow() - last_proactive.timestamp).total_seconds() / 3600
            # Linear penalty: 100% penalty if < 2 hours, 0% if > 8 hours
            if hours_since < 2:
                return 1.0
            elif hours_since < 8:
                return (8 - hours_since) / 6
        return 0.0

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

    async def _get_active_quirks_summary(self, user_id: str) -> str:
        """Get a summary of user's active quirks"""
        quirks = await self.db.get_active_quirks(user_id)
        if not quirks:
            return "No active quirks"
        
        quirk_descriptions = [f"{q.name} (strength: {q.strength:.1f})" for q in quirks[:3]]
        return ", ".join(quirk_descriptions)

    async def _generate_fallback_starter(self, need_type: str, personality_state) -> str:
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
            ],
            'creative': [
                "I've been thinking about creative projects lately. Have you been working on anything fun?",
                "I had an idea for a story and thought you might enjoy brainstorming with me.",
                "I saw something that reminded me of your creative side. Want to explore some ideas together?"
            ],
            'rest': [
                "I hope you're taking some time to relax today. How are you feeling?",
                "Sometimes we all need a break. How's your rest and relaxation going?",
                "I noticed you might be feeling tired. How about we have a calm, peaceful chat?"
            ]
        }

        # Select random template based on need type
        need_templates = templates.get(need_type, templates['social'])
        return random.choice(need_templates)

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
```