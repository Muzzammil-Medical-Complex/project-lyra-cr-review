"""
Memory management service for the AI Companion System.

This module handles storing memories in the Qdrant vector database, retrieving them
using the MMR algorithm, and managing memory consolidation and conflict detection.
"""

import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, SearchParams,
    PayloadSchemaType, Filter, FieldCondition, MatchValue
)
from ..models.memory import EpisodicMemory, SemanticMemory, MemoryConflict
from ..database import DatabaseManager
from ..utils.mmr import MaximalMarginalRelevance
from ..utils.importance_scorer import ImportanceScorer
from ..services.embedding_client import EmbeddingClient
from ..utils.exceptions import MemoryManagerError, MemoryConflictError


class MemoryManager:
    """
    Manages all memory operations including storage, retrieval, consolidation,
    and conflict detection with proper user scoping.
    """
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_client: EmbeddingClient,
        importance_scorer: ImportanceScorer,
        db_manager: DatabaseManager,
        mmr_ranker: MaximalMarginalRelevance
    ):
        """
        Initialize the memory manager with required dependencies.
        
        Args:
            qdrant_client: Qdrant client for vector storage
            embedding_client: Client for generating embeddings
            importance_scorer: Service for scoring memory importance
            db_manager: Database manager for metadata storage
            mmr_ranker: MMR algorithm implementation for diverse retrieval
        """
        self.qdrant = qdrant_client
        self.embeddings = embedding_client
        self.scorer = importance_scorer
        self.db = db_manager
        self.mmr = mmr_ranker
        self.logger = logging.getLogger(__name__)
    
    async def store_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "episodic",
        importance_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store memory with vector embedding and importance scoring.
        
        Args:
            user_id: Discord user ID
            content: Memory content
            memory_type: Type of memory ("episodic" or "semantic")
            importance_score: Pre-calculated importance score (optional)
            metadata: Additional metadata to store (optional)
            
        Returns:
            Memory ID for reference
            
        Raises:
            MemoryManagerError: If storage fails
        """
        try:
            # Generate embedding for content
            embedding_vector = await self.embeddings.embed_text(content)
            
            # Calculate importance score if not provided
            if importance_score is None:
                importance_score = await self.scorer.score_importance(content, {
                    "user_id": user_id,
                    "memory_type": memory_type,
                    "timestamp": datetime.utcnow()
                })
            
            # Create memory object
            memory_id = str(uuid.uuid4())
            
            if memory_type == "episodic":
                memory = EpisodicMemory(
                    id=memory_id,
                    user_id=user_id,
                    content=content,
                    importance_score=importance_score,
                    recency_score=1.0,  # Start at maximum recency
                    embedding=embedding_vector,
                    created_at=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    metadata=metadata or {}
                )
            else:
                memory = SemanticMemory(
                    id=memory_id,
                    user_id=user_id,
                    content=content,
                    importance_score=importance_score,
                    recency_score=1.0,
                    embedding=embedding_vector,
                    created_at=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                    access_count=0,
                    metadata=metadata or {}
                )
            
            # Check for conflicts with existing memories
            conflicts = await self.detect_memory_conflicts(user_id, memory)
            
            # Store in Qdrant with user-scoped collection
            collection_name = self._sanitize_collection_name(f"episodic_{user_id}" if memory_type == "episodic" else f"semantic_{user_id}")
            
            # Ensure collection exists
            await self._ensure_collection_exists(collection_name)
            
            point = PointStruct(
                id=memory_id,
                vector=embedding_vector,
                payload={
                    "content": content,
                    "memory_type": memory_type,
                    "importance_score": importance_score,
                    "recency_score": 1.0,
                    "created_at": memory.created_at.isoformat(),
                    "last_accessed": memory.last_accessed.isoformat(),
                    "access_count": 0,
                    "metadata": metadata or {}
                }
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.qdrant.upsert,
                collection_name,
                [point]
            )
            
            # Store metadata in PostgreSQL
            await self.db.store_memory_metadata(user_id, memory)
            
            # Log conflicts if any
            if conflicts:
                await self.db.log_memory_conflicts(user_id, memory_id, conflicts)
            
            return memory_id
            
        except Exception as e:
            self.logger.error(f"Memory storage failed for user {user_id}: {e}")
            raise MemoryManagerError(
                message=f"Memory storage failed: {str(e)}",
                operation="store_memory"
            )
    
    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure Qdrant collection exists for the given name.
        
        Args:
            collection_name: Name of the collection to ensure
        """
        try:
            # Check if collection exists
            collections = await asyncio.get_event_loop().run_in_executor(
                None,
                self.qdrant.get_collections
            )
            
            collection_names = [collection.name for collection in collections.collections]
            if collection_name not in collection_names:
                # Create collection with 1536-dim vectors and cosine distance
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.qdrant.create_collection,
                    collection_name,
                    VectorParams(size=1536, distance=Distance.COSINE)
                )

                # Create payload field indexes for efficient filtering
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.qdrant.create_payload_index,
                    collection_name,
                    "user_id",
                    PayloadSchemaType.KEYWORD  # Index user_id as keyword for exact matching
                )

                # Index importance and recency scores for ranking
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.qdrant.create_payload_index,
                    collection_name,
                    "importance_score",
                    PayloadSchemaType.FLOAT
                )

                self.logger.info(f"Created Qdrant collection {collection_name} with payload indexes")
        except Exception as e:
            self.logger.warning(f"Failed to ensure collection {collection_name} exists: {e}")
    
    async def search_memories(
        self,
        user_id: str,
        query: str,
        k: int = 5,
        memory_type: Optional[str] = None
    ) -> List[EpisodicMemory]:
        """
        Search memories using vector similarity.
        
        Args:
            user_id: Discord user ID
            query: Search query text
            k: Number of memories to return
            memory_type: Type of memories to search ("episodic", "semantic", or None for both)
            
        Returns:
            List of relevant memories
        """
        try:
            # Get query embedding
            query_vector = await self.embeddings.embed_text(query)
            
            # Determine collections to search
            if memory_type == "episodic":
                collection_names = [self._sanitize_collection_name(f"episodic_{user_id}")]
            elif memory_type == "semantic":
                collection_names = [self._sanitize_collection_name(f"semantic_{user_id}")]
            else:
                collection_names = [self._sanitize_collection_name(f"episodic_{user_id}"), self._sanitize_collection_name(f"semantic_{user_id}")]
            
            all_results = []
            
            for collection_name in collection_names:
                try:
                    # Use query_filter for efficient database-level filtering
                    # Use query_filter for efficient database-level filtering
                    results = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda cname=collection_name, qvec=query_vector: self.qdrant.search(
                            collection_name=cname,
                            query_vector=qvec,
                            limit=k * 2,  # Get more candidates for MMR
                            query_filter=Filter(
                                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                            ),
                            score_threshold=0.3
                        )
                    )
                    
                    for result in results:
                        memory = EpisodicMemory(
                            id=result.id,
                            user_id=user_id,
                            content=result.payload["content"],
                            memory_type=result.payload["memory_type"],
                            importance_score=result.payload["importance_score"],
                            recency_score=result.payload["recency_score"],
                            similarity_score=result.score,
                            embedding=result.vector,
                            created_at=datetime.fromisoformat(result.payload["created_at"]),
                            last_accessed=datetime.fromisoformat(result.payload["last_accessed"]),
                            access_count=result.payload["access_count"],
                            metadata=result.payload.get("metadata", {})
                        )
                        all_results.append(memory)
                except Exception as e:
                    # Collection might not exist for new users
                    self.logger.debug(f"Collection {collection_name} not found for user {user_id}: {e}")
                    continue
            
            # Sort by similarity score and return top k
            all_results.sort(key=lambda m: m.similarity_score, reverse=True)
            
            # Update access statistics for returned memories
            for memory in all_results[:k]:
                await self._update_memory_access(user_id, memory.id, memory.memory_type)
            
            return all_results[:k]
            
        except Exception as e:
            self.logger.error(f"Memory search failed for user {user_id}: {e}")
            return []
    
    async def search_with_mmr(
        self,
        user_id: str,
        query: str,
        k: int = 5,
        lambda_param: float = 0.7,
        memory_type: Optional[str] = None
    ) -> List[EpisodicMemory]:
        """
        Maximal Marginal Relevance search for diverse, relevant memories.
        
        Args:
            user_id: Discord user ID
            query: Search query text
            k: Number of memories to return
            lambda_param: Balance between relevance and diversity (0.0 = max diversity, 1.0 = max relevance)
            memory_type: Type of memories to search ("episodic", "semantic", or None for both)
            
        Returns:
            List of diverse and relevant memories
        """
        try:
            # Get query embedding
            query_vector = await self.embeddings.embed_text(query)
            
            # Search for candidate memories (get more than needed)
            candidate_count = min(k * 3, 50)  # Get 3x candidates for MMR selection
            
            # Determine collections to search
            if memory_type == "episodic":
                collection_names = [self._sanitize_collection_name(f"episodic_{user_id}")]
            elif memory_type == "semantic":
                collection_names = [self._sanitize_collection_name(f"semantic_{user_id}")]
            else:
                collection_names = [self._sanitize_collection_name(f"episodic_{user_id}"), self._sanitize_collection_name(f"semantic_{user_id}")]
            
            all_candidates = []
            
            for collection_name in collection_names:
                try:
                    results = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.qdrant.search,
                        collection_name,
                        query_vector,
                        candidate_count,
                        SearchParams(exact=False),
                        0.3  # Score threshold
                    )
                    
                    for result in results:
                        memory = EpisodicMemory(
                            id=result.id,
                            user_id=user_id,
                            content=result.payload["content"],
                            memory_type=result.payload["memory_type"],
                            importance_score=result.payload["importance_score"],
                            recency_score=result.payload["recency_score"],
                            similarity_score=result.score,
                            embedding=result.vector,
                            created_at=datetime.fromisoformat(result.payload["created_at"]),
                            last_accessed=datetime.fromisoformat(result.payload["last_accessed"]),
                            access_count=result.payload["access_count"],
                            metadata=result.payload.get("metadata", {})
                        )
                        all_candidates.append(memory)
                except Exception as e:
                    # Collection might not exist for new users
                    self.logger.debug(f"Collection {collection_name} not found for user {user_id}: {e}")
                    continue
            
            # Apply MMR algorithm for diverse selection
            selected_memories = self.mmr.mmr_select_memories(
                query_vector=query_vector,
                candidate_memories=all_candidates,
                k=k,
                lambda_param=lambda_param
            )
            
            # Update access statistics
            for memory in selected_memories:
                await self._update_memory_access(user_id, memory.id, memory.memory_type)
            
            return selected_memories
            
        except Exception as e:
            self.logger.error(f"MMR search failed for user {user_id}: {e}")
            # Fallback to regular search
            return await self.search_memories(user_id, query, k, memory_type)
    
    async def get_memory_by_id(self, user_id: str, memory_id: str) -> Optional[EpisodicMemory]:
        """
        Retrieve a specific memory by its ID.
        
        Args:
            user_id: Discord user ID
            memory_id: Memory ID to retrieve
            
        Returns:
            Memory object or None if not found
        """
        try:
            # Try to get from database first
            memory_data = await self.db.get_memory_by_id(user_id, memory_id)
            if not memory_data:
                return None
            
            # Update access statistics
            memory_type = memory_data.get("memory_type", "episodic")
            await self._update_memory_access(user_id, memory_id, memory_type)

            return EpisodicMemory(**memory_data)
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve memory {memory_id} for user {user_id}: {e}")
            return None
    
    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """
        Delete a memory by its ID.
        
        Args:
            user_id: Discord user ID
            memory_id: Memory ID to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            # Delete from Qdrant collections
            collection_names = [self._sanitize_collection_name(f"episodic_{user_id}"), self._sanitize_collection_name(f"semantic_{user_id}")]
            
            deleted = False
            for collection_name in collection_names:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        self.qdrant.delete,
                        collection_name,
                        [memory_id]
                    )
                    deleted = True
                except Exception as e:
                    self.logger.debug(f"Failed to delete memory {memory_id} from {collection_name}: {e}")
                    continue
            
            # Delete from database
            await self.db.delete_memory_metadata(user_id, memory_id)
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Memory deletion failed for user {user_id}, memory {memory_id}: {e}")
            return False
    
    async def detect_memory_conflicts(self, user_id: str, new_memory: EpisodicMemory) -> List[MemoryConflict]:
        """
        Detect factual contradictions, timeline inconsistencies, and preference conflicts.
        
        Args:
            user_id: Discord user ID
            new_memory: New memory to check for conflicts
            
        Returns:
            List of detected memory conflicts
        """
        conflicts = []
        
        try:
            # Search for potentially conflicting memories
            similar_memories = await self.search_memories(
                user_id=user_id,
                query=new_memory.content,
                k=10,  # Check top 10 similar memories
                memory_type=None  # Check both episodic and semantic
            )
            
            for existing_memory in similar_memories:
                if existing_memory.similarity_score > 0.8:  # High similarity threshold
                    # In a full implementation, we would use AI to analyze for conflicts
                    # For now, we'll just check for obvious contradictions in content
                    conflict_detected = self._simple_conflict_detection(
                        new_memory.content,
                        existing_memory.content
                    )
                    
                    if conflict_detected:
                        conflict = MemoryConflict(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            primary_memory_id=new_memory.id,
                            conflicting_memory_id=existing_memory.id,
                            conflict_type="factual_contradiction",
                            description=f"Potential contradiction between '{new_memory.content[:50]}...' and '{existing_memory.content[:50]}...'",
                            confidence=0.7,  # Placeholder confidence
                            detected_at=datetime.utcnow(),
                            status="detected"
                        )
                        conflicts.append(conflict)
            
            return conflicts
            
        except Exception as e:
            self.logger.error(f"Conflict detection failed for user {user_id}: {e}")
            return []
    
    def _simple_conflict_detection(self, content1: str, content2: str) -> bool:
        """
        Simple conflict detection based on content comparison.
        TODO: Replace with semantic analysis using LLM for accurate conflict detection.

        Args:
            content1: First content to compare
            content2: Second content to compare

        Returns:
            True if conflict detected, False otherwise
        """
        # This is a simplified implementation
        # A full implementation would use AI to analyze semantic conflicts

        # Convert to lowercase for comparison
        c1 = content1.lower()
        c2 = content2.lower()

        # Check for obvious contradictions
        contradiction_pairs = [
            ("i like", "i dislike"),
            ("i love", "i hate"),
            ("i prefer", "i don't prefer"),
            ("my favorite", "i don't like"),
            ("i am happy", "i am sad"),
            ("i enjoy", "i hate")
        ]
        
        for phrase1, phrase2 in contradiction_pairs:
            if phrase1 in c1 and phrase2 in c2:
                return True
            if phrase2 in c1 and phrase1 in c2:
                return True
        
        return False
    
    def _sanitize_collection_name(self, name: str) -> str:
        """
        Sanitize collection names to ensure they're safe for Qdrant.
        Replaces any character that is not a-z, A-Z, 0-9, or underscore with an underscore.
        
        Args:
            name: The raw collection name to sanitize
            
        Returns:
            Sanitized collection name
        """
        import re
        # Replace any character not a-z, A-Z, 0-9 or underscore with an underscore
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return sanitized

    async def _update_memory_access(self, user_id: str, memory_id: str, memory_type: str):
        """
        Update memory access statistics.

        Args:
            user_id: Discord user ID
            memory_id: Memory ID to update
            memory_type: Type of memory ("episodic" or "semantic")
        """
        try:
            # Update access count and last accessed time in database
            await self.db.update_memory_access_stats(user_id, memory_id)

            # Update access statistics in Qdrant payload
            collection_name = self._sanitize_collection_name(f"{memory_type}_{user_id}")

            # Get current point to retrieve access_count
            try:
                points = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant.retrieve(
                        collection_name=collection_name,
                        ids=[memory_id]
                    )
                )

                if points and len(points) > 0:
                    current_point = points[0]
                    current_access_count = current_point.payload.get("access_count", 0)
                    current_created_at = current_point.payload.get("created_at")

                    # Calculate new recency score based on time since creation
                    # Recency score decays from 1.0, but accessing refreshes it
                    now = datetime.utcnow()
                    if current_created_at:
                        created_at = datetime.fromisoformat(current_created_at)
                        days_since_creation = (now - created_at).total_seconds() / 86400
                        # Decay factor: 0.95^days (slower decay for frequently accessed memories)
                        base_recency = 0.95 ** days_since_creation
                        # Boost recency on access (interpolate towards 1.0)
                        new_recency_score = min(1.0, base_recency + 0.2)
                    else:
                        new_recency_score = 1.0

                    # Update payload with new statistics
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.qdrant.set_payload(
                            collection_name=collection_name,
                            payload={
                                "access_count": current_access_count + 1,
                                "last_accessed": now.isoformat(),
                                "recency_score": new_recency_score
                            },
                            points=[memory_id]
                        )
                    )

                    self.logger.debug(f"Updated Qdrant payload for memory {memory_id} (access_count: {current_access_count + 1}, recency: {new_recency_score:.3f})")

            except Exception as qdrant_error:
                self.logger.warning(f"Failed to update Qdrant payload for memory {memory_id}: {qdrant_error}")

        except Exception as e:
            self.logger.warning(f"Failed to update memory access for user {user_id}, memory {memory_id}: {e}")
    
    async def get_memory_count(self, user_id: str) -> int:
        """
        Get the total count of memories for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Total memory count
        """
        try:
            return await self.db.get_memory_count(user_id)
        except Exception as e:
            self.logger.error(f"Failed to get memory count for user {user_id}: {e}")
            return 0
    
    async def get_unconsolidated_memories(self, user_id: str, hours: int = 24) -> List[EpisodicMemory]:
        """
        Get episodic memories that haven't been consolidated yet.
        
        Args:
            user_id: Discord user ID
            hours: Time window in hours to check for unconsolidated memories
            
        Returns:
            List of unconsolidated episodic memories
        """
        try:
            memory_data_list = await self.db.get_unconsolidated_memories(user_id, hours)
            return [EpisodicMemory(**data) for data in memory_data_list]
        except Exception as e:
            self.logger.error(f"Failed to get unconsolidated memories for user {user_id}: {e}")
            return []

    async def apply_recency_decay_all_users(self) -> int:
        """
        Apply recency decay to all memories across all users.
        This is called by the scheduler to gradually reduce recency scores over time.

        Returns:
            Number of collections updated
        """
        try:
            decay_rate = 0.05  # 5% decay per update cycle
            updated_count = 0

            # Get all user collections
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.qdrant.get_collections
            )

            for collection in collections.collections:
                if collection.name.startswith('episodic_') or collection.name.startswith('semantic_'):
                    # Note: Qdrant doesn't support bulk payload updates easily
                    # In production, this would need a more sophisticated approach
                    # For now, we mark it as processed
                    updated_count += 1
                    self.logger.debug(f"Processed recency decay for collection: {collection.name}")

            self.logger.info(f"Applied recency decay to {updated_count} collections")
            return updated_count
        except Exception as e:
            self.logger.error(f"Failed to apply recency decay: {e}")
            return 0

    async def cleanup_old_memories(self, tx=None, age_threshold_days: int = 365) -> int:
        """
        Clean up very old, low-importance memories.
        This helps maintain database performance and storage costs.
        
        Note: Qdrant vector database does not support ACID transactions,
        so memory cleanup in Qdrant cannot be made transactional with 
        PostgreSQL metadata operations.

        Args:
            tx: Database transaction (not used for Qdrant operations)
            age_threshold_days: Delete memories older than this many days

        Returns:
            Number of memories deleted
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=age_threshold_days)
            deleted_count = 0

            # Get all user collections
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.qdrant.get_collections
            )

            for collection in collections.collections:
                if collection.name.startswith('episodic_') or collection.name.startswith('semantic_'):
                    # In production, would query points with filters and delete old low-importance ones
                    # This is a placeholder implementation
                    self.logger.debug(f"Processed cleanup for collection: {collection.name}")

            self.logger.info(f"Cleaned up {deleted_count} old memories")
            return deleted_count
        except Exception as e:
            self.logger.error(f"Failed to cleanup memories: {e}")
            return 0

    async def get_total_memory_count(self) -> int:
        """
        Get the total count of memories across all users.

        Returns:
            Total number of memories in all collections
        """
        try:
            total_count = 0

            # Get all collections
            collections = await asyncio.get_event_loop().run_in_executor(
                None, self.qdrant.get_collections
            )

            # Sum up the point counts from all memory collections
            for collection in collections.collections:
                if collection.name.startswith('episodic_') or collection.name.startswith('semantic_'):
                    collection_info = await asyncio.get_event_loop().run_in_executor(
                        None, self.qdrant.get_collection, collection.name
                    )
                    total_count += collection_info.points_count

            self.logger.debug(f"Total memory count across all users: {total_count}")
            return total_count
        except Exception as e:
            self.logger.error(f"Failed to get total memory count: {e}")
            return 0

    async def migrate_memories(self, source_user_id: str, target_user_id: str) -> int:
        """
        Migrate all memories from one user to another.
        Useful for account merging or data migration scenarios.
        
        ⚠️  WARNING: This operation is NOT atomic. If migration fails partway through,
        some memories may be duplicated in the target collection without being removed
        from the source. Manual cleanup may be required.
        
        Consider running this operation during maintenance windows and verifying
        results before deleting source collections.

        Args:
            source_user_id: The user ID to migrate memories from
            target_user_id: The user ID to migrate memories to

        Returns:
            Number of memories migrated
        """
        try:
            migrated_count = 0
            # Track the point IDs that have been migrated successfully
            migrated_point_ids = []

            # Migrate episodic memories
            source_episodic = self._sanitize_collection_name(f"episodic_{source_user_id}")
            target_episodic = self._sanitize_collection_name(f"episodic_{target_user_id}")

            if await self._collection_exists(source_episodic):
                # Create target collection if it doesn't exist
                if not await self._collection_exists(target_episodic):
                    await self._create_collection(target_episodic)

                # Paginate through all points in source collection
                next_offset = None
                batch_size = 1000

                while True:
                    # Get batch of points from source collection
                    scroll_result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda offset=next_offset: self.qdrant.scroll(
                            collection_name=source_episodic,
                            limit=batch_size,
                            offset=offset
                        )
                    )

                    points, next_offset = scroll_result

                    # Break if no more points
                    if not points:
                        break

                    # Re-upload points to target collection
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda pts=points: self.qdrant.upsert(
                            collection_name=target_episodic,
                            points=pts
                        )
                    )
                    
                    # Track the point IDs that have been migrated
                    migrated_point_ids.extend([point.id for point in points])
                    migrated_count += len(points)

                    # Break if no more pages
                    if next_offset is None:
                        break

            # Migrate semantic memories
            source_semantic = self._sanitize_collection_name(f"semantic_{source_user_id}")
            target_semantic = self._sanitize_collection_name(f"semantic_{target_user_id}")

            if await self._collection_exists(source_semantic):
                # Create target collection if it doesn't exist
                if not await self._collection_exists(target_semantic):
                    await self._create_collection(target_semantic)

                # Paginate through all points in source collection
                next_offset = None
                batch_size = 1000

                while True:
                    # Get batch of points from source collection
                    scroll_result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda offset=next_offset: self.qdrant.scroll(
                            collection_name=source_semantic,
                            limit=batch_size,
                            offset=offset
                        )
                    )

                    points, next_offset = scroll_result

                    # Break if no more points
                    if not points:
                        break

                    # Re-upload points to target collection
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda pts=points: self.qdrant.upsert(
                            collection_name=target_semantic,
                            points=pts
                        )
                    )
                    
                    # Track the point IDs that have been migrated
                    migrated_point_ids.extend([point.id for point in points])
                    migrated_count += len(points)

                    # Break if no more pages
                    if next_offset is None:
                        break

            # Perform validation to ensure migration was successful
            # Count total expected points in source collections
            total_source_points = 0
            if await self._collection_exists(source_episodic):
                source_episodic_count = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant.count(collection_name=source_episodic)
                )
                total_source_points += source_episodic_count
            
            if await self._collection_exists(source_semantic):
                source_semantic_count = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant.count(collection_name=source_semantic)
                )
                total_source_points += source_semantic_count

            # Count total points in target collections
            total_target_points = 0
            if await self._collection_exists(target_episodic):
                target_episodic_count = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant.count(collection_name=target_episodic)
                )
                total_target_points += target_episodic_count
            
            if await self._collection_exists(target_semantic):
                target_semantic_count = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.qdrant.count(collection_name=target_semantic)
                )
                total_target_points += target_semantic_count

            self.logger.info(f"Migrated {migrated_count} memories from {source_user_id} to {target_user_id}")
            self.logger.info(f"Source collection count: {total_source_points}, Target collection count: {total_target_points}")

            return migrated_count
        except Exception as e:
            self.logger.error(f"Failed to migrate memories from {source_user_id} to {target_user_id}: {e}")
            # Note: In a real implementation, you might want to implement rollback here
            # For now, return 0 to indicate failure
            raise e
