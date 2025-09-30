"""
FastAPI application for the Gemini Embedding Service.
Provides endpoints for generating text embeddings with caching and rate limiting.
"""
import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import google.generativeai as genai
import redis
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Gemini Embedding Service",
    description="API for generating text embeddings using Google's Gemini model",
    version="1.0.0"
)

# Get API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Redis for caching
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Initialize thread pool for blocking operations
thread_pool = ThreadPoolExecutor(max_workers=10)

class EmbedRequest(BaseModel):
    text: str
    task_type: Optional[str] = "RETRIEVAL_QUERY"  # Default task type for retrieval
    title: Optional[str] = None  # Optional title for the text


class EmbedResponse(BaseModel):
    embedding: List[float]
    cached: bool = False


class EmbedBatchRequest(BaseModel):
    texts: List[str]
    task_type: Optional[str] = "RETRIEVAL_QUERY"
    title: Optional[str] = None


class EmbedBatchResponse(BaseModel):
    embeddings: List[List[float]]
    cached: List[bool]


def get_cache_key(text: str, task_type: str = "RETRIEVAL_QUERY") -> str:
    """Generate a cache key for the given text and task type."""
    cache_input = f"{text}:{task_type}"
    return f"embed:{hashlib.md5(cache_input.encode()).hexdigest()}"


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("Starting up Gemini Embedding Service...")
    
    # Test Redis connection
    try:
        redis_client.ping()
        logger.info("Connected to Redis successfully")
    except Exception as e:
        logger.error(f"Could not connect to Redis: {e}")
    
    logger.info("Gemini Embedding Service started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down Gemini Embedding Service...")
    
    # Shutdown thread pool
    thread_pool.shutdown(wait=True)
    
    logger.info("Gemini Embedding Service shutdown complete")


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Middleware to add processing time header."""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "gemini-embedding-service"
    }
    
    # Check Redis connectivity
    try:
        redis_client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status


@app.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """
    Generate embedding for a single text.
    
    Supports caching to reduce API calls and costs.
    """
    try:
        # Create cache key
        cache_key = get_cache_key(request.text, request.task_type)
        
        # Check cache first
        cached_result = redis_client.get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for text: {request.text[:50]}...")
            embedding = json.loads(cached_result)
            return EmbedResponse(embedding=embedding, cached=True)
        
        # Generate embedding using Gemini
        logger.info(f"Generating embedding for text: {request.text[:50]}...")
        
        # Using thread pool since genai operations are blocking
        def generate_embedding():
            result = genai.embed_content(
                model="models/embedding-001",
                content=request.text,
                task_type=request.task_type,
                title=request.title
            )
            return result['embedding']
        
        embedding = await asyncio.get_event_loop().run_in_executor(
            thread_pool, generate_embedding
        )
        
        # Cache the result (expire in 24 hours)
        redis_client.setex(cache_key, 86400, json.dumps(embedding))
        
        logger.info(f"Generated embedding of length {len(embedding)} for text")
        
        return EmbedResponse(embedding=embedding, cached=False)
        
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")


@app.post("/embed_batch", response_model=EmbedBatchResponse)
async def embed_batch(request: EmbedBatchRequest):
    """
    Generate embeddings for a batch of texts.
    Processes in chunks to respect API rate limits.
    """
    try:
        embeddings = []
        cached_flags = []
        
        # Process in chunks of 100 to respect rate limits
        for chunk in chunk_list(request.texts, 100):
            # Check cache for each text in the chunk
            chunk_embeddings = []
            for text in chunk:
                cache_key = get_cache_key(text, request.task_type)
                cached_result = redis_client.get(cache_key)
                
                if cached_result:
                    logger.debug(f"Cache hit for text: {text[:30]}...")
                    embedding = json.loads(cached_result)
                    chunk_embeddings.append(embedding)
                    cached_flags.append(True)
                else:
                    chunk_embeddings.append(None)  # Placeholder
                    cached_flags.append(False)
            
            # Generate embeddings for texts not in cache
            texts_to_generate = [
                text for text, cached in zip(chunk, cached_flags[-len(chunk):]) if not cached
            ]
            
            if texts_to_generate:
                logger.info(f"Generating embeddings for {len(texts_to_generate)} texts...")
                
                # Using thread pool for batch generation
                def generate_batch_embeddings():
                    return genai.embed_content(
                        model="models/embedding-001",
                        content=texts_to_generate,
                        task_type=request.task_type,
                        title=request.title
                    )
                
                batch_result = await asyncio.get_event_loop().run_in_executor(
                    thread_pool, generate_batch_embeddings
                )
                
                generated_embeddings = batch_result['embedding']
                
                # Update results and cache
                gen_idx = 0
                for i, (text, was_cached) in enumerate(zip(chunk, cached_flags[-len(chunk):])):
                    if not was_cached:
                        embedding = generated_embeddings[gen_idx]
                        chunk_embeddings[i] = embedding
                        gen_idx += 1
                        
                        # Cache the result
                        cache_key = get_cache_key(text, request.task_type)
                        redis_client.setex(cache_key, 86400, json.dumps(embedding))
            
            embeddings.extend(chunk_embeddings)
        
        logger.info(f"Generated {len(embeddings)} embeddings in batch")
        
        return EmbedBatchResponse(embeddings=embeddings, cached=cached_flags)
        
    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating batch embeddings: {str(e)}")


@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    try:
        # Get Redis info
        info = redis_client.info()
        db_size = redis_client.dbsize()
        
        return {
            "status": "connected",
            "db_size": db_size,
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory_human", "N/A"),
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": info.get("keyspace_hits", 0) / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0))
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/cache/clear")
async def clear_cache():
    """Clear all embedding cache."""
    try:
        # Only clear embedding cache keys (keys that start with "embed:")
        cursor = 0
        cleared_count = 0
        
        while True:
            cursor, keys = redis_client.scan(cursor=cursor, match="embed:*", count=1000)
            if keys:
                redis_client.delete(*keys)
                cleared_count += len(keys)
            if cursor == 0:
                break
        
        logger.info(f"Cleared {cleared_count} embedding cache entries")
        return {"cleared_count": cleared_count, "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("EMBEDDING_SERVICE_PORT", 8002)),
        log_level="info"
    )