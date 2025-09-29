"""
Groq API client for the AI Companion System.

This module provides a wrapper around the Groq API for fast LLM operations
like scoring and security analysis.
"""

import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from ..utils.exceptions import ServiceUnavailableError


class GroqClient:
    """
    A client for interacting with the Groq API for fast LLM operations.
    """
    
    def __init__(self, api_key: str, model: str = "llama-4-maverick"):
        """
        Initialize the Groq client.
        
        Args:
            api_key: Groq API key
            model: Model to use for completions
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
        self.logger = logging.getLogger(__name__)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate a chat completion using the Groq API.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to instance model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            API response dictionary
            
        Raises:
            ServiceUnavailableError: If API call fails
        """
        model = model or self.model
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise ServiceUnavailableError(
                    service_name="Groq",
                    message=f"API request failed with status {response.status_code}: {response.text}"
                )
                
        except httpx.RequestError as e:
            self.logger.error(f"Groq API request error: {e}")
            raise ServiceUnavailableError(
                service_name="Groq",
                message=f"Request error: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in Groq API call: {e}")
            raise ServiceUnavailableError(
                service_name="Groq",
                message=f"Unexpected error: {str(e)}"
            )
    
    async def _request_with_backoff(
        self,
        endpoint: str,
        data: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make a request with exponential backoff for rate limiting.
        
        Args:
            endpoint: API endpoint
            data: Request data
            max_retries: Maximum number of retry attempts
            
        Returns:
            API response dictionary
        """
        import random
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/{endpoint}",
                    json=data
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limit
                    if attempt == max_retries - 1:
                        raise ServiceUnavailableError(
                            service_name="Groq",
                            message="Rate limit exceeded after max retries"
                        )
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                else:
                    raise ServiceUnavailableError(
                        service_name="Groq",
                        message=f"API request failed with status {response.status_code}: {response.text}"
                    )
                    
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise ServiceUnavailableError(
                        service_name="Groq",
                        message=f"Request error after max retries: {str(e)}"
                    )
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)
    
    async def score_importance(self, content: str, context: Dict[str, Any]) -> float:
        """
        Score memory importance using Groq API.
        
        Args:
            content: Content to score
            context: Context for scoring
            
        Returns:
            Importance score between 0.0 and 1.0
        """
        # This would be implemented using the importance scorer
        # For now, we'll just return a placeholder
        return 0.5
    
    async def detect_threat(self, message: str, threat_types: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect security threats in user messages.
        
        Args:
            message: User message to analyze
            threat_types: Types of threats to check for
            context: Additional context for analysis
            
        Returns:
            Threat analysis result
        """
        # This would be implemented using the security detector
        # For now, we'll just return a placeholder
        return {
            "threat_detected": False,
            "threat_type": "none",
            "confidence": 0.0,
            "reasoning": "No threat detected"
        }
    
    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
