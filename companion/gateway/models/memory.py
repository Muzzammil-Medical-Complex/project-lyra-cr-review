"""
Memory data models for the AI Companion System.

This module defines Pydantic models for representing episodic and semantic memories,
memory queries, and memory conflicts. These models are used by the memory management
system to store, retrieve, and maintain consistency of the AI's memories.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
import uuid


class EpisodicMemory(BaseModel):
    """
    Episodic memories: specific events and experiences that occurred at particular times.
    These represent personal experiences and conversations from the AI's perspective.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this memory"
    )
    user_id: str = Field(
        ...,
        description="ID of the user this memory belongs to"
    )
    content: str = Field(
        ...,
        description="The actual content of the memory"
    )
    memory_type: str = Field(
        default="episodic",
        description="Type of memory ('episodic' for this class)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this memory was created"
    )
    importance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How important this memory is (0.0-1.0)"
    )
    recency_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="How recent this memory is (1.0 = most recent)"
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding representation of this memory"
    )
    last_accessed: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this memory was last retrieved"
    )
    access_count: int = Field(
        default=0,
        ge=0,
        description="How many times this memory has been accessed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about this memory"
    )


class SemanticMemory(BaseModel):
    """
    Semantic memories: general knowledge, facts, and concepts abstracted from episodic memories.
    These represent consolidated knowledge derived from multiple experiences.
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this memory"
    )
    user_id: str = Field(
        ...,
        description="ID of the user this memory belongs to"
    )
    content: str = Field(
        ...,
        description="The actual content of the memory"
    )
    memory_type: str = Field(
        default="semantic",
        description="Type of memory ('semantic' for this class)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this memory was created"
    )
    importance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How important this memory is (0.0-1.0)"
    )
    recency_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="How recent this memory is (1.0 = most recent)"
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding representation of this memory"
    )
    last_accessed: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this memory was last retrieved"
    )
    access_count: int = Field(
        default=0,
        ge=0,
        description="How many times this memory has been accessed"
    )
    source_memory_ids: List[str] = Field(
        default_factory=list,
        description="IDs of episodic memories that contributed to this semantic memory"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in the accuracy of this consolidated knowledge (0.0-1.0)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about this memory"
    )


class MemoryQuery(BaseModel):
    """
    Query object for searching memories in the memory system.
    """
    user_id: str = Field(
        ...,
        description="ID of the user whose memories to search"
    )
    query_text: str = Field(
        ...,
        alias="text",
        description="Text to search for in memories"
    )
    query_embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding of the query text (computed if not provided)"
    )
    memory_type: Optional[str] = Field(
        default=None,
        description="Type of memory to search ('episodic', 'semantic', or None for both)"
    )
    k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of memories to retrieve (1-50)"
    )
    similarity_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for returned memories"
    )
    time_filter_hours: Optional[int] = Field(
        default=None,
        description="Only return memories created within this many hours (if specified)"
    )
    time_range_start: Optional[datetime] = Field(
        default=None,
        description="Start of time range filter (inclusive)"
    )
    time_range_end: Optional[datetime] = Field(
        default=None,
        description="End of time range filter (inclusive)"
    )
    min_importance: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum importance score filter (0.0-1.0)"
    )
    lambda_param: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="MMR lambda parameter balancing relevance vs diversity (0.0 = max diversity, 1.0 = max relevance)"
    )
    metadata_filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata filters to apply to the search"
    )
    include_embeddings: bool = Field(
        default=False,
        description="Whether to include embeddings in the returned memories"
    )


class MemoryConflict(BaseModel):
    """
    Represents a conflict between two memories (e.g., contradictory information).
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this conflict"
    )
    user_id: str = Field(
        ...,
        description="ID of the user this conflict belongs to"
    )
    conflict_type: str = Field(
        ...,
        description="Type of conflict ('factual_contradiction', 'timeline_inconsistency', 'preference_conflict', etc.)"
    )
    description: str = Field(
        ...,
        description="Description of the conflict"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that this is a real conflict (0.0-1.0)"
    )
    primary_memory_id: str = Field(
        ...,
        description="ID of the primary memory involved in the conflict"
    )
    conflicting_memory_id: str = Field(
        ...,
        description="ID of the conflicting memory"
    )
    related_memory_ids: List[str] = Field(
        default_factory=list,
        description="Additional related memories involved in the conflict"
    )
    status: str = Field(
        default="detected",
        description="Status of the conflict ('detected', 'investigating', 'resolved', 'ignored')"
    )
    resolution_method: Optional[str] = Field(
        default=None,
        description="Method used to resolve the conflict (if resolved)"
    )
    resolution_notes: Optional[str] = Field(
        default=None,
        description="Notes about how the conflict was resolved"
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the conflict was first detected"
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        description="When the conflict was resolved (if resolved)"
    )
    conversation_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Context in which the conflict was discovered"
    )
    user_notified: bool = Field(
        default=False,
        description="Whether the user was notified about this conflict"
    )


class MemoryTheme(BaseModel):
    """
    Represents a thematic pattern identified across multiple memories.
    Used by the reflection agent to consolidate memories.
    """
    theme_name: str = Field(
        ...,
        description="Name of the identified theme"
    )
    description: str = Field(
        ...,
        description="Description of what this theme represents"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the theme identification (0.0-1.0)"
    )
    related_memory_ids: List[str] = Field(
        default_factory=list,
        description="IDs of memories that belong to this theme"
    )
    temporal_span_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Time span in hours that this theme covers"
    )
    importance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall importance of this theme (0.0-1.0)"
    )


class ConsolidationResult(BaseModel):
    """
    Result of memory consolidation process performed by reflection agent.
    """
    user_id: str = Field(
        ...,
        description="User ID for whom consolidation was performed"
    )
    status: str = Field(
        default="success",
        description="Status of the consolidation ('success', 'partial', 'failed')"
    )
    identified_themes: List[MemoryTheme] = Field(
        default_factory=list,
        description="Themes identified during consolidation"
    )
    consolidated_memories: List[str] = Field(
        default_factory=list,
        description="IDs of memories that were consolidated"
    )
    consolidation_count: int = Field(
        default=0,
        ge=0,
        description="Number of memories successfully consolidated"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during consolidation"
    )

    def add_consolidation_error(self, theme: str, error: str):
        """Add an error that occurred during theme consolidation."""
        self.errors.append(f"Theme '{theme}': {error}")


# Type alias for generic Memory (can be either episodic or semantic)
Memory = Union[EpisodicMemory, SemanticMemory]


class MemorySearchResult(BaseModel):
    """
    Result from a memory search operation, including the memory and its similarity score.
    """
    memory: Memory = Field(
        ...,
        description="The memory object (episodic or semantic)"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between query and memory (0.0-1.0)"
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Combined relevance score from MMR algorithm (0.0-1.0)"
    )


class ConsolidationBatch(BaseModel):
    """
    Result of a batch memory consolidation operation.
    """
    original_memory_ids: List[str] = Field(
        default_factory=list,
        description="IDs of original episodic memories that were consolidated"
    )
    consolidated_memory_ids: List[str] = Field(
        default_factory=list,
        description="IDs of resulting semantic memories after consolidation"
    )
    consolidation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the consolidation occurred"
    )