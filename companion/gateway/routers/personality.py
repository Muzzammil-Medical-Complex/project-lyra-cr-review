"""
Personality router for the AI Companion System.
Provides API endpoints for inspecting and managing the companion's personality state.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..models.personality import (
    PersonalitySnapshot, PADState, BigFiveTraits, Quirk, PsychologicalNeed
)
from ..services.personality_engine import PersonalityEngine
from ..services.user_service import UserService
from ..database import DatabaseManager
from ..utils.exceptions import UserNotFoundError, PersonalityEngineError

# Import dependency functions from main
from ..main import get_personality, get_users, get_db, get_memory

router = APIRouter(tags=["personality"])

logger = logging.getLogger(__name__)


@router.get("/current/{user_id}", response_model=PersonalitySnapshot)
async def get_current_personality(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get the current personality snapshot for a user.
    Includes Big Five traits, PAD state, quirks, and needs.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get current personality snapshot
        snapshot = await personality_engine.get_personality_snapshot(user_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Personality data not found for user {user_id}")
        
        return snapshot
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting current personality for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{user_id}", response_model=List[Dict[str, Any]])
async def get_personality_history(
    user_id: str,
    days: int = Query(7, ge=1, le=365),
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get historical personality states for a user over the specified number of days.
    Returns PAD states with timestamps.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get historical personality data
        history = await personality_engine.get_personality_history(user_id, days=days)
        
        return history
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting personality history for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/quirks/{user_id}", response_model=List[Quirk])
async def get_user_quirks(
    user_id: str,
    active_only: bool = Query(True),
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get all quirks for a user.
    Can filter to active quirks only.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get quirks
        if active_only:
            quirks = await personality_engine.get_active_quirks(user_id)
        else:
            quirks = await personality_engine.get_all_quirks(user_id)
        
        return quirks
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting quirks for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/needs/{user_id}", response_model=List[PsychologicalNeed])
async def get_user_needs(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get all psychological needs for a user with their current levels.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get needs
        needs = await personality_engine.get_user_needs(user_id)
        
        return needs
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting needs for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/evolution/{user_id}", response_model=Dict[str, Any])
async def get_personality_evolution(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get personality evolution metrics for a user.
    Shows how personality has changed over time.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get evolution metrics
        evolution_metrics = await personality_engine.get_evolution_metrics(user_id)
        
        return {
            "user_id": user_id,
            "evolution_metrics": evolution_metrics,
            "timestamp": datetime.utcnow()
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting evolution metrics for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/override/{user_id}", response_model=PersonalitySnapshot)
async def override_personality_state(
    user_id: str,
    pad_state: PADState,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Override the current PAD state for a user (admin endpoint).
    This is primarily for testing or emergency correction.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Check if user has admin privileges (in a real implementation, this would be more robust)
        if not getattr(user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Admin access required to override personality state")
        
        # Override PAD state
        updated_snapshot = await personality_engine.override_pad_state(user_id, pad_state)
        
        logger.info(f"Personality state overridden for user {user_id} by admin")
        
        return updated_snapshot
        
    except HTTPException:
        raise
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error overriding personality state for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/baseline/{user_id}", response_model=Dict[str, Any])
async def get_personality_baseline(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get the long-term personality baseline for a user.
    This shows the stable, drifting PAD baseline that emotional states fluctuate around.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get baseline
        baseline = await personality_engine.get_personality_baseline(user_id)
        
        return {
            "user_id": user_id,
            "baseline": baseline,
            "timestamp": datetime.utcnow()
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting personality baseline for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/traits/{user_id}", response_model=BigFiveTraits)
async def get_big_five_traits(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get the fixed Big Five personality traits for a user.
    These traits are set during user initialization and don't change.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get Big Five traits
        traits = await personality_engine.get_big_five_traits(user_id)
        
        return traits
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting Big Five traits for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/quirk/reinforce/{user_id}", response_model=bool)
async def reinforce_quirk(
    user_id: str,
    quirk_name: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Reinforce a specific quirk for a user, increasing its strength.
    This is typically called when the user exhibits behavior matching the quirk.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Reinforce the quirk
        success = await personality_engine.reinforce_quirk(user_id, quirk_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Quirk '{quirk_name}' not found for user {user_id}")
        
        logger.info(f"Quirk '{quirk_name}' reinforced for user {user_id}")
        
        return success
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error reinforcing quirk '{quirk_name}' for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/need/update/{user_id}/{need_type}", response_model=PsychologicalNeed)
async def update_need_level(
    user_id: str,
    need_type: str,
    new_level: float = Query(..., ge=0.0, le=1.0),
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Update the current level of a specific psychological need.
    This is typically called internally when the system detects need satisfaction or deprivation.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Update need level
        updated_need = await personality_engine.update_need_level(
            user_id=user_id,
            need_type=need_type,
            new_level=new_level
        )
        
        if not updated_need:
            raise HTTPException(status_code=404, detail=f"Need '{need_type}' not found for user {user_id}")
        
        logger.info(f"Need '{need_type}' updated to {new_level:.2f} for user {user_id}")
        
        return updated_need
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating need '{need_type}' for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stability/{user_id}", response_model=Dict[str, Any])
async def get_personality_stability(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get personality stability metrics for a user.
    Stability indicates how consistent the personality has been over time.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get stability metrics
        stability_metrics = await personality_engine.get_personality_stability(user_id)
        
        return {
            "user_id": user_id,
            "stability_metrics": stability_metrics,
            "timestamp": datetime.utcnow()
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting stability metrics for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/emotions/{user_id}", response_model=Dict[str, Any])
async def get_emotional_state(
    user_id: str,
    personality_engine: PersonalityEngine = Depends(get_personality),
    user_service: UserService = Depends(get_users)
):
    """
    Get the current emotional state (PAD) for a user.
    Includes the emotion label and intensity metrics.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get current PAD state
        current_pad = await personality_engine.get_current_pad_state(user_id)
        
        if not current_pad:
            raise HTTPException(status_code=404, detail=f"PAD state not found for user {user_id}")
        
        # Convert to emotion octant
        emotion_label = current_pad.to_emotion_octant()
        
        return {
            "user_id": user_id,
            "current_pad": current_pad,
            "emotion_label": emotion_label,
            "timestamp": datetime.utcnow()
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except PersonalityEngineError as e:
        raise HTTPException(status_code=500, detail=f"Personality engine error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting emotional state for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")