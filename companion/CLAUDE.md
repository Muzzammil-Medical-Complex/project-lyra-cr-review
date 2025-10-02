# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-user AI companion system with evolving personality, memory management, and proactive conversation capabilities. The system creates unique, evolving AI personalities for each user using Big Five traits, PAD emotional states, quirks, and psychological needs.

## Core Architecture

The system consists of 7 containerized microservices orchestrated via Docker Compose:

1. **PostgreSQL + pgvector** - User profiles, personality states, interaction logs
2. **Qdrant** - Vector database for semantic memory storage/retrieval
3. **Redis** - Caching layer for performance optimization
4. **Letta** - Agent framework for stateful conversations
5. **Embedding Service** - Gemini API wrapper for text embeddings
6. **Gateway API** - Main FastAPI application orchestrating all services
7. **Discord Bot** - User interface with proactive messaging

### Service Dependencies

The Gateway API (`gateway/main.py`) implements a 4-phase startup sequence that MUST be respected when modifying initialization:

1. **Phase 1: Core Infrastructure** - Database, Qdrant, Redis connections
2. **Phase 2: Utility Services** - Groq, Chutes, ImportanceScorer, MMR, SemanticInjectionDetector, EmbeddingClient
3. **Phase 3: Core Services** - PersonalityEngine, MemoryManager, LettaService, UserService (order matters!)
4. **Phase 4: Advanced Services** - AppraisalEngine, ProactiveManager, ReflectionService

Dependencies are injected through the `ServiceContainer` class. When adding new services, place them in the correct phase based on their dependencies.

## Key Systems

### Personality System
- **Big Five Traits** (fixed): Stored in `personality_state` table, set at user initialization
- **PAD Emotional States** (dynamic): Pleasure, Arousal, Dominance dimensions, updated per interaction
- **OCC Appraisal Engine**: Cognitive appraisal model in `gateway/agents/appraisal.py` calculates emotional responses
- **Quirks**: Behavioral patterns stored in `quirks` table, decay/reinforce based on interaction
- **Psychological Needs**: Social, validation, intellectual, creative, rest needs in `needs` table

### Memory System
- **Episodic Memory**: Specific events stored in Qdrant with per-user collections (`episodic_{user_id}`)
- **Semantic Memory**: General knowledge in Qdrant collections (`semantic_{user_id}`)
- **MMR Retrieval**: `gateway/utils/mmr.py` implements Maximal Marginal Relevance for diverse retrieval
- **Importance Scoring**: `gateway/utils/importance_scorer.py` uses Groq to score memory importance
- **Memory Conflicts**: Detected and stored in `memory_conflicts` table

### Multi-User Isolation
All database queries MUST be scoped to `user_id`. Every table has a `user_id` column. Qdrant collections are per-user with naming pattern: `{collection_type}_{user_id}`.

### Security
- **Semantic Injection Detection**: `gateway/security/semantic_injection_detector.py` detects role manipulation
- **Defensive Responses**: `gateway/security/defensive_response.py` generates personality-consistent responses
- **Incident Tracking**: All security events logged in `security_incidents` table

## Development Commands

### Running the Stack
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f [service_name]

# Restart specific service
docker-compose restart gateway

# Stop all services
docker-compose down
```

### Database Migrations
```bash
# Apply migrations in order
docker-compose exec postgres psql -U companion -d companion_db -f /migrations/001_init.sql
docker-compose exec postgres psql -U companion -d companion_db -f /migrations/002_personhood.sql
# Continue for all numbered migrations...
```

### Running Gateway Locally
```bash
cd gateway
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running Discord Bot Locally
```bash
cd discord_bot
python -m discord_bot.bot
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test types
pytest tests/unit/
pytest tests/integration/

# Run with markers
pytest -m unit
pytest -m integration
pytest -m slow

# Run single test file
pytest tests/unit/test_personality_engine.py

# Run with coverage
pytest --cov=gateway tests/
```

Test fixtures are defined in `tests/conftest.py` with markers for `@pytest.mark.unit`, `@pytest.mark.integration`, and `@pytest.mark.slow`.

## Configuration

All configuration is managed through environment variables defined in `.env` (see `.env.example` for template). Settings are loaded via `gateway/config.py` using Pydantic's `BaseSettings`.

### Critical Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `QDRANT_URL` - Qdrant vector database URL
- `CHUTES_API_KEY` - Primary LLM (Qwen3-80B)
- `GROQ_API_KEY` - Fast LLM for scoring/security (Llama-4-Maverick)
- `GEMINI_API_KEY` - Embeddings (embedding-001, 1536-dim)
- `DISCORD_BOT_TOKEN` - Discord bot authentication

## Database Schema

