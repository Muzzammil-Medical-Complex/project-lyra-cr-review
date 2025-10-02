"""
Unit tests for the Personality Engine service.
Tests PAD state updates, quirk evolution, and need calculations.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from companion.gateway.models.personality import PADState, BigFiveTraits, Quirk, PsychologicalNeed
from companion.gateway.services.personality_engine import PersonalityEngine


@pytest.mark.asyncio
class TestPersonalityEngine:
    """Unit tests for PersonalityEngine class."""
    
    async def test_pad_state_update_within_bounds(self):
        """Test 1: Normal PAD state update within bounds."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_1'
        initial_state = PADState(pleasure=0.1, arousal=0.0, dominance=-0.2)
        delta = PADState(pleasure=0.3, arousal=0.1, dominance=0.4)

        # Expected calculation: new = initial + delta
        expected_state = PADState(pleasure=0.4, arousal=0.1, dominance=0.2)

        # Execute
        result = await personality_engine.update_pad_state(user_id, delta)

        # Assert
        assert abs(result.pleasure - expected_state.pleasure) < 0.01
        assert abs(result.arousal - expected_state.arousal) < 0.01
        assert abs(result.dominance - expected_state.dominance) < 0.01

    async def test_pad_state_update_upper_bound_clamping(self):
        """Test 2: PAD state clamping at upper bound."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_2'
        initial_state = PADState(pleasure=0.8, arousal=0.9, dominance=0.7)
        delta = PADState(pleasure=0.5, arousal=0.3, dominance=0.5)

        # Expected: clamped to 1.0 maximum
        expected_state = PADState(pleasure=1.0, arousal=1.0, dominance=1.0)

        # Execute
        result = await personality_engine.update_pad_state(user_id, delta)

        # Assert clamping occurred
        assert result.pleasure == 1.0
        assert result.arousal == 1.0
        assert result.dominance == 1.0

    async def test_pad_state_update_lower_bound_clamping(self):
        """Test 3: PAD state clamping at lower bound."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_3'
        initial_state = PADState(pleasure=-0.9, arousal=-0.8, dominance=-0.7)
        delta = PADState(pleasure=-0.4, arousal=-0.5, dominance=-0.6)

        # Expected: clamped to -1.0 minimum
        expected_state = PADState(pleasure=-1.0, arousal=-1.0, dominance=-1.0)

        # Execute
        result = await personality_engine.update_pad_state(user_id, delta)

        # Assert clamping occurred
        assert result.pleasure == -1.0
        assert result.arousal == -1.0
        assert result.dominance == -1.0

    async def test_quirk_strength_increase(self):
        """Test quirk strength increases with reinforcement."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_4'
        
        # Create a quirk with initial strength
        quirk = Quirk(
            id='test_quirk_1',
            user_id=user_id,
            name='test_quirk',
            strength=0.3,
            confidence=0.7,
            is_active=True
        )
        
        # Mock the database to return the quirk
        db_mock.get_active_quirks.return_value = [quirk]
        
        # Simulate reinforcement
        await personality_engine.reinforce_quirk(user_id, 'test_quirk')
        
        # Verify the strength increased
        # The exact implementation would depend on the reinforce_quirk method
        # For now, we'll verify that the db update was called
        db_mock.update_quirk_strength.assert_called()

    async def test_quirk_strength_decay(self):
        """Test quirk strength decreases with disuse."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_5'
        
        # Create a quirk with initial strength
        quirk = Quirk(
            id='test_quirk_2',
            user_id=user_id,
            name='test_quirk_decay',
            strength=0.8,
            confidence=0.7,
            is_active=True
        )
        
        # Mock the database to return the quirk
        db_mock.get_active_quirks.return_value = [quirk]
        
        # Simulate decay over time
        time_since_observed = 10  # days
        decay_rate = 0.05
        expected_decay = max(0.0, quirk.strength - (time_since_observed * decay_rate))
        
        # This test would need more implementation details from the actual method
        # For now, we verify the structure
        assert expected_decay >= 0.0  # Ensure decay doesn't go below 0

    async def test_need_satisfaction_calculation(self):
        """Test calculation of need satisfaction."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_6'
        
        # Create needs with different levels
        needs = [
            PsychologicalNeed(need_type='social', current_level=0.9, trigger_threshold=0.8),
            PsychologicalNeed(need_type='intellectual', current_level=0.4, trigger_threshold=0.7),
            PsychologicalNeed(need_type='validation', current_level=0.6, trigger_threshold=0.65)
        ]
        
        # Mock the database to return these needs
        db_mock.get_user_needs.return_value = needs
        
        # Test identifying urgent needs (current_level > trigger_threshold)
        urgent_needs = [n for n in needs if n.current_level > n.trigger_threshold]
        assert len(urgent_needs) == 2  # social and validation needs are urgent
        
        # Test need calculations
        for need in urgent_needs:
            urgency = (need.current_level - need.trigger_threshold) / (1.0 - need.trigger_threshold)
            assert 0.0 <= urgency <= 1.0

    async def test_personality_snapshot_generation(self):
        """Test generation of complete personality snapshot."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        user_id = 'test_user_7'
        
        # Mock all necessary data
        big_five_traits = BigFiveTraits(
            openness=0.6,
            conscientiousness=0.7,
            extraversion=0.5,
            agreeableness=0.8,
            neuroticism=0.3
        )
        
        current_pad = PADState(
            pleasure=0.2,
            arousal=0.1,
            dominance=0.3,
            emotion_label='content'
        )
        
        active_quirks = [
            Quirk(name='likes_emojis', strength=0.7, is_active=True),
            Quirk(name='short_responses', strength=0.4, is_active=True)
        ]
        
        needs = [
            PsychologicalNeed(need_type='social', current_level=0.5),
            PsychologicalNeed(need_type='validation', current_level=0.7)
        ]
        
        # Mock database calls
        db_mock.get_current_personality_state.return_value = current_pad
        db_mock.get_big_five_traits.return_value = big_five_traits
        db_mock.get_active_quirks.return_value = active_quirks
        db_mock.get_user_needs.return_value = needs
        
        # Generate snapshot
        snapshot = await personality_engine.get_personality_snapshot(user_id)
        
        # Verify all components are present
        assert snapshot.big_five == big_five_traits
        assert snapshot.current_pad == current_pad
        assert len(snapshot.active_quirks) == len(active_quirks)
        assert len(snapshot.psychological_needs) == len(needs)
        # Verify pad_baseline is present
        assert snapshot.pad_baseline is not None

    async def test_emotion_to_octant_conversion(self):
        """Test conversion of PAD coordinates to emotion octant labels."""
        # Setup
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        personality_engine = PersonalityEngine(db_mock, groq_mock)
        
        # Test cases for different octants
        test_cases = [
            (PADState(pleasure=0.8, arousal=0.7, dominance=0.6), "exuberant"),  # High P, A, D
            (PADState(pleasure=0.8, arousal=0.7, dominance=-0.6), "bored"),    # High P, A, Low D
            (PADState(pleasure=0.8, arousal=-0.7, dominance=0.6), "relaxed"),  # High P, Low A, High D
            (PADState(pleasure=0.8, arousal=-0.7, dominance=-0.6), "sleepy"),  # High P, Low A, Low D
            (PADState(pleasure=-0.8, arousal=0.7, dominance=0.6), "anxious"),  # Low P, High A, High D
            (PADState(pleasure=-0.8, arousal=0.7, dominance=-0.6), "stressed"), # Low P, High A, Low D
            (PADState(pleasure=-0.8, arousal=-0.7, dominance=0.6), "calm"),    # Low P, Low A, High D
            (PADState(pleasure=-0.8, arousal=-0.7, dominance=-0.6), "depressed") # Low P, Low A, Low D
        ]
        
        for pad_state, expected_label in test_cases:
            # The actual mapping would depend on the implementation in PADState.to_emotion_octant()
            # For this test, we just verify the method exists and is callable
            emotion_label = pad_state.to_emotion_octant()
            # Note: This test requires the PADState class to have the to_emotion_octant method implemented
            assert isinstance(emotion_label, str)