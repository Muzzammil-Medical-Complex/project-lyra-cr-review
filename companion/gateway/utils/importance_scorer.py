"""
Memory importance scoring utility for the AI Companion System.

This module uses the Groq API to score the importance of conversation memories
on a scale from 0.0 to 1.0, with additional fallback mechanisms for reliability.
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from ..services.groq_client import GroqClient
from ..utils.exceptions import ServiceUnavailableError


class ImportanceScorer:
    """
    Scores the importance of memories using the Groq API with a detailed prompt
    that includes examples and scoring criteria.
    """
    
    def __init__(self, groq_client: GroqClient):
        """
        Initialize the importance scorer with a Groq client.
        
        Args:
            groq_client: Groq API client to use for scoring
        """
        self.groq_client = groq_client
        self.logger = logging.getLogger(__name__)
        
        # Redis client for caching (will be set when available)
        self.redis_client = None
        
        # Import redis here to make it optional
        try:
            import redis.asyncio as redis
            # This would be initialized when the service is fully set up
        except ImportError:
            self.logger.warning("Redis not available, caching will be disabled")
    
    def set_redis_client(self, redis_client):
        """
        Set the Redis client for caching scores.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client
    
    async def score_importance(self, content: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        Score memory importance using Groq with exact prompt.
        
        Args:
            content: Content of the memory to score
            context: Additional context for scoring (optional)
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        try:
            # Create a cache key based on the content and context
            cache_key = f"importance:{hash(content)}:{hash(str(context or {}))}"
            
            # Check cache first if Redis is available
            if self.redis_client:
                try:
                    cached_score = await self.redis_client.get(cache_key)
                    if cached_score:
                        score = float(cached_score)
                        self.logger.debug(f"Retrieved cached importance score: {score}")
                        return score
                except Exception as e:
                    self.logger.warning(f"Cache retrieval failed: {e}")
            
            prompt = self._build_importance_prompt(content, context)
            
            response = await self.groq_client.chat.completions.create(
                model=self.groq_client.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1  # Low temperature for consistent scoring
            )
            
            score_text = response.choices[0].message.content.strip()
            
            # Extract the score using regex to handle cases where extra text is returned
            score_match = re.search(r"(\d+(?:\.\d+)?|\d+)", score_text)
            if score_match:
                score = min(1.0, max(0.0, float(score_match.group(0))))
            else:
                # If no number found, use heuristic fallback
                self.logger.warning(f"Could not parse score from response: {score_text}, using heuristic")
                score = self._heuristic_importance_score(content)
            
            # Cache the score if Redis is available
            if self.redis_client:
                try:
                    # Cache for 1 hour
                    await self.redis_client.setex(cache_key, 3600, str(score))
                except Exception as e:
                    self.logger.warning(f"Cache storage failed: {e}")
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error scoring importance: {e}")
            # Fallback heuristic scoring
            return self._heuristic_importance_score(content)
    
    async def batch_score(self, contents: List[str], context: Optional[Dict[str, Any]] = None) -> List[float]:
        """
        Score multiple contents for importance in a batch.
        
        Args:
            contents: List of contents to score
            context: Context to use for all scores (optional)
            
        Returns:
            List of importance scores
        """
        scores = []
        for content in contents:
            score = await self.score_importance(content, context)
            scores.append(score)
        return scores
    
    def _build_importance_prompt(self, content: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Build the complete prompt for importance scoring.
        
        Args:
            content: Content to score
            context: Additional context (optional)
            
        Returns:
            Complete prompt string
        """
        # Scoring criteria from the guide
        scoring_criteria = """SCORING CRITERIA (with weights):
- Emotional Significance (30%): Personal revelations, strong emotions, meaningful events
- Future Relevance (25%): Information likely to be referenced again
- Uniqueness (25%): Rare or distinctive information about the user
- Personal Disclosure (20%): User sharing personal details, preferences, relationships"""

        # Examples from the guide
        examples = """EXAMPLES:

Input: "I just got a new puppy named Max!"
Output: 0.75
Reasoning: High emotional significance (happy event), future relevance (will likely discuss puppy again), personal disclosure

Input: "What's the weather like?"
Output: 0.1
Reasoning: No emotional significance, no personal disclosure, generic question unlikely to be referenced

Input: "My dad passed away last month, I'm still grieving"
Output: 0.95
Reasoning: Extremely high emotional significance, major life event, personal disclosure, high future relevance

Input: "I prefer tea over coffee"
Output: 0.4
Reasoning: Personal preference (moderate disclosure), some future relevance, but not emotionally significant

Input: "I just got promoted to senior engineer at Google!"
Output: 0.9
Reasoning: Major life achievement (high emotional), career milestone (high future relevance), significant personal disclosure"""

        context_str = str(context) if context else "No additional context"
        
        return f"""You are an AI that scores the importance of conversation memories on a scale from 0.0 to 1.0.

{scoring_criteria}

{examples}

Now score this memory:

User Message: "{content}"
Context: {context_str}

Output only a single number between 0.0 and 1.0:"""
    
    def _heuristic_importance_score(self, content: str) -> float:
        """
        Fallback heuristic scoring when API calls fail.
        This method mimics the AI behavior using simple rules.
        
        Args:
            content: Content to score
            
        Returns:
            Heuristic importance score between 0.0 and 1.0
        """
        score = 0.0
        
        # Emotional significance indicators
        emotional_words = [
            'love', 'hate', 'happy', 'sad', 'angry', 'excited', 'depressed', 'anxious',
            'scared', 'proud', 'ashamed', 'guilty', 'grateful', 'blessed', 'amazing',
            'incredible', 'terrible', 'awful', 'wonderful', 'fantastic', 'brilliant',
            'brilliant', 'awful', 'perfect', 'horrible', 'amazing', 'incredible'
        ]
        
        for word in emotional_words:
            if word in content.lower():
                score += 0.1
        
        # Life events indicators
        life_events = [
            'married', 'engaged', 'divorced', 'graduated', 'promoted', 'fired', 'quit',
            'died', 'passed away', 'born', 'pregnant', 'baby', 'child', 'moved',
            'relocated', 'job', 'career', 'degree', 'school', 'university'
        ]
        
        for event in life_events:
            if event in content.lower():
                score += 0.15
        
        # Personal disclosure indicators
        personal_indicators = [
            'I feel', 'I think', 'I believe', 'my opinion', 'in my experience',
            'personally', 'to me', 'for me', 'my family', 'my friends', 'my life',
            'I want', 'I need', 'I like', 'I dislike', 'I prefer'
        ]
        
        for indicator in personal_indicators:
            if indicator in content.lower():
                score += 0.05
        
        # Uniqueness based on length and word count
        words = content.split()
        if len(words) > 10:  # Longer messages tend to be more substantive
            score += min(0.2, len(words) * 0.01)  # Up to 0.2 for long messages
        
        # Capitalize emphasis (all caps) indicates importance
        if any(word.isupper() and len(word) > 3 for word in content.split()):
            score += 0.1
        
        # Questions with personal context
        if '?' in content and any(word in content.lower() for word in ['you', 'your', 'what', 'why', 'how']):
            score += 0.05
        
        # Ensure score is between 0.0 and 1.0
        return min(1.0, max(0.0, score))
    
    async def score_memory_importance(
        self,
        content: str,
        content_type: str = "conversation",
        user_context: Optional[Dict[str, Any]] = None,
        temporal_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Score memory importance with detailed context.
        
        Args:
            content: Content of the memory to score
            content_type: Type of content ('conversation', 'fact', 'event', etc.)
            user_context: Context about the user (optional)
            temporal_context: Temporal context (optional)
            
        Returns:
            Dictionary with score and reasoning
        """
        context = {
            "content_type": content_type,
            "user_context": user_context,
            "temporal_context": temporal_context
        }
        
        score = await self.score_importance(content, context)
        
        return {
            "score": score,
            "content_type": content_type,
            "user_context": user_context,
            "temporal_context": temporal_context,
            "timestamp": "now"
        }