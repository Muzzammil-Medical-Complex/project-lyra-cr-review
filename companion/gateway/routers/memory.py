"""
Memory router for the AI Companion System.
Provides API endpoints for searching, storing, and managing episodic and semantic memories.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from ..models.memory import (
    Memory, MemorySearchResult, MemoryQuery, MemoryConflict, 
    EpisodicMemory, SemanticMemory, ConsolidationBatch
)
from ..services.memory_manager import MemoryManager
from ..services.user_service import UserService
from ..database import DatabaseManager
from ..utils.exceptions import MemoryManagerError, UserNotFoundError

# Import dependency functions from main
from ..main import get_memory, get_users, get_db, get_personality

router = APIRouter(prefix="/memory", tags=["memory"])

logger = logging.getLogger(__name__)


@router.post("/search/{user_id}", response_model=List[MemorySearchResult])
async def search_memories(
    user_id: str,
    query: MemoryQuery,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Search for memories using semantic search and MMR ranking.
    Supports filtering by memory type, time range, and importance.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Perform memory search
        results = await memory_manager.search_with_mmr(
            user_id=user_id,
            query=query.text,
            k=query.k or 5,
            memory_type=query.memory_type,
            time_range_start=query.time_range_start,
            time_range_end=query.time_range_end,
            min_importance=query.min_importance,
            lambda_param=query.lambda_param or 0.7
        )
        
        return results
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error searching memories for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/episodic/{user_id}", response_model=List[EpisodicMemory])
async def get_episodic_memories(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Get episodic memories for a user with pagination.
    Episodic memories are specific events or conversations from the user's experience.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get episodic memories
        memories = await memory_manager.get_memories_by_type(
            user_id=user_id,
            memory_type="episodic",
            limit=limit,
            offset=offset
        )
        
        return memories
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting episodic memories for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/semantic/{user_id}", response_model=List[SemanticMemory])
async def get_semantic_memories(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Get semantic memories for a user with pagination.
    Semantic memories are general knowledge, facts, and patterns extracted from episodic memories.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get semantic memories
        memories = await memory_manager.get_memories_by_type(
            user_id=user_id,
            memory_type="semantic",
            limit=limit,
            offset=offset
        )
        
        return memories
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting semantic memories for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/store/{user_id}", response_model=str)
async def store_memory(
    user_id: str,
    memory: Memory,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Store a new memory for a user.
    Automatically determines if it should be episodic or semantic based on content and context.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Store memory
        memory_id = await memory_manager.store_memory(
            user_id=user_id,
            content=memory.content,
            memory_type=memory.memory_type or "episodic",
            importance_score=memory.importance_score,
            metadata=memory.metadata or {}
        )
        
        logger.info(f"Memory stored for user {user_id}: {memory_id}")
        
        return memory_id
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error storing memory for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/by_id/{user_id}/{memory_id}", response_model=Memory)
async def get_memory_by_id(
    user_id: str,
    memory_id: str,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Get a specific memory by its ID.
    Verifies that the memory belongs to the specified user.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get memory by ID
        memory = await memory_manager.get_memory_by_id(
            user_id=user_id,
            memory_id=memory_id
        )
        
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found for user {user_id}")
        
        return memory
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting memory {memory_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/update/{user_id}/{memory_id}", response_model=bool)
async def update_memory(
    user_id: str,
    memory_id: str,
    memory: Memory,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Update an existing memory's content, importance, or metadata.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Update memory
        success = await memory_manager.update_memory(
            user_id=user_id,
            memory_id=memory_id,
            content=memory.content,
            importance_score=memory.importance_score,
            metadata=memory.metadata
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found for user {user_id}")
        
        logger.info(f"Memory updated for user {user_id}: {memory_id}")
        
        return success
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating memory {memory_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/delete/{user_id}/{memory_id}", response_model=bool)
async def delete_memory(
    user_id: str,
    memory_id: str,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Delete a memory by its ID.
    Also removes it from vector storage and updates any related references.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Delete memory
        success = await memory_manager.delete_memory(
            user_id=user_id,
            memory_id=memory_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found for user {user_id}")
        
        logger.info(f"Memory deleted for user {user_id}: {memory_id}")
        
        return success
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/consolidate/{user_id}", response_model=ConsolidationBatch)
async def consolidate_memories(
    user_id: str,
    memory_ids: List[str],
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Consolidate multiple episodic memories into a single semantic memory.
    This is typically used during the nightly reflection process.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get the memories to consolidate
        memories_to_consolidate = []
        for memory_id in memory_ids:
            memory = await memory_manager.get_memory_by_id(user_id, memory_id)
            if memory:
                memories_to_consolidate.append(memory)
        
        if len(memories_to_consolidate) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 memories to consolidate")
        
        # Perform consolidation
        consolidated_memories = await memory_manager.consolidate_episodic_to_semantic(
            user_id=user_id,
            episodic_memories=memories_to_consolidate
        )
        
        logger.info(f"Consolidated {len(memories_to_consolidate)} memories for user {user_id}")
        
        return ConsolidationBatch(
            original_memory_ids=memory_ids,
            consolidated_memory_ids=[m.id for m in consolidated_memories],
            consolidation_timestamp=datetime.utcnow()
        )
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error consolidating memories for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conflicts/{user_id}", response_model=List[MemoryConflict])
async def get_memory_conflicts(
    user_id: str,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Get memory conflicts for a user.
    Memory conflicts occur when there are contradictory or inconsistent memories.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get memory conflicts
        conflicts = await memory_manager.get_memory_conflicts(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return conflicts
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting memory conflicts for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/resolve_conflict/{user_id}/{conflict_id}", response_model=bool)
async def resolve_memory_conflict(
    user_id: str,
    conflict_id: str,
    resolution_method: str,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Resolve a memory conflict using a specified method.
    Methods: 'temporal_precedence', 'confidence_based', 'user_clarification', 'ignore'
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        valid_methods = ["temporal_precedence", "confidence_based", "user_clarification", "ignore"]
        if resolution_method not in valid_methods:
            raise HTTPException(status_code=400, detail=f"Invalid resolution method. Valid methods: {valid_methods}")
        
        # Resolve conflict
        success = await memory_manager.resolve_conflict(
            user_id=user_id,
            conflict_id=conflict_id,
            resolution_method=resolution_method
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Memory conflict {conflict_id} not found for user {user_id}")
        
        logger.info(f"Memory conflict resolved for user {user_id}: {conflict_id} using {resolution_method}")
        
        return success
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error resolving memory conflict {conflict_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/{user_id}", response_model=Dict[str, Any])
async def get_memory_stats(
    user_id: str,
    memory_manager: MemoryManager = Depends(get_memory),
    user_service: UserService = Depends(get_users)
):
    """
    Get memory statistics for a user.
    Includes counts, average importance, and other metrics.
    """
    try:
        # Verify user exists
        user = await user_service.get_user_profile(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        # Get memory statistics
        stats = await memory_manager.get_memory_stats(user_id)
        
        return {
            "user_id": user_id,
            "stats": stats,
            "timestamp": datetime.utcnow()
        }
        
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    except MemoryManagerError as e:
        raise HTTPException(status_code=500, detail=f"Memory manager error: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting memory stats for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")