Key tables (see `database/migrations/` for full schemas):
- `user_profiles` - User metadata and status
- `personality_state` - Big Five + PAD state (one current row per user via `is_current` flag)
- `interactions` - Full conversation history
- `quirks` - Behavioral patterns with strength values
- `needs` - Psychological needs with urgency levels
- `memory_conflicts` - Conflicting memories requiring resolution
- `security_incidents` - Security threat logs

## Code Organization

```plaintext
gateway/
├── main.py              # FastAPI app + 4-phase startup
├── config.py            # Settings via Pydantic
├── database.py          # DatabaseManager with connection pooling
├── routers/             # FastAPI route handlers
├── services/            # Core business logic services
├── agents/              # Cognitive agents (appraisal, reflection, proactive)
├── models/              # Pydantic data models
├── data_models/         # Database models
├── security/            # Security detection and responses
└── utils/               # Utilities (MMR, importance scoring, scheduler)

discord_bot/
├── bot.py               # Main bot with message handling
├── commands.py          # Slash command implementations
└── utils.py             # Bot utility functions

embedding_service/
└── main.py              # Gemini embedding API wrapper

database/
└── migrations/          # SQL migrations (numbered 001-006)

tests/
├── conftest.py          # Pytest fixtures and configuration
├── unit/                # Unit tests for individual components
└── integration/         # Integration tests for full workflows
```

## Important Patterns

### Database Queries
Always use parameterized queries through `DatabaseManager`:
```python
await db.execute("SELECT * FROM table WHERE user_id = %s", (user_id,))
await db.fetchone("SELECT * FROM table WHERE user_id = %s AND id = %s", (user_id, id))
await db.fetchall("SELECT * FROM table WHERE user_id = %s", (user_id,))
```

### Memory Operations
MemoryManager automatically handles per-user collection isolation:
```python
# Store episodic memory (creates collection if not exists)
memory_id = await memory_manager.store_episodic_memory(user_id, content, metadata)

# Retrieve with MMR
memories = await memory_manager.search_with_mmr(user_id, query, k=5, lambda_param=0.7)
```

### Personality Updates
PersonalityEngine manages PAD state transitions:
```python
# Get current state
snapshot = await personality_engine.get_personality_snapshot(user_id)

# Update PAD based on interaction
new_pad = await personality_engine.update_pad_state(user_id, emotional_impact)
```

### Service Access in Routes
Use FastAPI dependency injection (providers in `gateway/main.py`):
```python
from gateway.main import get_db, get_memory, get_personality

@router.post("/endpoint")
async def handler(
    db: DatabaseManager = Depends(get_db),
    memory: MemoryManager = Depends(get_memory),
    personality: PersonalityEngine = Depends(get_personality)
):
    # Service operations...
```

## Background Jobs

Scheduled tasks are managed by `gateway/utils/scheduler.py`:
- **Nightly Reflection** (2 AM UTC) - Consolidates episodic memories to semantic, updates personality baselines
- **Proactive Message Scheduler** (hourly) - Evaluates users for proactive conversation opportunities
- **Need Decay** (hourly) - Decays psychological needs that haven't been fulfilled

Background service management is handled by `BackgroundServiceManager` in `gateway/utils/background.py`.

## LLM Configuration

The system uses multiple LLMs for different purposes:
- **Primary LLM** (Chutes/Qwen3-80B): Main conversation generation via `ChutesClient`
- **Fast LLM** (Groq/Llama-4-Maverick): Importance scoring, security detection, appraisal calculations via `GroqClient`
- **Embeddings** (Gemini): Text embeddings via `EmbeddingClient` (proxied through embedding_service)

## Health Checks

All services expose health endpoints:
- Gateway: `http://localhost:8000/health`
- Embedding Service: `http://localhost:8002/health`
- Individual service status: `http://localhost:8000/status`

## Common Gotchas

1. **User Scoping**: Never query without filtering by `user_id` - data leakage is a security risk
2. **Qdrant Collections**: Collections are created lazily on first memory store for a user
3. **Personality State**: Only one row per user should have `is_current=TRUE` in `personality_state`
4. **Migration Order**: Database migrations must be applied in numerical order (001, 002, etc.)
5. **Service Initialization**: Respect the 4-phase startup order in `gateway/main.py:lifespan()`
6. **Redis Caching**: ImportanceScorer and SemanticInjectionDetector use Redis for caching; ensure Redis is injected via `set_redis_client()`
7. **Async Operations**: All service methods are async; always use `await`

## Deployment

Production deployment uses Docker Compose. See `scripts/deploy.sh` for automated deployment process.

Health checks are configured in `docker-compose.yml` for each service with proper dependency ordering (`depends_on` with `condition: service_healthy`).