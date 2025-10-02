"""
Maximal Marginal Relevance (MMR) algorithm implementation for the AI Companion System.

This module implements the MMR algorithm for selecting diverse yet relevant memories
during retrieval. The algorithm balances relevance to the query with diversity among
selected items to avoid redundancy.
"""

from typing import List, Tuple
import numpy as np
from numpy.linalg import norm
from ..models.memory import EpisodicMemory, SemanticMemory


class MaximalMarginalRelevance:
    """
    Implements the Maximal Marginal Relevance algorithm for diverse memory retrieval.
    
    The MMR algorithm selects items that are both relevant to the query and diverse
    among the selected set, preventing redundancy in retrieved memories.
    """

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        # Convert to numpy arrays for efficient computation
        a = np.array(vec1)
        b = np.array(vec2)
        
        # Calculate cosine similarity: (A · B) / (||A|| * ||B||)
        dot_product = np.dot(a, b)
        norm_a = norm(a)
        norm_b = norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    def mmr_select_memories(
        self,
        query_vector: List[float],
        candidate_memories: List[EpisodicMemory],
        k: int,
        lambda_param: float = 0.7
    ) -> List[EpisodicMemory]:
        """
        Maximal Marginal Relevance Algorithm - Exact Implementation
        
        STEP-BY-STEP PROCEDURE:
        1. Calculate cosine similarity between query Q and all N documents
        2. Initialize selected set S with highest similarity document
        3. Loop k-1 times: calculate MMR score for each remaining document
        4. Add highest MMR score document to S
        5. Return S
        
        Args:
            query_vector: The query vector for which to find relevant memories
            candidate_memories: List of candidate memories to rank
            k: Number of memories to select
            lambda_param: Balance between relevance and diversity (0.0 = max diversity, 1.0 = max relevance)
            
        Returns:
            List of k selected memories that are diverse yet relevant
        """
        if not candidate_memories:
            return []
        
        if k <= 0:
            return []
        
        # STEP 1: Calculate cosine similarity between query and all documents
        similarities = {}
        for memory in candidate_memories:
            if memory.embedding is None:
                # If no embedding exists, calculate similarity based on content
                # For now, we'll skip this memory, but in a full implementation,
                # we would generate an embedding for the content
                continue
            similarity = self._cosine_similarity(query_vector, memory.embedding)
            similarities[memory.id] = similarity
        
        # If no valid similarities were computed, return top k by other metrics
        if not similarities:
            return candidate_memories[:min(k, len(candidate_memories))]
        
        # STEP 2: Initialize selected set with highest similarity document
        selected_memories = []
        remaining_memories = [m for m in candidate_memories if m.id in similarities]
        
        if not remaining_memories:
            return []
        
        # Find document with highest similarity to query
        best_memory = max(remaining_memories, key=lambda m: similarities.get(m.id, 0.0))
        selected_memories.append(best_memory)
        remaining_memories.remove(best_memory)
        
        # STEP 3-4: Loop k-1 times
        for _ in range(min(k - 1, len(remaining_memories))):
            if not remaining_memories:
                break
            
            best_mmr_score = float('-inf')
            best_memory = None
            
            # Calculate MMR score for each remaining document
            for candidate in remaining_memories:
                # Relevance component: Sim(Q, d_i)
                relevance = similarities.get(candidate.id, 0.0)
                
                # Diversity component: max(Sim(d_i, d_j)) for d_j in selected set
                max_similarity_to_selected = 0.0
                for selected in selected_memories:
                    if candidate.embedding is not None and selected.embedding is not None:
                        similarity_to_selected = self._cosine_similarity(
                            candidate.embedding,
                            selected.embedding
                        )
                        max_similarity_to_selected = max(max_similarity_to_selected, similarity_to_selected)
                
                # MMR Formula: λ * Rel(Q, d_i) - (1-λ) * max(Sim(d_i, d_j))
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity_to_selected
                
                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_memory = candidate
            
            # Add best scoring document to selected set
            if best_memory:
                selected_memories.append(best_memory)
                remaining_memories.remove(best_memory)
        
        # STEP 5: Return selected set
        return selected_memories
    
    def calculate_memory_diversity(
        self,
        memories: List[EpisodicMemory]
    ) -> float:
        """
        Calculate how diverse a set of memories is.
        
        Args:
            memories: List of memories to evaluate
            
        Returns:
            Average pairwise cosine similarity (lower = more diverse)
        """
        if len(memories) < 2:
            return 0.0
        
        similarities = []
        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                if (memories[i].embedding is not None and 
                    memories[j].embedding is not None):
                    similarity = self._cosine_similarity(
                        memories[i].embedding,
                        memories[j].embedding
                    )
                    similarities.append(similarity)
        
        if not similarities:
            return 0.0
        
        return 1.0 - sum(similarities) / len(similarities)  # Return diversity (1 - average similarity)
    
    def mmr_rank_with_importance(
        self,
        query_vector: List[float],
        candidate_memories: List[EpisodicMemory],
        k: int,
        lambda_param: float = 0.7,
        importance_weight: float = 0.1
    ) -> List[EpisodicMemory]:
        """
        MMR algorithm with additional consideration for memory importance scores.
        
        Args:
            query_vector: The query vector for which to find relevant memories
            candidate_memories: List of candidate memories to rank
            k: Number of memories to select
            lambda_param: Balance between relevance and diversity
            importance_weight: Weight to apply to memory importance scores
            
        Returns:
            List of k selected memories with MMR and importance scoring
        """
        if not candidate_memories:
            return []
        
        if k <= 0:
            return []
        
        # Calculate cosine similarities
        similarities = {}
        for memory in candidate_memories:
            if memory.embedding is None:
                continue
            similarity = self._cosine_similarity(query_vector, memory.embedding)
            similarities[memory.id] = similarity
        
        if not similarities:
            return candidate_memories[:min(k, len(candidate_memories))]
        
        # Initialize selected set
        selected_memories = []
        remaining_memories = [m for m in candidate_memories if m.id in similarities]
        
        if not remaining_memories:
            return []
        
        # Find document with highest weighted score (similarity + importance)
        best_memory = max(
            remaining_memories,
            key=lambda m: similarities.get(m.id, 0.0) + (m.importance_score * importance_weight)
        )
        selected_memories.append(best_memory)
        remaining_memories.remove(best_memory)
        
        # Loop k-1 times
        for _ in range(min(k - 1, len(remaining_memories))):
            if not remaining_memories:
                break
            
            best_mmr_score = float('-inf')
            best_memory = None
            
            for candidate in remaining_memories:
                # Relevance component: Sim(Q, d_i)
                base_relevance = similarities.get(candidate.id, 0.0)
                
                # Add importance boost
                relevance = base_relevance + (candidate.importance_score * importance_weight)
                
                # Diversity component: max(Sim(d_i, d_j)) for d_j in selected set
                max_similarity_to_selected = 0.0
                for selected in selected_memories:
                    if candidate.embedding is not None and selected.embedding is not None:
                        similarity_to_selected = self._cosine_similarity(
                            candidate.embedding,
                            selected.embedding
                        )
                        max_similarity_to_selected = max(max_similarity_to_selected, similarity_to_selected)
                
                # MMR Formula: λ * Rel(Q, d_i) - (1-λ) * max(Sim(d_i, d_j))
                mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity_to_selected
                
                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_memory = candidate
            
            if best_memory:
                selected_memories.append(best_memory)
                remaining_memories.remove(best_memory)
        
        return selected_memories