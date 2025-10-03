"""
Chat router for the AI Companion System.
Handles all user interactions, message processing, and conversation management.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
import asyncio
import logging
import uuid
from datetime import datetime

from ..models.interaction import ChatRequest, ChatResponse, InteractionRecord, ProactiveContext
from ..models.personality import PADState, PersonalitySnapshot
from ..services.letta_service import LettaService
from ..services.personality_engine import PersonalityEngine
from ..services.memory_manager import MemoryManager
from ..services.user_service import UserService
from ..security.semantic_injection_detector import SemanticInjectionDetector
from ..agents.appraisal import AppraisalEngine
from ..agents.proactive_manager import ProactiveManager
from ..database import DatabaseManager
from ..utils.exceptions import ChatProcessingError, SecurityThreatDetected, UserNotFoundError

# Import dependency functions from main
from ..main import (
    get_letta, get_personality, get_memory, get_users, 
    get_security, get_appraisal, get_proactive, get_db
)

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)


@router.post("/message", response_model=ChatResponse)
async def process_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    letta_service: LettaService = Depends(get_letta),
    personality_engine: PersonalityEngine = Depends(get_personality),
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users),
    security_detector: SemanticInjectionDetector = Depends(get_security),
    appraisal_engine: AppraisalEngine = Depends(get_appraisal),
    proactive_manager: ProactiveManager = Depends(get_proactive)
):
    """
    Process a user message and generate a response from the AI companion.
    This endpoint handles the full message processing pipeline including
    security checks, personality updates, memory operations, and response generation.
    """
    start_time = datetime.utcnow()
    
    try:
        # Verify user exists and is active
        user_profile = await user_service.get_user_profile(request.user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {request.user_id} not found")
        
        if user_profile.status != 'active':
            raise HTTPException(status_code=403, detail="User account is not active")
        
        # Check for security threats
        threat_analysis = await security_detector.analyze_threat(
            user_id=request.user_id, 
            message=request.message
        )
        
        if threat_analysis.threat_detected:
            logger.warning(f"Security threat detected for user {request.user_id}: {threat_analysis}")
            response = await security_detector.generate_defensive_response(
                threat_type=threat_analysis.threat_type,
                user_personality=await personality_engine.get_personality_snapshot(request.user_id)
            )
            
            # Log the security incident
            await user_service.log_security_incident(
                user_id=request.user_id,
                incident_type=threat_analysis.threat_type,
                severity=threat_analysis.severity,
                detected_content=request.message,
                confidence=threat_analysis.confidence
            )
            
            return ChatResponse(
                user_id=request.user_id,
                message_id=request.message_id,
                agent_response=response,
                security_threat_detected=threat_analysis.threat_type,
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )
        
        # Get current personality state
        personality_snapshot = await personality_engine.get_personality_snapshot(request.user_id)
        
        # Store the interaction with initial PAD state
        session_id = request.session_id or str(uuid.uuid4())
        interaction_record = InteractionRecord(
            user_id=request.user_id,
            session_id=session_id,
            user_message=request.message,
            timestamp=start_time,
            pad_before={
                "pleasure": personality_snapshot.current_pad.pleasure,
                "arousal": personality_snapshot.current_pad.arousal,
                "dominance": personality_snapshot.current_pad.dominance,
            },
            user_initiated=True
        )
        
        # Retrieve relevant memories using MMR
        relevant_memories = await memory_manager.search_with_mmr(
            user_id=request.user_id,
            query=request.message,
            k=5,
            lambda_param=0.7
        )
        
        # Calculate emotional response to user message using appraisal engine
        new_pad_state = await appraisal_engine.generate_emotional_state(
            user_message=request.message,
            current_state=personality_snapshot.current_pad,
            personality=personality_snapshot
        )

        # Calculate delta from current state to new state
        delta_pad = PADState(
            pleasure=new_pad_state.pleasure - personality_snapshot.current_pad.pleasure,
            arousal=new_pad_state.arousal - personality_snapshot.current_pad.arousal,
            dominance=new_pad_state.dominance - personality_snapshot.current_pad.dominance,
        )

        # Update personality with PAD delta
        updated_personality = await personality_engine.update_pad_state(
            user_id=request.user_id,
            delta=delta_pad,
        )
        
        # Prepare context for Letta agent
        context = {
            "personality_snapshot": personality_snapshot,
            "relevant_memories": [m.content for m in relevant_memories],
            "current_emotional_state": new_pad_state.to_emotion_octant()
        }
        
        # Generate response using Letta service
        agent_response = await letta_service.send_message(
            agent_id=user_profile.letta_agent_id,
            message=request.message,
            context=context
        )
        
        # Update the interaction record with response and final PAD state
        interaction_record.agent_response = agent_response
        interaction_record.pad_after = {
            "pleasure": updated_personality.pleasure,
            "arousal": updated_personality.arousal,
            "dominance": updated_personality.dominance,
        }
        interaction_record.emotion_before = personality_snapshot.current_pad.to_emotion_octant()
        interaction_record.emotion_after = updated_personality.to_emotion_octant()
        interaction_record.response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        interaction_record.memories_retrieved = len(relevant_memories)
        
        # Store the completed interaction
        await user_service.log_interaction(interaction_record)
        
        # Store the user's message as a memory
        await memory_manager.store_memory(
            user_id=request.user_id,
            content=request.message,
            memory_type="episodic",
            importance_score=0.5  # Default importance for conversational content
        )
        
        # Store the agent's response as a memory
        await memory_manager.store_memory(
            user_id=request.user_id,
            content=agent_response,
            memory_type="episodic",
            importance_score=0.5
        )
        
        # Schedule background tasks for proactive checks
        background_tasks.add_task(
            _check_proactive_opportunities,
            request.user_id,
            proactive_manager
        )
        
        logger.info(f"Processed message for user {request.user_id} in {(datetime.utcnow() - start_time).total_seconds() * 1000:.2f}ms")
        
        return ChatResponse(
            user_id=request.user_id,
            message_id=request.message_id,
            agent_response=agent_response,
            processing_time_ms=interaction_record.response_time_ms,
            emotional_impact={
                "pleasure": new_pad_state.pleasure,
                "arousal": new_pad_state.arousal,
                "dominance": new_pad_state.dominance,
            },
            memories_retrieved=len(relevant_memories)
        )
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {request.user_id} not found") from None
    except SecurityThreatDetected as e:
        raise HTTPException(status_code=400, detail=f"Security threat detected: {e!s}") from e
    except ChatProcessingError as e:
        logger.exception(f"Chat processing error for {request.user_id}")
        raise HTTPException(status_code=500, detail=f"Chat processing error: {e!s}") from e
    except Exception as e:
        logger.exception(f"Unexpected error processing message for {request.user_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _check_proactive_opportunities(
    user_id: str,
    proactive_manager: ProactiveManager
):
    """
    Background task to check for proactive conversation opportunities after message processing.
    """
    try:
        # Small delay to allow other operations to complete
        await asyncio.sleep(1)
        
        should_initiate = await proactive_manager.should_initiate_conversation(user_id)
        if should_initiate:
            logger.info(f"Proactive opportunity detected for user {user_id}")
            # In a real implementation, this would trigger proactive messaging
            # via the Discord bot or other channels
            
    except Exception as e:
        logger.error(f"Error in proactive check for {user_id}: {e}")


@router.post("/proactive/{user_id}", response_model=ChatResponse)
async def initiate_proactive_conversation(
    user_id: str,
    proactive_context: ProactiveContext,
    letta_service: LettaService = Depends(get_letta),
    personality_engine: PersonalityEngine = Depends(get_personality),
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users),
    proactive_manager: ProactiveManager = Depends(get_proactive)
):
    """
    Initiate a proactive conversation with a user based on context.
    This endpoint is typically called by background jobs or external triggers.
    """
    start_time = datetime.utcnow()
    
    try:
        # Verify user exists and proactive messaging is enabled
        user_profile = await user_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        if not user_profile.proactive_messaging_enabled:
            raise HTTPException(status_code=403, detail="Proactive messaging not enabled for this user")
        
        # Generate conversation starter based on context
        conversation_starter = await proactive_manager.generate_conversation_starter(
            user_id=user_id,
            trigger_reason=proactive_context.trigger_reason
        )
        
        # Get current personality state
        personality_snapshot = await personality_engine.get_personality_snapshot(user_id)
        
        # Retrieve relevant memories for context
        relevant_memories = await memory_manager.search_with_mmr(
            user_id=user_id,
            query=proactive_context.context_summary or conversation_starter,
            k=3,
            lambda_param=0.7
        )
        
        # Prepare context for Letta agent
        context = {
            "personality_snapshot": personality_snapshot,
            "relevant_memories": [m.content for m in relevant_memories],
            "current_emotional_state": personality_snapshot.current_pad.to_emotion_octant(),
            "proactive_context": proactive_context
        }
        
        # Generate response using Letta service
        agent_response = await letta_service.send_message(
            agent_id=user_profile.letta_agent_id,
            message=conversation_starter,
            context=context
        )
        
        # Log the proactive interaction
        interaction_record = InteractionRecord(
            user_id=user_id,
            session_id=f"proactive_{start_time.isoformat()}",
            user_message=conversation_starter,
            agent_response=agent_response,
            timestamp=start_time,
            pad_before={
                "pleasure": personality_snapshot.current_pad.pleasure,
                "arousal": personality_snapshot.current_pad.arousal,
                "dominance": personality_snapshot.current_pad.dominance,
            },
            pad_after={
                "pleasure": personality_snapshot.current_pad.pleasure,
                "arousal": personality_snapshot.current_pad.arousal,
                "dominance": personality_snapshot.current_pad.dominance,
            },  # No emotional change for proactive start
            is_proactive=True,
            proactive_trigger=proactive_context.trigger_reason,
            proactive_score=proactive_context.urgency_score or 0.0,
            response_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            user_initiated=False
        )
        
        await user_service.log_interaction(interaction_record)
        
        logger.info(f"Proactive conversation initiated for user {user_id}")
        
        return ChatResponse(
            user_id=user_id,
            message_id=f"proactive_{start_time.timestamp()}",
            agent_response=agent_response,
            processing_time_ms=interaction_record.response_time_ms,
            is_proactive=True,
            proactive_trigger=proactive_context.trigger_reason
        )
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error initiating proactive conversation for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session/{user_id}", response_model=Dict[str, Any])
async def get_conversation_session(
    user_id: str,
    session_id: Optional[str] = None,
    user_service: UserService = Depends(get_users)
):
    """
    Get a conversation session for a user.
    If no session_id provided, returns the most recent session.
    """
    try:
        # Verify user exists
        user_profile = await user_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get conversation history
        if session_id:
            session = await user_service.get_session_by_id(user_id, session_id)
        else:
            session = await user_service.get_most_recent_session(user_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="No conversation session found")
        
        return {
            "user_id": user_id,
            "session_id": session.get('session_id', session_id),
            "messages": session.get('messages', []),
            "session_start": session.get('start_time'),
            "session_end": session.get('end_time'),
            "message_count": len(session.get('messages', []))
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error getting session for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session/{user_id}/end", response_model=Dict[str, bool])
async def end_conversation_session(
    user_id: str,
    session_id: str,
    user_service: UserService = Depends(get_users)
):
    """
    Explicitly end a conversation session.
    This allows for proper session management and cleanup.
    """
    try:
        # Verify user exists
        user_profile = await user_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # End the session
        success = await user_service.end_session(user_id, session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found for user {user_id}")
        
        logger.info(f"Session {session_id} ended for user {user_id}")
        
        return {"success": success}
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error ending session {session_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/capabilities/{user_id}", response_model=Dict[str, Any])
async def get_user_capabilities(
    user_id: str,
    user_service: UserService = Depends(get_users),
    personality_engine: PersonalityEngine = Depends(get_personality)
):
    """
    Get the capabilities and current state available for a user's conversations.
    """
    try:
        # Verify user exists
        user_profile = await user_service.get_user_profile(user_id)
        if not user_profile:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get personality snapshot to determine capabilities
        personality = await personality_engine.get_personality_snapshot(user_id)
        
        # Determine user's conversation capabilities based on their data
        capabilities = {
            "user_id": user_id,
            "personality_model": "BigFive_PAD",
            "memory_system": True,
            "proactive_conversations": user_profile.proactive_messaging_enabled,
            "personality_evolution": True,
            "emotional_model": "PAD",
            "current_emotional_state": personality.current_pad.to_emotion_octant() if personality else "unknown",
            "memory_retrieval_enabled": True,
            "security_monitoring": True,
            "quirk_tracking": True,
            "needs_monitoring": True,
            "max_message_history": 50,
            "personality_stability": getattr(personality, "stability_score", 0.0) if personality else 0.0
        }
        
        return capabilities
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error getting capabilities for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")