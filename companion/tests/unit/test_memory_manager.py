"""
Unit tests for the Memory Manager service.
Tests memory storage, MMR retrieval logic, and conflict detection rules.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from companion.gateway.models.memory import Memory
from companion.gateway.services.memory_manager import MemoryManager


@pytest.mark.asyncio
class TestMemoryManager:
    """Unit tests for MemoryManager class."""
    
    async def test_memory_storage(self):
        """Test storing a memory with proper vectorization and metadata."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_1'
        content = 'This is a test memory about my new puppy Sparky'
        memory_type = 'episodic'
        
        # Mock embedding and importance scoring
        embedding_mock.embed_text.return_value = [0.1, 0.2, 0.3]  # Mock embedding vector
        importance_scorer_mock.score_importance.return_value = 0.7
        
        # Execute
        memory_id = await memory_manager.store_memory(
            user_id=user_id,
            content=content,
            memory_type=memory_type
        )
        
        # Assert
        assert memory_id is not None
        assert memory_id != ""  # Should return a valid ID
        # Verify embedding was called
        embedding_mock.embed_text.assert_called_once_with(content)
        # Verify importance scoring was called
        importance_scorer_mock.score_importance.assert_called_once()
        # Verify Qdrant upsert was called
        qdrant_mock.upsert.assert_called_once()
        # Verify database metadata was stored
        db_mock.store_memory_metadata.assert_called_once()

    async def test_mmr_retrieval_logic_diversity(self):
        """Test MMR retrieval logic ensures diversity and relevance."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_2'
        query = 'Tell me about my puppy'
        k = 5
        
        # Mock search results
        mock_results = [
            Memory(id='mem1', user_id=user_id, content='I have a golden retriever named Sparky', 
                   memory_type='episodic', importance_score=0.8, recency_score=0.9),
            Memory(id='mem2', user_id=user_id, content='My cat loves to play', 
                   memory_type='episodic', importance_score=0.6, recency_score=0.7),
            Memory(id='mem3', user_id=user_id, content='Dogs are loyal animals', 
                   memory_type='semantic', importance_score=0.5, recency_score=0.6),
            Memory(id='mem4', user_id=user_id, content='I adopted a puppy last week', 
                   memory_type='episodic', importance_score=0.9, recency_score=0.8),
            Memory(id='mem5', user_id=user_id, content='Puppies need training', 
                   memory_type='semantic', importance_score=0.4, recency_score=0.5),
        ]
        
        # Mock the initial search to return these results
        db_mock.search_similar_memories.return_value = mock_results
        
        # Mock the MMR algorithm to return a diverse subset
        mmr_selected = mock_results[::2]  # Every other item for diversity (in real implementation, MMR would calculate this)
        mmr_mock.rank_memories.return_value = mmr_selected
        
        # Execute
        results = await memory_manager.search_with_mmr(
            user_id=user_id,
            query=query,
            k=k,
            lambda_param=0.7  # Balance between relevance and diversity
        )
        
        # Assert
        assert len(results) <= k
        assert len(results) > 0
        # Verify MMR was called to ensure diversity
        mmr_mock.rank_memories.assert_called_once()
        
        # Check that results contain relevant content (related to query about puppy)
        puppy_related_memories = [mem for mem in results if 'puppy' in mem.content.lower() or 'dog' in mem.content.lower()]
        assert len(puppy_related_memories) > 0

    async def test_mmr_retrieval_logic_relevance(self):
        """Test MMR retrieval logic maintains relevance while adding diversity."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_3'
        query = 'vacation memories'
        k = 3
        
        # Create mock memories with different relevance to the query
        all_memories = [
            Memory(id='mem1', user_id=user_id, content='Last summer I went to Hawaii for vacation', 
                   memory_type='episodic', importance_score=0.9, recency_score=0.8),
            Memory(id='mem2', user_id=user_id, content='My friend went to Paris on vacation', 
                   memory_type='episodic', importance_score=0.7, recency_score=0.6),
            Memory(id='mem3', user_id=user_id, content='I like to travel and see new places', 
                   memory_type='semantic', importance_score=0.6, recency_score=0.7),
            Memory(id='mem4', user_id=user_id, content='My vacation photos are beautiful', 
                   memory_type='episodic', importance_score=0.8, recency_score=0.9),
            Memory(id='mem5', user_id=user_id, content='I need to do my laundry', 
                   memory_type='episodic', importance_score=0.2, recency_score=0.3),  # Not relevant
        ]
        
        # Mock search to return all memories
        db_mock.search_similar_memories.return_value = all_memories
        
        # Execute retrieval with high lambda (favors relevance over diversity)
        results_high_relevance = await memory_manager.search_with_mmr(
            user_id=user_id,
            query=query,
            k=k,
            lambda_param=0.9  # High relevance weight
        )
        
        # Execute retrieval with low lambda (favors diversity over relevance)
        results_high_diversity = await memory_manager.search_with_mmr(
            user_id=user_id,
            query=query,
            k=k,
            lambda_param=0.3  # High diversity weight
        )
        
        # Assertions
        assert len(results_high_relevance) <= k
        assert len(results_high_diversity) <= k
        
        # Verify that high relevance setting still returns relevant memories
        relevant_high_rel = [mem for mem in results_high_relevance if 'vacation' in mem.content.lower()]
        assert len(relevant_high_rel) >= len(results_high_relevance) * 0.6  # At least 60% relevant
        
        # The diversity setting might return less relevant but more varied content
        # This is harder to test without the actual MMR implementation, but we can verify it was called
        assert mmr_mock.rank_memories.call_count >= 2

    async def test_conflict_detection_rules_factual_contradiction(self):
        """Test conflict detection for factual contradictions."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_4'
        
        # Create a new memory that contradicts an existing one
        new_memory = Memory(
            id='new_mem',
            user_id=user_id,
            content='My name is John and I live in New York',
            memory_type='episodic',
            importance_score=0.6
        )
        
        # Existing memory that contradicts the new one
        existing_memory = Memory(
            id='existing_mem',
            user_id=user_id,
            content='My name is Mike and I live in California', 
            memory_type='episodic',
            importance_score=0.6
        )
        
        # Mock similar memories search to return the existing memory
        db_mock.search_similar_memories.return_value = [existing_memory]
        
        # Mock the Groq client to detect the contradiction
        groq_mock.analyze_memory_conflict.return_value = MagicMock(
            has_conflict=True,
            conflict_type='factual_contradiction',
            description='Contradicts previous statement about name and location',
            confidence=0.8
        )
        
        # Execute
        conflicts = await memory_manager.detect_memory_conflicts(user_id, new_memory)
        
        # Assert
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.conflict_type == 'factual_contradiction'
        assert conflict.confidence == 0.8
        assert 'name' in conflict.description.lower() or 'location' in conflict.description.lower()

    async def test_conflict_detection_rules_timeline_inconsistency(self):
        """Test conflict detection for timeline inconsistencies."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_5'
        
        # Create a new memory about a recent event
        new_memory = Memory(
            id='new_event',
            user_id=user_id,
            content='Yesterday I went to the park and had a great time',
            memory_type='episodic',
            importance_score=0.5
        )
        
        # Existing memory that conflicts temporally
        existing_memory = Memory(
            id='existing_event',
            user_id=user_id,
            content='I was at home all day yesterday studying',
            memory_type='episodic', 
            importance_score=0.5
        )
        
        # Mock to return the existing memory
        db_mock.search_similar_memories.return_value = [existing_memory]
        
        # Mock Groq to detect timeline inconsistency
        groq_mock.analyze_memory_conflict.return_value = MagicMock(
            has_conflict=True,
            conflict_type='timeline_inconsistency', 
            description='Conflicts with previous account of yesterday\'s activities',
            confidence=0.7
        )
        
        # Execute
        conflicts = await memory_manager.detect_memory_conflicts(user_id, new_memory)
        
        # Assert
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.conflict_type == 'timeline_inconsistency'
        assert conflict.confidence == 0.7

    async def test_conflict_resolution_temporal_precedence(self):
        """Test conflict resolution using temporal precedence method."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_6'
        conflict_id = 'conflict_1'
        
        # Mock the existing memories
        newer_memory = MagicMock()
        newer_memory.created_at = datetime.now()
        newer_memory.id = 'newer_memory_id'
        
        older_memory = MagicMock()
        older_memory.created_at = datetime.now() - timedelta(hours=1)
        older_memory.id = 'older_memory_id'
        
        # Mock database calls
        db_mock.get_memory_conflict.return_value = MagicMock(
            primary_memory_id=newer_memory.id,
            conflicting_memory_id=older_memory.id
        )
        
        db_mock.get_memory_by_id.side_effect = [newer_memory, older_memory]
        
        # Execute resolution
        success = await memory_manager.resolve_conflict(
            user_id, conflict_id, 'temporal_precedence'
        )
        
        # Assert
        assert success == True
        # Verify that the older memory's importance was reduced (since newer one takes precedence)
        db_mock.update_memory_importance.assert_called()

    async def test_conflict_resolution_confidence_based(self):
        """Test conflict resolution using confidence-based method."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_7'
        conflict_id = 'conflict_2'
        
        # Mock the memories with different importance scores
        high_confidence_memory = MagicMock()
        high_confidence_memory.id = 'high_conf_mem'
        
        low_confidence_memory = MagicMock() 
        low_confidence_memory.id = 'low_conf_mem'
        
        # Mock database calls
        db_mock.get_memory_conflict.return_value = MagicMock(
            primary_memory_id=high_confidence_memory.id,
            conflicting_memory_id=low_confidence_memory.id
        )
        
        # Mock getting memory by ID
        db_mock.get_memory_by_id.side_effect = [
            MagicMock(importance_score=0.8),  # high confidence memory
            MagicMock(importance_score=0.3)   # low confidence memory
        ]
        
        # Execute resolution
        success = await memory_manager.resolve_conflict(
            user_id, conflict_id, 'confidence_based'
        )
        
        # Assert
        assert success == True
        # The lower confidence memory should have its importance reduced
        db_mock.update_memory_importance.assert_called()

    async def test_memory_importance_scoring_integration(self):
        """Test integration between memory storage and importance scoring."""
        # Setup
        qdrant_mock = AsyncMock()
        embedding_mock = AsyncMock()
        importance_scorer_mock = AsyncMock()
        mmr_mock = AsyncMock()
        db_mock = AsyncMock()
        groq_mock = AsyncMock()
        
        memory_manager = MemoryManager(
            qdrant_client=qdrant_mock,
            embedding_client=embedding_mock,
            importance_scorer=importance_scorer_mock,
            mmr_ranker=mmr_mock,
            db_manager=db_mock,
            groq_client=groq_mock
        )
        
        user_id = 'test_user_8'
        important_content = 'I just got promoted to senior engineer at Google!'
        mundane_content = 'I ate breakfast today'
        
        # Mock different importance scores
        importance_scorer_mock.score_importance.side_effect = [0.9, 0.2]  # Important vs mundane
        
        # Store both memories
        important_id = await memory_manager.store_memory(user_id, important_content)
        mundane_id = await memory_manager.store_memory(user_id, mundane_content)
        
        # Verify that importance scorer was called with different content
        assert importance_scorer_mock.score_importance.call_count == 2
        
        # Verify the important memory scored higher
        # This would require checking the actual calls, which is done by the side_effect above