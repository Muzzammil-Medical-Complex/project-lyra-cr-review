"""
Chutes.ai API client for the AI Companion System.

This module provides a wrapper around the Chutes.ai API for primary LLM operations
with fallback logic to secondary models when needed.
"""

import httpx
import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
from ..utils.exceptions import ServiceUnavailableError


class ChutesClient:
    """
    A client for interacting with the Chutes.ai API for primary LLM operations.
    Implements fallback logic to secondary models when primary model fails.
    """
    
    def __init__(self, api_key: str, primary_model: str = "qwen3-80b-a3b-instruct", fallback_model: str = "qwen2-72b-instruct"):
        """
        Initialize the Chutes client.
        
        Args:
            api_key: Chutes.ai API key
            primary_model: Primary model to use for completions
            fallback_model: Fallback model to use when primary fails
        """
        self.api_key = api_key
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.base_url = "https://api.chutes.ai/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0
        )
        self.logger = logging.getLogger(__name__)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Generate a chat completion using the Chutes.ai API with fallback logic.
        
        Args:
            messages: List of message dictionaries
            model: Model to use (defaults to primary model)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            API response dictionary
            
        Raises:
            ServiceUnavailableError: If both primary and fallback API calls fail
        """
        model = model or self.primary_model
        
        try:
            # Try primary model first
            response = await self._make_api_request(messages, model, max_tokens, temperature)
            return response
        except ServiceUnavailableError as e:
            self.logger.warning(f"Primary model {model} failed: {e.message}")
            
            # If fallback is disabled or we already tried fallback, raise error
            if self.fallback_model is None or model == self.fallback_model:
                raise e
            
            # Try fallback model
            self.logger.info(f"Attempting fallback to model: {self.fallback_model}")
            try:
                fallback_response = await self._make_api_request(messages, self.fallback_model, max_tokens, temperature)
                fallback_response['fallback_used'] = True
                return fallback_response
            except ServiceUnavailableError as fallback_error:
                self.logger.error(f"Both primary and fallback models failed: {fallback_error.message}")
                raise fallback_error
    
    async def _make_api_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """
        Make a single API request to Chutes.ai.
        
        Args:
            messages: List of message dictionaries
            model: Model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            API response dictionary
            
        Raises:
            ServiceUnavailableError: If API call fails
        """
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
            elif response.status_code == 429:
                raise ServiceUnavailableError(
                    service_name="Chutes",
                    message="Rate limit exceeded"
                )
            elif response.status_code == 503:
                raise ServiceUnavailableError(
                    service_name="Chutes",
                    message="Service temporarily unavailable"
                )
            else:
                raise ServiceUnavailableError(
                    service_name="Chutes",
                    message=f"API request failed with status {response.status_code}: {response.text}"
                )
                
        except httpx.RequestError as e:
            self.logger.error(f"Chutes API request error: {e}")
            raise ServiceUnavailableError(
                service_name="Chutes",
                message=f"Request error: {str(e)}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error in Chutes API call: {e}")
            raise ServiceUnavailableError(
                service_name="Chutes",
                message=f"Unexpected error: {str(e)}"
            )
    
    async def get_available_models(self) -> List[str]:
        """
        Get list of available models from Chutes.ai.
        
        Returns:
            List of available model names
        """
        try:
            response = await self.client.get(f"{self.base_url}/models")
            if response.status_code == 200:
                data = response.json()
                return [model['id'] for model in data.get('data', [])]
            else:
                self.logger.warning(f"Failed to fetch models: {response.status_code}")
                return [self.primary_model, self.fallback_model]
        except Exception as e:
            self.logger.error(f"Error fetching available models: {e}")
            return [self.primary_model, self.fallback_model]

    async def health_check(self) -> bool:
        """
        Check if the Chutes API is accessible and responding.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Make a minimal API call to test connectivity
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.primary_model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                    "temperature": 0.0
                }
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Chutes health check failed: {e}")
            return False

    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
