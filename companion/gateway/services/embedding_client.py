"""
Gemini embedding service client for the AI Companion System.

This module provides a wrapper around the Gemini embedding service for generating
vector embeddings for memories and search queries.
"""

import httpx
import asyncio
import logging
import json
import hashlib
from typing import List, Optional, Dict, Any
from ..utils.exceptions import ServiceUnavailableError


class EmbeddingClient:
    """
    Client for communicating with the standalone Gemini embedding service.
    """
    
    def __init__(self, service_url: str, api_key: str, dimensions: int = 1536):
        """
        Initialize the embedding client.
        
        Args:
            service_url: URL of the embedding service
            api_key: Gemini API key
            dimensions: Embedding vector dimensions
        """
        self.service_url = service_url.rstrip('/')
        self.api_key = api_key
        self.dimensions = dimensions
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logging.getLogger(__name__)
        
        # Redis client for caching (will be set when available)
        self.redis_client = None
    
    def set_redis_client(self, redis_client):
        """
        Set the Redis client for caching embeddings.
        
        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            ServiceUnavailableError: If embedding service is unavailable
        """
        try:
            # Create a cache key based on the text and dimensions using deterministic hash
            cache_key = f"embed:{hashlib.sha256(text.encode('utf-8')).hexdigest()}:{self.dimensions}"

            # Check cache first if Redis is available
            if self.redis_client:
                try:
                    cached_embedding = await self.redis_client.get(cache_key)
                    if cached_embedding:
                        embedding = json.loads(cached_embedding)
                        self.logger.debug(f"Retrieved cached embedding for text: {text[:50]}...")
                        return embedding
                except Exception as e:
                    self.logger.warning(f"Cache retrieval failed: {e}")

            # Make API request to embedding service with API key in Authorization header
            response = await self.client.post(
                f"{self.service_url}/embed",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": text,
                    "dimensions": self.dimensions
                }
            )
            
            if response.status_code == 200:
                embedding = response.json()["embedding"]
                
                # Cache the embedding if Redis is available
                if self.redis_client:
                    try:
                        # Cache for 24 hours
                        await self.redis_client.setex(cache_key, 86400, json.dumps(embedding))
                    except Exception as e:
                        self.logger.warning(f"Cache storage failed: {e}")
                
                return embedding
            else:
                raise ServiceUnavailableError(
                    service_name="Embedding Service",
                    message=f"Embedding service returned status {response.status_code}: {response.text}"
                )
                
        except httpx.RequestError as e:
            self.logger.exception("Embedding service request error")
            raise ServiceUnavailableError(
                service_name="Embedding Service",
                message=f"Request error: {str(e)}"
            ) from e
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
            
        Raises:
            ServiceUnavailableError: If embedding service is unavailable
        """
        try:
            # Process in chunks to avoid overwhelming the service
            chunk_size = 100
            embeddings = []
            
            for i in range(0, len(texts), chunk_size):
                chunk = texts[i:i + chunk_size]
                
                response = await self.client.post(
                    f"{self.service_url}/embed_batch",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "texts": chunk,
                        "dimensions": self.dimensions
                    }
                )
                
                if response.status_code == 200:
                    batch_embeddings = response.json()["embeddings"]
                    embeddings.extend(batch_embeddings)
                else:
                    raise ServiceUnavailableError(
                        service_name="Embedding Service",
                        message=f"Batch embedding service returned status {response.status_code}: {response.text}"
                    )
            
            return embeddings

        except httpx.RequestError as e:
            self.logger.error(f"Batch embedding service request error: {e}")
            raise ServiceUnavailableError(
                service_name="Embedding Service",
                message=f"Batch request error: {str(e)}"
            )
        except (KeyError, json.JSONDecodeError) as e:
            self.logger.exception(f"Batch embedding response parsing error: {e}. Response may be malformed.")
            raise ServiceUnavailableError(
                service_name="Embedding Service",
                message=f"Invalid response format: {str(e)}"
            ) from e
        except ServiceUnavailableError:
            # Re-raise ServiceUnavailableError from within the try block
            raise
    
    async def close(self):
        """
        Close the HTTP client connection.
        """
        await self.client.aclose()
