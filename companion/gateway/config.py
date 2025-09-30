"""
Configuration management for the AI Companion System.

This module defines the Settings class using Pydantic's BaseSettings to handle
all environment variables and configuration settings for the system.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    # Core Infrastructure
    database_url: str = Field(
        default="postgresql://username:password@postgres:5432/companion_db",
        description="PostgreSQL Database connection URL"
    )
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL for caching and sessions"
    )
    qdrant_url: str = Field(
        default="http://qdrant:6333",
        description="Qdrant vector database URL"
    )

    # AI Service APIs
    chutes_api_key: str = Field(
        ...,
        description="Chutes.ai API key for primary LLM"
    )
    groq_api_key: str = Field(
        ...,
        description="Groq API key for fast LLM scoring/security"
    )
    gemini_api_key: str = Field(
        ...,
        description="Google Gemini API key for embeddings"
    )

    # Discord Integration
    discord_bot_token: str = Field(
        ...,
        description="Discord bot token for the companion bot"
    )

    # Service Configuration
    gateway_port: int = Field(
        default=8000,
        description="Gateway API port"
    )
    gateway_host: str = Field(
        default="0.0.0.0",
        description="Gateway API host"
    )
    gateway_debug: bool = Field(
        default=False,
        description="Enable debug mode for gateway"
    )
    discord_bot_port: int = Field(
        default=8001,
        description="Discord bot port"
    )
    embedding_service_port: int = Field(
        default=8002,
        description="Embedding service port"
    )
    embedding_service_host: str = Field(
        default="0.0.0.0",
        description="Embedding service host"
    )
    embedding_service_url: str = Field(
        default="http://embedding_service:8002",
        description="Embedding service base URL"
    )

    # Model Configuration
    primary_llm_model: str = Field(
        default="qwen3-80b-a3b-instruct",
        description="Primary LLM model for the companion"
    )
    fallback_llm_model: str = Field(
        default="qwen2-72b-instruct",
        description="Fallback LLM model"
    )
    scoring_llm_model: str = Field(
        default="llama-4-maverick",
        description="Fast LLM model for scoring and security"
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Dimensions for embedding vectors"
    )

    # Personality System
    pad_drift_rate: float = Field(
        default=0.01,
        ge=0.0,
        le=0.1,
        description="PAD baseline drift rate (0.01 = 1% max change per day)"
    )
    quirk_decay_rate: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Quirk decay rate when not reinforced"
    )
    quirk_reinforcement_rate: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Rate at which quirks are reinforced"
    )

    # Security Configuration
    security_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threat detection confidence threshold (0.0-1.0)"
    )
    security_offense_window_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Window for tracking repeat offenders (days)"
    )
    max_proactive_per_day: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of proactive conversations per day"
    )

    # Performance Tuning
    db_pool_min_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Database connection pool minimum size"
    )
    db_pool_max_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool maximum size"
    )
    redis_pool_size: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Redis connection pool size"
    )
    max_reflection_batch_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of users to process per reflection batch"
    )
    max_concurrent_ai_calls: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent AI API calls"
    )

    # Development/Production Modes
    environment: str = Field(
        default="development",
        description="Environment mode ('development' or 'production')"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # Monitoring (Optional)
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking (optional)"
    )

    # Letta Configuration
    letta_server_url: str = Field(
        default="http://letta:8283",
        description="Letta framework server URL"
    )
    letta_api_key: Optional[str] = Field(
        default=None,
        description="Letta API key if authentication is required"
    )

    # Qdrant Collection Configuration
    qdrant_episodic_collection_prefix: str = Field(
        default="episodic_",
        description="Prefix for per-user episodic memory collections"
    )
    qdrant_semantic_collection_prefix: str = Field(
        default="semantic_",
        description="Prefix for per-user semantic memory collections"
    )

    # Redis Configuration Details
    redis_max_connections: int = Field(
        default=50,
        description="Maximum Redis connection pool size"
    )
    redis_decode_responses: bool = Field(
        default=True,
        description="Whether to decode Redis responses to strings"
    )

    class Config:
        # Load from .env file
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True


# Create a single instance of settings
settings = Settings()