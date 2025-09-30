"""
Main entry point for the AI Companion Gateway API.
Implements the complete 4-phase startup sequence and service orchestration.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os
from typing import Optional

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Phase 1: Core Infrastructure - Import core modules first
from .config import Settings
from .database import DatabaseManager

# Import QdrantClient for vector database
from qdrant_client import QdrantClient
import redis.asyncio as redis

from .utils.exceptions import setup_exception_handlers

# Phase 2: Utility Services - Import utilities that depend on core
from .utils.importance_scorer import ImportanceScorer
from .utils.mmr import MaximalMarginalRelevance
from .security.semantic_injection_detector import SemanticInjectionDetector
from .utils.scheduler import SchedulerService, setup_background_jobs
from .utils.background import BackgroundServiceManager

# Phase 3: Core Services - Import services that depend on utilities
from .services.groq_client import GroqClient
from .services.chutes_client import ChutesClient
from .services.embedding_client import EmbeddingClient
from .services.personality_engine import PersonalityEngine
from .services.memory_manager import MemoryManager
from .services.letta_service import LettaService
from .services.user_service import UserService

# Phase 4: Advanced Services & Routers - Import everything else
from .services.proactive_manager import ProactiveManager
from .services.reflection import ReflectionService
from .agents.appraisal import AppraisalEngine
from .routers import chat, memory, personality, admin, health


class ServiceContainer:
    """Dependency injection container for all services."""

    def __init__(self):
        # Will be initialized during startup
        self.db: Optional[DatabaseManager] = None
        self.qdrant: Optional[QdrantClient] = None  # Added Qdrant client
        self.redis: Optional[redis.Redis] = None
        self.groq: Optional[GroqClient] = None
        self.chutes: Optional[ChutesClient] = None
        self.embedding_client: Optional[EmbeddingClient] = None
        self.importance_scorer: Optional[ImportanceScorer] = None
        self.mmr: Optional[MaximalMarginalRelevance] = None
        self.security: Optional[SemanticInjectionDetector] = None
        self.personality: Optional[PersonalityEngine] = None
        self.memory: Optional[MemoryManager] = None
        self.letta: Optional[LettaService] = None
        self.users: Optional[UserService] = None
        self.proactive: Optional[ProactiveManager] = None
        self.reflection: Optional[ReflectionService] = None
        self.appraisal: Optional[AppraisalEngine] = None
        self.scheduler: Optional[SchedulerService] = None
        self.background: Optional[BackgroundServiceManager] = None


# Global container instance
services = ServiceContainer()


# Dependency provider functions for FastAPI
def get_db() -> DatabaseManager:
    return services.db

def get_qdrant() -> QdrantClient:
    return services.qdrant

def get_groq() -> GroqClient:
    return services.groq

def get_chutes() -> ChutesClient:
    return services.chutes

def get_importance_scorer() -> ImportanceScorer:
    return services.importance_scorer

def get_mmr() -> MaximalMarginalRelevance:
    return services.mmr

def get_security() -> SemanticInjectionDetector:
    return services.security

def get_personality() -> PersonalityEngine:
    return services.personality

def get_memory() -> MemoryManager:
    return services.memory

def get_letta() -> LettaService:
    return services.letta

def get_users() -> UserService:
    return services.users

def get_proactive() -> ProactiveManager:
    return services.proactive

def get_reflection() -> ReflectionService:
    return services.reflection

def get_appraisal() -> AppraisalEngine:
    return services.appraisal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """4-Phase Service Initialization"""

    # PHASE 1: Core Infrastructure
    logger.info("🚀 Phase 1: Initializing core infrastructure...")
    
    settings = Settings()
    services.db = DatabaseManager(settings.database_url)
    await services.db.initialize()
    
    # Initialize Qdrant client for vector database
    services.qdrant = QdrantClient(url=settings.qdrant_url)
    logger.info(f"✅ Qdrant client initialized with URL: {settings.qdrant_url}")
    
    services.redis = redis.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        decode_responses=settings.redis_decode_responses
    )
    try:
        await services.redis.ping()
        logger.info("✅ Redis client initialized and connected")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise
    
    # PHASE 2: Utility Services
    logger.info("🔧 Phase 2: Initializing utility services...")
    
    services.groq = GroqClient(
        api_key=settings.groq_api_key,
        model=settings.scoring_llm_model
    )

    services.chutes = ChutesClient(
        api_key=settings.chutes_api_key,
        primary_model=settings.primary_llm_model,
        fallback_model=settings.fallback_llm_model
    )

    services.importance_scorer = ImportanceScorer(services.groq)
    services.mmr = MaximalMarginalRelevance()
    services.security = SemanticInjectionDetector(services.groq)

    # Initialize EmbeddingClient
    services.embedding_client = EmbeddingClient(
        service_url=settings.embedding_service_url,
        api_key=settings.gemini_api_key,
        dimensions=settings.embedding_dimensions
    )

    # PHASE 3: Core Services (Order matters for dependencies!)
    logger.info("⚙️ Phase 3: Initializing core services...")

    services.personality = PersonalityEngine(
        db=services.db,
        groq_client=services.groq
    )

    # FIXED: Initialize MemoryManager with the actual embedding client
    services.memory = MemoryManager(
        qdrant_client=services.qdrant,
        embedding_client=services.embedding_client,  # Fixed: Pass the actual embedding client
        importance_scorer=services.importance_scorer,
        mmr_ranker=services.mmr,
        db_manager=services.db,
        groq_client=services.groq
    )
    
    services.letta = LettaService(
        server_url=settings.letta_server_url,
        personality_engine=services.personality,
        chutes_client=services.chutes # Add this line
    )
    
    services.users = UserService(
        db=services.db,
        letta_service=services.letta,
        personality_engine=services.personality
    )

    # Initialize background services before advanced services that might use them
    services.background = BackgroundServiceManager(services)
    await services.background.initialize()

    # PHASE 4: Advanced Services
    logger.info("🚀 Phase 4: Initializing advanced services...")
    
    services.appraisal = AppraisalEngine(groq_client=services.groq)
    services.proactive = ProactiveManager(
        personality_engine=services.personality,
        memory_manager=services.memory,
        user_service=services.users,
        groq_client=services.groq,
        db_manager=services.db
    )
    
    services.reflection = ReflectionService(
        memory_manager=services.memory,
        personality_engine=services.personality,
        groq_client=services.groq,
        db_manager=services.db
    )

    # Inject Redis into dependent services
    services.importance_scorer.set_redis_client(services.redis) # Inject Redis
    services.security.set_redis_client(services.redis) # Inject Redis

    # Initialize scheduler with services
    services.scheduler = await setup_background_jobs(services)
    
    logger.info("✅ All services initialized successfully!")

    yield  # Application runs here

    # Cleanup
    logger.info("🛑 Shutting down services...")
    
    # Shutdown scheduler
    if services.scheduler:
        services.scheduler.shutdown_scheduler()
    
    # Shutdown background services
    if services.background:
        await services.background.stop()
    
    # Close Qdrant client
    if services.qdrant:
        services.qdrant.close()
    
    # Close database connection
    if services.db:
        await services.db.close()

    logger.info("✅ All services shut down")


# Create FastAPI app
app = FastAPI(
    title="AI Companion System",
    description="Multi-user AI companion with personality evolution",
    version="1.0.0",
    lifespan=lifespan
)

# Setup middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Expose custom headers
    expose_headers=["X-Process-Time"]
)

# Setup exception handlers
setup_exception_handlers(app)

# Include routers with dependencies
app.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
    dependencies=[]
)

app.include_router(
    chat.router,
    prefix="/api/chat",
    tags=["chat"],
    dependencies=[]
)

app.include_router(
    memory.router,
    prefix="/api/memory",
    tags=["memory"],
    dependencies=[]
)

app.include_router(
    personality.router,
    prefix="/api/personality",
    tags=["personality"],
    dependencies=[]
)

app.include_router(
    admin.router,
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[]
)


@app.get("/")
async def root():
    """Root endpoint for basic service information."""
    return {
        "service": "AI Companion Gateway",
        "version": "1.0.0",
        "status": "running",
        "message": "Welcome to the AI Companion System Gateway API"
    }


@app.get("/info")
async def service_info():
    """Get detailed service information."""
    return {
        "service": "AI Companion Gateway",
        "version": "1.0.0",
        "build_date": os.getenv("BUILD_DATE", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "features": [
            "Personality-driven conversations",
            "Episodic/Semantic memory system",
            "Proactive conversation management",
            "Emotional state tracking (PAD model)",
            "Quirk and need evolution",
            "Security threat detection",
            "Multi-user support with isolation"
        ],
        "api_endpoints": [
            "/api/chat",
            "/api/memory", 
            "/api/personality",
            "/api/admin",
            "/health"
        ]
    }


@app.get("/status")
async def service_status():
    """Get overall service status and health."""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "services_initialized": all([
            services.db is not None,
            services.qdrant is not None,  # Added check for Qdrant
            services.groq is not None,
            services.personality is not None,
            services.memory is not None
        ])
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url)}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",  # Use the app instance from this file
        host=os.getenv("GATEWAY_HOST", "0.0.0.0"),
        port=int(os.getenv("GATEWAY_PORT", 8000)),
        reload=os.getenv("GATEWAY_DEBUG", "false").lower() == "true"
    )
