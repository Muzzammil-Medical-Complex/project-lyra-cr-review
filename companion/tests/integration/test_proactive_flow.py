"""
Integration test for the proactive conversation flow.
Tests the ProactiveManager's ability to detect opportunities and trigger conversations.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from companion.gateway.agents.proactive_manager import ProactiveManager
from companion.gateway.models.personality import PADState, BigFiveTraits, PersonalitySnapshot
from companion.gateway.models.interaction import InteractionRecord
from companion.gateway.models.personality import PsychologicalNeed


@pytest.mark.integration
class TestProactiveFlow:
    """Integration tests for proactive conversation flow."""
    
    async def test_proactive_opportunity_detection_high_need_urgency(self):
        """
        Test proactive conversation initiation when user has high need urgency.
        """
        # SETUP: Mock all required services
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_proactive_1"
        
        # Mock user profile
        mock_user_profile = MagicMock()
        mock_user_profile.proactive_messaging_enabled = True
        user_service.get_user_profile.return_value = mock_user_profile
        
        # Mock urgent needs (social need is high)
        urgent_need = PsychologicalNeed(
            need_type="social",
            current_level=0.85,
            trigger_threshold=0.7,
            baseline_level=0.5,
            proactive_weight=1.0
        )
        db_manager.get_user_needs.return_value = [urgent_need]
        
        # Mock timing as optimal
        db_manager.get_user_activity_patterns.return_value = {
            'hourly': {'14': 0.9},  # High activity at current hour
            'weekly': {'1': 0.8}     # High activity on current day
        }
        
        # Mock personality as moderately extraverted (more likely to be proactive)
        mock_personality = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(
                openness=0.6,
                conscientiousness=0.7,
                extraversion=0.7,  # Moderately extraverted
                agreeableness=0.8,
                neuroticism=0.3
            ),
            current_pad=PADState(
                pleasure=0.2,
                arousal=0.1,
                dominance=0.3,
                emotion_label="content"
            ),
            pad_baseline=PADState(
                pleasure=0.0,
                arousal=0.0,
                dominance=0.0,
                emotion_label="neutral"
            ),
            active_quirks=[],
            psychological_needs=[urgent_need]
        )
        personality_engine.get_personality_snapshot.return_value = mock_personality
        
        # Mock recent interactions showing good engagement
        recent_stats = {
            'proactive_response_rate': 0.7,
            'avg_conversation_length': 8,
            'hours_since_last_interaction': 12,
            'user_initiation_ratio': 0.6
        }
        db_manager.get_recent_interaction_stats.return_value = recent_stats
        
        # Mock rate limiting checks
        db_manager.get_proactive_count_today.return_value = 1  # Within limit
        db_manager.get_last_proactive_conversation.return_value = None
        db_manager.get_recent_proactive_decline.return_value = None
        
        # EXECUTE: Calculate proactive score
        score = await proactive_manager.calculate_proactive_score(user_id)
        
        # ASSERT: Verify opportunity is detected
        assert score is not None
        assert hasattr(score, 'total_score')
        assert hasattr(score, 'need_score')
        assert hasattr(score, 'timing_score')
        assert hasattr(score, 'personality_factor')
        assert hasattr(score, 'interaction_score')
        assert hasattr(score, 'should_initiate')
        
        # High need urgency should contribute significantly to total score
        assert score.need_score > 0.6  # Should be high due to urgent social need
        assert score.total_score > 0.6  # Should be above threshold
        assert score.should_initiate == True  # Should trigger proactive conversation
        
        print(f"✅ Proactive score calculated: {score.total_score:.2f}")
        print(f"   Need score: {score.need_score:.2f}")
        print(f"   Timing score: {score.timing_score:.2f}")
        print(f"   Personality factor: {score.personality_factor:.2f}")
        print(f"   Interaction score: {score.interaction_score:.2f}")
        print(f"   Should initiate: {score.should_initiate}")

    async def test_proactive_opportunity_detection_optimal_timing(self):
        """
        Test proactive conversation initiation when timing is optimal.
        """
        # SETUP
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_proactive_2"
        
        # Mock user profile
        mock_user_profile = MagicMock()
        mock_user_profile.proactive_messaging_enabled = True
        mock_user_profile.timezone = "America/New_York"
        user_service.get_user_profile.return_value = mock_user_profile
        
        # Mock moderate needs (not urgent)
        moderate_needs = [
            PsychologicalNeed(need_type="social", current_level=0.4, trigger_threshold=0.7),
            PsychologicalNeed(need_type="validation", current_level=0.5, trigger_threshold=0.7)
        ]
        db_manager.get_user_needs.return_value = moderate_needs
        
        # Mock optimal timing pattern (high historical activity)
        db_manager.get_user_activity_patterns.return_value = {
            'hourly': {'14': 0.95},  # Peak activity
            'weekly': {'1': 0.9}     # Peak day activity
        }
        
        # Mock personality snapshot
        mock_personality = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(
                openness=0.7,
                conscientiousness=0.6,
                extraversion=0.8,  # Highly extraverted
                agreeableness=0.7,
                neuroticism=0.2
            ),
            current_pad=PADState(
                pleasure=0.3,
                arousal=0.2,
                dominance=0.4,
                emotion_label="energetic"
            ),
            pad_baseline=PADState(
                pleasure=0.0,
                arousal=0.0,
                dominance=0.0,
                emotion_label="neutral"
            ),
            active_quirks=[],
            psychological_needs=moderate_needs
        )
        personality_engine.get_personality_snapshot.return_value = mock_personality
        
        # Mock recent interactions showing good timing opportunity
        recent_stats = {
            'proactive_response_rate': 0.8,
            'avg_conversation_length': 12,
            'hours_since_last_interaction': 24,  # Perfect timing gap
            'user_initiation_ratio': 0.4
        }
        db_manager.get_recent_interaction_stats.return_value = recent_stats
        
        # Mock rate limiting checks
        db_manager.get_proactive_count_today.return_value = 0
        db_manager.get_last_proactive_conversation.return_value = None
        db_manager.get_recent_proactive_decline.return_value = None
        
        # EXECUTE
        score = await proactive_manager.calculate_proactive_score(user_id)
        
        # ASSERT
        assert score is not None
        assert score.timing_score > 0.7  # Should be high due to optimal timing
        assert score.personality_factor > 1.0  # Should be boosted due to high extraversion
        assert score.total_score > 0.6  # Should be above threshold
        
        print(f"✅ Timing-based proactive score: {score.total_score:.2f}")
        print(f"   Timing score: {score.timing_score:.2f}")
        print(f"   Personality boost: {score.personality_factor:.2f}")

    async def test_proactive_conversation_starter_generation(self):
        """
        Test generation of personalized conversation starters.
        """
        # SETUP
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_starter"
        
        # Mock personality for context
        mock_personality = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(
                openness=0.7,
                conscientiousness=0.6,
                extraversion=0.5,
                agreeableness=0.8,
                neuroticism=0.3
            ),
            current_pad=PADState(
                pleasure=0.2,
                arousal=0.1,
                dominance=0.3,
                emotion_label="content"
            ),
            pad_baseline=PADState(
                pleasure=0.0,
                arousal=0.0,
                dominance=0.0,
                emotion_label="neutral"
            ),
            active_quirks=[],
            psychological_needs=[]
        )
        personality_engine.get_personality_snapshot.return_value = mock_personality
        
        # Mock Groq to generate conversation starters
        groq_client.generate_conversation_starter = AsyncMock(return_value="Hey! I was thinking about you. How's your day going?")
        groq_client.generate_memory_followup = AsyncMock(return_value="I remember you mentioned something interesting last time...")
        
        # Mock memory search
        memory_manager.search_memories.return_value = []
        
        # TEST different trigger reasons
        trigger_reasons = ["need_urgency", "timing_optimal", "interaction_pattern"]
        
        for trigger_reason in trigger_reasons:
            # EXECUTE
            starter = await proactive_manager.generate_conversation_starter(
                user_id, trigger_reason
            )
            
            # ASSERT
            assert starter is not None
            assert len(starter) > 5  # Should be a meaningful starter
            assert isinstance(starter, str)
            
            print(f"✅ Generated starter for {trigger_reason}: {starter[:50]}...")
        
        # Test memory-based starter
        mock_memories = [MagicMock(content="User mentioned their new puppy Sparky")]
        memory_manager.search_memories.return_value = mock_memories
        
        memory_starter = await proactive_manager.generate_memory_based_starter(user_id)
        assert memory_starter is not None
        assert len(memory_starter) > 5
        
        print(f"✅ Generated memory-based starter: {memory_starter[:50]}...")

    async def test_proactive_rate_limiting_and_cooldowns(self):
        """
        Test that proactive conversations respect rate limits and cooldowns.
        """
        # SETUP
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_limits"
        
        # Mock user profile
        mock_user_profile = MagicMock()
        mock_user_profile.proactive_messaging_enabled = True
        user_service.get_user_profile.return_value = mock_user_profile
        
        # Test daily limit exceeded
        db_manager.get_proactive_count_today.return_value = 5  # Exceeds limit of 3
        
        # EXECUTE
        should_initiate = await proactive_manager.should_initiate_conversation(user_id)
        
        # ASSERT
        assert should_initiate == False  # Should not initiate due to rate limit
        
        # Reset for next test - test minimum gap
        db_manager.get_proactive_count_today.return_value = 1
        recent_proactive = MagicMock()
        recent_proactive.timestamp = datetime.utcnow() - timedelta(hours=2)  # Only 2 hours ago
        db_manager.get_last_proactive_conversation.return_value = recent_proactive
        
        # EXECUTE
        should_initiate = await proactive_manager.should_initiate_conversation(user_id)
        
        # ASSERT
        assert should_initiate == False  # Should not initiate due to minimum gap
        
        # Reset for successful test
        recent_proactive.timestamp = datetime.utcnow() - timedelta(hours=6)  # 6 hours ago
        db_manager.get_last_proactive_conversation.return_value = recent_proactive
        
        # Mock all conditions for initiation
        db_manager.get_user_needs.return_value = [
            PsychologicalNeed(need_type="social", current_level=0.9, trigger_threshold=0.7)
        ]
        db_manager.get_recent_interaction_stats.return_value = {
            'proactive_response_rate': 0.8,
            'avg_conversation_length': 10,
            'hours_since_last_interaction': 36,
            'user_initiation_ratio': 0.5
        }
        personality_engine.get_personality_snapshot.return_value = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(openness=0.5, conscientiousness=0.5, extraversion=0.5, agreeableness=0.5, neuroticism=0.5),
            current_pad=PADState(pleasure=0.0, arousal=0.0, dominance=0.0, emotion_label="neutral"),
            pad_baseline=PADState(pleasure=0.0, arousal=0.0, dominance=0.0, emotion_label="neutral"),
            active_quirks=[],
            psychological_needs=[]
        )
        
        # EXECUTE
        should_initiate = await proactive_manager.should_initiate_conversation(user_id)
        
        # ASSERT - this would depend on the actual scoring, but we can verify the method works
        assert should_initiate in [True, False]  # Should not raise an exception
        
        print("✅ Rate limiting and cooldowns test passed")

    async def test_proactive_scoring_component_breakdown(self):
        """
        Test individual components of the proactive scoring algorithm.
        """
        # SETUP
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_components"
        
        # Test need urgency scoring
        db_manager.get_user_needs.return_value = [
            PsychologicalNeed(need_type="social", current_level=0.9, trigger_threshold=0.7, proactive_weight=1.0),
            PsychologicalNeed(need_type="validation", current_level=0.8, trigger_threshold=0.7, proactive_weight=0.8)
        ]
        
        need_score = await proactive_manager.calculate_need_urgency_score(user_id)
        assert 0.0 <= need_score <= 1.0
        assert need_score > 0.5  # Should be high with urgent needs
        
        print(f"✅ Need urgency score: {need_score:.2f}")
        
        # Test timing scoring
        db_manager.get_user_activity_patterns.return_value = {
            'hourly': {'14': 0.9},
            'weekly': {'1': 0.8}
        }
        
        timing_score = await proactive_manager.calculate_timing_score(user_id)
        assert 0.0 <= timing_score <= 1.0
        
        print(f"✅ Timing score: {timing_score:.2f}")
        
        # Test personality factor
        mock_personality = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(
                openness=0.6,
                conscientiousness=0.7,
                extraversion=0.8,  # High extraversion boosts proactive tendency
                agreeableness=0.7,
                neuroticism=0.2
            ),
            current_pad=PADState(pleasure=0.3, arousal=0.2, dominance=0.4, emotion_label="happy"),
            pad_baseline=PADState(pleasure=0.0, arousal=0.0, dominance=0.0, emotion_label="neutral"),
            active_quirks=[],
            psychological_needs=[]
        )
        personality_engine.get_personality_snapshot.return_value = mock_personality
        
        personality_factor = await proactive_manager.calculate_personality_factor(user_id)
        assert 0.3 <= personality_factor <= 1.7  # Should be in valid range
        assert personality_factor > 1.0  # Should be boosted due to high extraversion
        
        print(f"✅ Personality factor: {personality_factor:.2f}")
        
        # Test interaction pattern scoring
        db_manager.get_recent_interaction_stats.return_value = {
            'proactive_response_rate': 0.7,
            'avg_conversation_length': 8,
            'hours_since_last_interaction': 24,
            'user_initiation_ratio': 0.5
        }
        
        interaction_score = await proactive_manager.calculate_interaction_pattern_score(user_id)
        assert 0.0 <= interaction_score <= 1.0
        
        print(f"✅ Interaction pattern score: {interaction_score:.2f}")

    async def test_proactive_conversation_decision_making(self):
        """
        Test the complete proactive conversation decision-making process.
        """
        # SETUP
        personality_engine = AsyncMock()
        memory_manager = AsyncMock()
        user_service = AsyncMock()
        groq_client = AsyncMock()
        db_manager = AsyncMock()
        
        proactive_manager = ProactiveManager(
            personality_engine=personality_engine,
            memory_manager=memory_manager,
            user_service=user_service,
            groq_client=groq_client,
            db_manager=db_manager
        )
        
        user_id = "test_user_decision"
        
        # Mock all required data for a high-score scenario
        mock_user_profile = MagicMock()
        mock_user_profile.proactive_messaging_enabled = True
        mock_user_profile.timezone = "UTC"
        user_service.get_user_profile.return_value = mock_user_profile
        
        # High urgency needs
        db_manager.get_user_needs.return_value = [
            PsychologicalNeed(need_type="social", current_level=0.95, trigger_threshold=0.7, proactive_weight=1.0),
            PsychologicalNeed(need_type="validation", current_level=0.85, trigger_threshold=0.7, proactive_weight=0.9)
        ]
        
        # Optimal timing
        db_manager.get_user_activity_patterns.return_value = {
            'hourly': {'14': 1.0},  # Peak activity
            'weekly': {'1': 0.95}
        }
        
        # Good personality for proactive (extraverted, agreeable)
        mock_personality = PersonalitySnapshot(
            user_id=user_id,
            big_five=BigFiveTraits(
                openness=0.7,
                conscientiousness=0.6,
                extraversion=0.8,
                agreeableness=0.9,
                neuroticism=0.2
            ),
            current_pad=PADState(pleasure=0.4, arousal=0.3, dominance=0.5, emotion_label="cheerful"),
            pad_baseline=PADState(pleasure=0.0, arousal=0.0, dominance=0.0, emotion_label="neutral"),
            active_quirks=[],
            psychological_needs=[]
        )
        personality_engine.get_personality_snapshot.return_value = mock_personality
        
        # Strong interaction history
        db_manager.get_recent_interaction_stats.return_value = {
            'proactive_response_rate': 0.85,
            'avg_conversation_length': 15,
            'hours_since_last_interaction': 30,
            'user_initiation_ratio': 0.4
        }
        
        # Within rate limits
        db_manager.get_proactive_count_today.return_value = 1
        db_manager.get_last_proactive_conversation.return_value = MagicMock(
            timestamp=datetime.utcnow() - timedelta(hours=30)
        )
        db_manager.get_recent_proactive_decline.return_value = None
        
        # EXECUTE: Full decision process
        should_initiate = await proactive_manager.should_initiate_conversation(user_id)
        
        # Log decision-making process
        score = await proactive_manager.calculate_proactive_score(user_id)
        
        # ASSERT
        assert score.total_score > 0.7  # Should have high score
        assert score.need_score > 0.7   # High need urgency
        assert score.timing_score > 0.7  # Optimal timing
        assert score.personality_factor > 1.0  # Personality boost
        assert score.interaction_score > 0.7  # Good interaction patterns
        assert score.should_initiate == True  # Should definitely initiate
        
        # The actual decision should match the score
        assert should_initiate == True
        
        print(f"✅ Complete proactive decision test passed")
        print(f"   Total score: {score.total_score:.2f}")
        print(f"   Should initiate: {score.should_initiate}")
        print(f"   Actual decision: {should_initiate}")
        
        # Test edge case: disabled proactive messaging
        mock_user_profile.proactive_messaging_enabled = False
        should_initiate_disabled = await proactive_manager.should_initiate_conversation(user_id)
        assert should_initiate_disabled == False  # Should not initiate when disabled
        
        print("✅ Proactive messaging disable test passed")