"""
Interaction data models for the AI Companion System.

This module defines Pydantic models for representing user messages,
agent responses, proactive contexts, and interaction logs. These models
are used to track and analyze the conversations between users and the AI.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class UserMessage(BaseModel):
    """
    Represents a message sent by a user to the AI companion.
    """
    user_id: str = Field(
        ...,
        description="ID of the user who sent the message"
    )
    message: str = Field(
        ...,
        description="The content of the user's message"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the message was sent"
    )
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="ID of the conversation session"
    )
    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this specific message"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the message"
    )


class AgentResponse(BaseModel):
    """
    Represents a response from the AI companion to the user.
    """
    response: str = Field(
        ...,
        description="The content of the AI's response"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the response was generated"
    )
    session_id: str = Field(
        ...,
        description="ID of the conversation session"
    )
    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this response message"
    )
    response_time_ms: Optional[int] = Field(
        default=None,
        description="Time taken to generate the response in milliseconds"
    )
    token_count: Optional[int] = Field(
        default=None,
        description="Number of tokens in the response"
    )
    llm_model_used: Optional[str] = Field(
        default=None,
        description="Which language model was used to generate the response"
    )
    emotion_before: Optional[str] = Field(
        default=None,
        description="Emotional state of the AI before generating the response"
    )
    emotion_after: Optional[str] = Field(
        default=None,
        description="Emotional state of the AI after generating the response"
    )
    memories_retrieved: int = Field(
        default=0,
        ge=0,
        description="Number of memories retrieved during response generation"
    )
    personality_influence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="How the AI's personality influenced the response"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response"
    )


class ProactiveContext(BaseModel):
    """
    Context information for proactive conversation initiation.
    """
    user_id: str = Field(
        ...,
        description="ID of the user for whom conversation is considered"
    )
    trigger_reason: str = Field(
        ...,
        description="Reason for considering proactive conversation"
    )
    urgency_score: float = Field(
        ge=0.0,
        le=1.0,
        description="How urgent the proactive conversation is (0.0-1.0)"
    )
    optimal_time: Optional[datetime] = Field(
        default=None,
        description="Suggested optimal time for the proactive conversation"
    )
    context_summary: Optional[str] = Field(
        default=None,
        description="Summary of the context for the proactive message"
    )
    needs_to_address: List[str] = Field(
        default_factory=list,
        description="Psychological needs that could be addressed"
    )
    relevant_memories: List[str] = Field(
        default_factory=list,
        description="Relevant memories to reference in the proactive message"
    )
    personality_factors: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Personality factors that influence proactive approach"
    )
    timing_factors: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Timing factors considered for proactive conversation"
    )


class InteractionLog(BaseModel):
    """
    Log of a complete user-agent interaction, including context and outcomes.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this interaction log"
    )
    user_id: str = Field(
        ...,
        description="ID of the user involved in the interaction"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the interaction occurred"
    )
    session_id: str = Field(
        ...,
        description="ID of the conversation session"
    )
    user_message: UserMessage = Field(
        ...,
        description="The user's message in this interaction"
    )
    agent_response: AgentResponse = Field(
        ...,
        description="The agent's response in this interaction"
    )
    pad_before: Optional[Dict[str, float]] = Field(
        default=None,
        description="PAD emotional state before the interaction"
    )
    pad_after: Optional[Dict[str, float]] = Field(
        default=None,
        description="PAD emotional state after the interaction"
    )
    emotion_before: Optional[str] = Field(
        default=None,
        description="Emotional label before the interaction"
    )
    emotion_after: Optional[str] = Field(
        default=None,
        description="Emotional label after the interaction"
    )
    response_time_ms: Optional[int] = Field(
        default=None,
        description="Time taken to generate the response in milliseconds"
    )
    token_count: Optional[int] = Field(
        default=None,
        description="Number of tokens used in the exchange"
    )
    llm_model_used: Optional[str] = Field(
        default=None,
        description="Language model used for this interaction"
    )
    is_proactive: bool = Field(
        default=False,
        description="Whether this was a proactive interaction initiated by the AI"
    )
    proactive_trigger: Optional[str] = Field(
        default=None,
        description="What triggered the proactive conversation (if applicable)"
    )
    proactive_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Score of the proactive decision (if applicable)"
    )
    memories_retrieved: int = Field(
        default=0,
        ge=0,
        description="Number of memories retrieved during the interaction"
    )
    memories_stored: int = Field(
        default=0,
        ge=0,
        description="Number of memories stored during the interaction"
    )
    error_occurred: bool = Field(
        default=False,
        description="Whether an error occurred during the interaction"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Description of the error if one occurred"
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether a fallback response was used"
    )
    security_check_passed: bool = Field(
        default=True,
        description="Whether the interaction passed security checks"
    )
    security_threat_detected: Optional[str] = Field(
        default=None,
        description="Type of security threat detected (if any)"
    )
    user_initiated: bool = Field(
        default=True,
        description="Whether the interaction was initiated by the user"
    )
    conversation_length: int = Field(
        default=1,
        ge=1,
        description="Number of messages in this conversation so far"
    )
    user_satisfaction_implied: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Implied user satisfaction with the interaction (0.0-1.0)"
    )
    interaction_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the interaction"
    )


class EmotionalImpact(BaseModel):
    """
    Represents the emotional impact of an interaction on the AI's state.
    """
    pleasure_delta: float = Field(
        0.0,
        ge=-1.0,
        le=1.0,
        description="Change in pleasure dimension (-1.0 to 1.0)"
    )
    arousal_delta: float = Field(
        0.0,
        ge=-1.0,
        le=1.0,
        description="Change in arousal dimension (-1.0 to 1.0)"
    )
    dominance_delta: float = Field(
        0.0,
        ge=-1.0,
        le=1.0,
        description="Change in dominance dimension (-1.0 to 1.0)"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the emotional impact assessment"
    )


class InteractionRecord(BaseModel):
    """
    Complete record of a conversation interaction for database storage.
    """
    user_id: str
    session_id: str
    user_message: str
    agent_response: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pad_before: Optional[Dict[str, float]] = None
    pad_after: Optional[Dict[str, float]] = None
    emotion_before: Optional[str] = None
    emotion_after: Optional[str] = None
    is_proactive: bool = False
    proactive_trigger: Optional[str] = None
    proactive_score: Optional[float] = None
    response_time_ms: float = 0
    memories_retrieved: int = 0
    user_initiated: bool = True
    conversation_length: int = 1


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    user_id: str
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    user_id: str
    message_id: str
    agent_response: str
    processing_time_ms: float
    emotional_impact: Optional[Dict[str, float]] = None
    memories_retrieved: int = 0
    is_proactive: bool = False
    proactive_trigger: Optional[str] = None
    security_threat_detected: Optional[str] = None