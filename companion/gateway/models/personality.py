"""
Personality data models for the AI Companion System.

This module defines Pydantic models for representing personality traits,
emotional states, quirks, and psychological needs. These models are used
to maintain and evolve the AI companion's personality over time.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class BigFiveTraits(BaseModel):
    """
    The Big Five personality traits (OCEAN model).
    These traits are FIXED and should NOT change after initial personality creation.
    """
    openness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="FIXED trait - never changes after creation (0.0-1.0)"
    )
    conscientiousness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="FIXED trait - never changes after creation (0.0-1.0)"
    )
    extraversion: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="FIXED trait - never changes after creation (0.0-1.0)"
    )
    agreeableness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="FIXED trait - never changes after creation (0.0-1.0)"
    )
    neuroticism: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="FIXED trait - never changes after creation (0.0-1.0)"
    )


class PADState(BaseModel):
    """
    PAD Emotional State Model.
    P = Pleasure (positive/negative emotional valence)
    A = Arousal (emotional intensity/activation)
    D = Dominance (feeling of control/submission)
    These values fluctuate dynamically based on interactions.
    """
    pleasure: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Positive/negative emotional valence (-1.0 to 1.0)"
    )
    arousal: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Emotional intensity/activation (-1.0 to 1.0)"
    )
    dominance: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Feeling of control/submission (-1.0 to 1.0)"
    )
    
    pad_baseline: Optional['PADState'] = Field(
        default=None,
        description="Long-term PAD baseline that drifts over time"
    )
    emotion_label: Optional[str] = Field(
        default=None,
        description="Computed emotion label from PAD values"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this state was recorded"
    )

    def to_emotion_octant(self) -> str:
        """
        Map PAD coordinates to 8 basic emotions based on octant position.
        
        Returns:
            str: The emotion label corresponding to the current PAD state
        """
        p, a, d = self.pleasure > 0, self.arousal > 0, self.dominance > 0
        mapping = {
            (True, True, True): "exuberant",
            (True, True, False): "bored",
            (True, False, True): "relaxed",
            (True, False, False): "sleepy",
            (False, True, True): "anxious",
            (False, True, False): "stressed",
            (False, False, True): "calm",
            (False, False, False): "depressed"
        }
        return mapping.get((p, a, d), "neutral")


class Quirk(BaseModel):
    """
    Behavioral patterns, speech quirks, and preferences that evolve over time.
    """
    id: Optional[str] = Field(
        default=None,
        description="Unique identifier for the quirk"
    )
    user_id: str = Field(
        ...,
        description="ID of the user this quirk belongs to"
    )
    name: str = Field(
        ...,
        max_length=100,
        description="Unique name identifying the quirk"
    )
    category: str = Field(
        ...,
        pattern=r"^(speech_pattern|behavior|preference)$",
        description="Category of the quirk"
    )
    description: str = Field(
        ...,
        description="Detailed description of the quirk"
    )
    strength: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="How strongly this quirk is expressed (0.0-1.0)"
    )
    confidence: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="How confident we are this is a real pattern (0.0-1.0)"
    )
    decay_rate: float = Field(
        default=0.05,
        ge=0.01,
        le=0.2,
        description="How quickly the quirk fades without reinforcement"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this quirk is currently active"
    )
    examples: List[str] = Field(
        default_factory=list,
        max_items=5,
        description="Examples of interactions that demonstrate this quirk"
    )
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate that the quirk name is properly formatted."""
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError("Quirk name must contain only lowercase letters, numbers, and underscores")
        return v


class PsychologicalNeed(BaseModel):
    """
    Psychological needs with decay and satisfaction mechanics.
    """
    need_type: str = Field(
        ...,
        pattern=r"^(social|intellectual|creative|rest|validation)$",
        description="Type of psychological need"
    )
    current_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Current level of satisfaction for this need (0.0-1.0)"
    )
    baseline_level: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Baseline level of this need (0.0-1.0)"
    )
    decay_rate: float = Field(
        default=0.02,
        ge=0.005,
        le=0.05,
        description="How quickly the need increases per hour"
    )
    trigger_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=0.95,
        description="When need becomes urgent for proactive conversation (0.5-0.95)"
    )
    satisfaction_rate: float = Field(
        default=0.1,
        ge=0.05,
        le=0.3,
        description="How much interaction satisfies this need (0.05-0.3)"
    )
    
    @field_validator('need_type')
    def validate_need_type(cls, v):
        """Validate that the need type is one of the allowed values."""
        allowed_types = ['social', 'intellectual', 'creative', 'rest', 'validation']
        if v not in allowed_types:
            raise ValueError(f"need_type must be one of {allowed_types}")
        return v


class PersonalitySnapshot(BaseModel):
    """
    Complete snapshot of a user's personality state at a specific time.
    """
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Fixed Big Five traits (don't change over time)
    big_five: BigFiveTraits
    
    # Dynamic PAD emotional state
    current_pad: PADState
    pad_baseline: PADState
    
    # Evolving personality components
    active_quirks: List[Quirk] = Field(default_factory=list)
    psychological_needs: List[PsychologicalNeed] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class QuirkEvolutionResult(BaseModel):
    """
    Result of quirk evolution process performed by reflection agent.
    """
    user_id: str = Field(
        ...,
        description="User ID for whom quirk evolution was performed"
    )
    status: str = Field(
        default="success",
        description="Status of the evolution ('success', 'partial', 'failed')"
    )
    quirk_updates: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of quirk updates with before/after values"
    )
    total_quirks_processed: int = Field(
        default=0,
        ge=0,
        description="Total number of quirks processed"
    )
    quirks_strengthened: int = Field(
        default=0,
        ge=0,
        description="Number of quirks that were strengthened"
    )
    quirks_weakened: int = Field(
        default=0,
        ge=0,
        description="Number of quirks that were weakened"
    )


class PersonalityEvolutionResult(BaseModel):
    """
    Complete result of personality evolution including PAD drift and quirk evolution.
    """
    user_id: str = Field(
        ...,
        description="User ID for whom personality evolution was performed"
    )
    status: str = Field(
        default="success",
        description="Status of the evolution ('success', 'partial', 'failed')"
    )
    behavioral_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Analysis of behavioral patterns from interactions"
    )
    pad_drift_applied: Dict[str, float] = Field(
        default_factory=dict,
        description="PAD baseline drift that was applied (pleasure, arousal, dominance)"
    )
    quirk_evolution: Optional[QuirkEvolutionResult] = Field(
        default=None,
        description="Result of quirk evolution process"
    )
    needs_update: Dict[str, float] = Field(
        default_factory=dict,
        description="Updates to psychological needs baselines"
    )
    stability_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metrics about personality stability over time"
    )