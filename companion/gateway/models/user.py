"""
User profile models for the AI Companion System.

This module defines Pydantic models for representing user profiles,
preferences, and account-related information.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class UserProfile(BaseModel):
    """
    User profile model for the AI Companion System.
    """
    user_id: str = Field(
        ...,
        description="Unique identifier for the user (Discord ID)"
    )
    discord_username: str = Field(
        default="",
        description="Discord username of the user"
    )
    letta_agent_id: Optional[str] = Field(
        default=None,
        description="ID of the associated Letta agent"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the user profile was created"
    )
    last_active: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last time the user was active"
    )
    status: str = Field(
        default="active",
        description="User account status (active, inactive, banned)"
    )
    proactive_messaging_enabled: bool = Field(
        default=True,
        description="Whether proactive messaging is enabled for this user"
    )
    timezone: str = Field(
        default="UTC",
        description="User's timezone for scheduling proactive messages"
    )
    total_interactions: int = Field(
        default=0,
        ge=0,
        description="Total number of interactions with the AI"
    )
    initialization_completed: bool = Field(
        default=False,
        description="Whether user initialization is complete"
    )
    personality_initialized: bool = Field(
        default=False,
        description="Whether personality has been initialized"
    )

    class Config:
        # Allow arbitrary types for datetime
        arbitrary_types_allowed = True